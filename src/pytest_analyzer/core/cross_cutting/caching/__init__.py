"""Result caching strategies and implementations.

Contains caching mechanisms for expensive operations like
LLM API calls and test analysis results.
"""

from .config import CachePolicy, CacheSettings, CachingConfig, RedisSettings
from .decorators import analysis_cached, cached, config_cached, llm_cached
from .memory_cache import MemoryCache
from .protocols import ICacheProvider, ITieredCache
from .redis_cache import RedisCache
from .tiered_cache import TieredCache

__all__ = [
    "ICacheProvider",
    "ITieredCache",
    "MemoryCache",
    "RedisCache",
    "TieredCache",
    "cached",
    "llm_cached",
    "analysis_cached",
    "config_cached",
    "CachePolicy",
    "CacheSettings",
    "CachingConfig",
    "RedisSettings",
]
