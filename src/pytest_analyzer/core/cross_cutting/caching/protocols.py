"""Protocols and Abstract Base Classes for caching implementations."""

from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol


class ICacheProvider(Protocol):
    """Protocol for a single cache provider (e.g., Memory, Redis)."""

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve an item from the cache."""

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set an item in the cache with an optional TTL."""

    async def delete(self, key: str) -> None:
        """Delete an item from the cache."""

    async def disconnect(self) -> None:
        """Disconnect or clean up the cache provider."""


class ITieredCache(ABC):
    """Abstract base class for a tiered cache system."""

    @abstractmethod
    async def get(self, key: str, category: str) -> Optional[Any]:
        """Retrieve an item from the tiered cache for a specific category."""

    @abstractmethod
    async def set(self, key: str, value: Any, category: str) -> None:
        """Set an item in the tiered cache for a specific category."""

    @abstractmethod
    async def delete(self, key: str, category: str) -> None:
        """Delete an item from the tiered cache for a specific category."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect all underlying cache providers."""
