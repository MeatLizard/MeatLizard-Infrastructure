"""
Tests for Video Analytics Service

Tests analytics collection, aggregation, and reporting functionality.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from server.web.app.services.video_analytics_service import VideoAnalyticsService
from server.web.app.models import (
    Video, ViewSession, VideoLike, VideoComment, User, 
    AnalyticsEvent, VideoStatus, VideoVisibility
)


@pytest.fixture
async def analytics_service():
    """Create analytics service instance"""
    return VideoAnalyticsService()


@pytest.fixture
async def sample_user(db_session):
    """Create a sample user"""
    user = User(
        id=uuid4(),
        display_label="Test Creator",
        email="creator@test.com"
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def sample_video(db_session, sample_user):
    """Create a sample video"""
    video = Video(
        id=uuid4(),
        creator_id=sample_user.id,
        title="Test Video",
        description="A test video for analytics",
        original_filename="test.mp4",
        original_s3_key="videos/test.mp4",
        file_size=1000000,
        duration_seconds=300,  # 5 minutes
        source_resolution="1920x1080",
        source_framerate=30,
        status=VideoStatus.ready,
        visibility=VideoVisibility.public
    )
    db_session.add(video)
    await db_session.commit()
    return video


@pytest.fixture
async def sample_view_sessions(db_session, sample_video, sample_user):
    """Create sample view sessions"""
    sessions = []
    base_time = datetime.utcnow() - timedelta(hours=2)
    
    for i in range(5):
        session = ViewSession(
            id=uuid4(),
            video_id=sample_video.id,
            user_id=sample_user.id if i % 2 == 0 else None,
            session_token=f"token_{i}",
            current_position_seconds=60 * (i + 1),
            total_watch_time_seconds=60 * (i + 1),
            completion_percentage=20 * (i + 1),
            qualities_used=["720p", "1080p"] if i % 2 == 0 else ["480p"],
            quality_switches=i,
            buffering_events=i * 2,
            started_at=base_time + timedelta(minutes=i * 10),
            last_heartbeat=base_time + timedelta(minutes=i * 10 + 5)
        )
        sessions.append(session)
        db_session.add(session)
    
    await db_session.commit()
    return sessions


class TestVideoAnalyticsService:
    """Test video analytics service functionality"""
    
    async def test_record_view_event(self, analytics_service, sample_video, sample_user, db_session):
        """Test recording a view event"""
        event_data = {
            "user_agent": "Mozilla/5.0",
            "ip_address": "192.168.1.1",
            "referrer": "https://example.com"
        }
        
        await analytics_service.record_view_event(
            sample_video.id,
            sample_user.id,
            event_data
        )
        
        # Verify event was recorded
        events = await db_session.execute(
            "SELECT * FROM analytics_events WHERE event_type = 'video_view' AND content_id = :video_id",
            {"video_id": str(sample_video.id)}
        )
        event_rows = events.fetchall()
        
        assert len(event_rows) == 1
        assert event_rows[0].user_id == str(sample_user.id)
    
    async def test_record_engagement_event(self, analytics_service, sample_video, sample_user, db_session):
        """Test recording an engagement event"""
        event_data = {"action": "like", "timestamp": datetime.utcnow().isoformat()}
        
        await analytics_service.record_engagement_event(
            sample_video.id,
            sample_user.id,
            "like",
            event_data
        )
        
        # Verify event was recorded
        events = await db_session.execute(
            "SELECT * FROM analytics_events WHERE event_type = 'video_like' AND content_id = :video_id",
            {"video_id": str(sample_video.id)}
        )
        event_rows = events.fetchall()
        
        assert len(event_rows) == 1
    
    async def test_record_performance_event(self, analytics_service, sample_video, db_session):
        """Test recording a performance event"""
        session_id = uuid4()
        event_data = {
            "quality_from": "720p",
            "quality_to": "1080p",
            "buffer_duration": 2.5
        }
        
        await analytics_service.record_performance_event(
            sample_video.id,
            session_id,
            "quality_switch",
            event_data
        )
        
        # Verify event was recorded
        events = await db_session.execute(
            "SELECT * FROM analytics_events WHERE event_type = 'video_performance_quality_switch'",
        )
        event_rows = events.fetchall()
        
        assert len(event_rows) == 1
        assert str(session_id) in event_rows[0].data["session_id"]
    
    async def test_record_playback_progress(self, analytics_service, sample_view_sessions, db_session):
        """Test updating playback progress"""
        session = sample_view_sessions[0]
        
        await analytics_service.record_playback_progress(
            session.id,
            current_position=120,
            quality="1080p",
            buffering_events=3,
            quality_switches=2
        )
        
        # Refresh session from database
        await db_session.refresh(session)
        
        assert session.current_position_seconds == 120
        assert session.buffering_events == 3
        assert session.quality_switches == 2
        assert "1080p" in session.qualities_used
    
    async def test_get_video_analytics(self, analytics_service, sample_video, sample_view_sessions):
        """Test getting comprehensive video analytics"""
        analytics = await analytics_service.get_video_analytics(sample_video.id, "24h")
        
        assert analytics["video_id"] == str(sample_video.id)
        assert analytics["timeframe"] == "24h"
        
        # Check basic metrics
        basic_metrics = analytics["basic_metrics"]
        assert basic_metrics["total_views"] == 5
        assert basic_metrics["video_duration_seconds"] == 300
        assert basic_metrics["completion_rate_percent"] > 0
        
        # Check quality metrics
        quality_metrics = analytics["quality_metrics"]
        assert "quality_distribution" in quality_metrics
        assert quality_metrics["total_buffering_events"] > 0
        assert quality_metrics["total_quality_switches"] > 0
        
        # Check audience retention
        assert "audience_retention" in analytics
        assert len(analytics["audience_retention"]) > 0
        
        # Check views over time
        assert "views_over_time" in analytics
        assert len(analytics["views_over_time"]) > 0
    
    async def test_get_creator_analytics(self, analytics_service, sample_user, sample_video, sample_view_sessions):
        """Test getting creator analytics"""
        analytics = await analytics_service.get_creator_analytics(sample_user.id, "30d")
        
        assert analytics["creator_id"] == str(sample_user.id)
        assert analytics["timeframe"] == "30d"
        
        # Check overview
        overview = analytics["overview"]
        assert overview["total_videos"] == 1
        assert overview["total_views"] == 5
        assert overview["total_watch_time_hours"] > 0
        
        # Check top videos
        assert "top_videos" in analytics
        assert len(analytics["top_videos"]) > 0
        assert analytics["top_videos"][0]["video_id"] == str(sample_video.id)
    
    async def test_get_real_time_metrics(self, analytics_service, sample_video, sample_view_sessions):
        """Test getting real-time metrics"""
        # Update last heartbeat to make sessions appear active
        for session in sample_view_sessions[:2]:
            session.last_heartbeat = datetime.utcnow()
            session.ended_at = None
        
        metrics = await analytics_service.get_real_time_metrics(sample_video.id)
        
        assert metrics["video_id"] == str(sample_video.id)
        assert "timestamp" in metrics
        assert "active_viewers" in metrics
        assert "recent_activity" in metrics
    
    async def test_audience_retention_calculation(self, analytics_service, sample_video, sample_view_sessions, db_session):
        """Test audience retention calculation"""
        start_date = datetime.utcnow() - timedelta(hours=3)
        
        retention_data = await analytics_service._calculate_audience_retention(
            sample_video.id, 
            start_date, 
            db_session
        )
        
        assert len(retention_data) == 11  # 0% to 100% in 10% intervals
        assert all("percentage" in point for point in retention_data)
        assert all("viewers" in point for point in retention_data)
        assert all("retention_rate" in point for point in retention_data)
        
        # Retention should decrease as percentage increases
        assert retention_data[0]["retention_rate"] >= retention_data[-1]["retention_rate"]
    
    async def test_views_over_time(self, analytics_service, sample_video, sample_view_sessions, db_session):
        """Test views over time calculation"""
        start_date = datetime.utcnow() - timedelta(hours=3)
        
        views_over_time = await analytics_service._get_views_over_time(
            sample_video.id,
            start_date,
            "24h",
            db_session
        )
        
        assert len(views_over_time) > 0
        assert all("timestamp" in point for point in views_over_time)
        assert all("views" in point for point in views_over_time)
        
        # Total views should match our sample sessions
        total_views = sum(point["views"] for point in views_over_time)
        assert total_views == 5
    
    async def test_export_analytics_data(self, analytics_service, sample_video, sample_view_sessions):
        """Test exporting analytics data"""
        # Test JSON export
        json_data = await analytics_service.export_analytics_data(sample_video.id, "json")
        assert isinstance(json_data, dict)
        assert "video_id" in json_data
        
        # Test CSV export
        csv_data = await analytics_service.export_analytics_data(sample_video.id, "csv")
        assert isinstance(csv_data, dict)
        # CSV format should have flattened keys
        assert any("_" in key for key in csv_data.keys())
    
    async def test_analytics_with_engagement_data(self, analytics_service, sample_video, sample_user, db_session):
        """Test analytics with likes and comments"""
        # Add some likes
        like1 = VideoLike(
            video_id=sample_video.id,
            user_id=sample_user.id,
            is_like=True
        )
        like2 = VideoLike(
            video_id=sample_video.id,
            user_id=uuid4(),
            is_like=False
        )
        db_session.add_all([like1, like2])
        
        # Add some comments
        comment = VideoComment(
            video_id=sample_video.id,
            user_id=sample_user.id,
            content="Great video!"
        )
        db_session.add(comment)
        await db_session.commit()
        
        # Get analytics
        analytics = await analytics_service.get_video_analytics(sample_video.id, "24h")
        
        engagement_metrics = analytics["engagement_metrics"]
        assert engagement_metrics["likes"] == 1
        assert engagement_metrics["dislikes"] == 1
        assert engagement_metrics["comments"] == 1
        assert engagement_metrics["engagement_rate"] > 0
    
    async def test_analytics_empty_data(self, analytics_service):
        """Test analytics with no data"""
        non_existent_video_id = uuid4()
        
        analytics = await analytics_service.get_video_analytics(non_existent_video_id, "7d")
        assert analytics == {}
    
    async def test_creator_analytics_no_videos(self, analytics_service):
        """Test creator analytics with no videos"""
        non_existent_creator_id = uuid4()
        
        analytics = await analytics_service.get_creator_analytics(non_existent_creator_id, "30d")
        assert "error" in analytics
        assert "No videos found" in analytics["error"]