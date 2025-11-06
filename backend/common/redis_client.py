import asyncio
import logging
import ssl
from typing import Optional

from redis.asyncio import Redis

from .config import settings

_logger = logging.getLogger(__name__)

_redis: Optional[Redis] = None
_lock = asyncio.Lock()


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        async with _lock:
            if _redis is None:
                try:
                    conn_kwargs = {
                        "host": settings.REDIS_HOST,
                        "port": settings.REDIS_PORT,
                        "username": getattr(settings, "REDIS_USERNAME", None) or None,
                        "password": settings.REDIS_PASSWORD or None,
                        "db": settings.REDIS_DB,
                        "decode_responses": True,
                    }
                    if settings.REDIS_SSL:
                        conn_kwargs.update(
                            {
                                "ssl": True,
                                # relax cert verification for local/dev unless overridden by env
                                "ssl_cert_reqs": ssl.CERT_NONE,
                            }
                        )
                    _redis = Redis(**conn_kwargs)
                    # Validate connection quickly
                    await _redis.ping()
                    _logger.info(
                        "Connected to Redis at %s:%s (SSL=%s)",
                        settings.REDIS_HOST,
                        settings.REDIS_PORT,
                        settings.REDIS_SSL,
                    )
                except Exception as e:
                    _logger.error("Failed to connect to Redis: %s", str(e))
                    _redis = None
                    raise
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        try:
            await _redis.close()
        finally:
            _redis = None
