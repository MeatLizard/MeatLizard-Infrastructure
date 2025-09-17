"""
Tests for Video Cache Service

Tests caching functionality including cache hits/misses, invalidation,
warming strategies, and performance monitoring.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from server.web.app.services.video_cache_service import VideoCacheService, CacheStats
from server.web.app.services.redis_client import RedisClient, CacheKeyBuilder
from server.web.app.models import Video, User, VideoStatus, VideoVisibility


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    redis_client = AsyncMock(spec=RedisClient)
    redis_client.is_connected = True
    return redis_client


@pytest.fixture
def mock_db_session():
    """Mock database session for testing"""
    return AsyncMock()


@pytest.fixture
def cache_service(mock_db_session, mock_redis_client):
    """Video cache service instance for testing"""
    service = VideoCacheService(mock_db_session, mock_redis_client)
    return service


@pytest.fixture
def sample_video_data():
    """Sample video data for testing"""
    return {
        'id': 'test-video-id',
        'title': 'Test Video',
        'description': 'Test video description',
        'tags': ['test', 'video'],
        'visibility': 'public',
        'status': 'completed',
        'duration_seconds': 120.0,
        'source_resolution': '1920x1080',
        'source_framerate': 30.0,
        'file_size': 1024000,
        'thumbnail_s3_key': 'thumbnails/test-video-id/thumb.jpg',
        'created_at': '2024-01-01T00:00:00',
        'updated_at': '2024-01-01T00:00:00',
        'creator': {
            'id': 'test-user-id',
            'name': 'Test User'
        }
    }


class TestVideoCacheService:
    """Test cases for VideoCacheService"""
    
    @pytest.mark.asyncio
    async def test_get_video_metadata_cache_hit(self, cache_service, mock_redis_client, sample_video_data):
        """Test cache hit when getting video metadata"""
        # Setup
        video_id = 'test-video-id'
        mock_redis_client.get.return_value = sample_video_data
        
        # Execute
        result = await cache_service.get_video_metadata(video_id)
        
        # Verify
        assert result == sample_video_data
        mock_redis_client.get.assert_called_once_with(CacheKeyBuilder.video_metadata(video_id))
        assert cache_service.stats.hits == 1
        assert cache_service.stats.misses == 0
    
    @pytest.mark.asyncio
    async def test_get_video_metadata_cache_miss(self, cache_service, mock_redis_client, mock_db_session):
        """Test cache miss when getting video metadata"""
        # Setup
        video_id = 'test-video-id'
        mock_redis_client.get.return_value = None
        
        # Mock database response
        mock_video = MagicMock()
        mock_video.id = video_id
        mock_video.title = 'Test Video'
        mock_video.description = 'Test description'
        mock_video.tags = ['test']
        mock_video.visibility.value = 'public'
        mock_video.status.value = 'completed'
        mock_video.duration_seconds = 120.0
        mock_video.source_resolution = '1920x1080'
        mock_video.source_framerate = 30.0
        mock_video.file_size = 1024000
        mock_video.thumbnail_s3_key = 'thumb.jpg'
        mock_video.created_at = datetime(2024, 1, 1)
        mock_video.updated_at = datetime(2024, 1, 1)
        mock_video.creator_id = 'user-id'
        
        mock_user = MagicMock()
        mock_user.id = 'user-id'
        mock_user.display_label = 'Test User'
        
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_video, mock_user)
        mock_db_session.execute.return_value = mock_result
        
        # Execute
        result = await cache_service.get_video_metadata(video_id)
        
        # Verify
        assert result is not None
        assert result['id'] == video_id
        assert result['title'] == 'Test Video'
        assert cache_service.stats.hits == 0
        assert cache_service.stats.misses == 1
        mock_redis_client.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_video_metadata(self, cache_service, mock_redis_client, sample_video_data):
        """Test setting video metadata in cache"""
        # Setup
        video_id = 'test-video-id'
        mock_redis_client.set.return_value = True
        
        # Execute
        result = await cache_service.set_video_metadata(video_id, sample_video_data)
        
        # Verify
        assert result is True
        mock_redis_client.set.assert_called_once()
        assert cache_service.stats.sets == 1
    
    @pytest.mark.asyncio
    async def test_invalidate_video_metadata(self, cache_service, mock_redis_client, mock_db_session):
        """Test invalidating video metadata cache"""
        # Setup
        video_id = 'test-video-id'
        mock_redis_client.delete.return_value = 1
        
        # Mock video for related cache invalidation
        mock_video = MagicMock()
        mock_video.creator_id = 'user-id'
        mock_db_session.get.return_value = mock_video
        
        # Execute
        result = await cache_service.invalidate_video_metadata(video_id)
        
        # Verify
        assert result is True
        mock_redis_client.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_user_video_list_cache_hit(self, cache_service, mock_redis_client):
        """Test cache hit when getting user video list"""
        # Setup
        user_id = 'test-user-id'
        page = 0
        cached_list = [{'id': 'video1', 'title': 'Video 1'}]
        mock_redis_client.get.return_value = cached_list
        
        # Execute
        result = await cache_service.get_user_video_list(user_id, page)
        
        # Verify
        assert result == cached_list
        mock_redis_client.get.assert_called_once_with(CacheKeyBuilder.video_list(user_id, page))
        assert cache_service.stats.hits == 1
    
    @pytest.mark.asyncio
    async def test_get_popular_tags_cache_miss(self, cache_service, mock_redis_client, mock_db_session):
        """Test cache miss when getting popular tags"""
        # Setup
        mock_redis_client.get.return_value = None
        
        # Mock database response
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([(['tag1', 'tag2'],), (['tag2', 'tag3'],)])
        mock_db_session.execute.return_value = mock_result
        
        # Execute
        result = await cache_service.get_popular_tags(10)
        
        # Verify
        assert result is not None
        assert len(result) > 0
        assert cache_service.stats.misses == 1
        mock_redis_client.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_warm_cache_for_video(self, cache_service):
        """Test warming cache for a specific video"""
        # Setup
        video_id = 'test-video-id'
        
        # Mock get_video_metadata to return data
        with patch.object(cache_service, 'get_video_metadata') as mock_get:
            mock_get.return_value = {'id': video_id, 'title': 'Test Video'}
            
            # Execute
            result = await cache_service.warm_cache_for_video(video_id)
            
            # Verify
            assert result is True
            mock_get.assert_called_once_with(video_id)
    
    @pytest.mark.asyncio
    async def test_warm_cache_for_video_not_found(self, cache_service):
        """Test warming cache for non-existent video"""
        # Setup
        video_id = 'non-existent-video'
        
        # Mock get_video_metadata to return None
        with patch.object(cache_service, 'get_video_metadata') as mock_get:
            mock_get.return_value = None
            
            # Execute
            result = await cache_service.warm_cache_for_video(video_id)
            
            # Verify
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache_service, mock_redis_client):
        """Test getting cache statistics"""
        # Setup
        mock_redis_client.get.side_effect = [100, 20, 50, 5]  # hits, misses, sets, errors
        mock_redis_client.client.info.return_value = {
            'used_memory_human': '10MB',
            'connected_clients': 5,
            'total_commands_processed': 1000,
            'keyspace_hits': 800,
            'keyspace_misses': 200
        }
        
        # Execute
        result = await cache_service.get_cache_stats()
        
        # Verify
        assert 'cache_performance' in result
        assert 'redis_info' in result
        assert 'instance_stats' in result
        assert result['cache_performance']['hit_rate_percent'] == 83.33  # 100/(100+20)*100
    
    @pytest.mark.asyncio
    async def test_clear_all_cache(self, cache_service, mock_redis_client):
        """Test clearing all cache entries"""
        # Setup
        mock_redis_client.flushdb.return_value = True
        
        # Execute
        result = await cache_service.clear_all_cache()
        
        # Verify
        assert result is True
        mock_redis_client.flushdb.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_key_builder(self):
        """Test cache key building utility"""
        # Test video metadata key
        video_id = 'test-video-id'
        key = CacheKeyBuilder.video_metadata(video_id)
        assert key == f"video:metadata:{video_id}"
        
        # Test video list key
        user_id = 'test-user-id'
        page = 1
        key = CacheKeyBuilder.video_list(user_id, page)
        assert key == f"video:list:{user_id}:{page}"
        
        # Test search key
        query = 'test query'
        tags = ['tag1', 'tag2']
        key = CacheKeyBuilder.video_search(query, tags, 0)
        assert 'video:search:' in key
        
        # Test popular tags key
        key = CacheKeyBuilder.popular_tags()
        assert key == "video:tags:popular"
        
        # Test related tags key
        tag = 'test-tag'
        key = CacheKeyBuilder.related_tags(tag)
        assert key == f"video:tags:related:{tag}"
    
    @pytest.mark.asyncio
    async def test_concurrent_warming_prevention(self, cache_service):
        """Test that concurrent warming of the same video is prevented"""
        # Setup
        video_id = 'test-video-id'
        
        # Mock get_video_metadata with delay
        async def mock_get_with_delay(vid_id):
            await asyncio.sleep(0.1)
            return {'id': vid_id, 'title': 'Test Video'}
        
        with patch.object(cache_service, 'get_video_metadata', side_effect=mock_get_with_delay):
            # Execute concurrent warming requests
            task1 = asyncio.create_task(cache_service.warm_cache_for_video(video_id))
            task2 = asyncio.create_task(cache_service.warm_cache_for_video(video_id))
            
            results = await asyncio.gather(task1, task2)
            
            # Verify - one should succeed, one should fail due to concurrent warming prevention
            assert True in results
            assert False in results
    
    @pytest.mark.asyncio
    async def test_error_handling_redis_failure(self, cache_service, mock_redis_client):
        """Test error handling when Redis operations fail"""
        # Setup
        video_id = 'test-video-id'
        mock_redis_client.get.side_effect = Exception("Redis connection failed")
        
        # Execute
        result = await cache_service.get_video_metadata(video_id)
        
        # Verify
        assert result is None
        assert cache_service.stats.errors == 1
    
    @pytest.mark.asyncio
    async def test_cache_stats_calculation(self):
        """Test cache statistics calculation"""
        stats = CacheStats()
        
        # Test initial state
        assert stats.hit_rate == 0.0
        
        # Test with some hits and misses
        stats.hits = 80
        stats.misses = 20
        assert stats.hit_rate == 80.0
        
        # Test with only hits
        stats.hits = 100
        stats.misses = 0
        assert stats.hit_rate == 100.0
        
        # Test with only misses
        stats.hits = 0
        stats.misses = 50
        assert stats.hit_rate == 0.0


class TestCacheKeyBuilder:
    """Test cases for CacheKeyBuilder utility"""
    
    def test_video_metadata_key(self):
        """Test video metadata cache key generation"""
        video_id = 'abc123'
        key = CacheKeyBuilder.video_metadata(video_id)
        assert key == 'video:metadata:abc123'
    
    def test_video_list_key(self):
        """Test video list cache key generation"""
        user_id = 'user123'
        page = 2
        key = CacheKeyBuilder.video_list(user_id, page)
        assert key == 'video:list:user123:2'
    
    def test_video_search_key(self):
        """Test video search cache key generation"""
        query = 'test search'
        tags = ['tag1', 'tag2']
        page = 1
        key = CacheKeyBuilder.video_search(query, tags, page)
        
        # Key should contain search prefix and page
        assert key.startswith('video:search:')
        assert key.endswith(':1')
        
        # Same query and tags should produce same key
        key2 = CacheKeyBuilder.video_search(query, tags, page)
        assert key == key2
        
        # Different order of tags should produce same key (sorted)
        key3 = CacheKeyBuilder.video_search(query, ['tag2', 'tag1'], page)
        assert key == key3
    
    def test_popular_tags_key(self):
        """Test popular tags cache key generation"""
        key = CacheKeyBuilder.popular_tags()
        assert key == 'video:tags:popular'
    
    def test_related_tags_key(self):
        """Test related tags cache key generation"""
        tag = 'programming'
        key = CacheKeyBuilder.related_tags(tag)
        assert key == 'video:tags:related:programming'
    
    def test_video_analytics_key(self):
        """Test video analytics cache key generation"""
        video_id = 'video123'
        timeframe = '24h'
        key = CacheKeyBuilder.video_analytics(video_id, timeframe)
        assert key == 'video:analytics:video123:24h'
    
    def test_trending_videos_key(self):
        """Test trending videos cache key generation"""
        timeframe = '7d'
        key = CacheKeyBuilder.trending_videos(timeframe)
        assert key == 'video:trending:7d'
        
        # Test default timeframe
        key_default = CacheKeyBuilder.trending_videos()
        assert key_default == 'video:trending:24h'
    
    def test_user_stats_key(self):
        """Test user stats cache key generation"""
        user_id = 'user456'
        key = CacheKeyBuilder.user_stats(user_id)
        assert key == 'user:stats:user456'


if __name__ == '__main__':
    pytest.main([__file__])