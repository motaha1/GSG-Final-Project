from typing import Optional
import json

from ..common.redis_client import get_redis
from ..common.database import get_product_stock, update_product_stock, fetch_product
from ..common.config import settings


def redis_stock_key(product_id: int) -> str:
    return f"product:{product_id}:stock"


def redis_product_key(product_id: int) -> str:
    return f"product:{product_id}:data"


async def get_stock(product_id: int) -> Optional[int]:
    r = await get_redis()
    cached = await r.get(redis_stock_key(product_id))
    if cached is not None:
        try:
            return int(cached)
        except ValueError:
            pass
    # fallback to DB
    stock = await get_product_stock(product_id)
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
    # publish stock change event for realtime consumers
    await r.publish(settings.REDIS_STOCK_CHANNEL, str(new_stock))
    return new_stock


async def get_product(product_id: int):
    r = await get_redis()
    raw = await r.get(redis_product_key(product_id))
    if raw:
        try:
            return json.loads(raw)
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
    return prod
