from typing import Optional
import json
import logging

from ..common.redis_client import get_redis
from ..common.database import get_product_stock, update_product_stock, fetch_product, fetch_products
from backend.common.config import settings

_logger = logging.getLogger(__name__)


def redis_stock_key(product_id: int) -> str:
    return f"product:{product_id}:stock"


def redis_product_key(product_id: int) -> str:
    return f"product:{product_id}:data"


async def get_stock(product_id: int) -> Optional[int]:
    r = await get_redis()
    cached = await r.get(redis_stock_key(product_id))
    if cached is not None:
        try:
            value = int(cached)
            _logger.debug("Cache hit: stock | product_id=%s stock=%s", product_id, value)
            return value
        except ValueError:
            pass
    # fallback to DB
    stock = await get_product_stock(product_id)
    _logger.info("DB get stock | product_id=%s stock=%s (cache miss)", product_id, stock)
    if stock is not None:
        await r.set(redis_stock_key(product_id), stock)
        # also sync product cache if exists
        prod_json = await r.get(redis_product_key(product_id))
        if prod_json:
            try:
                prod = json.loads(prod_json)
                prod["stock"] = stock
                await r.set(redis_product_key(product_id), json.dumps(prod))
            except Exception:
                pass
    return stock


async def set_stock(product_id: int, new_stock: int) -> int:
    # Update DB then cache and notify
    await update_product_stock(product_id, new_stock)
    _logger.info("DB set stock | product_id=%s new_stock=%s", product_id, new_stock)
    r = await get_redis()
    await r.set(redis_stock_key(product_id), new_stock)
    # keep product cache in sync
    prod_json = await r.get(redis_product_key(product_id))
    if prod_json:
        try:
            prod = json.loads(prod_json)
            prod["stock"] = new_stock
            await r.set(redis_product_key(product_id), json.dumps(prod))
        except Exception:
            pass
    else:
        # warm product cache from DB if missing
        db_prod = await fetch_product(product_id)
        if db_prod is not None:
            db_prod["stock"] = new_stock
            await r.set(redis_product_key(product_id), json.dumps(db_prod))
    # publish stock change event for realtime consumers with product_id
    await r.publish(settings.REDIS_STOCK_CHANNEL, json.dumps({"product_id": product_id, "stock": new_stock}))
    _logger.info("Published manual stock update via Redis | product_id=%s stock=%s", product_id, new_stock)
    return new_stock


async def get_products():
    return await fetch_products()


async def get_product(product_id: int):
    r = await get_redis()
    raw = await r.get(redis_product_key(product_id))
    if raw:
        try:
            obj = json.loads(raw)
            _logger.debug("Cache hit: product | product_id=%s", product_id)
            return obj
        except Exception:
            pass
    # Fallback to DB then cache in Redis
    prod = await fetch_product(product_id)
    if prod is not None:
        try:
            await r.set(redis_product_key(product_id), json.dumps(prod))
        except Exception:
            pass
        # ensure stock key is also synced
        if "stock" in prod and prod["stock"] is not None:
            await r.set(redis_stock_key(product_id), int(prod["stock"]))
    _logger.info("DB get product | product_id=%s", product_id)
    return prod
