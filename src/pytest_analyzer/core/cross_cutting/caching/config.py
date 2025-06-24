"""Configuration models for caching strategies."""

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class CachePolicy(str, Enum):
    """Enum for different cache policies."""

    DISABLED = "disabled"
    MEMORY_ONLY = "memory_only"
    REDIS_ONLY = "redis_only"
    TIERED = "tiered"


class RedisSettings(BaseModel):
    """Settings for Redis connection."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ttl: int = 3600  # Default TTL for Redis cache in seconds (1 hour)


class CacheSettings(BaseModel):
    """General settings for a cache category."""

    ttl: int = 3600  # Default TTL in seconds (1 hour)
    max_size: Optional[int] = 128  # For memory cache


class CachingConfig(BaseModel):
    """Main configuration for caching."""

    policy: CachePolicy = CachePolicy.DISABLED
    redis: RedisSettings = Field(default_factory=RedisSettings)
    categories: Dict[str, CacheSettings] = Field(
        default_factory=lambda: {
            "default": CacheSettings(),
            "llm": CacheSettings(ttl=86400),  # 24 hours
            "analysis": CacheSettings(ttl=3600),  # 1 hour
            "config": CacheSettings(ttl=600),  # 10 minutes
        }
    )
