from typing import Optional, Dict, Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from .config import settings
from .db import Base
from ..inventory.model import Product
from ..orders.model import Order


# Async SQLAlchemy engine and session factory
engine = create_async_engine(settings.DB_URL, future=True, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure default product exists
    async with AsyncSessionLocal() as session:
        prod = await session.get(Product, settings.DEFAULT_PRODUCT_ID)
        if prod is None:
            prod = Product(
                id=settings.DEFAULT_PRODUCT_ID,
                name=settings.DEFAULT_PRODUCT_NAME,
                stock=settings.DEFAULT_PRODUCT_STOCK,
                price=settings.DEFAULT_PRODUCT_PRICE,
            )
            session.add(prod)
            await session.commit()


async def fetch_product(product_id: int) -> Optional[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        prod = await session.get(Product, product_id)
        if not prod:
            return None
        return {"id": prod.id, "name": prod.name, "stock": prod.stock, "price": prod.price}


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
            # res.rowcount can be None with certain DBs; check via returned rowcount-like attribute
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
        stmt = sa.update(Order).where(Order.id == order_id).set({Order.status: status})
        await session.execute(stmt)
        await session.commit()
