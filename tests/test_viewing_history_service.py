"""
Tests for viewing history service.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.models import User, Video, ViewSession, VideoStatus, VideoVisibility
from server.web.app.services.viewing_history_service import ViewingHistoryService

@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        display_label="Test User",
        email="test@example.com"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
async def test_creator(db_session: AsyncSession):
    """Create a test creator."""
    creator = User(
        id=uuid.uuid4(),
        display_label="Video Creator",
        email="creator@example.com"
    )
    db_session.add(creator)
    await db_session.commit()
    await db_session.refresh(creator)
    return creator

@pytest.fixture
async def test_video(db_session: AsyncSession, test_creator: User):
    """Create a test video."""
    video = Video(
        id=uuid.uuid4(),
        creator_id=test_creator.id,
        title="Test Video",
        description="A test video for viewing history",
        original_filename="test.mp4",
        original_s3_key="videos/test.mp4",
        file_size=1000000,
        duration_seconds=300,  # 5 minutes
        status=VideoStatus.ready,
        visibility=VideoVisibility.public
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)
    return video

@pytest.fixture
async def test_view_session(db_session: AsyncSession, test_user: User, test_video: Video):
    """Create a test viewing session."""
    session = ViewSession(
        id=uuid.uuid4(),
        video_id=test_video.id,
        user_id=test_user.id,
        session_token="test_session_token",
        current_position_seconds=150,  # 2.5 minutes
        total_watch_time_seconds=180,  # 3 minutes
        completion_percentage=50,
        started_at=datetime.utcnow() - timedelta(hours=1),
        last_heartbeat=datetime.utcnow() - timedelta(minutes=30),
        ended_at=datetime.utcnow() - timedelta(minutes=30)
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session

class TestViewingHistoryService:
    """Test viewing history service functionality."""
    
    async def test_get_user_viewing_history_empty(self, db_session: AsyncSession, test_user: User):
        """Test getting viewing history for user with no history."""
        service = ViewingHistoryService(db_session)
        
        result = await service.get_user_viewing_history(test_user.id)
        
        assert result is not None
        assert result["history"] == []
        assert result["user_id"] == str(test_user.id)
        assert result["pagination"]["total"] == 0
    
    async def test_get_user_viewing_history_with_data(
        self, 
        db_session: AsyncSession, 
        test_user: User, 
        test_video: Video, 
        test_view_session: ViewSession
    ):
        """Test getting viewing history with data."""
        service = ViewingHistoryService(db_session)
        
        result = await service.get_user_viewing_history(test_user.id)
        
        assert result is not None
        assert len(result["history"]) == 1
        assert result["history"][0]["video_id"] == str(test_video.id)
        assert result["history"][0]["title"] == test_video.title
        assert result["history"][0]["watch_progress"]["completion_percentage"] == 50
        assert result["history"][0]["can_resume"] is True
    
    async def test_get_user_viewing_history_pagination(
        self, 
        db_session: AsyncSession, 
        test_user: User, 
        test_creator: User
    ):
        """Test viewing history pagination."""
        service = ViewingHistoryService(db_session)
        
        # Create multiple videos and sessions
        videos = []
        for i in range(5):
            video = Video(
                id=uuid.uuid4(),
                creator_id=test_creator.id,
                title=f"Test Video {i}",
                description=f"Test video {i}",
                original_filename=f"test{i}.mp4",
                original_s3_key=f"videos/test{i}.mp4",
                file_size=1000000,
                duration_seconds=300,
                status=VideoStatus.ready,
                visibility=VideoVisibility.public
            )
            db_session.add(video)
            videos.append(video)
        
        await db_session.commit()
        
        # Create viewing sessions
        for i, video in enumerate(videos):
            session = ViewSession(
                id=uuid.uuid4(),
                video_id=video.id,
                user_id=test_user.id,
                session_token=f"session_{i}",
                current_position_seconds=60,
                total_watch_time_seconds=60,
                completion_percentage=20,
                started_at=datetime.utcnow() - timedelta(hours=i+1),
                last_heartbeat=datetime.utcnow() - timedelta(hours=i+1),
                ended_at=datetime.utcnow() - timedelta(hours=i+1)
            )
            db_session.add(session)
        
        await db_session.commit()
        
        # Test first page
        result = await service.get_user_viewing_history(test_user.id, page=1, limit=3)
        
        assert result is not None
        assert len(result["history"]) == 3
        assert result["pagination"]["total"] == 5
        assert result["pagination"]["pages"] == 2
        
        # Test second page
        result2 = await service.get_user_viewing_history(test_user.id, page=2, limit=3)
        
        assert result2 is not None
        assert len(result2["history"]) == 2
    
    async def test_get_user_viewing_history_filters_low_completion(
        self, 
        db_session: AsyncSession, 
        test_user: User, 
        test_video: Video
    ):
        """Test that viewing history filters out sessions with low completion."""
        service = ViewingHistoryService(db_session)
        
        # Create session with low completion (< 5%)
        low_completion_session = ViewSession(
            id=uuid.uuid4(),
            video_id=test_video.id,
            user_id=test_user.id,
            session_token="low_completion_session",
            current_position_seconds=5,
            total_watch_time_seconds=5,
            completion_percentage=2,  # Less than 5%
            started_at=datetime.utcnow() - timedelta(hours=1),
            last_heartbeat=datetime.utcnow() - timedelta(minutes=30),
            ended_at=datetime.utcnow() - timedelta(minutes=30)
        )
        db_session.add(low_completion_session)
        await db_session.commit()
        
        result = await service.get_user_viewing_history(test_user.id)
        
        assert result is not None
        assert len(result["history"]) == 0  # Should be filtered out
    
    async def test_clear_viewing_history(
        self, 
        db_session: AsyncSession, 
        test_user: User, 
        test_view_session: ViewSession
    ):
        """Test clearing all viewing history."""
        service = ViewingHistoryService(db_session)
        
        # Verify history exists
        result_before = await service.get_user_viewing_history(test_user.id)
        assert len(result_before["history"]) == 1
        
        # Clear history
        clear_result = await service.clear_viewing_history(test_user.id)
        assert clear_result["cleared_count"] == 1
        
        # Verify history is cleared
        result_after = await service.get_user_viewing_history(test_user.id)
        assert len(result_after["history"]) == 0
    
    async def test_remove_video_from_history(
        self, 
        db_session: AsyncSession, 
        test_user: User, 
        test_video: Video, 
        test_view_session: ViewSession
    ):
        """Test removing a specific video from history."""
        service = ViewingHistoryService(db_session)
        
        # Verify video is in history
        result_before = await service.get_user_viewing_history(test_user.id)
        assert len(result_before["history"]) == 1
        
        # Remove video from history
        remove_result = await service.remove_video_from_history(test_user.id, test_video.id)
        assert remove_result["found"] is True
        assert remove_result["removed_sessions"] == 1
        
        # Verify video is removed
        result_after = await service.get_user_viewing_history(test_user.id)
        assert len(result_after["history"]) == 0
    
    async def test_remove_nonexistent_video_from_history(
        self, 
        db_session: AsyncSession, 
        test_user: User
    ):
        """Test removing a nonexistent video from history."""
        service = ViewingHistoryService(db_session)
        fake_video_id = uuid.uuid4()
        
        result = await service.remove_video_from_history(test_user.id, fake_video_id)
        
        assert result["found"] is False
    
    async def test_get_viewing_stats(
        self, 
        db_session: AsyncSession, 
        test_user: User, 
        test_video: Video, 
        test_view_session: ViewSession
    ):
        """Test getting viewing statistics."""
        service = ViewingHistoryService(db_session)
        
        result = await service.get_viewing_stats(test_user.id)
        
        assert result is not None
        assert result["user_id"] == str(test_user.id)
        assert result["total_videos_watched"] == 1
        assert result["total_watch_time_seconds"] == 180
        assert result["completed_videos"] == 0  # 50% completion < 90%
        assert result["average_completion_percentage"] == 50.0
    
    async def test_get_continue_watching(
        self, 
        db_session: AsyncSession, 
        test_user: User, 
        test_video: Video
    ):
        """Test getting continue watching videos."""
        service = ViewingHistoryService(db_session)
        
        # Create a session with partial completion (can resume)
        resume_session = ViewSession(
            id=uuid.uuid4(),
            video_id=test_video.id,
            user_id=test_user.id,
            session_token="resume_session",
            current_position_seconds=120,  # 2 minutes
            total_watch_time_seconds=120,
            completion_percentage=40,  # Between 10-90%
            started_at=datetime.utcnow() - timedelta(hours=1),
            last_heartbeat=datetime.utcnow() - timedelta(minutes=30),
            ended_at=datetime.utcnow() - timedelta(minutes=30)
        )
        db_session.add(resume_session)
        await db_session.commit()
        
        result = await service.get_continue_watching(test_user.id)
        
        assert result is not None
        assert len(result["continue_watching"]) == 1
        assert result["continue_watching"][0]["video_id"] == str(test_video.id)
        assert result["continue_watching"][0]["resume_position_seconds"] == 120
        assert result["continue_watching"][0]["completion_percentage"] == 40
    
    async def test_get_recommendations_empty_history(
        self, 
        db_session: AsyncSession, 
        test_user: User
    ):
        """Test getting recommendations with empty viewing history."""
        service = ViewingHistoryService(db_session)
        
        result = await service.get_recommendations(test_user.id)
        
        assert result is not None
        assert result["recommendations"] == []
        assert result["user_id"] == str(test_user.id)
    
    async def test_get_recommendations_with_history(
        self, 
        db_session: AsyncSession, 
        test_user: User, 
        test_creator: User, 
        test_video: Video
    ):
        """Test getting recommendations based on viewing history."""
        service = ViewingHistoryService(db_session)
        
        # Create a viewing session with high completion
        high_completion_session = ViewSession(
            id=uuid.uuid4(),
            video_id=test_video.id,
            user_id=test_user.id,
            session_token="high_completion_session",
            current_position_seconds=270,
            total_watch_time_seconds=270,
            completion_percentage=90,
            started_at=datetime.utcnow() - timedelta(hours=1),
            last_heartbeat=datetime.utcnow() - timedelta(minutes=30),
            ended_at=datetime.utcnow() - timedelta(minutes=30)
        )
        db_session.add(high_completion_session)
        
        # Create another video from the same creator
        another_video = Video(
            id=uuid.uuid4(),
            creator_id=test_creator.id,
            title="Another Video",
            description="Another video from same creator",
            original_filename="another.mp4",
            original_s3_key="videos/another.mp4",
            file_size=1000000,
            duration_seconds=240,
            status=VideoStatus.ready,
            visibility=VideoVisibility.public
        )
        db_session.add(another_video)
        await db_session.commit()
        
        result = await service.get_recommendations(test_user.id)
        
        assert result is not None
        assert len(result["recommendations"]) >= 1
        # Should recommend videos from creators the user has watched
        recommended_video_ids = [rec["video_id"] for rec in result["recommendations"]]
        assert str(another_video.id) in recommended_video_ids
    
    async def test_format_duration(self, db_session: AsyncSession):
        """Test duration formatting helper."""
        service = ViewingHistoryService(db_session)
        
        assert service._format_duration(30) == "30s"
        assert service._format_duration(90) == "1m"
        assert service._format_duration(3600) == "1h"
        assert service._format_duration(3690) == "1h 1m"
    
    async def test_nonexistent_user_operations(self, db_session: AsyncSession):
        """Test operations on nonexistent users."""
        service = ViewingHistoryService(db_session)
        fake_user_id = uuid.uuid4()
        
        # Should return None for nonexistent user
        result = await service.get_user_viewing_history(fake_user_id)
        assert result is None