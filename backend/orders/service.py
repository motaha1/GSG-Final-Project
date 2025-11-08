import json
from typing import Dict

from ..common.config import settings
from ..common.kafka_client import get_producer
from ..common.database import create_order
from ..inventory.service import get_stock


async def submit_purchase(product_id: int, quantity: int) -> Dict:
    # Validate stock quickly (non-authoritative; final check in payments)
    stock = await get_stock(product_id)
    if stock is None:
        return {"ok": False, "error": "product_not_found"}
    if quantity <= 0:
        return {"ok": False, "error": "invalid_quantity"}
    if stock == 0:
        return {"ok": False, "error": "out_of_stock"}
    if stock < quantity:
        return {"ok": False, "error": "insufficient_stock", "available": stock}

    # Create order with pending status
    order_id = await create_order(product_id, quantity, status="pending")

    # Publish event to Kafka
    payload = {
        "order_id": order_id,
        "product_id": product_id,
        "quantity": quantity,
    }

    try:
        producer = await get_producer()
        await producer.send_and_wait(settings.PURCHASE_TOPIC, json.dumps(payload).encode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": "broker_unavailable", "order_id": order_id}

    return {"ok": True, "order_id": order_id}
