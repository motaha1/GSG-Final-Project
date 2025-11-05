import asyncio
import json
from typing import Optional

from ..common.config import settings
from ..common.kafka_client import create_consumer, close_consumer
from ..common.database import try_reserve_stock, update_order_status, get_product_stock, fetch_product
from ..common.redis_client import get_redis


def redis_stock_key(product_id: int) -> str:
    return f"product:{product_id}:stock"


def redis_product_key(product_id: int) -> str:
    return f"product:{product_id}:data"


async def payments_worker(stop_event: Optional[asyncio.Event] = None):
    """
    Kafka consumer that processes purchase events and finalizes payments.
    - Simulates payment delay
    - Tries to reserve stock atomically in DB
    - Updates order status and publishes stock update via Redis
    Resilient to Kafka outages: retries connection with backoff.
    """
    backoff = 1.0
    while True:
        if stop_event and stop_event.is_set():
            break
        consumer = None
        try:
            consumer = await create_consumer(settings.PURCHASE_TOPIC, group_id="payments-worker")
            backoff = 1.0  # reset after successful connect
            while True:
                if stop_event and stop_event.is_set():
                    break
                batch = await consumer.getmany(timeout_ms=1000)
                if not batch:
                    continue
                for _, messages in batch.items():
                    for result in messages:
                        try:
                            payload = json.loads(result.value.decode("utf-8"))
                        except Exception:
                            continue

                        order_id = int(payload.get("order_id"))
                        product_id = int(payload.get("product_id"))
                        quantity = int(payload.get("quantity"))

                        # Simulate payment gateway delay
                        await asyncio.sleep(1.0)

                        reserved = await try_reserve_stock(product_id, quantity)
                        if reserved:
                            await update_order_status(order_id, "paid")
                            # fetch new stock and publish
                            new_stock = await get_product_stock(product_id)
                            r = await get_redis()
                            await r.set(redis_stock_key(product_id), new_stock)
                            # update product JSON cache as well
                            prod_raw = await r.get(redis_product_key(product_id))
                            if prod_raw:
                                try:
                                    prod = json.loads(prod_raw)
                                    prod["stock"] = new_stock
                                    await r.set(redis_product_key(product_id), json.dumps(prod))
                                except Exception:
                                    pass
                            else:
                                # warm from DB if not present
                                prod = await fetch_product(product_id)
                                if prod is not None:
                                    prod["stock"] = new_stock
                                    await r.set(redis_product_key(product_id), json.dumps(prod))
                            await r.publish(settings.REDIS_STOCK_CHANNEL, str(new_stock))
                        else:
                            await update_order_status(order_id, "failed")
        except Exception:
            # Wait with backoff then retry connecting
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
        finally:
            await close_consumer(consumer)
