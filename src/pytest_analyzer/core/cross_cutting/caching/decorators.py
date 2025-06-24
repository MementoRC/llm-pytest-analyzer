"""Caching decorators for function results."""

import functools
import hashlib
import inspect
import json
import logging
from typing import Any, Callable, Optional

from .protocols import ITieredCache

logger = logging.getLogger(__name__)

_cache_instance: Optional[ITieredCache] = None


def configure_cache(cache: ITieredCache) -> None:
    """Configure the global cache instance."""
    global _cache_instance  # pylint: disable=global-statement
    _cache_instance = cache


def _generate_cache_key(func: Callable, *args: Any, **kwargs: Any) -> str:
    """Generate a deterministic cache key."""
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()

    try:
        arg_str = json.dumps(bound_args.arguments, sort_keys=True, default=str)
    except (TypeError, ValueError):
        arg_str = str(bound_args.arguments)

    key_material = f"{func.__module__}.{func.__name__}:{arg_str}"
    return hashlib.sha256(key_material.encode()).hexdigest()


def cached(key_prefix: str, ttl: Optional[int] = None) -> Callable:
    """Decorator for caching async function results."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if _cache_instance is None:
                logger.warning("Cache not configured for %s", func.__name__)
                return await func(*args, **kwargs)

            cache_key = f"{key_prefix}:{_generate_cache_key(func, *args, **kwargs)}"

            # Try to get from cache
            cached_result = await _cache_instance.get(cache_key, key_prefix)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await _cache_instance.set(cache_key, result, key_prefix)
            return result

        return wrapper

    return decorator


# Pre-configured decorators
llm_cached = cached("llm", ttl=86400)
analysis_cached = cached("analysis", ttl=3600)
config_cached = cached("config", ttl=600)
