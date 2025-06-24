"""Redis cache provider implementation (L2 Cache)."""

import asyncio
import logging
import pickle
from typing import Any, Optional

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError

from .config import RedisSettings
from .protocols import ICacheProvider

logger = logging.getLogger(__name__)


class RedisCache(ICacheProvider):
    """
    An asyncio-compatible Redis cache provider.

    Handles connection management, serialization, and graceful
    failures when Redis is unavailable.
    """

    def __init__(self, settings: RedisSettings):
        self._settings = settings
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._lock = asyncio.Lock()
        self._is_connected = False

    async def connect(self) -> None:
        if self._is_connected and self._client:
            return

        async with self._lock:
            if self._is_connected and self._client:
                return

            try:
                logger.info(
                    f"Connecting to Redis at {self._settings.host}:{self._settings.port}..."
                )
                redis_url = f"redis://{self._settings.host}:{self._settings.port}/{self._settings.db}"
                self._pool = ConnectionPool.from_url(
                    url=redis_url,
                    password=self._settings.password,
                    # The `ssl` argument is part of from_url in recent versions
                )
                self._client = redis.Redis(connection_pool=self._pool)
                await self._client.ping()
                self._is_connected = True
                logger.info("Successfully connected to Redis.")
            except RedisError as e:
                logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
                self._is_connected = False
                self._client = None
                self._pool = None

    async def disconnect(self) -> None:
        if not self._is_connected or not self._pool:
            return

        async with self._lock:
            if not self._is_connected or not self._pool:
                return

            try:
                await self._pool.disconnect()
                logger.info("Disconnected from Redis.")
            except RedisError as e:
                logger.error(
                    f"Error while disconnecting from Redis: {e}", exc_info=True
                )
            finally:
                self._is_connected = False
                self._client = None
                self._pool = None

    async def get(self, key: str) -> Optional[Any]:
        if not self._is_connected or not self._client:
            logger.warning("Redis is not connected. Cannot get key '%s'.", key)
            return None

        try:
            cached_value = await self._client.get(key)
            if cached_value is None:
                return None
            return pickle.loads(cached_value)
        except RedisError as e:
            logger.error(f"Redis GET error for key '{key}': {e}", exc_info=True)
            return None
        except (pickle.PickleError, TypeError) as e:
            logger.error(f"Deserialization error for key '{key}': {e}", exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if not self._is_connected or not self._client:
            logger.warning("Redis is not connected. Cannot set key '%s'.", key)
            return

        try:
            serialized_value = pickle.dumps(value)
            await self._client.set(key, serialized_value, ex=ttl)
        except RedisError as e:
            logger.error(f"Redis SET error for key '{key}': {e}", exc_info=True)
        except (pickle.PickleError, TypeError) as e:
            logger.error(f"Serialization error for key '{key}': {e}", exc_info=True)

    async def delete(self, key: str) -> None:
        if not self._is_connected or not self._client:
            logger.warning("Redis is not connected. Cannot delete key '%s'.", key)
            return

        try:
            await self._client.delete(key)
        except RedisError as e:
            logger.error(f"Redis DELETE error for key '{key}': {e}", exc_info=True)

    async def clear(self) -> None:
        if not self._is_connected or not self._client:
            logger.warning("Redis is not connected. Cannot clear cache.")
            return

        try:
            await self._client.flushdb()
            logger.info("Redis cache cleared (FLUSHDB).")
        except RedisError as e:
            logger.error(f"Redis FLUSHDB error: {e}", exc_info=True)
