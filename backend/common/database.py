from typing import Optional, Dict, Any, List

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from .config import settings
from .db import Base
from ..inventory.model import Product
from ..orders.model import Order


# Async SQLAlchemy engine and session factory
engine = create_async_engine(settings.DB_URL, future=True, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _column_exists(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    cols = [c['name'] for c in insp.get_columns(table)]
    return column in cols


async def init_db() -> None:
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add image_url column if missing (simple migration)
        def _migrate(sync_conn):
            insp = sa.inspect(sync_conn)
            cols = [c['name'] for c in insp.get_columns('products')]
            if 'image_url' not in cols:
                sync_conn.execute(sa.text("ALTER TABLE products ADD COLUMN image_url VARCHAR(512)"))
        await conn.run_sync(_migrate)

    # Seed multiple products if table is empty
    async with AsyncSessionLocal() as session:
        res = await session.execute(sa.select(sa.func.count(Product.id)))
        count = int(res.scalar() or 0)
        if count == 0:
            products: List[Product] = [
                Product(id=1, name="Widget", stock=100, price=9.99, image_url="https://picsum.photos/seed/widget/400/300"),
                Product(id=2, name="Gadget", stock=50, price=14.99, image_url="https://picsum.photos/seed/gadget/400/300"),
                Product(id=3, name="Thingamajig", stock=75, price=19.99, image_url="https://picsum.photos/seed/thing/400/300"),
            ]
            session.add_all(products)
            await session.commit()


async def fetch_product(product_id: int) -> Optional[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        prod = await session.get(Product, product_id)
        if not prod:
            return None
        return {"id": prod.id, "name": prod.name, "stock": prod.stock, "price": prod.price, "image_url": prod.image_url}


async def fetch_products() -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        res = await session.execute(sa.select(Product))
        items = []
        for prod in res.scalars().all():
            items.append({"id": prod.id, "name": prod.name, "stock": prod.stock, "price": prod.price, "image_url": prod.image_url})
        return items


async def get_product_stock(product_id: int) -> Optional[int]:
    async with AsyncSessionLocal() as session:
        stmt = sa.select(Product.stock).where(Product.id == product_id)
        res = await session.execute(stmt)
        row = res.first()
        return int(row[0]) if row else None


async def update_product_stock(product_id: int, new_stock: int) -> None:
    async with AsyncSessionLocal() as session:
        stmt = sa.update(Product).where(Product.id == product_id).values(stock=new_stock)
        await session.execute(stmt)
        await session.commit()


async def try_reserve_stock(product_id: int, quantity: int) -> bool:
    """Atomically decrement stock if available. Returns True on success."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt = (
                sa.update(Product)
                .where(Product.id == product_id, Product.stock >= quantity)
                .values(stock=Product.stock - quantity)
            )
            res = await session.execute(stmt)
            updated = res.rowcount or 0
        return updated > 0


async def create_order(product_id: int, quantity: int, status: str = "pending") -> int:
    async with AsyncSessionLocal() as session:
        order = Order(product_id=product_id, quantity=quantity, status=status)
        session.add(order)
        await session.flush()  # assign PK
        order_id = int(order.id)
        await session.commit()
        return order_id


async def update_order_status(order_id: int, status: str) -> None:
    async with AsyncSessionLocal() as session:
        stmt = sa.update(Order).where(Order.id == order_id).values(status=status)
        await session.execute(stmt)
        await session.commit()
