import hashlib
import time
import logging
from typing import Optional, Dict
from datetime import datetime

from app.core.rate_limit import get_redis_client

logger = logging.getLogger("skypulse.idempotency")


class IdempotencyService:
    """
    Guarantees that identical raw weather observations from external connectors
    are not processed multiple times. Uses Redis with an in-memory fallback.
    """

    def __init__(self, in_memory_max_size: int = 10000):
        self._memory_cache: Dict[str, float] = {}  # key -> expiry timestamp
        self._max_size = in_memory_max_size

    def compute_key(
        self,
        source_id: str,
        external_id: Optional[str] = None,
        text: Optional[str] = None,
        observed_at: Optional[datetime] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> str:
        """
        Generate a unique SHA-256 fingerprint for a report.
        If an external ID exists from the upstream provider, use (source_id, external_id).
        Otherwise, combine source, normalized text snippet, rounded timestamp, and coordinates.
        """
        if external_id:
            raw = f"src:{source_id}:ext:{external_id}"
        else:
            # Round time to 5-minute bucket to catch near-simultaneous duplicate broadcasts
            time_bucket = 0
            if observed_at:
                time_bucket = int(observed_at.timestamp() // 300)
            
            # Round coordinates to ~100m (~3 decimal places)
            lat_r = round(latitude, 3) if latitude is not None else "none"
            lon_r = round(longitude, 3) if longitude is not None else "none"
            text_snippet = (text or "").strip().lower()[:150]

            raw = f"src:{source_id}:t:{time_bucket}:loc:{lat_r},{lon_r}:txt:{text_snippet}"

        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def is_duplicate(self, key: str, ttl_seconds: int = 86400) -> bool:
        """
        Check if key has been seen recently. If not, record it and return False.
        If already seen, return True (indicating duplicate).
        """
        redis = await get_redis_client()
        redis_key = f"skypulse:idemp:{key}"

        if redis:
            try:
                # SET with NX (not exists) returns True if set, False if already exists
                is_new = await redis.set(redis_key, "1", ex=ttl_seconds, nx=True)
                return not bool(is_new)
            except Exception as e:
                logger.debug("Redis idempotency error (%s), using in-memory fallback", e)

        # In-memory fallback
        now = time.time()
        self._purge_expired(now)

        if key in self._memory_cache:
            if self._memory_cache[key] > now:
                return True

        if len(self._memory_cache) >= self._max_size:
            # Remove oldest key
            oldest_key = min(self._memory_cache, key=self._memory_cache.get)
            del self._memory_cache[oldest_key]

        self._memory_cache[key] = now + ttl_seconds
        return False

    def _purge_expired(self, now: float) -> None:
        expired = [k for k, exp in self._memory_cache.items() if exp <= now]
        for k in expired:
            del self._memory_cache[k]


idempotency_service = IdempotencyService()
