from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..common.db import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price: Mapped[float] = mapped_column(
        # use Integer cents or Numeric in production; keep simple float per PRD
        default=0.0
    )

