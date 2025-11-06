import asyncio
from backend.common.database import AsyncSessionLocal, engine
from backend.inventory.model import Product
import sqlalchemy as sa


async def seed_missing_products():
    """Add missing products and update existing one with image"""
    async with AsyncSessionLocal() as session:
        # Update product 1 with image
        stmt = sa.update(Product).where(Product.id == 1).values(
            image_url="https://picsum.photos/seed/widget/400/300"
        )
        await session.execute(stmt)

        # Check if product 2 exists
        result = await session.execute(sa.select(Product).where(Product.id == 2))
        if not result.scalar_one_or_none():
            session.add(Product(
                id=2,
                name="Gadget",
                stock=50,
                price=14.99,
                image_url="https://picsum.photos/seed/gadget/400/300"
            ))

        # Check if product 3 exists
        result = await session.execute(sa.select(Product).where(Product.id == 3))
        if not result.scalar_one_or_none():
            session.add(Product(
                id=3,
                name="Thingamajig",
                stock=75,
                price=19.99,
                image_url="https://picsum.photos/seed/thing/400/300"
            ))

        await session.commit()
        print("✅ Products seeded successfully!")

        # Verify
        result = await session.execute(sa.select(Product))
        products = result.scalars().all()
        print(f"Total products in DB: {len(products)}")
        for p in products:
            print(f"  - {p.id}: {p.name} (stock: {p.stock}, price: ${p.price}, image: {p.image_url})")


if __name__ == "__main__":
    asyncio.run(seed_missing_products())

