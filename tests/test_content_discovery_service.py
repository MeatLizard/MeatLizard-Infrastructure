"""
Tests for content discovery service.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from server.web.app.services.content_discovery_service import ContentDiscoveryService, SortOrder
from server.web.app.models import Video, VideoVisibility, VideoStatus


class TestContentDiscoveryService:
    """Test cases for ContentDiscoveryService."""
    
    @pytest.fixture
    def discovery_service(self):
        """Create a ContentDiscoveryService instance with mocked dependencies."""
        service = ContentDiscoveryService()
        service.get_db_session = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        return session
    
    @pytest.fixture
    def sample_videos(self):
        """Create sample videos for testing."""
        videos = []
        for i in range(5):
            video = Video(
                id=uuid.uuid4(),
                creator_id=uuid.uuid4(),
                title=f"Test Video {i+1}",
                description=f"Description for video {i+1}",
                duration_seconds=300 + i * 60,
                visibility=VideoVisibility.public,
                status=VideoStatus.ready,
                category="technology",
                tags=["test", "video", f"tag{i}"],
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            videos.append(video)
        return videos
    
    @pytest.mark.asyncio
    async def test_browse_videos_basic(self, discovery_service, mock_db_session, sample_videos):
        """Test basic video browsing functionality."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        
        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = len(sample_videos)
        
        # Mock videos query
        videos_result = MagicMock()
        videos_result.scalars.return_value.all.return_value = sample_videos
        
        mock_db_session.execute = AsyncMock(side_effect=[count_result, videos_result])
        
        # Execute
        videos, total = await discovery_service.browse_videos(limit=10, offset=0)
        
        # Verify
        assert len(videos) == len(sample_videos)
        assert total == len(sample_videos)
        assert mock_db_session.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_browse_videos_with_filters(self, discovery_service, mock_db_session, sample_videos):
        """Test video browsing with filters applied."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        
        filtered_videos = [v for v in sample_videos if v.category == "technology"]
        
        count_result = MagicMock()
        count_result.scalar.return_value = len(filtered_videos)
        
        videos_result = MagicMock()
        videos_result.scalars.return_value.all.return_value = filtered_videos
        
        mock_db_session.execute = AsyncMock(side_effect=[count_result, videos_result])
        
        # Execute
        videos, total = await discovery_service.browse_videos(
            category="technology",
            search_query="test",
            sort_order=SortOrder.newest,
            limit=10,
            offset=0
        )
        
        # Verify
        assert len(videos) == len(filtered_videos)
        assert total == len(filtered_videos)
        assert mock_db_session.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_trending_videos(self, discovery_service, mock_db_session, sample_videos):
        """Test getting trending videos."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        
        # Mock the query result - trending returns tuples of (video, view_count)
        trending_result = MagicMock()
        trending_result.all.return_value = [(video, 100 - i*10) for i, video in enumerate(sample_videos)]
        
        mock_db_session.execute = AsyncMock(return_value=trending_result)
        
        # Execute
        videos = await discovery_service.get_trending_videos(timeframe="week", limit=5)
        
        # Verify
        assert len(videos) == len(sample_videos)
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_popular_videos(self, discovery_service, mock_db_session, sample_videos):
        """Test getting popular videos based on likes."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        
        # Mock the query result - popular returns tuples of (video, like_count)
        popular_result = MagicMock()
        popular_result.all.return_value = [(video, 50 - i*5) for i, video in enumerate(sample_videos)]
        
        mock_db_session.execute = AsyncMock(return_value=popular_result)
        
        # Execute
        videos = await discovery_service.get_popular_videos(timeframe="month", limit=5)
        
        # Verify
        assert len(videos) == len(sample_videos)
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_related_videos(self, discovery_service, mock_db_session, sample_videos):
        """Test getting related videos."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        
        source_video = sample_videos[0]
        related_videos = sample_videos[1:3]  # Videos 2 and 3 are related
        
        # Mock source video query
        source_result = MagicMock()
        source_result.scalar_one_or_none.return_value = source_video
        
        # Mock related videos query
        related_result = MagicMock()
        related_result.scalars.return_value.all.return_value = related_videos
        
        mock_db_session.execute = AsyncMock(side_effect=[source_result, related_result])
        
        # Execute
        videos = await discovery_service.get_related_videos(
            video_id=source_video.id,
            limit=5
        )
        
        # Verify
        assert len(videos) == len(related_videos)
        assert mock_db_session.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_related_videos_nonexistent(self, discovery_service, mock_db_session):
        """Test getting related videos for non-existent video."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        
        source_result = MagicMock()
        source_result.scalar_one_or_none.return_value = None
        
        mock_db_session.execute = AsyncMock(return_value=source_result)
        
        # Execute
        videos = await discovery_service.get_related_videos(
            video_id=uuid.uuid4(),
            limit=5
        )
        
        # Verify
        assert len(videos) == 0
        mock_db_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_content(self, discovery_service, mock_db_session, sample_videos):
        """Test content search functionality."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        
        # Mock browse_videos method
        discovery_service.browse_videos = AsyncMock(return_value=(sample_videos[:3], 3))
        
        # Mock channel search
        channel_count_result = MagicMock()
        channel_count_result.scalar.return_value = 0
        
        channel_result = MagicMock()
        channel_result.scalars.return_value.all.return_value = []
        
        # Mock playlist search
        playlist_count_result = MagicMock()
        playlist_count_result.scalar.return_value = 0
        
        playlist_result = MagicMock()
        playlist_result.scalars.return_value.all.return_value = []
        
        mock_db_session.execute = AsyncMock(side_effect=[
            channel_count_result, channel_result,
            playlist_count_result, playlist_result
        ])
        
        # Execute
        results = await discovery_service.search_content(
            search_query="test",
            content_types=["videos", "channels", "playlists"],
            limit=10,
            offset=0
        )
        
        # Verify
        assert "videos" in results
        assert results["videos"]["total"] == 3
        assert len(results["videos"]["items"]) == 3
        assert "channels" in results
        assert "playlists" in results
    
    @pytest.mark.asyncio
    async def test_get_categories(self, discovery_service, mock_db_session):
        """Test getting categories with counts."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        
        # Mock video categories query
        video_categories_result = MagicMock()
        video_categories_result.all.return_value = [
            ("technology", 10),
            ("gaming", 8),
            ("education", 5)
        ]
        
        # Mock channel categories query
        channel_categories_result = MagicMock()
        channel_categories_result.all.return_value = [
            ("technology", 3),
            ("gaming", 2),
            ("music", 1)
        ]
        
        mock_db_session.execute = AsyncMock(side_effect=[
            video_categories_result,
            channel_categories_result
        ])
        
        # Execute
        categories = await discovery_service.get_categories()
        
        # Verify
        assert len(categories) == 4  # technology, gaming, education, music
        
        # Check technology category (should have both video and channel counts)
        tech_category = next(c for c in categories if c['name'] == 'technology')
        assert tech_category['video_count'] == 10
        assert tech_category['channel_count'] == 3
        
        # Check music category (should have only channel count)
        music_category = next(c for c in categories if c['name'] == 'music')
        assert music_category['video_count'] == 0
        assert music_category['channel_count'] == 1
    
    @pytest.mark.asyncio
    async def test_get_recommended_videos(self, discovery_service, mock_db_session, sample_videos):
        """Test getting personalized recommendations."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        user_id = uuid.uuid4()
        
        # Mock user preferences query
        preferences_result = MagicMock()
        preferences_result.all.return_value = [
            ("technology", ["test", "video"], 5),
            ("gaming", ["game", "play"], 3)
        ]
        
        # Mock recommended videos query
        recommended_result = MagicMock()
        recommended_result.scalars.return_value.all.return_value = sample_videos[:3]
        
        mock_db_session.execute = AsyncMock(side_effect=[
            preferences_result,
            recommended_result
        ])
        
        # Execute
        videos = await discovery_service.get_recommended_videos(
            user_id=user_id,
            limit=10
        )
        
        # Verify
        assert len(videos) == 3
        assert mock_db_session.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_recommended_videos_no_history(self, discovery_service, mock_db_session, sample_videos):
        """Test getting recommendations for user with no viewing history."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        discovery_service.get_trending_videos = AsyncMock(return_value=sample_videos[:5])
        user_id = uuid.uuid4()
        
        # Mock empty preferences query
        preferences_result = MagicMock()
        preferences_result.all.return_value = []
        
        mock_db_session.execute = AsyncMock(return_value=preferences_result)
        
        # Execute
        videos = await discovery_service.get_recommended_videos(
            user_id=user_id,
            limit=10
        )
        
        # Verify - should fall back to trending videos
        assert len(videos) == 5
        discovery_service.get_trending_videos.assert_called_once_with(
            viewer_user_id=user_id,
            limit=10
        )
    
    @pytest.mark.asyncio
    async def test_get_video_analytics_for_discovery(self, discovery_service, mock_db_session):
        """Test getting video analytics for discovery algorithms."""
        # Setup
        discovery_service.get_db_session.return_value = mock_db_session
        video_id = uuid.uuid4()
        
        # Mock analytics queries
        view_count_result = MagicMock()
        view_count_result.scalar.return_value = 150
        
        like_count_result = MagicMock()
        like_count_result.scalar.return_value = 25
        
        dislike_count_result = MagicMock()
        dislike_count_result.scalar.return_value = 5
        
        avg_watch_time_result = MagicMock()
        avg_watch_time_result.scalar.return_value = 180.5
        
        completion_rate_result = MagicMock()
        completion_rate_result.scalar.return_value = 75.2
        
        mock_db_session.execute = AsyncMock(side_effect=[
            view_count_result,
            like_count_result,
            dislike_count_result,
            avg_watch_time_result,
            completion_rate_result
        ])
        
        # Execute
        analytics = await discovery_service.get_video_analytics_for_discovery(video_id)
        
        # Verify
        assert analytics['view_count'] == 150
        assert analytics['like_count'] == 25
        assert analytics['dislike_count'] == 5
        assert analytics['engagement_rate'] == (25 + 5) / 150 * 100  # 20%
        assert analytics['like_ratio'] == 25 / 30 * 100  # ~83.33%
        assert analytics['avg_watch_time_seconds'] == 180.5
        assert analytics['completion_rate'] == 75.2
        assert mock_db_session.execute.call_count == 5