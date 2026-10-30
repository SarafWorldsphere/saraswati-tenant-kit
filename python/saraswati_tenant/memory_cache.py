"""One in-memory cache for this process. Domain lookup and catalog resolution share it."""

from __future__ import annotations

import time
from typing import Any

SCHOOL_CACHE_SECONDS = 60 * 60 * 24


class MemoryCache:
    """Values stay for `ttl_seconds`. `get` returns None on a miss, so do not store None."""

    def __init__(self, ttl_seconds: float = SCHOOL_CACHE_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        hit = self._entries.get(key)
        if hit is None:
            return None
        stored_at, value = hit
        if time.monotonic() - stored_at >= self.ttl_seconds:
            self._entries.pop(key, None)
            return None
        return value

    def put(self, key: str, value: Any) -> Any:
        self._entries[key] = (time.monotonic(), value)
        return value

    def clear(self) -> None:
        self._entries.clear()


school_cache = MemoryCache()
