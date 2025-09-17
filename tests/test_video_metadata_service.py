"""
Comprehensive unit tests for VideoMetadataService.
"""
import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from pydantic import ValidationError

from server.web.app.services.video_metadata_service import (
    VideoMetadataService,
    VideoMetadataInput,
    VideoMetadataUpdate,
    VideoMetadataResponse,
    TagSuggestion
)
from server.web.app.models import Video, User, VideoVisibility


@pytest.fixture
async def mock_db():
    """Mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_cache_service():
    """Mock cache service."""
    cache_service = MagicMock()
    cache_service.get_video_metadata = AsyncMock(return_value=None)
    cache_service.set_video_metadata = AsyncMock()
    cache_service.invalidate_video_metadata = AsyncMock()
    return cache_service


@pytest.fixture
async def metadata_service(mock_db, mock_cache_service):
    """Create VideoMetadataService with mocked dependencies."""
    return VideoMetadataService(mock_db, mock_cache_service)


@pytest.fixture
def sample_video():
    """Sample video for testing."""
    return Video(
        id=str(uuid.uuid4()),
        creator_id=str(uuid.uuid4()),
        title="Test Video",
        description="A test video description",
        tags=["test", "video", "sample"],
        visibility=VideoVisibility.public,
        duration_seconds=120,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def sample_user():
    """Sample user for testing."""
    return User(
        id=str(uuid.uuid4()),
        display_label="Test User"
    )


@pytest.fixture
def sample_metadata_input():
    """Sample metadata input for testing."""
    return VideoMetadataInput(
        title="Updated Video Title",
        description="Updated video description",
        tags=["updated", "test", "video"]
    )


class TestVideoMetadataInput:
    """Test cases for VideoMetadataInput model."""
    
    def test_valid_metadata_input(self):
        """Test valid metadata input creation."""
        metadata = VideoMetadataInput(
            title="Test Video",
            description="A test video",
            tags=["test", "video"]
        )
        
        assert metadata.title == "Test Video"
        assert metadata.description == "A test video"
        assert metadata.tags == ["test", "video"]
    
    def test_title_validation_empty(self):
        """Test title validation with empty title."""
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadataInput(title="", description="Test")
        
        assert "Title is required" in str(exc_info.value)
    
    def test_title_validation_too_long(self):
        """Test title validation with title too long."""
        long_title = "x" * 101  # 101 characters
        
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadataInput(title=long_title, description="Test")
        
        assert "Title must be 100 characters or less" in str(exc_info.value)
    
    def test_title_validation_whitespace_trimmed(self):
        """Test title validation trims whitespace."""
        metadata = VideoMetadataInput(title="  Test Video  ", description="Test")
        
        assert metadata.title == "Test Video"
    
    def test_description_validation_too_long(self):
        """Test description validation with description too long."""
        long_description = "x" * 5001  # 5001 characters
        
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadataInput(title="Test", description=long_description)
        
        assert "Description must be 5000 characters or less" in str(exc_info.value)
    
    def test_description_validation_empty_becomes_none(self):
        """Test description validation converts empty string to None."""
        metadata = VideoMetadataInput(title="Test", description="   ")
        
        assert metadata.description is None
    
    def test_tags_validation_too_many(self):
        """Test tags validation with too many tags."""
        many_tags = [f"tag{i}" for i in range(25)]  # 25 tags
        
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadataInput(title="Test", tags=many_tags)
        
        assert "Maximum 20 tags allowed" in str(exc_info.value)
    
    def test_tags_validation_normalization(self):
        """Test tags validation normalizes tags."""
        metadata = VideoMetadataInput(
            title="Test",
            tags=["Test Tag", "UPPERCASE", "special@chars!", "  whitespace  ", "duplicate", "duplicate"]
        )
        
        # Should normalize and deduplicate
        assert "testtag" in metadata.tags
        assert "uppercase" in metadata.tags
        assert "specialchars" in metadata.tags
        assert "whitespace" in metadata.tags
        assert metadata.tags.count("duplicate") == 1
    
    def test_tags_validation_filters_invalid(self):
        """Test tags validation filters out invalid tags."""
        metadata = VideoMetadataInput(
            title="Test",
            tags=["valid", "x", "", "  ", "toolongtagnamethatisinvalid" * 2]
        )
        
        # Should only keep valid tags
        assert "valid" in metadata.tags
        assert "x" not in metadata.tags  # Too short
        assert "" not in metadata.tags
        assert "  " not in metadata.tags
    
    def test_normalize_tag_valid(self):
        """Test tag normalization with valid tag."""
        result = VideoMetadataInput._normalize_tag("Test Tag")
        assert result == "testtag"
    
    def test_normalize_tag_with_special_chars(self):
        """Test tag normalization removes special characters."""
        result = VideoMetadataInput._normalize_tag("test@tag#123!")
        assert result == "testtag123"
    
    def test_normalize_tag_preserves_hyphens_underscores(self):
        """Test tag normalization preserves hyphens and underscores."""
        result = VideoMetadataInput._normalize_tag("test-tag_name")
        assert result == "test-tag_name"
    
    def test_normalize_tag_too_short(self):
        """Test tag normalization rejects too short tags."""
        result = VideoMetadataInput._normalize_tag("x")
        assert result is None
    
    def test_normalize_tag_too_long(self):
        """Test tag normalization rejects too long tags."""
        long_tag = "x" * 31  # 31 characters
        result = VideoMetadataInput._normalize_tag(long_tag)
        assert result is None
    
    def test_normalize_tag_empty(self):
        """Test tag normalization with empty tag."""
        result = VideoMetadataInput._normalize_tag("")
        assert result is None
    
    def test_normalize_tag_none(self):
        """Test tag normalization with None."""
        result = VideoMetadataInput._normalize_tag(None)
        assert result is None


class TestVideoMetadataUpdate:
    """Test cases for VideoMetadataUpdate model."""
    
    def test_valid_metadata_update(self):
        """Test valid metadata update creation."""
        update = VideoMetadataUpdate(
            title="Updated Title",
            description="Updated description",
            tags=["updated", "tags"]
        )
        
        assert update.title == "Updated Title"
        assert update.description == "Updated description"
        assert update.tags == ["updated", "tags"]
    
    def test_partial_metadata_update(self):
        """Test partial metadata update."""
        update = VideoMetadataUpdate(title="Updated Title")
        
        assert update.title == "Updated Title"
        assert update.description is None
        assert update.tags is None
    
    def test_title_validation_empty(self):
        """Test title validation rejects empty title."""
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadataUpdate(title="")
        
        assert "Title cannot be empty" in str(exc_info.value)
    
    def test_title_validation_too_long(self):
        """Test title validation rejects too long title."""
        long_title = "x" * 101
        
        with pytest.raises(ValidationError) as exc_info:
            VideoMetadataUpdate(title=long_title)
        
        assert "Title must be 100 characters or less" in str(exc_info.value)


class TestVideoMetadataService:
    """Test cases for VideoMetadataService."""
    
    async def test_create_metadata_success(self, metadata_service, mock_db, sample_video, sample_user, sample_metadata_input):
        """Test successful metadata creation."""
        mock_db.get.side_effect = [sample_video, sample_user]
        
        result = await metadata_service.create_metadata(
            sample_video.id, sample_metadata_input, str(sample_video.creator_id)
        )
        
        # Verify metadata updated
        assert sample_video.title == sample_metadata_input.title
        assert sample_video.description == sample_metadata_input.description
        assert sample_video.tags == sample_metadata_input.tags
        
        # Verify response
        assert isinstance(result, VideoMetadataResponse)
        assert result.title == sample_metadata_input.title
        assert result.description == sample_metadata_input.description
        assert result.tags == sample_metadata_input.tags
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    async def test_create_metadata_video_not_found(self, metadata_service, mock_db, sample_metadata_input):
        """Test metadata creation for non-existent video."""
        mock_db.get.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await metadata_service.create_metadata("non-existent", sample_metadata_input, "user-id")
        
        assert exc_info.value.status_code == 404
        assert "Video not found" in str(exc_info.value.detail)
    
    async def test_create_metadata_unauthorized(self, metadata_service, mock_db, sample_video, sample_metadata_input):
        """Test metadata creation by unauthorized user."""
        mock_db.get.return_value = sample_video
        
        with pytest.raises(HTTPException) as exc_info:
            await metadata_service.create_metadata(
                sample_video.id, sample_metadata_input, "different-user-id"
            )
        
        assert exc_info.value.status_code == 403
        assert "Not authorized" in str(exc_info.value.detail)
    
    async def test_create_metadata_with_cache_invalidation(self, metadata_service, mock_db, mock_cache_service, 
                                                         sample_video, sample_user, sample_metadata_input):
        """Test metadata creation invalidates cache."""
        mock_db.get.side_effect = [sample_video, sample_user]
        
        await metadata_service.create_metadata(
            sample_video.id, sample_metadata_input, str(sample_video.creator_id)
        )
        
        # Verify cache invalidation
        mock_cache_service.invalidate_video_metadata.assert_called_once_with(sample_video.id)
    
    async def test_update_metadata_success(self, metadata_service, mock_db, sample_video, sample_user):
        """Test successful metadata update."""
        mock_db.get.side_effect = [sample_video, sample_user]
        
        update = VideoMetadataUpdate(
            title="New Title",
            description="New description"
        )
        
        result = await metadata_service.update_metadata(
            sample_video.id, update, str(sample_video.creator_id)
        )
        
        # Verify partial update
        assert sample_video.title == "New Title"
        assert sample_video.description == "New description"
        assert sample_video.tags == ["test", "video", "sample"]  # Unchanged
        
        # Verify response
        assert result.title == "New Title"
        assert result.description == "New description"
    
    async def test_update_metadata_video_not_found(self, metadata_service, mock_db):
        """Test metadata update for non-existent video."""
        mock_db.get.return_value = None
        
        update = VideoMetadataUpdate(title="New Title")
        
        with pytest.raises(HTTPException) as exc_info:
            await metadata_service.update_metadata("non-existent", update, "user-id")
        
        assert exc_info.value.status_code == 404
        assert "Video not found" in str(exc_info.value.detail)
    
    async def test_update_metadata_unauthorized(self, metadata_service, mock_db, sample_video):
        """Test metadata update by unauthorized user."""
        mock_db.get.return_value = sample_video
        
        update = VideoMetadataUpdate(title="New Title")
        
        with pytest.raises(HTTPException) as exc_info:
            await metadata_service.update_metadata(sample_video.id, update, "different-user-id")
        
        assert exc_info.value.status_code == 403
        assert "Not authorized" in str(exc_info.value.detail)
    
    async def test_get_metadata_from_cache(self, metadata_service, mock_cache_service):
        """Test metadata retrieval from cache."""
        cached_data = {
            'id': 'test-video-id',
            'title': 'Cached Video',
            'description': 'Cached description',
            'tags': ['cached', 'tags'],
            'visibility': 'public',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'creator': {
                'id': 'creator-id',
                'name': 'Creator Name'
            }
        }
        mock_cache_service.get_video_metadata.return_value = cached_data
        
        result = await metadata_service.get_metadata('test-video-id')
        
        # Verify cached data used
        assert result.title == 'Cached Video'
        assert result.description == 'Cached description'
        assert result.tags == ['cached', 'tags']
        
        # Verify cache was checked
        mock_cache_service.get_video_metadata.assert_called_once_with('test-video-id')
    
    async def test_get_metadata_from_database(self, metadata_service, mock_db, mock_cache_service, 
                                            sample_video, sample_user):
        """Test metadata retrieval from database when not cached."""
        mock_cache_service.get_video_metadata.return_value = None
        
        # Mock database query result
        mock_result = MagicMock()
        mock_result.first.return_value = (sample_video, sample_user)
        mock_db.execute.return_value = mock_result
        
        result = await metadata_service.get_metadata(sample_video.id)
        
        # Verify database query result
        assert result.title == sample_video.title
        assert result.description == sample_video.description
        assert result.tags == sample_video.tags
        assert result.creator_name == sample_user.display_label
        
        # Verify cache was set
        mock_cache_service.set_video_metadata.assert_called_once()
    
    async def test_get_metadata_video_not_found(self, metadata_service, mock_db, mock_cache_service):
        """Test metadata retrieval for non-existent video."""
        mock_cache_service.get_video_metadata.return_value = None
        
        # Mock database query returning no results
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(HTTPException) as exc_info:
            await metadata_service.get_metadata("non-existent")
        
        assert exc_info.value.status_code == 404
        assert "Video not found" in str(exc_info.value.detail)
    
    async def test_get_metadata_private_video_unauthorized(self, metadata_service, mock_cache_service):
        """Test metadata retrieval for private video by unauthorized user."""
        cached_data = {
            'id': 'test-video-id',
            'title': 'Private Video',
            'visibility': 'private',
            'creator': {'id': 'creator-id'}
        }
        mock_cache_service.get_video_metadata.return_value = cached_data
        
        with pytest.raises(HTTPException) as exc_info:
            await metadata_service.get_metadata('test-video-id', 'different-user-id')
        
        assert exc_info.value.status_code == 403
        assert "Not authorized" in str(exc_info.value.detail)
    
    async def test_get_user_videos_metadata(self, metadata_service, mock_db, sample_video, sample_user):
        """Test retrieval of user's videos metadata."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.all.return_value = [(sample_video, sample_user)]
        mock_db.execute.return_value = mock_result
        
        result = await metadata_service.get_user_videos_metadata(str(sample_user.id))
        
        # Verify results
        assert len(result) == 1
        assert result[0].title == sample_video.title
        assert result[0].creator_name == sample_user.display_label
    
    async def test_search_videos_by_metadata(self, metadata_service, mock_db, sample_video, sample_user):
        """Test video search by metadata."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.all.return_value = [(sample_video, sample_user)]
        mock_db.execute.return_value = mock_result
        
        result = await metadata_service.search_videos_by_metadata(
            query="test",
            tags=["video"],
            limit=10
        )
        
        # Verify results
        assert len(result) == 1
        assert result[0].title == sample_video.title
    
    async def test_get_popular_tags(self, metadata_service, mock_db):
        """Test retrieval of popular tags."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([
            (["tag1", "tag2"],),
            (["tag1", "tag3"],),
            (["tag2", "tag3"],)
        ])
        mock_db.execute.return_value = mock_result
        
        result = await metadata_service.get_popular_tags(limit=5)
        
        # Verify tag counts
        assert len(result) >= 1
        assert all(isinstance(tag, TagSuggestion) for tag in result)
        
        # Should be sorted by usage count
        if len(result) > 1:
            assert result[0].usage_count >= result[1].usage_count
    
    async def test_get_related_tags(self, metadata_service, mock_db):
        """Test retrieval of related tags."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([
            (["target", "related1", "related2"],),
            (["target", "related1", "related3"],),
            (["target", "related2", "related3"],)
        ])
        mock_db.execute.return_value = mock_result
        
        result = await metadata_service.get_related_tags("target", limit=5)
        
        # Verify related tags (should not include target tag)
        assert "target" not in result
        assert len(result) >= 1
        assert all(isinstance(tag, str) for tag in result)
    
    def test_parse_tags_from_string(self, metadata_service):
        """Test parsing tags from comma-separated string."""
        tags_string = "tag1, Tag2, SPECIAL@CHARS!, duplicate, duplicate"
        
        result = metadata_service.parse_tags_from_string(tags_string)
        
        # Verify parsing and normalization
        assert "tag1" in result
        assert "tag2" in result
        assert "specialchars" in result
        assert result.count("duplicate") == 1
    
    def test_parse_tags_from_empty_string(self, metadata_service):
        """Test parsing tags from empty string."""
        result = metadata_service.parse_tags_from_string("")
        assert result == []
        
        result = metadata_service.parse_tags_from_string(None)
        assert result == []
    
    def test_validate_metadata_input_success(self, metadata_service):
        """Test successful metadata input validation."""
        metadata_dict = {
            "title": "Test Video",
            "description": "Test description",
            "tags": ["test", "video"]
        }
        
        result = metadata_service.validate_metadata_input(metadata_dict)
        
        assert isinstance(result, VideoMetadataInput)
        assert result.title == "Test Video"
        assert result.description == "Test description"
        assert result.tags == ["test", "video"]
    
    def test_validate_metadata_input_error(self, metadata_service):
        """Test metadata input validation with error."""
        metadata_dict = {
            "title": "",  # Invalid empty title
            "description": "Test description"
        }
        
        with pytest.raises(HTTPException) as exc_info:
            metadata_service.validate_metadata_input(metadata_dict)
        
        assert exc_info.value.status_code == 400
    
    async def test_bulk_update_tags_success(self, metadata_service, mock_db):
        """Test successful bulk tag update."""
        # Create sample videos
        video1 = Video(id="video1", creator_id="user1", tags=["old1", "old2"])
        video2 = Video(id="video2", creator_id="user1", tags=["old2", "old3"])
        
        mock_db.get.side_effect = [video1, video2]
        
        result = await metadata_service.bulk_update_tags(
            video_ids=["video1", "video2"],
            tags_to_add=["new1", "new2"],
            tags_to_remove=["old1"],
            user_id="user1"
        )
        
        # Verify updates
        assert result == 2
        assert "new1" in video1.tags
        assert "new2" in video1.tags
        assert "old1" not in video1.tags
        assert "old2" in video1.tags  # Should remain
        
        # Verify database commit
        mock_db.commit.assert_called_once()
    
    async def test_bulk_update_tags_unauthorized(self, metadata_service, mock_db):
        """Test bulk tag update with unauthorized videos."""
        # Create video with different owner
        video1 = Video(id="video1", creator_id="different-user", tags=["old1"])
        
        mock_db.get.return_value = video1
        
        result = await metadata_service.bulk_update_tags(
            video_ids=["video1"],
            tags_to_add=["new1"],
            tags_to_remove=[],
            user_id="user1"
        )
        
        # Should skip unauthorized videos
        assert result == 0
        assert "new1" not in video1.tags
    
    async def test_bulk_update_tags_nonexistent_video(self, metadata_service, mock_db):
        """Test bulk tag update with non-existent video."""
        mock_db.get.return_value = None
        
        result = await metadata_service.bulk_update_tags(
            video_ids=["nonexistent"],
            tags_to_add=["new1"],
            tags_to_remove=[],
            user_id="user1"
        )
        
        # Should skip non-existent videos
        assert result == 0


class TestVideoMetadataResponse:
    """Test cases for VideoMetadataResponse model."""
    
    def test_video_metadata_response_creation(self):
        """Test VideoMetadataResponse creation."""
        response = VideoMetadataResponse(
            video_id="test-video-id",
            title="Test Video",
            description="Test description",
            tags=["test", "video"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            creator_id="creator-id",
            creator_name="Creator Name"
        )
        
        assert response.video_id == "test-video-id"
        assert response.title == "Test Video"
        assert response.description == "Test description"
        assert response.tags == ["test", "video"]
        assert response.creator_id == "creator-id"
        assert response.creator_name == "Creator Name"


class TestTagSuggestion:
    """Test cases for TagSuggestion model."""
    
    def test_tag_suggestion_creation(self):
        """Test TagSuggestion creation."""
        suggestion = TagSuggestion(
            tag="test",
            usage_count=10,
            related_tags=["video", "sample"]
        )
        
        assert suggestion.tag == "test"
        assert suggestion.usage_count == 10
        assert suggestion.related_tags == ["video", "sample"]
    
    def test_tag_suggestion_defaults(self):
        """Test TagSuggestion with default values."""
        suggestion = TagSuggestion(tag="test", usage_count=5)
        
        assert suggestion.related_tags == []


if __name__ == "__main__":
    pytest.main([__file__])