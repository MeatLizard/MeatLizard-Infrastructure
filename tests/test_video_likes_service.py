"""
Tests for video likes service.
"""
import pytest
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.models import User, Video, VideoLike, VideoStatus, VideoVisibility
from server.web.app.services.video_likes_service import VideoLikesService

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
async def test_video(db_session: AsyncSession, test_user: User):
    """Create a test video."""
    video = Video(
        id=uuid.uuid4(),
        creator_id=test_user.id,
        title="Test Video",
        description="A test video",
        original_filename="test.mp4",
        original_s3_key="videos/test.mp4",
        file_size=1000000,
        duration_seconds=120,
        status=VideoStatus.ready,
        visibility=VideoVisibility.public
    )
    db_session.add(video)
    await db_session.commit()
    await db_session.refresh(video)
    return video

@pytest.fixture
async def another_user(db_session: AsyncSession):
    """Create another test user."""
    user = User(
        id=uuid.uuid4(),
        display_label="Another User",
        email="another@example.com"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

class TestVideoLikesService:
    """Test video likes service functionality."""
    
    async def test_like_video_new_like(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test liking a video for the first time."""
        service = VideoLikesService(db_session)
        
        result = await service.like_video(test_video.id, test_user.id)
        
        assert result is not None
        assert result["action"] == "liked"
        assert result["like_count"] == 1
        assert result["dislike_count"] == 0
        assert result["user_status"] == "liked"
    
    async def test_like_video_remove_existing_like(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test removing an existing like."""
        service = VideoLikesService(db_session)
        
        # First like the video
        await service.like_video(test_video.id, test_user.id)
        
        # Like again to remove
        result = await service.like_video(test_video.id, test_user.id)
        
        assert result is not None
        assert result["action"] == "removed_like"
        assert result["like_count"] == 0
        assert result["dislike_count"] == 0
        assert result["user_status"] is None
    
    async def test_like_video_change_from_dislike(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test changing from dislike to like."""
        service = VideoLikesService(db_session)
        
        # First dislike the video
        await service.dislike_video(test_video.id, test_user.id)
        
        # Then like it
        result = await service.like_video(test_video.id, test_user.id)
        
        assert result is not None
        assert result["action"] == "changed_to_like"
        assert result["like_count"] == 1
        assert result["dislike_count"] == 0
        assert result["user_status"] == "liked"
    
    async def test_dislike_video_new_dislike(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test disliking a video for the first time."""
        service = VideoLikesService(db_session)
        
        result = await service.dislike_video(test_video.id, test_user.id)
        
        assert result is not None
        assert result["action"] == "disliked"
        assert result["like_count"] == 0
        assert result["dislike_count"] == 1
        assert result["user_status"] == "disliked"
    
    async def test_dislike_video_remove_existing_dislike(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test removing an existing dislike."""
        service = VideoLikesService(db_session)
        
        # First dislike the video
        await service.dislike_video(test_video.id, test_user.id)
        
        # Dislike again to remove
        result = await service.dislike_video(test_video.id, test_user.id)
        
        assert result is not None
        assert result["action"] == "removed_dislike"
        assert result["like_count"] == 0
        assert result["dislike_count"] == 0
        assert result["user_status"] is None
    
    async def test_dislike_video_change_from_like(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test changing from like to dislike."""
        service = VideoLikesService(db_session)
        
        # First like the video
        await service.like_video(test_video.id, test_user.id)
        
        # Then dislike it
        result = await service.dislike_video(test_video.id, test_user.id)
        
        assert result is not None
        assert result["action"] == "changed_to_dislike"
        assert result["like_count"] == 0
        assert result["dislike_count"] == 1
        assert result["user_status"] == "disliked"
    
    async def test_remove_like_dislike_existing(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test removing an existing like/dislike."""
        service = VideoLikesService(db_session)
        
        # First like the video
        await service.like_video(test_video.id, test_user.id)
        
        # Remove the like
        result = await service.remove_like_dislike(test_video.id, test_user.id)
        
        assert result is not None
        assert result["action"] == "removed"
        assert result["like_count"] == 0
        assert result["dislike_count"] == 0
        assert result["user_status"] is None
    
    async def test_remove_like_dislike_none_existing(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test removing like/dislike when none exists."""
        service = VideoLikesService(db_session)
        
        result = await service.remove_like_dislike(test_video.id, test_user.id)
        
        assert result is not None
        assert result["action"] == "no_change"
        assert result["like_count"] == 0
        assert result["dislike_count"] == 0
        assert result["user_status"] is None
    
    async def test_get_video_likes_counts(self, db_session: AsyncSession, test_video: Video, test_user: User, another_user: User):
        """Test getting like/dislike counts for a video."""
        service = VideoLikesService(db_session)
        
        # Add some likes and dislikes
        await service.like_video(test_video.id, test_user.id)
        await service.dislike_video(test_video.id, another_user.id)
        
        result = await service.get_video_likes(test_video.id)
        
        assert result is not None
        assert result["video_id"] == str(test_video.id)
        assert result["like_count"] == 1
        assert result["dislike_count"] == 1
    
    async def test_get_video_likes_nonexistent_video(self, db_session: AsyncSession):
        """Test getting likes for a nonexistent video."""
        service = VideoLikesService(db_session)
        
        fake_video_id = uuid.uuid4()
        result = await service.get_video_likes(fake_video_id)
        
        assert result is None
    
    async def test_get_user_like_status_liked(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test getting user like status when user has liked."""
        service = VideoLikesService(db_session)
        
        # Like the video
        await service.like_video(test_video.id, test_user.id)
        
        result = await service.get_user_like_status(test_video.id, test_user.id)
        
        assert result["video_id"] == str(test_video.id)
        assert result["user_status"] == "liked"
    
    async def test_get_user_like_status_disliked(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test getting user like status when user has disliked."""
        service = VideoLikesService(db_session)
        
        # Dislike the video
        await service.dislike_video(test_video.id, test_user.id)
        
        result = await service.get_user_like_status(test_video.id, test_user.id)
        
        assert result["video_id"] == str(test_video.id)
        assert result["user_status"] == "disliked"
    
    async def test_get_user_like_status_none(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test getting user like status when user has no preference."""
        service = VideoLikesService(db_session)
        
        result = await service.get_user_like_status(test_video.id, test_user.id)
        
        assert result["video_id"] == str(test_video.id)
        assert result["user_status"] is None
    
    async def test_multiple_users_like_same_video(self, db_session: AsyncSession, test_video: Video, test_user: User, another_user: User):
        """Test multiple users liking the same video."""
        service = VideoLikesService(db_session)
        
        # Both users like the video
        await service.like_video(test_video.id, test_user.id)
        result = await service.like_video(test_video.id, another_user.id)
        
        assert result["like_count"] == 2
        assert result["dislike_count"] == 0
    
    async def test_duplicate_vote_prevention(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test that duplicate votes are prevented by database constraint."""
        service = VideoLikesService(db_session)
        
        # Like the video
        await service.like_video(test_video.id, test_user.id)
        
        # Try to manually create another like (should be prevented by unique constraint)
        duplicate_like = VideoLike(
            video_id=test_video.id,
            user_id=test_user.id,
            is_like=True
        )
        db_session.add(duplicate_like)
        
        with pytest.raises(Exception):  # Should raise integrity error
            await db_session.commit()
    
    async def test_nonexistent_video_operations(self, db_session: AsyncSession, test_user: User):
        """Test operations on nonexistent videos."""
        service = VideoLikesService(db_session)
        fake_video_id = uuid.uuid4()
        
        # All operations should return None for nonexistent videos
        like_result = await service.like_video(fake_video_id, test_user.id)
        dislike_result = await service.dislike_video(fake_video_id, test_user.id)
        remove_result = await service.remove_like_dislike(fake_video_id, test_user.id)
        get_result = await service.get_video_likes(fake_video_id)
        
        assert like_result is None
        assert dislike_result is None
        assert remove_result is None
        assert get_result is None