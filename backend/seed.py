import asyncio
import sqlalchemy as sa
import json

from .common.database import init_db, AsyncSessionLocal
from .inventory.model import Product
from .common.redis_client import get_redis


SAMPLE_PRODUCTS = [
    {"name": "Laptop Pro 14", "stock": 20, "price": 1499.00},
    {"name": "Wireless Mouse", "stock": 150, "price": 24.99},
    {"name": "Mechanical Keyboard", "stock": 80, "price": 89.99},
    {"name": "USB-C Hub", "stock": 120, "price": 39.99},
    {"name": "Noise-cancelling Headphones", "stock": 35, "price": 199.99},
    {"name": "4K Monitor 27\"", "stock": 25, "price": 329.99},
    {"name": "Portable SSD 1TB", "stock": 60, "price": 99.99},
    {"name": "Smartphone Charger 65W", "stock": 200, "price": 19.99},
    {"name": "Webcam 1080p", "stock": 75, "price": 49.99},
    {"name": "Bluetooth Speaker", "stock": 40, "price": 59.99},
]


def redis_stock_key(product_id: int) -> str:
    return f"product:{product_id}:stock"


def redis_product_key(product_id: int) -> str:
    return f"product:{product_id}:data"


async def seed_products() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        added = 0
        for p in SAMPLE_PRODUCTS:
            # avoid duplicates by name
            res = await session.execute(sa.select(Product.id).where(Product.name == p["name"]))
            if res.first():
                continue
            session.add(Product(name=p["name"], stock=p["stock"], price=p["price"]))
            added += 1
        if added:
            await session.commit()
        print(f"Seed complete. Added {added} products.")

    # Warm Redis cache with all products
    r = await get_redis()
    async with AsyncSessionLocal() as session:
        result = await session.execute(sa.select(Product))
        for prod in result.scalars():
            data = {"id": prod.id, "name": prod.name, "stock": prod.stock, "price": prod.price}
            await r.set(redis_product_key(prod.id), json.dumps(data))
            await r.set(redis_stock_key(prod.id), int(prod.stock))


async def amain():
    await seed_products()


if __name__ == "__main__":
    asyncio.run(amain())
