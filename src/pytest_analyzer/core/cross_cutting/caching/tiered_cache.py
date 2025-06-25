"""Tiered cache implementation."""

from typing import Any, List, Optional

from .config import CachingConfig
from .protocols import ICacheProvider, ITieredCache


class TieredCache(ITieredCache):
    """Multi-level cache combining multiple providers."""

    def __init__(self, providers: List[ICacheProvider], config: CachingConfig) -> None:
        super().__init__()
        self._providers = providers
        self._config = config

    async def get(self, key: str, category: str) -> Optional[Any]:
        """Get value from cache tiers."""
        for i, provider in enumerate(self._providers):
            try:
                value = await provider.get(key)
                if value is not None:
                    # Populate higher tiers
                    if i > 0:
                        category_settings = self._config.categories.get(
                            category, self._config.categories["default"]
                        )
                        for higher_provider in self._providers[:i]:
                            await higher_provider.set(
                                key, value, ttl=category_settings.ttl
                            )
                    return value
            except Exception:  # pylint: disable=broad-except
                continue
        return None

    async def set(self, key: str, value: Any, category: str) -> None:
        """Set value in all cache tiers."""
        category_settings = self._config.categories.get(
            category, self._config.categories["default"]
        )
        for provider in self._providers:
            try:
                await provider.set(key, value, ttl=category_settings.ttl)
            except Exception:  # pylint: disable=broad-except
                continue

    async def delete(self, key: str, category: str) -> None:
        """Delete value from all cache tiers."""
        for provider in self._providers:
            try:
                await provider.delete(key)
            except Exception:  # pylint: disable=broad-except
                continue

    async def disconnect(self) -> None:
        """Disconnect all providers."""
        for provider in self._providers:
            try:
                await provider.disconnect()
            except Exception:  # pylint: disable=broad-except
                continue
