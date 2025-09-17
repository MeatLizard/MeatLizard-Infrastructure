"""
Comprehensive unit tests for ThumbnailService.
"""
import pytest
import asyncio
import os
import tempfile
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from server.web.app.services.thumbnail_service import (
    ThumbnailService,
    ThumbnailInfo,
    ThumbnailRequest,
    ThumbnailResponse,
    ThumbnailSelectionRequest,
    ThumbnailGenerationError
)
from server.web.app.models import Video, VideoStatus


@pytest.fixture
async def mock_db():
    """Mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.get = AsyncMock()
    return db


@pytest.fixture
def mock_s3_service():
    """Mock S3 service."""
    s3_service = MagicMock()
    s3_service.is_available.return_value = False
    s3_service.upload_file_content = AsyncMock()
    s3_service.get_file_url = AsyncMock(return_value="https://cdn.example.com/thumbnail.jpg")
    s3_service.get_file_content = AsyncMock(return_value=b"fake image data")
    s3_service.download_file = AsyncMock()
    s3_service.delete_folder = AsyncMock()
    return s3_service


@pytest.fixture
async def thumbnail_service(mock_db, mock_s3_service):
    """Create ThumbnailService with mocked dependencies."""
    with patch.object(ThumbnailService, '_find_ffmpeg', return_value='ffmpeg'):
        service = ThumbnailService(mock_db)
        service.s3_service = mock_s3_service
        return service


@pytest.fixture
def sample_video():
    """Sample video for testing."""
    return Video(
        id=str(uuid.uuid4()),
        creator_id=str(uuid.uuid4()),
        title="Test Video",
        duration_seconds=120,
        status=VideoStatus.ready,
        original_s3_key="videos/test-video.mp4"
    )


@pytest.fixture
def sample_thumbnail_info():
    """Sample thumbnail info for testing."""
    return ThumbnailInfo(
        timestamp=60.0,
        filename="thumb_02_60_0s.jpg",
        s3_key="thumbnails/test-video/thumb_02_60_0s.jpg",
        local_path="/tmp/thumb_02_60_0s.jpg",
        width=320,
        height=180,
        file_size=15000,
        is_selected=True
    )


class TestThumbnailService:
    """Test cases for ThumbnailService."""
    
    def test_find_ffmpeg_success(self):
        """Test successful FFmpeg detection."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            service = ThumbnailService(AsyncMock())
            assert service.ffmpeg_path == 'ffmpeg'
    
    def test_find_ffmpeg_not_found(self):
        """Test FFmpeg not found error."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="FFmpeg not found"):
                ThumbnailService(AsyncMock())
    
    @patch('os.path.exists')
    @patch('os.makedirs')
    async def test_generate_thumbnails_for_video_success(self, mock_makedirs, mock_exists, 
                                                       thumbnail_service, mock_db, sample_video):
        """Test successful thumbnail generation for video."""
        mock_exists.return_value = True
        mock_db.get.return_value = sample_video
        
        # Mock single thumbnail generation
        mock_thumbnail = ThumbnailInfo(
            timestamp=12.0,
            filename="thumb_00_12_0s.jpg",
            s3_key="thumbnails/test/thumb_00_12_0s.jpg",
            width=320,
            height=180,
            file_size=15000
        )
        
        thumbnail_service._generate_single_thumbnail = AsyncMock(return_value=mock_thumbnail)
        
        result = await thumbnail_service.generate_thumbnails_for_video(
            video_id=sample_video.id,
            video_path="/fake/video.mp4"
        )
        
        # Verify thumbnails generated
        assert len(result) == 5  # Default timestamps
        assert all(isinstance(thumb, ThumbnailInfo) for thumb in result)
        
        # Verify one thumbnail is selected
        selected_count = sum(1 for thumb in result if thumb.is_selected)
        assert selected_count == 1
        
        # Verify database operations
        mock_db.commit.assert_called_once()
    
    async def test_generate_thumbnails_for_video_not_found(self, thumbnail_service, mock_db):
        """Test thumbnail generation for non-existent video."""
        mock_db.get.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await thumbnail_service.generate_thumbnails_for_video("non-existent", "/fake/video.mp4")
        
        assert exc_info.value.status_code == 404
        assert "Video not found" in str(exc_info.value.detail)
    
    @patch('os.path.exists')
    async def test_generate_thumbnails_for_video_file_not_found(self, mock_exists, 
                                                              thumbnail_service, mock_db, sample_video):
        """Test thumbnail generation with video file not found."""
        mock_exists.return_value = False
        mock_db.get.return_value = sample_video
        
        with pytest.raises(ThumbnailGenerationError, match="Video file not found"):
            await thumbnail_service.generate_thumbnails_for_video(
                sample_video.id, "/fake/nonexistent.mp4"
            )
    
    @patch('os.path.exists')
    @patch('os.makedirs')
    async def test_generate_thumbnails_for_video_custom_timestamps(self, mock_makedirs, mock_exists,
                                                                 thumbnail_service, mock_db, sample_video):
        """Test thumbnail generation with custom timestamps."""
        mock_exists.return_value = True
        mock_db.get.return_value = sample_video
        
        custom_timestamps = [10.0, 30.0, 60.0]
        
        # Mock single thumbnail generation
        thumbnail_service._generate_single_thumbnail = AsyncMock(
            side_effect=lambda **kwargs: ThumbnailInfo(
                timestamp=kwargs['timestamp'],
                filename=f"thumb_{kwargs['index']:02d}.jpg",
                s3_key=f"thumbnails/test/thumb_{kwargs['index']:02d}.jpg",
                width=320,
                height=180,
                file_size=15000
            )
        )
        
        result = await thumbnail_service.generate_thumbnails_for_video(
            video_id=sample_video.id,
            video_path="/fake/video.mp4",
            timestamps=custom_timestamps
        )
        
        # Verify custom timestamps used
        assert len(result) == 3
        assert [thumb.timestamp for thumb in result] == custom_timestamps
    
    @patch('os.path.exists')
    @patch('os.makedirs')
    async def test_generate_thumbnails_for_video_all_fail(self, mock_makedirs, mock_exists,
                                                        thumbnail_service, mock_db, sample_video):
        """Test thumbnail generation when all thumbnails fail."""
        mock_exists.return_value = True
        mock_db.get.return_value = sample_video
        
        # Mock all thumbnail generation to fail
        thumbnail_service._generate_single_thumbnail = AsyncMock(
            side_effect=ThumbnailGenerationError("Generation failed")
        )
        
        with pytest.raises(ThumbnailGenerationError, match="Failed to generate any thumbnails"):
            await thumbnail_service.generate_thumbnails_for_video(
                sample_video.id, "/fake/video.mp4"
            )
    
    @patch('os.path.getsize')
    @patch('os.path.exists')
    @patch('asyncio.create_subprocess_exec')
    async def test_generate_single_thumbnail_success(self, mock_subprocess, mock_exists, mock_getsize,
                                                   thumbnail_service):
        """Test successful single thumbnail generation."""
        mock_exists.return_value = True
        mock_getsize.return_value = 15000
        
        # Mock FFmpeg process
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process
        
        result = await thumbnail_service._generate_single_thumbnail(
            video_id="test-video",
            video_path="/fake/video.mp4",
            timestamp=60.0,
            output_dir="/fake/output",
            width=320,
            height=180,
            index=2
        )
        
        # Verify thumbnail info
        assert isinstance(result, ThumbnailInfo)
        assert result.timestamp == 60.0
        assert "thumb_02_60_0s.jpg" in result.filename
        assert result.width == 320
        assert result.height == 180
        assert result.file_size == 15000
    
    @patch('asyncio.create_subprocess_exec')
    async def test_generate_single_thumbnail_ffmpeg_error(self, mock_subprocess, thumbnail_service):
        """Test single thumbnail generation with FFmpeg error."""
        # Mock FFmpeg process failure
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"FFmpeg error")
        mock_subprocess.return_value = mock_process
        
        with pytest.raises(ThumbnailGenerationError, match="Failed to generate thumbnail"):
            await thumbnail_service._generate_single_thumbnail(
                video_id="test-video",
                video_path="/fake/video.mp4",
                timestamp=60.0,
                output_dir="/fake/output",
                width=320,
                height=180,
                index=2
            )
    
    @patch('os.path.exists')
    @patch('asyncio.create_subprocess_exec')
    async def test_generate_single_thumbnail_file_not_created(self, mock_subprocess, mock_exists,
                                                            thumbnail_service):
        """Test single thumbnail generation when output file not created."""
        mock_exists.return_value = False  # Output file doesn't exist
        
        # Mock successful FFmpeg process
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process
        
        with pytest.raises(ThumbnailGenerationError, match="Thumbnail file not created"):
            await thumbnail_service._generate_single_thumbnail(
                video_id="test-video",
                video_path="/fake/video.mp4",
                timestamp=60.0,
                output_dir="/fake/output",
                width=320,
                height=180,
                index=2
            )
    
    @patch('builtins.open', new_callable=mock_open, read_data=b"fake image data")
    async def test_upload_thumbnail_to_s3_success(self, mock_file, thumbnail_service, mock_s3_service):
        """Test successful thumbnail upload to S3."""
        thumbnail_service.s3_service = mock_s3_service
        
        await thumbnail_service._upload_thumbnail_to_s3("/fake/thumbnail.jpg", "thumbnails/test/thumb.jpg")
        
        # Verify S3 upload
        mock_s3_service.upload_file_content.assert_called_once_with(
            content=b"fake image data",
            key="thumbnails/test/thumb.jpg",
            content_type='image/jpeg'
        )
    
    async def test_upload_thumbnail_to_s3_error(self, thumbnail_service, mock_s3_service):
        """Test thumbnail upload to S3 with error."""
        mock_s3_service.upload_file_content.side_effect = Exception("S3 error")
        thumbnail_service.s3_service = mock_s3_service
        
        with pytest.raises(ThumbnailGenerationError, match="Failed to upload thumbnail to S3"):
            await thumbnail_service._upload_thumbnail_to_s3("/fake/thumbnail.jpg", "thumbnails/test/thumb.jpg")
    
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.path.getsize')
    async def test_get_video_thumbnails_success(self, mock_getsize, mock_listdir, mock_exists,
                                              thumbnail_service, mock_db, sample_video):
        """Test successful retrieval of video thumbnails."""
        mock_db.get.return_value = sample_video
        mock_exists.return_value = True
        mock_listdir.return_value = ["thumb_00_12_0s.jpg", "thumb_01_30_0s.jpg", "thumb_02_60_0s.jpg"]
        mock_getsize.return_value = 15000
        
        result = await thumbnail_service.get_video_thumbnails(sample_video.id)
        
        # Verify thumbnails returned
        assert len(result) == 3
        assert all(isinstance(thumb, ThumbnailResponse) for thumb in result)
        assert all(thumb.file_size == 15000 for thumb in result)
    
    async def test_get_video_thumbnails_video_not_found(self, thumbnail_service, mock_db):
        """Test thumbnail retrieval for non-existent video."""
        mock_db.get.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await thumbnail_service.get_video_thumbnails("non-existent")
        
        assert exc_info.value.status_code == 404
        assert "Video not found" in str(exc_info.value.detail)
    
    @patch('os.path.exists')
    async def test_get_video_thumbnails_no_directory(self, mock_exists, thumbnail_service, mock_db, sample_video):
        """Test thumbnail retrieval when no thumbnails directory exists."""
        mock_db.get.return_value = sample_video
        mock_exists.return_value = False
        
        result = await thumbnail_service.get_video_thumbnails(sample_video.id)
        
        # Should return empty list
        assert result == []
    
    def test_extract_timestamp_from_filename_success(self, thumbnail_service):
        """Test successful timestamp extraction from filename."""
        filename = "thumb_02_60_0s.jpg"
        
        result = thumbnail_service._extract_timestamp_from_filename(filename)
        
        assert result == 60.0
    
    def test_extract_timestamp_from_filename_with_decimal(self, thumbnail_service):
        """Test timestamp extraction with decimal value."""
        filename = "thumb_01_30_5s.jpg"
        
        result = thumbnail_service._extract_timestamp_from_filename(filename)
        
        assert result == 30.5
    
    def test_extract_timestamp_from_filename_invalid(self, thumbnail_service):
        """Test timestamp extraction from invalid filename."""
        filename = "invalid_filename.jpg"
        
        result = thumbnail_service._extract_timestamp_from_filename(filename)
        
        assert result == 0.0
    
    async def test_select_thumbnail_success(self, thumbnail_service, mock_db, sample_video):
        """Test successful thumbnail selection."""
        mock_db.get.return_value = sample_video
        
        # Mock get_video_thumbnails
        mock_thumbnails = [
            ThumbnailResponse(
                timestamp=30.0,
                filename="thumb_01_30_0s.jpg",
                url="/api/video/thumbnails/test/thumb_01_30_0s.jpg",
                width=320,
                height=180,
                file_size=15000,
                is_selected=False
            )
        ]
        thumbnail_service.get_video_thumbnails = AsyncMock(return_value=mock_thumbnails)
        
        result = await thumbnail_service.select_thumbnail(
            sample_video.id, 30.0, str(sample_video.creator_id)
        )
        
        # Verify selection
        assert result.is_selected is True
        assert result.timestamp == 30.0
        
        # Verify database update
        assert sample_video.thumbnail_s3_key == f"thumbnails/{sample_video.id}/thumb_01_30_0s.jpg"
        mock_db.commit.assert_called_once()
    
    async def test_select_thumbnail_video_not_found(self, thumbnail_service, mock_db):
        """Test thumbnail selection for non-existent video."""
        mock_db.get.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await thumbnail_service.select_thumbnail("non-existent", 30.0, "user-id")
        
        assert exc_info.value.status_code == 404
        assert "Video not found" in str(exc_info.value.detail)
    
    async def test_select_thumbnail_unauthorized(self, thumbnail_service, mock_db, sample_video):
        """Test thumbnail selection by unauthorized user."""
        mock_db.get.return_value = sample_video
        
        with pytest.raises(HTTPException) as exc_info:
            await thumbnail_service.select_thumbnail(sample_video.id, 30.0, "different-user-id")
        
        assert exc_info.value.status_code == 403
        assert "Not authorized" in str(exc_info.value.detail)
    
    async def test_select_thumbnail_not_found(self, thumbnail_service, mock_db, sample_video):
        """Test thumbnail selection when thumbnail not found."""
        mock_db.get.return_value = sample_video
        
        # Mock empty thumbnails list
        thumbnail_service.get_video_thumbnails = AsyncMock(return_value=[])
        
        with pytest.raises(HTTPException) as exc_info:
            await thumbnail_service.select_thumbnail(
                sample_video.id, 30.0, str(sample_video.creator_id)
            )
        
        assert exc_info.value.status_code == 404
        assert "Thumbnail not found" in str(exc_info.value.detail)
    
    @patch('os.path.exists')
    @patch('os.makedirs')
    async def test_regenerate_thumbnails_success(self, mock_makedirs, mock_exists,
                                               thumbnail_service, mock_db, sample_video):
        """Test successful thumbnail regeneration."""
        mock_db.get.return_value = sample_video
        mock_exists.return_value = True
        
        # Mock methods
        thumbnail_service._clear_existing_thumbnails = AsyncMock()
        thumbnail_service.generate_thumbnails_for_video = AsyncMock(
            return_value=[
                ThumbnailInfo(
                    timestamp=30.0,
                    filename="thumb_00_30_0s.jpg",
                    s3_key="thumbnails/test/thumb_00_30_0s.jpg",
                    width=320,
                    height=180,
                    file_size=15000,
                    is_selected=True
                )
            ]
        )
        
        result = await thumbnail_service.regenerate_thumbnails(
            sample_video.id, str(sample_video.creator_id), [30.0]
        )
        
        # Verify regeneration
        assert len(result) == 1
        assert result[0].timestamp == 30.0
        
        # Verify cleanup called
        thumbnail_service._clear_existing_thumbnails.assert_called_once_with(sample_video.id)
    
    async def test_regenerate_thumbnails_video_not_found(self, thumbnail_service, mock_db):
        """Test thumbnail regeneration for non-existent video."""
        mock_db.get.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await thumbnail_service.regenerate_thumbnails("non-existent", "user-id")
        
        assert exc_info.value.status_code == 404
        assert "Video not found" in str(exc_info.value.detail)
    
    async def test_regenerate_thumbnails_unauthorized(self, thumbnail_service, mock_db, sample_video):
        """Test thumbnail regeneration by unauthorized user."""
        mock_db.get.return_value = sample_video
        
        with pytest.raises(HTTPException) as exc_info:
            await thumbnail_service.regenerate_thumbnails(sample_video.id, "different-user-id")
        
        assert exc_info.value.status_code == 403
        assert "Not authorized" in str(exc_info.value.detail)
    
    @patch('os.path.exists')
    async def test_regenerate_thumbnails_no_video_file(self, mock_exists, thumbnail_service, mock_db, sample_video):
        """Test thumbnail regeneration when video file not found."""
        mock_db.get.return_value = sample_video
        mock_exists.return_value = False
        thumbnail_service.s3_service.is_available.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            await thumbnail_service.regenerate_thumbnails(
                sample_video.id, str(sample_video.creator_id)
            )
        
        assert exc_info.value.status_code == 404
        assert "Original video file not found" in str(exc_info.value.detail)
    
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.remove')
    async def test_clear_existing_thumbnails_local(self, mock_remove, mock_listdir, mock_exists,
                                                 thumbnail_service):
        """Test clearing existing local thumbnails."""
        mock_exists.return_value = True
        mock_listdir.return_value = ["thumb_01.jpg", "thumb_02.jpg"]
        
        await thumbnail_service._clear_existing_thumbnails("test-video")
        
        # Verify files removed
        assert mock_remove.call_count == 2
    
    @patch('os.path.exists')
    async def test_clear_existing_thumbnails_s3(self, mock_exists, thumbnail_service, mock_s3_service):
        """Test clearing existing S3 thumbnails."""
        mock_exists.return_value = False
        mock_s3_service.is_available.return_value = True
        thumbnail_service.s3_service = mock_s3_service
        
        await thumbnail_service._clear_existing_thumbnails("test-video")
        
        # Verify S3 folder deletion
        mock_s3_service.delete_folder.assert_called_once_with("thumbnails/test-video/")
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data=b"fake image data")
    async def test_get_thumbnail_file_local(self, mock_file, mock_exists, thumbnail_service):
        """Test getting thumbnail file from local storage."""
        mock_exists.return_value = True
        
        content, content_type = await thumbnail_service.get_thumbnail_file("test-video", "thumb.jpg")
        
        assert content == b"fake image data"
        assert content_type == "image/jpeg"
    
    @patch('os.path.exists')
    async def test_get_thumbnail_file_s3(self, mock_exists, thumbnail_service, mock_s3_service):
        """Test getting thumbnail file from S3 storage."""
        mock_exists.return_value = False
        mock_s3_service.is_available.return_value = True
        mock_s3_service.get_file_content.return_value = b"s3 image data"
        thumbnail_service.s3_service = mock_s3_service
        
        content, content_type = await thumbnail_service.get_thumbnail_file("test-video", "thumb.jpg")
        
        assert content == b"s3 image data"
        assert content_type == "image/jpeg"
    
    @patch('os.path.exists')
    async def test_get_thumbnail_file_not_found(self, mock_exists, thumbnail_service):
        """Test getting non-existent thumbnail file."""
        mock_exists.return_value = False
        thumbnail_service.s3_service.is_available.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            await thumbnail_service.get_thumbnail_file("test-video", "nonexistent.jpg")
        
        assert exc_info.value.status_code == 404
        assert "Thumbnail not found" in str(exc_info.value.detail)
    
    def test_get_default_thumbnail_timestamps_normal(self, thumbnail_service):
        """Test getting default thumbnail timestamps for normal duration."""
        duration = 120.0  # 2 minutes
        
        timestamps = thumbnail_service.get_default_thumbnail_timestamps(duration)
        
        expected = [12.0, 30.0, 60.0, 90.0, 108.0]  # 10%, 25%, 50%, 75%, 90%
        assert timestamps == expected
    
    def test_get_default_thumbnail_timestamps_short(self, thumbnail_service):
        """Test getting default thumbnail timestamps for short duration."""
        duration = 5.0  # 5 seconds
        
        timestamps = thumbnail_service.get_default_thumbnail_timestamps(duration)
        
        # All timestamps should be within bounds
        assert all(0 <= t <= 4.0 for t in timestamps)  # duration - 1
        assert len(timestamps) == 5
    
    def test_get_default_thumbnail_timestamps_zero(self, thumbnail_service):
        """Test getting default thumbnail timestamps for zero duration."""
        duration = 0.0
        
        timestamps = thumbnail_service.get_default_thumbnail_timestamps(duration)
        
        assert timestamps == [0.0]
    
    async def test_auto_select_best_thumbnail_success(self, thumbnail_service, mock_db, sample_video):
        """Test automatic selection of best thumbnail."""
        mock_db.get.return_value = sample_video
        
        # Mock thumbnails
        mock_thumbnails = [
            ThumbnailResponse(timestamp=12.0, filename="thumb_00.jpg", url="url1", width=320, height=180, file_size=15000, is_selected=False),
            ThumbnailResponse(timestamp=30.0, filename="thumb_01.jpg", url="url2", width=320, height=180, file_size=15000, is_selected=False),
            ThumbnailResponse(timestamp=60.0, filename="thumb_02.jpg", url="url3", width=320, height=180, file_size=15000, is_selected=False)
        ]
        thumbnail_service.get_video_thumbnails = AsyncMock(return_value=mock_thumbnails)
        
        result = await thumbnail_service.auto_select_best_thumbnail(sample_video.id)
        
        # Should select middle thumbnail
        assert result.timestamp == 30.0
        assert result.is_selected is True
        
        # Verify database update
        assert sample_video.thumbnail_s3_key == f"thumbnails/{sample_video.id}/thumb_01.jpg"
        mock_db.commit.assert_called_once()
    
    async def test_auto_select_best_thumbnail_no_thumbnails(self, thumbnail_service):
        """Test automatic selection when no thumbnails exist."""
        thumbnail_service.get_video_thumbnails = AsyncMock(return_value=[])
        
        result = await thumbnail_service.auto_select_best_thumbnail("test-video")
        
        assert result is None


class TestThumbnailInfo:
    """Test cases for ThumbnailInfo dataclass."""
    
    def test_thumbnail_info_creation(self):
        """Test ThumbnailInfo creation."""
        info = ThumbnailInfo(
            timestamp=60.0,
            filename="thumb_02_60_0s.jpg",
            s3_key="thumbnails/test/thumb_02_60_0s.jpg",
            local_path="/tmp/thumb_02_60_0s.jpg",
            width=320,
            height=180,
            file_size=15000,
            is_selected=True
        )
        
        assert info.timestamp == 60.0
        assert info.filename == "thumb_02_60_0s.jpg"
        assert info.s3_key == "thumbnails/test/thumb_02_60_0s.jpg"
        assert info.local_path == "/tmp/thumb_02_60_0s.jpg"
        assert info.width == 320
        assert info.height == 180
        assert info.file_size == 15000
        assert info.is_selected is True
    
    def test_thumbnail_info_defaults(self):
        """Test ThumbnailInfo with default values."""
        info = ThumbnailInfo(
            timestamp=60.0,
            filename="thumb.jpg",
            s3_key="thumbnails/test/thumb.jpg"
        )
        
        assert info.local_path is None
        assert info.width == 0
        assert info.height == 0
        assert info.file_size == 0
        assert info.is_selected is False


class TestThumbnailModels:
    """Test cases for Pydantic models."""
    
    def test_thumbnail_request_creation(self):
        """Test ThumbnailRequest creation."""
        request = ThumbnailRequest(
            timestamps=[10.0, 30.0, 60.0],
            width=640,
            height=360,
            quality=90
        )
        
        assert request.timestamps == [10.0, 30.0, 60.0]
        assert request.width == 640
        assert request.height == 360
        assert request.quality == 90
    
    def test_thumbnail_request_defaults(self):
        """Test ThumbnailRequest with default values."""
        request = ThumbnailRequest(timestamps=[30.0])
        
        assert request.width == 320
        assert request.height == 180
        assert request.quality == 85
    
    def test_thumbnail_response_creation(self):
        """Test ThumbnailResponse creation."""
        response = ThumbnailResponse(
            timestamp=60.0,
            filename="thumb.jpg",
            url="https://example.com/thumb.jpg",
            width=320,
            height=180,
            file_size=15000,
            is_selected=True
        )
        
        assert response.timestamp == 60.0
        assert response.filename == "thumb.jpg"
        assert response.url == "https://example.com/thumb.jpg"
        assert response.width == 320
        assert response.height == 180
        assert response.file_size == 15000
        assert response.is_selected is True
    
    def test_thumbnail_selection_request_creation(self):
        """Test ThumbnailSelectionRequest creation."""
        request = ThumbnailSelectionRequest(selected_timestamp=60.0)
        
        assert request.selected_timestamp == 60.0


class TestThumbnailGenerationError:
    """Test cases for ThumbnailGenerationError exception."""
    
    def test_thumbnail_generation_error_creation(self):
        """Test ThumbnailGenerationError creation."""
        error = ThumbnailGenerationError("Test error message")
        
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


if __name__ == "__main__":
    pytest.main([__file__])