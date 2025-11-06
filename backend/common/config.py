import os
from dataclasses import dataclass


def _get_bool(env_name: str, default: bool = False) -> bool:
    val = os.getenv(env_name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Settings:
    # App
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

    # Database (SQLite by default in a Docker volume)
    DB_URL: str = os.getenv("DB_URL", "sqlite+aiosqlite:////data/data.db")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_USERNAME: str = os.getenv("REDIS_USERNAME", "")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_SSL: bool = _get_bool("REDIS_SSL", False)
    REDIS_STOCK_CHANNEL: str = os.getenv("REDIS_STOCK_CHANNEL", "stock-updates")

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    PURCHASE_TOPIC: str = os.getenv("PURCHASE_TOPIC", "purchases")

    # Defaults for seeding
    DEFAULT_PRODUCT_ID: int = int(os.getenv("DEFAULT_PRODUCT_ID", "1"))
    DEFAULT_PRODUCT_NAME: str = os.getenv("DEFAULT_PRODUCT_NAME", "Widget")
    DEFAULT_PRODUCT_STOCK: int = int(os.getenv("DEFAULT_PRODUCT_STOCK", "100"))
    DEFAULT_PRODUCT_PRICE: float = float(os.getenv("DEFAULT_PRODUCT_PRICE", "9.99"))


settings = Settings()
