"""In-memory cache implementation."""

import time
from typing import Any, Dict, Optional, Tuple

from .protocols import ICacheProvider


class MemoryCache(ICacheProvider):
    """Simple in-memory cache with TTL support."""

    def __init__(self) -> None:
        self._cache: Dict[str, Tuple[Any, float]] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            return None

        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        expiry = time.time() + (ttl or 3600)  # Default 1 hour
        self._cache[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        if key in self._cache:
            del self._cache[key]

    async def disconnect(self) -> None:
        """Clear cache on disconnect."""
        self._cache.clear()
