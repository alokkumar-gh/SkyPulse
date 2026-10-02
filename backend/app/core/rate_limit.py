import time
import logging
from typing import Optional
from fastapi import Request, HTTPException, status
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("skypulse.ratelimit")

_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> Optional[aioredis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            await _redis_client.ping()
        except Exception as e:
            logger.debug("Redis rate limiter unavailable: %s. Failing open.", e)
            _redis_client = None
    return _redis_client


def rate_limiter(requests_per_minute: int = 20):
    async def dependency(request: Request):
        # Demo mode or test mode may bypass or relax
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        key = f"rate_limit:{client_ip}"

        try:
            r = await get_redis_client()
            if r is None:
                return  # fail open

            now = int(time.time())
            window_start = now - 60

            # Redis sorted set for sliding window
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {f"{now}_{time.time_ns()}": now})
            pipe.zcard(key)
            pipe.expire(key, 65)
            results = await pipe.execute()

            request_count = results[2]
            if request_count > requests_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Maximum {requests_per_minute} requests per minute.",
                        "details": {"retry_after_seconds": 60},
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.debug("Rate limit check failed with error: %s (failing open)", e)
            return

    return dependency
