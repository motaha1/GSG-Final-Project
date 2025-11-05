from quart import Blueprint, jsonify, request

from .service import get_stock, set_stock, get_product
from ..common.config import settings

bp = Blueprint("inventory", __name__)


@bp.get("/stock")
async def stock_get():
    product_id = int(request.args.get("product_id", settings.DEFAULT_PRODUCT_ID))
    product = await get_product(product_id)
    if product is None:
        return jsonify({"error": "product_not_found"}), 404
    stock = await get_stock(product_id)
    return jsonify({"product_id": product_id, "name": product["name"], "stock": stock, "price": product["price"]})


@bp.put("/stock")
async def stock_put():
    data = await request.get_json(force=True)
    product_id = int(data.get("product_id", settings.DEFAULT_PRODUCT_ID))
    new_stock = int(data["stock"])  # required
    updated = await set_stock(product_id, new_stock)
    return jsonify({"product_id": product_id, "stock": updated})

