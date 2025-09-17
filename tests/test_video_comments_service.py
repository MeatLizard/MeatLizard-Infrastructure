"""
Tests for video comments service.
"""
import pytest
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.models import User, Video, VideoComment, VideoStatus, VideoVisibility
from server.web.app.services.video_comments_service import VideoCommentsService

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

class TestVideoCommentsService:
    """Test video comments service functionality."""
    
    async def test_create_comment_success(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test creating a comment successfully."""
        service = VideoCommentsService(db_session)
        
        result = await service.create_comment(
            video_id=test_video.id,
            user_id=test_user.id,
            content="This is a test comment"
        )
        
        assert result is not None
        assert result["content"] == "This is a test comment"
        assert result["user_name"] == test_user.display_label
        assert result["parent_comment_id"] is None
        assert result["reply_count"] == 0
    
    async def test_create_comment_nonexistent_video(self, db_session: AsyncSession, test_user: User):
        """Test creating a comment on a nonexistent video."""
        service = VideoCommentsService(db_session)
        fake_video_id = uuid.uuid4()
        
        result = await service.create_comment(
            video_id=fake_video_id,
            user_id=test_user.id,
            content="This is a test comment"
        )
        
        assert result is None
    
    async def test_create_comment_empty_content(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test creating a comment with empty content."""
        service = VideoCommentsService(db_session)
        
        result = await service.create_comment(
            video_id=test_video.id,
            user_id=test_user.id,
            content=""
        )
        
        assert result is not None
        assert result["error"] == "invalid_content"
    
    async def test_create_reply_comment(self, db_session: AsyncSession, test_video: Video, test_user: User, another_user: User):
        """Test creating a reply to a comment."""
        service = VideoCommentsService(db_session)
        
        # Create parent comment
        parent_result = await service.create_comment(
            video_id=test_video.id,
            user_id=test_user.id,
            content="Parent comment"
        )
        parent_comment_id = uuid.UUID(parent_result["id"])
        
        # Create reply
        reply_result = await service.create_comment(
            video_id=test_video.id,
            user_id=another_user.id,
            content="Reply comment",
            parent_comment_id=parent_comment_id
        )
        
        assert reply_result is not None
        assert reply_result["content"] == "Reply comment"
        assert reply_result["parent_comment_id"] == str(parent_comment_id)
        assert reply_result["user_name"] == another_user.display_label
    
    async def test_create_reply_nonexistent_parent(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test creating a reply to a nonexistent parent comment."""
        service = VideoCommentsService(db_session)
        fake_parent_id = uuid.uuid4()
        
        result = await service.create_comment(
            video_id=test_video.id,
            user_id=test_user.id,
            content="Reply comment",
            parent_comment_id=fake_parent_id
        )
        
        assert result is None
    
    async def test_get_video_comments_empty(self, db_session: AsyncSession, test_video: Video):
        """Test getting comments for a video with no comments."""
        service = VideoCommentsService(db_session)
        
        result = await service.get_video_comments(test_video.id)
        
        assert result is not None
        assert result["comments"] == []
        assert result["pagination"]["total"] == 0
    
    async def test_get_video_comments_with_data(self, db_session: AsyncSession, test_video: Video, test_user: User, another_user: User):
        """Test getting comments for a video with comments."""
        service = VideoCommentsService(db_session)
        
        # Create some comments
        await service.create_comment(test_video.id, test_user.id, "First comment")
        await service.create_comment(test_video.id, another_user.id, "Second comment")
        
        result = await service.get_video_comments(test_video.id)
        
        assert result is not None
        assert len(result["comments"]) == 2
        assert result["pagination"]["total"] == 2
        assert result["comments"][0]["content"] == "Second comment"  # Newest first
        assert result["comments"][1]["content"] == "First comment"
    
    async def test_get_video_comments_pagination(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test comment pagination."""
        service = VideoCommentsService(db_session)
        
        # Create multiple comments
        for i in range(5):
            await service.create_comment(test_video.id, test_user.id, f"Comment {i}")
        
        # Get first page
        result = await service.get_video_comments(test_video.id, page=1, limit=3)
        
        assert result is not None
        assert len(result["comments"]) == 3
        assert result["pagination"]["total"] == 5
        assert result["pagination"]["pages"] == 2
        
        # Get second page
        result2 = await service.get_video_comments(test_video.id, page=2, limit=3)
        
        assert result2 is not None
        assert len(result2["comments"]) == 2
    
    async def test_get_video_comments_sorting(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test comment sorting options."""
        service = VideoCommentsService(db_session)
        
        # Create comments with slight delay to ensure different timestamps
        comment1 = await service.create_comment(test_video.id, test_user.id, "First comment")
        comment2 = await service.create_comment(test_video.id, test_user.id, "Second comment")
        
        # Test newest first (default)
        result_newest = await service.get_video_comments(test_video.id, sort_by="newest")
        assert result_newest["comments"][0]["content"] == "Second comment"
        
        # Test oldest first
        result_oldest = await service.get_video_comments(test_video.id, sort_by="oldest")
        assert result_oldest["comments"][0]["content"] == "First comment"
    
    async def test_get_comment_replies(self, db_session: AsyncSession, test_video: Video, test_user: User, another_user: User):
        """Test getting replies to a comment."""
        service = VideoCommentsService(db_session)
        
        # Create parent comment
        parent_result = await service.create_comment(test_video.id, test_user.id, "Parent comment")
        parent_comment_id = uuid.UUID(parent_result["id"])
        
        # Create replies
        await service.create_comment(test_video.id, another_user.id, "Reply 1", parent_comment_id)
        await service.create_comment(test_video.id, test_user.id, "Reply 2", parent_comment_id)
        
        result = await service.get_comment_replies(test_video.id, parent_comment_id)
        
        assert result is not None
        assert len(result["replies"]) == 2
        assert result["parent_comment_id"] == str(parent_comment_id)
        assert result["replies"][0]["content"] == "Reply 1"  # Oldest first for replies
        assert result["replies"][1]["content"] == "Reply 2"
    
    async def test_update_comment_success(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test updating a comment successfully."""
        service = VideoCommentsService(db_session)
        
        # Create comment
        comment_result = await service.create_comment(test_video.id, test_user.id, "Original content")
        comment_id = uuid.UUID(comment_result["id"])
        
        # Update comment
        update_result = await service.update_comment(
            video_id=test_video.id,
            comment_id=comment_id,
            user_id=test_user.id,
            content="Updated content"
        )
        
        assert update_result is not None
        assert update_result["content"] == "Updated content"
        assert "error" not in update_result
    
    async def test_update_comment_unauthorized(self, db_session: AsyncSession, test_video: Video, test_user: User, another_user: User):
        """Test updating a comment by a different user."""
        service = VideoCommentsService(db_session)
        
        # Create comment
        comment_result = await service.create_comment(test_video.id, test_user.id, "Original content")
        comment_id = uuid.UUID(comment_result["id"])
        
        # Try to update as different user
        update_result = await service.update_comment(
            video_id=test_video.id,
            comment_id=comment_id,
            user_id=another_user.id,
            content="Updated content"
        )
        
        assert update_result is not None
        assert update_result["error"] == "unauthorized"
    
    async def test_delete_comment_success(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test deleting a comment successfully."""
        service = VideoCommentsService(db_session)
        
        # Create comment
        comment_result = await service.create_comment(test_video.id, test_user.id, "To be deleted")
        comment_id = uuid.UUID(comment_result["id"])
        
        # Delete comment
        delete_result = await service.delete_comment(
            video_id=test_video.id,
            comment_id=comment_id,
            user_id=test_user.id
        )
        
        assert delete_result is not None
        assert delete_result["deleted"] is True
        assert "error" not in delete_result
        
        # Verify comment is soft deleted (not visible in listings)
        comments_result = await service.get_video_comments(test_video.id)
        assert len(comments_result["comments"]) == 0
    
    async def test_delete_comment_unauthorized(self, db_session: AsyncSession, test_video: Video, test_user: User, another_user: User):
        """Test deleting a comment by a different user."""
        service = VideoCommentsService(db_session)
        
        # Create comment
        comment_result = await service.create_comment(test_video.id, test_user.id, "To be deleted")
        comment_id = uuid.UUID(comment_result["id"])
        
        # Try to delete as different user
        delete_result = await service.delete_comment(
            video_id=test_video.id,
            comment_id=comment_id,
            user_id=another_user.id
        )
        
        assert delete_result is not None
        assert delete_result["error"] == "unauthorized"
    
    async def test_get_comment_stats(self, db_session: AsyncSession, test_video: Video, test_user: User, another_user: User):
        """Test getting comment statistics."""
        service = VideoCommentsService(db_session)
        
        # Create comments and replies
        parent_result = await service.create_comment(test_video.id, test_user.id, "Parent comment")
        parent_comment_id = uuid.UUID(parent_result["id"])
        
        await service.create_comment(test_video.id, another_user.id, "Another parent comment")
        await service.create_comment(test_video.id, test_user.id, "Reply", parent_comment_id)
        
        result = await service.get_comment_stats(test_video.id)
        
        assert result is not None
        assert result["video_id"] == str(test_video.id)
        assert result["total_comments"] == 3
        assert result["top_level_comments"] == 2
        assert result["replies"] == 1
    
    async def test_content_moderation_excessive_repetition(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test content moderation for excessive repetition."""
        service = VideoCommentsService(db_session)
        
        # Create comment with excessive repetition
        repetitive_content = "spam spam spam spam spam spam spam"
        
        result = await service.create_comment(
            video_id=test_video.id,
            user_id=test_user.id,
            content=repetitive_content
        )
        
        assert result is not None
        assert result["error"] == "moderation_failed"
        assert "repetition" in result["message"].lower()
    
    async def test_content_moderation_excessive_caps(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test content moderation for excessive capitalization."""
        service = VideoCommentsService(db_session)
        
        # Create comment with excessive caps
        caps_content = "THIS IS ALL CAPS AND VERY ANNOYING"
        
        result = await service.create_comment(
            video_id=test_video.id,
            user_id=test_user.id,
            content=caps_content
        )
        
        assert result is not None
        assert result["error"] == "moderation_failed"
        assert "capitalization" in result["message"].lower()
    
    async def test_content_cleaning(self, db_session: AsyncSession, test_video: Video, test_user: User):
        """Test content cleaning functionality."""
        service = VideoCommentsService(db_session)
        
        # Test HTML tag removal
        content_with_html = "This is a <script>alert('xss')</script> comment"
        
        result = await service.create_comment(
            video_id=test_video.id,
            user_id=test_user.id,
            content=content_with_html
        )
        
        assert result is not None
        assert "<script>" not in result["content"]
        assert "alert('xss')" in result["content"]  # Content should remain but tags removed
    
    async def test_nonexistent_video_operations(self, db_session: AsyncSession, test_user: User):
        """Test operations on nonexistent videos."""
        service = VideoCommentsService(db_session)
        fake_video_id = uuid.uuid4()
        
        # All operations should return None for nonexistent videos
        create_result = await service.create_comment(fake_video_id, test_user.id, "Test")
        get_result = await service.get_video_comments(fake_video_id)
        stats_result = await service.get_comment_stats(fake_video_id)
        
        assert create_result is None
        assert get_result is None
        assert stats_result is None