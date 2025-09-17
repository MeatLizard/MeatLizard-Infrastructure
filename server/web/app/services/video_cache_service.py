"""
Video Cache Service

Implements Redis caching for video metadata with intelligent cache invalidation,
cache warming for popular videos, and performance monitoring.
"""
import asyncio
import json
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from server.web.app.models import Video, User, ViewSession, VideoLike, VideoComment
from server.web.app.services.redis_client import RedisClient, CacheKeyBuilder, get_redis_client
from server.web.app.services.base_service import BaseService

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Cache performance statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


class VideoCacheService(BaseService):
    """Service for caching video metadata and related data"""
    
    # Cache TTL settings (in seconds)
    CACHE_TTL = {
        'video_metadata': 3600,      # 1 hour
        'video_list': 1800,          # 30 minutes
        'search_results': 900,       # 15 minutes
        'popular_tags': 7200,        # 2 hours
        'related_tags': 3600,        # 1 hour
        'analytics': 1800,           # 30 minutes
        'trending': 600,             # 10 minutes
        'user_stats': 1800,          # 30 minutes
    }
    
    def __init__(self, db: AsyncSession, redis_client: RedisClient = None):
        self.db = db
        self.redis = redis_client
        self.stats = CacheStats()
        self._warming_in_progress: Set[str] = set()
    
    async def _get_redis(self) -> RedisClient:
        """Get Redis client instance"""
        if self.redis is None:
            self.redis = await get_redis_client()
        return self.redis
    
    async def _record_hit(self):
        """Record cache hit"""
        self.stats.hits += 1
        redis = await self._get_redis()
        await redis.incr("cache:stats:hits")
    
    async def _record_miss(self):
        """Record cache miss"""
        self.stats.misses += 1
        redis = await self._get_redis()
        await redis.incr("cache:stats:misses")
    
    async def _record_set(self):
        """Record cache set operation"""
        self.stats.sets += 1
        redis = await self._get_redis()
        await redis.incr("cache:stats:sets")
    
    async def _record_error(self):
        """Record cache error"""
        self.stats.errors += 1
        redis = await self._get_redis()
        await redis.incr("cache:stats:errors")
    
    async def get_video_metadata(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get video metadata from cache or database
        
        Args:
            video_id: Video ID
            
        Returns:
            Video metadata dictionary or None if not found
        """
        redis = await self._get_redis()
        cache_key = CacheKeyBuilder.video_metadata(video_id)
        
        try:
            # Try cache first
            cached_data = await redis.get(cache_key)
            if cached_data:
                await self._record_hit()
                return cached_data
            
            await self._record_miss()
            
            # Fetch from database
            stmt = (
                select(Video, User)
                .join(User, Video.creator_id == User.id)
                .where(Video.id == video_id)
            )
            result = await self.db.execute(stmt)
            row = result.first()
            
            if not row:
                return None
            
            video, creator = row
            
            # Build metadata dictionary
            metadata = {
                'id': str(video.id),
                'title': video.title,
                'description': video.description,
                'tags': video.tags or [],
                'visibility': video.visibility.value,
                'status': video.status.value,
                'duration_seconds': video.duration_seconds,
                'source_resolution': video.source_resolution,
                'source_framerate': video.source_framerate,
                'file_size': video.file_size,
                'thumbnail_s3_key': video.thumbnail_s3_key,
                'created_at': video.created_at.isoformat(),
                'updated_at': video.updated_at.isoformat(),
                'creator': {
                    'id': str(creator.id),
                    'name': creator.display_label,
                },
                'cached_at': datetime.utcnow().isoformat()
            }
            
            # Cache the metadata
            await redis.set(
                cache_key, 
                metadata, 
                expire=self.CACHE_TTL['video_metadata']
            )
            await self._record_set()
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting video metadata for {video_id}: {e}")
            await self._record_error()
            return None
    
    async def set_video_metadata(self, video_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Cache video metadata
        
        Args:
            video_id: Video ID
            metadata: Metadata dictionary to cache
            
        Returns:
            True if successful, False otherwise
        """
        redis = await self._get_redis()
        cache_key = CacheKeyBuilder.video_metadata(video_id)
        
        try:
            metadata['cached_at'] = datetime.utcnow().isoformat()
            success = await redis.set(
                cache_key, 
                metadata, 
                expire=self.CACHE_TTL['video_metadata']
            )
            if success:
                await self._record_set()
            return success
            
        except Exception as e:
            logger.error(f"Error caching video metadata for {video_id}: {e}")
            await self._record_error()
            return False
    
    async def invalidate_video_metadata(self, video_id: str) -> bool:
        """
        Invalidate cached video metadata
        
        Args:
            video_id: Video ID
            
        Returns:
            True if successful, False otherwise
        """
        redis = await self._get_redis()
        
        try:
            # Invalidate main metadata cache
            cache_key = CacheKeyBuilder.video_metadata(video_id)
            deleted = await redis.delete(cache_key)
            
            # Also invalidate related caches
            await self._invalidate_related_caches(video_id)
            
            return deleted > 0
            
        except Exception as e:
            logger.error(f"Error invalidating video metadata for {video_id}: {e}")
            await self._record_error()
            return False
    
    async def _invalidate_related_caches(self, video_id: str):
        """Invalidate caches related to a video"""
        redis = await self._get_redis()
        
        try:
            # Get video to find creator
            video = await self.db.get(Video, video_id)
            if not video:
                return
            
            # Invalidate creator's video lists
            creator_id = str(video.creator_id)
            pattern = f"video:list:{creator_id}:*"
            
            # Note: In production, you might want to use SCAN instead of KEYS
            # for better performance with large datasets
            keys_to_delete = []
            
            # Invalidate search results that might contain this video
            # This is a simplified approach - in production you might want
            # a more sophisticated cache tagging system
            
            # Invalidate trending videos if this video was trending
            keys_to_delete.extend([
                "video:trending:1h",
                "video:trending:24h", 
                "video:trending:7d"
            ])
            
            # Invalidate popular tags cache since video tags might have changed
            keys_to_delete.append("video:tags:popular")
            
            if keys_to_delete:
                await redis.delete(*keys_to_delete)
                
        except Exception as e:
            logger.error(f"Error invalidating related caches for video {video_id}: {e}")
    
    async def get_user_video_list(
        self, 
        user_id: str, 
        page: int = 0, 
        limit: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached user video list
        
        Args:
            user_id: User ID
            page: Page number
            limit: Items per page
            
        Returns:
            List of video metadata dictionaries
        """
        redis = await self._get_redis()
        cache_key = CacheKeyBuilder.video_list(user_id, page)
        
        try:
            # Try cache first
            cached_data = await redis.get(cache_key)
            if cached_data:
                await self._record_hit()
                return cached_data
            
            await self._record_miss()
            
            # Fetch from database
            offset = page * limit
            stmt = (
                select(Video, User)
                .join(User, Video.creator_id == User.id)
                .where(Video.creator_id == user_id)
                .order_by(Video.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            result = await self.db.execute(stmt)
            rows = result.all()
            
            # Build video list
            video_list = []
            for video, creator in rows:
                video_data = {
                    'id': str(video.id),
                    'title': video.title,
                    'description': video.description,
                    'tags': video.tags or [],
                    'visibility': video.visibility.value,
                    'status': video.status.value,
                    'duration_seconds': video.duration_seconds,
                    'thumbnail_s3_key': video.thumbnail_s3_key,
                    'created_at': video.created_at.isoformat(),
                    'creator_name': creator.display_label
                }
                video_list.append(video_data)
            
            # Cache the list
            await redis.set(
                cache_key,
                video_list,
                expire=self.CACHE_TTL['video_list']
            )
            await self._record_set()
            
            return video_list
            
        except Exception as e:
            logger.error(f"Error getting user video list for {user_id}: {e}")
            await self._record_error()
            return None
    
    async def get_popular_tags(self, limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached popular tags
        
        Args:
            limit: Maximum number of tags to return
            
        Returns:
            List of tag dictionaries with usage counts
        """
        redis = await self._get_redis()
        cache_key = CacheKeyBuilder.popular_tags()
        
        try:
            # Try cache first
            cached_data = await redis.get(cache_key)
            if cached_data:
                await self._record_hit()
                return cached_data
            
            await self._record_miss()
            
            # Calculate popular tags from database
            # This is a simplified implementation - in production you might
            # want to use a more efficient approach with pre-computed tag counts
            
            stmt = select(Video.tags).where(Video.tags.isnot(None))
            result = await self.db.execute(stmt)
            
            tag_counts = {}
            for (tags,) in result:
                if tags:
                    for tag in tags:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            # Sort by usage count
            sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            
            popular_tags = [
                {'tag': tag, 'usage_count': count}
                for tag, count in sorted_tags
            ]
            
            # Cache the results
            await redis.set(
                cache_key,
                popular_tags,
                expire=self.CACHE_TTL['popular_tags']
            )
            await self._record_set()
            
            return popular_tags
            
        except Exception as e:
            logger.error(f"Error getting popular tags: {e}")
            await self._record_error()
            return None
    
    async def get_trending_videos(
        self, 
        timeframe: str = "24h", 
        limit: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached trending videos
        
        Args:
            timeframe: Time period (1h, 24h, 7d)
            limit: Maximum number of videos to return
            
        Returns:
            List of trending video metadata
        """
        redis = await self._get_redis()
        cache_key = CacheKeyBuilder.trending_videos(timeframe)
        
        try:
            # Try cache first
            cached_data = await redis.get(cache_key)
            if cached_data:
                await self._record_hit()
                return cached_data
            
            await self._record_miss()
            
            # Calculate trending videos from database
            # Define time window
            time_windows = {
                '1h': timedelta(hours=1),
                '24h': timedelta(days=1),
                '7d': timedelta(days=7)
            }
            
            time_window = time_windows.get(timeframe, timedelta(days=1))
            since_time = datetime.utcnow() - time_window
            
            # Get videos with recent activity (views, likes, comments)
            stmt = (
                select(
                    Video,
                    User,
                    func.count(ViewSession.id).label('view_count'),
                    func.count(VideoLike.id).label('like_count'),
                    func.count(VideoComment.id).label('comment_count')
                )
                .join(User, Video.creator_id == User.id)
                .outerjoin(ViewSession, and_(
                    ViewSession.video_id == Video.id,
                    ViewSession.started_at >= since_time
                ))
                .outerjoin(VideoLike, and_(
                    VideoLike.video_id == Video.id,
                    VideoLike.created_at >= since_time
                ))
                .outerjoin(VideoComment, and_(
                    VideoComment.video_id == Video.id,
                    VideoComment.created_at >= since_time
                ))
                .where(Video.visibility == 'public')
                .group_by(Video.id, User.id)
                .order_by(
                    (func.count(ViewSession.id) * 1.0 + 
                     func.count(VideoLike.id) * 2.0 + 
                     func.count(VideoComment.id) * 3.0).desc()
                )
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            rows = result.all()
            
            trending_videos = []
            for video, creator, view_count, like_count, comment_count in rows:
                video_data = {
                    'id': str(video.id),
                    'title': video.title,
                    'description': video.description,
                    'tags': video.tags or [],
                    'duration_seconds': video.duration_seconds,
                    'thumbnail_s3_key': video.thumbnail_s3_key,
                    'created_at': video.created_at.isoformat(),
                    'creator_name': creator.display_label,
                    'trending_score': {
                        'views': view_count,
                        'likes': like_count,
                        'comments': comment_count
                    }
                }
                trending_videos.append(video_data)
            
            # Cache the results
            await redis.set(
                cache_key,
                trending_videos,
                expire=self.CACHE_TTL['trending']
            )
            await self._record_set()
            
            return trending_videos
            
        except Exception as e:
            logger.error(f"Error getting trending videos: {e}")
            await self._record_error()
            return None
    
    async def warm_cache_for_video(self, video_id: str) -> bool:
        """
        Warm cache for a specific video
        
        Args:
            video_id: Video ID to warm cache for
            
        Returns:
            True if successful, False otherwise
        """
        if video_id in self._warming_in_progress:
            return False
        
        self._warming_in_progress.add(video_id)
        
        try:
            # Warm video metadata cache
            metadata = await self.get_video_metadata(video_id)
            if not metadata:
                return False
            
            # Warm related caches if this is a popular video
            # You could add logic here to warm other related caches
            
            logger.info(f"Cache warmed for video {video_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error warming cache for video {video_id}: {e}")
            return False
        finally:
            self._warming_in_progress.discard(video_id)
    
    async def warm_popular_videos_cache(self, limit: int = 100) -> int:
        """
        Warm cache for popular videos
        
        Args:
            limit: Number of popular videos to warm
            
        Returns:
            Number of videos successfully warmed
        """
        try:
            # Get popular videos based on recent activity
            since_time = datetime.utcnow() - timedelta(days=7)
            
            stmt = (
                select(Video.id, func.count(ViewSession.id).label('view_count'))
                .outerjoin(ViewSession, and_(
                    ViewSession.video_id == Video.id,
                    ViewSession.started_at >= since_time
                ))
                .where(Video.visibility == 'public')
                .group_by(Video.id)
                .order_by(func.count(ViewSession.id).desc())
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            popular_video_ids = [str(video_id) for video_id, _ in result]
            
            # Warm cache for each popular video
            warmed_count = 0
            for video_id in popular_video_ids:
                if await self.warm_cache_for_video(video_id):
                    warmed_count += 1
            
            logger.info(f"Warmed cache for {warmed_count}/{len(popular_video_ids)} popular videos")
            return warmed_count
            
        except Exception as e:
            logger.error(f"Error warming popular videos cache: {e}")
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics
        
        Returns:
            Dictionary with cache statistics
        """
        redis = await self._get_redis()
        
        try:
            # Get Redis stats
            redis_hits = await redis.get("cache:stats:hits", default=0)
            redis_misses = await redis.get("cache:stats:misses", default=0)
            redis_sets = await redis.get("cache:stats:sets", default=0)
            redis_errors = await redis.get("cache:stats:errors", default=0)
            
            total_requests = redis_hits + redis_misses
            hit_rate = (redis_hits / total_requests * 100) if total_requests > 0 else 0.0
            
            # Get Redis info
            redis_info = await redis.client.info()
            
            return {
                'cache_performance': {
                    'hits': redis_hits,
                    'misses': redis_misses,
                    'sets': redis_sets,
                    'errors': redis_errors,
                    'hit_rate_percent': round(hit_rate, 2),
                    'total_requests': total_requests
                },
                'redis_info': {
                    'used_memory': redis_info.get('used_memory_human', 'N/A'),
                    'connected_clients': redis_info.get('connected_clients', 0),
                    'total_commands_processed': redis_info.get('total_commands_processed', 0),
                    'keyspace_hits': redis_info.get('keyspace_hits', 0),
                    'keyspace_misses': redis_info.get('keyspace_misses', 0)
                },
                'instance_stats': {
                    'hits': self.stats.hits,
                    'misses': self.stats.misses,
                    'sets': self.stats.sets,
                    'deletes': self.stats.deletes,
                    'errors': self.stats.errors,
                    'hit_rate_percent': round(self.stats.hit_rate, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'error': str(e)}
    
    async def clear_all_cache(self) -> bool:
        """
        Clear all video-related cache entries
        
        Returns:
            True if successful, False otherwise
        """
        redis = await self._get_redis()
        
        try:
            # In production, you might want to be more selective
            # This is a simple implementation that clears the entire database
            await redis.flushdb()
            logger.info("All cache cleared")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False


# Dependency for FastAPI
async def get_video_cache_service(db: AsyncSession) -> VideoCacheService:
    """Get video cache service instance"""
    return VideoCacheService(db)