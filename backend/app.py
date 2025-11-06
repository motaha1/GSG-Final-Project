import asyncio
import logging
import os
from pathlib import Path

from quart import Quart, jsonify, render_template, request

from .common.database import init_db
from .common.redis_client import close_redis
from .common.kafka_client import close_producer
from .inventory.controller import bp as inventory_bp
from .orders.controller import bp as orders_bp
from .realtime.controller import bp as realtime_bp
from .payments.worker import payments_worker
from .inventory.service import get_products, get_product

# Prometheus metrics
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time


log = logging.getLogger(__name__)

# Get instance ID from environment
INSTANCE_ID = os.getenv("INSTANCE_ID", "unknown")

# Basic metrics with proper buckets for latency
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float("inf"))
)


def create_app() -> Quart:
    base_dir = Path(__file__).resolve().parent.parent
    templates_dir = base_dir / "templates"
    static_dir = base_dir / "static"

    app = Quart(
        __name__,
        template_folder=str(templates_dir),
        static_folder=str(static_dir),
        static_url_path="/static",
    )

    # Blueprints
    app.register_blueprint(inventory_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(realtime_bp)

    @app.before_request
    async def before_request():
        # Store start time
        request._start_time = time.time()
        # Log instance handling the request
        log.info(f"[Instance {INSTANCE_ID}] {request.method} {request.path}")

    @app.after_request
    async def after_request(response):
        try:
            # Calculate request duration
            if hasattr(request, "_start_time"):
                duration = time.time() - request._start_time

                # Normalize endpoint for metrics (to avoid too many unique labels)
                endpoint = request.path
                # Group dynamic routes
                if endpoint.startswith("/product/"):
                    endpoint = "/product/<id>"
                elif endpoint.startswith("/stock"):
                    endpoint = "/stock"
                elif endpoint.startswith("/purchase"):
                    endpoint = "/purchase"
                elif endpoint.startswith("/static/"):
                    endpoint = "/static/*"

                # Record latency
                REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)

                # Record request count
                REQUEST_COUNT.labels(
                    method=request.method,
                    endpoint=endpoint,
                    status=str(response.status_code)
                ).inc()

                # Add instance header to response
                response.headers['X-Instance-ID'] = INSTANCE_ID
        except Exception as e:
            log.error(f"Error recording metrics: {e}")
        finally:
            return response

    @app.get("/metrics")
    async def metrics():
        data = generate_latest()
        return app.response_class(data, mimetype=CONTENT_TYPE_LATEST)

    @app.get("/health")
    async def health():
        return jsonify({"status": "ok"})

    @app.get("/")
    async def index():
        return await render_template("index.html")

    @app.get("/shop")
    async def shop():
        """Products list page with SSE"""
        products = await get_products()
        return await render_template("products.html", products=products)

    @app.get("/product/<int:product_id>")
    async def product_page(product_id: int):
        """Single product detail page with SSE and purchase form"""
        product = await get_product(product_id)
        if not product:
            return await render_template("product.html", error=True, product=None), 404
        return await render_template("product.html", product=product, error=False)

    @app.before_serving
    async def startup():
        logging.basicConfig(level=logging.INFO)
        log.info("Initializing database...")
        await init_db()
        log.info("Database ready.")
        # Start payments worker in background
        app.background_tasks = getattr(app, "background_tasks", set())
        stop_event = asyncio.Event()
        app._payments_stop = stop_event
        try:
            task = asyncio.create_task(payments_worker(stop_event))
            # Quart's background_tasks is a set
            app.background_tasks.add(task)
            log.info("Payments worker started.")
        except Exception as e:
            log.error(f"Failed to start payments worker: {e}")

    @app.after_serving
    async def shutdown():
        # Stop payments worker
        stop_event = getattr(app, "_payments_stop", None)
        if stop_event:
            stop_event.set()
        for t in getattr(app, "background_tasks", set()):
            try:
                await asyncio.wait_for(t, timeout=2.0)
            except Exception:
                t.cancel()
        await close_producer()
        await close_redis()
        log.info("Shutdown complete.")

    return app
