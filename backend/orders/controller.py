from quart import Blueprint, jsonify, request

from .service import submit_purchase
from ..common.config import settings

bp = Blueprint("orders", __name__)


@bp.post("/purchase")
async def purchase_post():
    data = await request.get_json(force=True)
    product_id = int(data.get("product_id", settings.DEFAULT_PRODUCT_ID))
    quantity = int(data.get("quantity", 1))
    result = await submit_purchase(product_id, quantity)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status

