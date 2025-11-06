import asyncio
import json
from quart import Blueprint, Response

from ..common.redis_client import get_redis
from ..common.config import settings

bp = Blueprint("realtime", __name__)


@bp.get("/events")
async def sse_events():

    async def gen():
        pubsub = None
        r = None
        backoff = 1.0
        # Advise client on retry
        yield "retry: 3000\n\n"
        try:
            while True:
                try:
                    if r is None:
                        r = await get_redis()
                    if pubsub is None:
                        pubsub = r.pubsub(ignore_subscribe_messages=True)
                        await pubsub.subscribe(settings.REDIS_STOCK_CHANNEL)
                    message = await pubsub.get_message(timeout=5.0)
                    if message:
                        data = message.get("data")
                        # Allow both plain number (backward compatible) and JSON
                        try:
                            payload = json.loads(data) if isinstance(data, str) else data
                        except Exception:
                            payload = {"stock": data}
                        yield "event: stock\n"
                        yield f"data: {json.dumps(payload)}\n\n"
                    else:
                        # Keep-alive to prevent closes by proxies
                        yield ": keep-alive\n\n"
                    backoff = 1.0  # reset after success
                except asyncio.CancelledError:
                    break
                except Exception:
                    # Publish a comment and retry with backoff, then reconnect
                    yield f": redis-error, retrying in {int(backoff)}s\n\n"
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 15.0)
                    # reset clients
                    try:
                        if pubsub is not None:
                            try:
                                await pubsub.unsubscribe(settings.REDIS_STOCK_CHANNEL)
                            except Exception:
                                pass
                            await pubsub.close()
                    except Exception:
                        pass
                    pubsub = None
                    r = None
        finally:
            # Cleanup on exit
            try:
                if pubsub is not None:
                    try:
                        await pubsub.unsubscribe(settings.REDIS_STOCK_CHANNEL)
                    except Exception:
                        pass
                    await pubsub.close()
            except Exception:
                pass

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return Response(gen(), mimetype="text/event-stream", headers=headers)
