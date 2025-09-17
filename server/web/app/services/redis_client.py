"""
Redis Client Service

Provides Redis connection management and caching utilities for the video platform.
Handles connection pooling, serialization, and cache operations.
"""
import json
import pickle
import asyncio
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import logging

from server.web.app.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client with connection pooling and serialization support"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.pool = None
        self.client = None
        self._connected = False
    
    async def connect(self):
        """Initialize Redis connection pool"""
        try:
            self.pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
            self.client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.client.ping()
            self._connected = True
            logger.info("Redis connection established")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()
        self._connected = False
        logger.info("Redis connection closed")
    
    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        return self._connected
    
    async def ensure_connected(self):
        """Ensure Redis connection is active"""
        if not self._connected:
            await self.connect()
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[int] = None,
        serialize: bool = True
    ) -> bool:
        """
        Set a key-value pair in Redis
        
        Args:
            key: Redis key
            value: Value to store
            expire: Expiration time in seconds
            serialize: Whether to serialize the value as JSON
        """
        await self.ensure_connected()
        
        try:
            if serialize:
                if isinstance(value, (dict, list)):
                    serialized_value = json.dumps(value, default=str)
                else:
                    serialized_value = str(value)
            else:
                serialized_value = value
            
            result = await self.client.set(key, serialized_value, ex=expire)
            return result
            
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    async def get(
        self, 
        key: str, 
        deserialize: bool = True,
        default: Any = None
    ) -> Any:
        """
        Get a value from Redis
        
        Args:
            key: Redis key
            deserialize: Whether to deserialize JSON values
            default: Default value if key doesn't exist
        """
        await self.ensure_connected()
        
        try:
            value = await self.client.get(key)
            if value is None:
                return default
            
            if deserialize:
                try:
                    return json.loads(value.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return value.decode('utf-8')
            else:
                return value.decode('utf-8')
                
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return default
    
    async def delete(self, *keys: str) -> int:
        """Delete one or more keys from Redis"""
        await self.ensure_connected()
        
        try:
            return await self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE error for keys {keys}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis"""
        await self.ensure_connected()
        
        try:
            return bool(await self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key"""
        await self.ensure_connected()
        
        try:
            return await self.client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key {key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get time to live for a key"""
        await self.ensure_connected()
        
        try:
            return await self.client.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL error for key {key}: {e}")
            return -1
    
    async def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """Set hash fields"""
        await self.ensure_connected()
        
        try:
            # Serialize values in the mapping
            serialized_mapping = {}
            for k, v in mapping.items():
                if isinstance(v, (dict, list)):
                    serialized_mapping[k] = json.dumps(v, default=str)
                else:
                    serialized_mapping[k] = str(v)
            
            return await self.client.hset(name, mapping=serialized_mapping)
        except Exception as e:
            logger.error(f"Redis HSET error for hash {name}: {e}")
            return 0
    
    async def hget(self, name: str, key: str, deserialize: bool = True) -> Any:
        """Get hash field value"""
        await self.ensure_connected()
        
        try:
            value = await self.client.hget(name, key)
            if value is None:
                return None
            
            if deserialize:
                try:
                    return json.loads(value.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return value.decode('utf-8')
            else:
                return value.decode('utf-8')
                
        except Exception as e:
            logger.error(f"Redis HGET error for hash {name}, key {key}: {e}")
            return None
    
    async def hgetall(self, name: str, deserialize: bool = True) -> Dict[str, Any]:
        """Get all hash fields"""
        await self.ensure_connected()
        
        try:
            result = await self.client.hgetall(name)
            if not result:
                return {}
            
            if deserialize:
                deserialized = {}
                for k, v in result.items():
                    key = k.decode('utf-8')
                    try:
                        deserialized[key] = json.loads(v.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        deserialized[key] = v.decode('utf-8')
                return deserialized
            else:
                return {k.decode('utf-8'): v.decode('utf-8') for k, v in result.items()}
                
        except Exception as e:
            logger.error(f"Redis HGETALL error for hash {name}: {e}")
            return {}
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields"""
        await self.ensure_connected()
        
        try:
            return await self.client.hdel(name, *keys)
        except Exception as e:
            logger.error(f"Redis HDEL error for hash {name}, keys {keys}: {e}")
            return 0
    
    async def zadd(self, name: str, mapping: Dict[str, float]) -> int:
        """Add members to sorted set"""
        await self.ensure_connected()
        
        try:
            return await self.client.zadd(name, mapping)
        except Exception as e:
            logger.error(f"Redis ZADD error for sorted set {name}: {e}")
            return 0
    
    async def zrange(
        self, 
        name: str, 
        start: int, 
        end: int, 
        withscores: bool = False
    ) -> List[Any]:
        """Get range from sorted set"""
        await self.ensure_connected()
        
        try:
            result = await self.client.zrange(name, start, end, withscores=withscores)
            if withscores:
                return [(item.decode('utf-8'), score) for item, score in result]
            else:
                return [item.decode('utf-8') for item in result]
        except Exception as e:
            logger.error(f"Redis ZRANGE error for sorted set {name}: {e}")
            return []
    
    async def zrem(self, name: str, *values: str) -> int:
        """Remove members from sorted set"""
        await self.ensure_connected()
        
        try:
            return await self.client.zrem(name, *values)
        except Exception as e:
            logger.error(f"Redis ZREM error for sorted set {name}: {e}")
            return 0
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a key's value"""
        await self.ensure_connected()
        
        try:
            return await self.client.incr(key, amount)
        except Exception as e:
            logger.error(f"Redis INCR error for key {key}: {e}")
            return 0
    
    async def decr(self, key: str, amount: int = 1) -> int:
        """Decrement a key's value"""
        await self.ensure_connected()
        
        try:
            return await self.client.decr(key, amount)
        except Exception as e:
            logger.error(f"Redis DECR error for key {key}: {e}")
            return 0
    
    async def pipeline(self):
        """Create a Redis pipeline for batch operations"""
        await self.ensure_connected()
        return self.client.pipeline()
    
    async def flushdb(self):
        """Flush current database (use with caution!)"""
        await self.ensure_connected()
        
        try:
            return await self.client.flushdb()
        except Exception as e:
            logger.error(f"Redis FLUSHDB error: {e}")
            return False


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """Get the global Redis client instance"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    return _redis_client


async def close_redis_client():
    """Close the global Redis client"""
    global _redis_client
    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None


class CacheKeyBuilder:
    """Utility class for building consistent cache keys"""
    
    @staticmethod
    def video_metadata(video_id: str) -> str:
        """Cache key for video metadata"""
        return f"video:metadata:{video_id}"
    
    @staticmethod
    def video_list(user_id: str, page: int = 0) -> str:
        """Cache key for user's video list"""
        return f"video:list:{user_id}:{page}"
    
    @staticmethod
    def video_search(query: str, tags: List[str] = None, page: int = 0) -> str:
        """Cache key for video search results"""
        tags_str = ",".join(sorted(tags)) if tags else ""
        query_hash = hash(f"{query}:{tags_str}")
        return f"video:search:{query_hash}:{page}"
    
    @staticmethod
    def popular_tags() -> str:
        """Cache key for popular tags"""
        return "video:tags:popular"
    
    @staticmethod
    def related_tags(tag: str) -> str:
        """Cache key for related tags"""
        return f"video:tags:related:{tag}"
    
    @staticmethod
    def video_analytics(video_id: str, timeframe: str) -> str:
        """Cache key for video analytics"""
        return f"video:analytics:{video_id}:{timeframe}"
    
    @staticmethod
    def trending_videos(timeframe: str = "24h") -> str:
        """Cache key for trending videos"""
        return f"video:trending:{timeframe}"
    
    @staticmethod
    def user_stats(user_id: str) -> str:
        """Cache key for user statistics"""
        return f"user:stats:{user_id}"