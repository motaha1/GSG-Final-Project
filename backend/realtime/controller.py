from quart import Blueprint, Response

from ..common.redis_client import get_redis
from ..common.config import settings

bp = Blueprint("realtime", __name__)


@bp.get("/events")
async def sse_events():
    r = await get_redis()
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    await pubsub.subscribe(settings.REDIS_STOCK_CHANNEL)

    async def gen():
        try:
            # Initial reconnection advice for SSE clients
            yield "retry: 3000\n\n"
            while True:
                message = await pubsub.get_message(timeout=5.0)
                if message:
                    data = message.get("data")
                    yield "event: stock\n"
                    yield f"data: {data}\n\n"
                else:
                    # Keep-alive comment to prevent proxies from closing idle connections
                    yield ": keep-alive\n\n"
        finally:
            try:
                await pubsub.unsubscribe(settings.REDIS_STOCK_CHANNEL)
            finally:
                await pubsub.close()

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(gen(), mimetype="text/event-stream", headers=headers)

