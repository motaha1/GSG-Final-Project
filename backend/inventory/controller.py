from quart import Blueprint, jsonify, request

from .service import get_stock, set_stock, get_product, get_products, redis_stock_key
from ..common.config import settings
from ..common.database import get_product_stock
from ..common.redis_client import get_redis

bp = Blueprint("inventory", __name__)


@bp.get("/products")
async def products_list():
    items = await get_products()
    return jsonify({"products": items})


@bp.get("/products/<int:product_id>")
async def product_detail(product_id: int):
    prod = await get_product(product_id)
    if not prod:
        return jsonify({"error": "product_not_found"}), 404
    stock = await get_stock(product_id)
    return jsonify({"product": prod, "stock": stock})


@bp.get("/stock")
async def stock_get_default():
    product_id = int(request.args.get("product_id", settings.DEFAULT_PRODUCT_ID))
    product = await get_product(product_id)
    if product is None:
        return jsonify({"error": "product_not_found"}), 404
    stock = await get_stock(product_id)
    return jsonify({"product_id": product_id, "name": product["name"], "stock": stock, "price": product["price"], "image_url": product.get("image_url")})


@bp.put("/stock")
async def stock_put_default():
    data = await request.get_json(force=True)
    product_id = int(data.get("product_id", settings.DEFAULT_PRODUCT_ID))
    new_stock = int(data["stock"])  # required
    updated = await set_stock(product_id, new_stock)
    return jsonify({"product_id": product_id, "stock": updated})


# Debug: compare DB vs Redis stock
@bp.get("/debug/stock")
async def stock_debug():
    product_id = int(request.args.get("product_id", settings.DEFAULT_PRODUCT_ID))
    db_stock = await get_product_stock(product_id)
    r = await get_redis()
    redis_val = await r.get(redis_stock_key(product_id))
    try:
        redis_stock = int(redis_val) if redis_val is not None else None
    except Exception:
        redis_stock = redis_val
    return jsonify({"product_id": product_id, "db_stock": db_stock, "redis_stock": redis_stock})


# Debug: clear Redis cache for the product
@bp.delete("/debug/cache")
async def cache_clear():
    product_id = int(request.args.get("product_id", settings.DEFAULT_PRODUCT_ID))
    r = await get_redis()
    deleted = 0
    try:
        deleted += await r.delete(redis_stock_key(product_id))
        deleted += await r.delete(f"product:{product_id}:data")
    except Exception:
        pass
    return jsonify({"product_id": product_id, "deleted": deleted})
