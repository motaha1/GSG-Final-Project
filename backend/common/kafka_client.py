import asyncio
from typing import Optional

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from .config import settings

_producer: Optional[AIOKafkaProducer] = None
_producer_lock = asyncio.Lock()


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        async with _producer_lock:
            if _producer is None:
                _producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
                await _producer.start()
    return _producer


async def close_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None


async def create_consumer(topic: str, group_id: str) -> AIOKafkaConsumer:
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=group_id,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    return consumer


async def close_consumer(consumer: Optional[AIOKafkaConsumer]) -> None:
    if consumer is not None:
        await consumer.stop()

