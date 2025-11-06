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
                backoff = 1.0
                last_exc: Optional[BaseException] = None
                for _ in range(8):  # ~ up to ~1+2+4+8+16+30+30+30 ~= 121s
                    try:
                        producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
                        await producer.start()
                        _producer = producer
                        break
                    except Exception as e:
                        last_exc = e
                        _producer = None
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 30.0)
                if _producer is None:
                    # Propagate the last error after retries
                    raise last_exc or RuntimeError("Kafka producer start failed")
    return _producer


async def close_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None


async def create_consumer(topic: str, group_id: str) -> AIOKafkaConsumer:
    backoff = 1.0
    last_exc: Optional[BaseException] = None
    for _ in range(8):
        try:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                group_id=group_id,
                enable_auto_commit=True,
                auto_offset_reset="earliest",
            )
            await consumer.start()
            return consumer
        except Exception as e:
            last_exc = e
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
    raise last_exc or RuntimeError("Kafka consumer start failed")


async def close_consumer(consumer: Optional[AIOKafkaConsumer]) -> None:
    if consumer is not None:
        await consumer.stop()
