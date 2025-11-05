import asyncio
import logging
from pathlib import Path

from quart import Quart, jsonify, render_template

from .common.config import settings
from .common.database import init_db
from .common.redis_client import close_redis
from .common.kafka_client import close_producer
from .inventory.controller import bp as inventory_bp
from .orders.controller import bp as orders_bp
from .realtime.controller import bp as realtime_bp
from .payments.worker import payments_worker


log = logging.getLogger(__name__)


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

    app.register_blueprint(inventory_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(realtime_bp)

    @app.get("/health")
    async def health():
        return jsonify({"status": "ok"})

    @app.get("/")
    async def index():
        return await render_template("index.html")

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
