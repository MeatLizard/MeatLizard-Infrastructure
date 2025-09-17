"""
Comprehensive unit tests for VideoUploadService.
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

from server.web.app.services.video_upload_service import (
    VideoUploadService, 
    UploadSession, 
    VideoMetadata, 
    ChunkResult
)
from server.web.app.models import Video, VideoStatus
from server.web.app.services.video_analysis_service import VideoValidationError


@pytest.fixture
async def mock_db():
    """Mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.get = AsyncMock()
    return db


@pytest.fixture
def mock_services():
    """Mock all dependent services."""
    services = {
        'analysis_service': MagicMock(),
        's3_service': MagicMock(),
        'metadata_service': MagicMock(),
        'thumbnail_service': MagicMock(),
        'transcoding_service': MagicMock(),
        'quality_preset_service': MagicMock()
    }
    
    # Configure default behaviors
    services['analysis_service'].validate_file_info = MagicMock()
    services['s3_service'].is_available.return_value = False
    services['s3_service'].generate_video_key.return_value = "videos/test-key.mp4"
    
    return services


@pytest.fixture
async def upload_service(mock_db, mock_services):
    """Create VideoUploadService with mocked dependencies."""
    service = VideoUploadService(mock_db)
    
    # Replace services with mocks
    for service_name, mock_service in mock_services.items():
        setattr(service, service_name, mock_service)
    
    return service


@pytest.fixture
def sample_video_metadata():
    """Sample video metadata for testing."""
    return VideoMetadata(
        title="Test Video",
        description="A test video for unit testing",
        tags=["test", "video", "upload"]
    )


@pytest.fixture
def sample_file_info():
    """Sample file info for testing."""
    return {
        'filename': 'test_video.mp4',
        'size': 1024 * 1024 * 100,  # 100MB
        'total_chunks': 10,
        'mime_type': 'video/mp4'
    }


class TestVideoUploadService:
    """Test cases for VideoUploadService."""
    
    async def test_initiate_upload_success(self, upload_service, mock_db, sample_video_metadata, sample_file_info):
        """Test successful upload initiation."""
        user_id = str(uuid.uuid4())
        
        # Mock video creation
        mock_video = Video(
            id=str(uuid.uuid4()),
            creator_id=user_id,
            title=sample_video_metadata.title,
            status=VideoStatus.uploading
        )
        
        # Call the method
        session = await upload_service.initiate_upload(user_id, sample_video_metadata, sample_file_info)
        
        # Verify session creation
        assert isinstance(session, UploadSession)
        assert session.user_id == user_id
        assert session.metadata['filename'] == sample_file_info['filename']
        assert session.metadata['size'] == sample_file_info['size']
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        
        # Verify session is stored
        assert session.session_id in upload_service.active_sessions
    
    async def test_initiate_upload_validation_error(self, upload_service, sample_video_metadata, sample_file_info):
        """Test upload initiation with validation error."""
        user_id = str(uuid.uuid4())
        
        # Mock validation error
        upload_service.analysis_service.validate_file_info.side_effect = VideoValidationError("Invalid file")
        
        # Call the method and expect exception
        with pytest.raises(HTTPException) as exc_info:
            await upload_service.initiate_upload(user_id, sample_video_metadata, sample_file_info)
        
        assert exc_info.value.status_code == 400
        assert "Invalid file" in str(exc_info.value.detail)
    
    async def test_initiate_upload_with_s3(self, upload_service, mock_db, sample_video_metadata, sample_file_info):
        """Test upload initiation with S3 enabled."""
        user_id = str(uuid.uuid4())
        
        # Enable S3 and mock S3 session
        upload_service.s3_service.is_available.return_value = True
        mock_s3_session = MagicMock()
        upload_service.s3_service.initiate_multipart_upload = AsyncMock(return_value=mock_s3_session)
        
        # Call the method
        session = await upload_service.initiate_upload(user_id, sample_video_metadata, sample_file_info)
        
        # Verify S3 session is set
        assert session.s3_session == mock_s3_session
        upload_service.s3_service.initiate_multipart_upload.assert_called_once()
    
    @patch('os.makedirs')
    async def test_initiate_upload_local_storage(self, mock_makedirs, upload_service, mock_db, 
                                               sample_video_metadata, sample_file_info):
        """Test upload initiation with local storage."""
        user_id = str(uuid.uuid4())
        
        # Disable S3
        upload_service.s3_service.is_available.return_value = False
        
        # Call the method
        session = await upload_service.initiate_upload(user_id, sample_video_metadata, sample_file_info)
        
        # Verify temp file path is set
        assert session.temp_file_path is not None
        assert session.temp_file_path.endswith('.tmp')
        mock_makedirs.assert_called_once()
    
    async def test_process_chunk_success_s3(self, upload_service):
        """Test successful chunk processing with S3."""
        # Create mock session with S3
        session_id = str(uuid.uuid4())
        mock_s3_session = MagicMock()
        session = UploadSession(session_id, str(uuid.uuid4()), str(uuid.uuid4()), {})
        session.s3_session = mock_s3_session
        upload_service.active_sessions[session_id] = session
        
        # Enable S3
        upload_service.s3_service.is_available.return_value = True
        upload_service.s3_service.upload_part = AsyncMock()
        
        # Call the method
        chunk_data = b"test chunk data"
        result = await upload_service.process_chunk(session_id, chunk_data, 1)
        
        # Verify result
        assert isinstance(result, ChunkResult)
        assert result.success is True
        assert result.chunk_number == 1
        
        # Verify S3 upload
        upload_service.s3_service.upload_part.assert_called_once_with(mock_s3_session, 1, chunk_data)
        
        # Verify session updates
        assert session.chunks_received == 1
        assert session.uploaded_size == len(chunk_data)
    
    @patch('aiofiles.open', new_callable=mock_open)
    async def test_process_chunk_success_local(self, mock_file, upload_service):
        """Test successful chunk processing with local storage."""
        # Create mock session without S3
        session_id = str(uuid.uuid4())
        session = UploadSession(session_id, str(uuid.uuid4()), str(uuid.uuid4()), {})
        session.temp_file_path = "/tmp/test.tmp"
        upload_service.active_sessions[session_id] = session
        
        # Disable S3
        upload_service.s3_service.is_available.return_value = False
        
        # Call the method
        chunk_data = b"test chunk data"
        result = await upload_service.process_chunk(session_id, chunk_data, 1)
        
        # Verify result
        assert result.success is True
        assert result.chunk_number == 1
        
        # Verify file operations
        mock_file.assert_called_once_with("/tmp/test.tmp", 'ab')
    
    async def test_process_chunk_session_not_found(self, upload_service):
        """Test chunk processing with invalid session ID."""
        chunk_data = b"test chunk data"
        
        # Call the method with invalid session ID
        with pytest.raises(HTTPException) as exc_info:
            await upload_service.process_chunk("invalid-session", chunk_data, 1)
        
        assert exc_info.value.status_code == 404
        assert "Upload session not found" in str(exc_info.value.detail)
    
    async def test_process_chunk_s3_error(self, upload_service):
        """Test chunk processing with S3 error."""
        # Create mock session with S3
        session_id = str(uuid.uuid4())
        mock_s3_session = MagicMock()
        session = UploadSession(session_id, str(uuid.uuid4()), str(uuid.uuid4()), {})
        session.s3_session = mock_s3_session
        upload_service.active_sessions[session_id] = session
        
        # Enable S3 and mock error
        upload_service.s3_service.is_available.return_value = True
        upload_service.s3_service.upload_part = AsyncMock(side_effect=Exception("S3 error"))
        
        # Call the method
        chunk_data = b"test chunk data"
        result = await upload_service.process_chunk(session_id, chunk_data, 1)
        
        # Verify error result
        assert result.success is False
        assert "S3 error" in result.message
    
    async def test_complete_upload_success_s3(self, upload_service, mock_db):
        """Test successful upload completion with S3."""
        # Create mock session with S3
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())
        mock_s3_session = MagicMock()
        session = UploadSession(session_id, video_id, str(uuid.uuid4()), {'filename': 'test.mp4'})
        session.s3_session = mock_s3_session
        upload_service.active_sessions[session_id] = session
        
        # Mock S3 completion
        upload_service.s3_service.is_available.return_value = True
        mock_result = MagicMock()
        mock_result.success = True
        upload_service.s3_service.complete_multipart_upload = AsyncMock(return_value=mock_result)
        
        # Mock video retrieval
        mock_video = Video(id=video_id, status=VideoStatus.uploading)
        mock_db.get.return_value = mock_video
        
        # Mock transcoding service
        upload_service.transcoding_service.queue_transcoding_job = AsyncMock()
        
        # Call the method
        quality_presets = ["720p_30fps", "1080p_30fps"]
        result = await upload_service.complete_upload(session_id, quality_presets)
        
        # Verify result
        assert result == mock_video
        assert mock_video.status == VideoStatus.processing
        
        # Verify S3 completion
        upload_service.s3_service.complete_multipart_upload.assert_called_once_with(mock_s3_session)
        
        # Verify database operations
        mock_db.commit.assert_called()
        
        # Verify session cleanup
        assert session_id not in upload_service.active_sessions
    
    @patch('os.path.exists')
    @patch('os.rename')
    @patch('os.makedirs')
    async def test_complete_upload_success_local(self, mock_makedirs, mock_rename, mock_exists, 
                                               upload_service, mock_db):
        """Test successful upload completion with local storage."""
        # Create mock session without S3
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())
        session = UploadSession(session_id, video_id, str(uuid.uuid4()), {'filename': 'test.mp4'})
        session.temp_file_path = "/tmp/test.tmp"
        upload_service.active_sessions[session_id] = session
        
        # Disable S3
        upload_service.s3_service.is_available.return_value = False
        
        # Mock file operations
        mock_exists.return_value = True
        
        # Mock video retrieval and analysis
        mock_video = Video(id=video_id, status=VideoStatus.uploading)
        mock_db.get.return_value = mock_video
        
        mock_analysis = MagicMock()
        mock_analysis.is_valid = True
        mock_analysis.duration_seconds = 120.5
        mock_analysis.width = 1920
        mock_analysis.height = 1080
        mock_analysis.framerate = 30
        mock_analysis.codec = "h264"
        mock_analysis.bitrate = 5000000
        upload_service.analysis_service.analyze_video_file = AsyncMock(return_value=mock_analysis)
        
        # Mock thumbnail and transcoding services
        upload_service.thumbnail_service.generate_thumbnails_for_video = AsyncMock()
        upload_service.transcoding_service.queue_transcoding_job = AsyncMock()
        
        # Call the method
        quality_presets = ["720p_30fps"]
        result = await upload_service.complete_upload(session_id, quality_presets)
        
        # Verify result
        assert result == mock_video
        assert mock_video.status == VideoStatus.processing
        assert mock_video.duration_seconds == 120
        assert mock_video.source_resolution == "1920x1080"
        
        # Verify file operations
        mock_rename.assert_called_once()
        
        # Verify analysis and thumbnail generation
        upload_service.analysis_service.analyze_video_file.assert_called_once()
        upload_service.thumbnail_service.generate_thumbnails_for_video.assert_called_once()
    
    async def test_complete_upload_s3_failure(self, upload_service):
        """Test upload completion with S3 failure."""
        # Create mock session with S3
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())
        mock_s3_session = MagicMock()
        session = UploadSession(session_id, video_id, str(uuid.uuid4()), {'filename': 'test.mp4'})
        session.s3_session = mock_s3_session
        upload_service.active_sessions[session_id] = session
        
        # Mock S3 failure
        upload_service.s3_service.is_available.return_value = True
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "S3 upload failed"
        upload_service.s3_service.complete_multipart_upload = AsyncMock(return_value=mock_result)
        
        # Mock cancel_upload
        upload_service.cancel_upload = AsyncMock()
        
        # Call the method and expect exception
        with pytest.raises(HTTPException) as exc_info:
            await upload_service.complete_upload(session_id, [])
        
        assert exc_info.value.status_code == 500
        assert "Failed to complete upload" in str(exc_info.value.detail)
        
        # Verify cleanup was called
        upload_service.cancel_upload.assert_called_once_with(session_id)
    
    async def test_cancel_upload_success_s3(self, upload_service, mock_db):
        """Test successful upload cancellation with S3."""
        # Create mock session with S3
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())
        mock_s3_session = MagicMock()
        session = UploadSession(session_id, video_id, str(uuid.uuid4()), {})
        session.s3_session = mock_s3_session
        upload_service.active_sessions[session_id] = session
        
        # Mock S3 and database operations
        upload_service.s3_service.is_available.return_value = True
        upload_service.s3_service.abort_multipart_upload = AsyncMock()
        
        mock_video = Video(id=video_id, status=VideoStatus.uploading)
        mock_db.get.return_value = mock_video
        
        # Call the method
        result = await upload_service.cancel_upload(session_id)
        
        # Verify result
        assert result is True
        
        # Verify S3 abort
        upload_service.s3_service.abort_multipart_upload.assert_called_once_with(mock_s3_session)
        
        # Verify video status update
        assert mock_video.status == VideoStatus.failed
        mock_db.commit.assert_called_once()
        
        # Verify session cleanup
        assert session_id not in upload_service.active_sessions
    
    @patch('os.path.exists')
    @patch('os.remove')
    async def test_cancel_upload_success_local(self, mock_remove, mock_exists, upload_service, mock_db):
        """Test successful upload cancellation with local storage."""
        # Create mock session without S3
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())
        session = UploadSession(session_id, video_id, str(uuid.uuid4()), {})
        session.temp_file_path = "/tmp/test.tmp"
        upload_service.active_sessions[session_id] = session
        
        # Disable S3
        upload_service.s3_service.is_available.return_value = False
        
        # Mock file operations
        mock_exists.return_value = True
        
        # Mock video retrieval
        mock_video = Video(id=video_id, status=VideoStatus.uploading)
        mock_db.get.return_value = mock_video
        
        # Call the method
        result = await upload_service.cancel_upload(session_id)
        
        # Verify result
        assert result is True
        
        # Verify file removal
        mock_remove.assert_called_once_with("/tmp/test.tmp")
        
        # Verify video status update
        assert mock_video.status == VideoStatus.failed
    
    async def test_cancel_upload_session_not_found(self, upload_service):
        """Test upload cancellation with invalid session ID."""
        result = await upload_service.cancel_upload("invalid-session")
        assert result is False
    
    def test_validate_file_info_success(self, upload_service):
        """Test successful file info validation."""
        file_info = {
            'filename': 'test_video.mp4',
            'size': 1024 * 1024 * 100  # 100MB
        }
        
        result = upload_service._validate_file_info(file_info)
        assert result is True
    
    def test_validate_file_info_missing_fields(self, upload_service):
        """Test file info validation with missing fields."""
        file_info = {'filename': 'test_video.mp4'}  # Missing size
        
        result = upload_service._validate_file_info(file_info)
        assert result is False
    
    def test_validate_file_info_too_large(self, upload_service):
        """Test file info validation with file too large."""
        file_info = {
            'filename': 'test_video.mp4',
            'size': 11 * 1024 * 1024 * 1024  # 11GB (over limit)
        }
        
        result = upload_service._validate_file_info(file_info)
        assert result is False
    
    def test_validate_file_info_invalid_extension(self, upload_service):
        """Test file info validation with invalid extension."""
        file_info = {
            'filename': 'test_video.txt',  # Invalid extension
            'size': 1024 * 1024 * 100
        }
        
        result = upload_service._validate_file_info(file_info)
        assert result is False
    
    async def test_queue_transcoding_jobs_success(self, upload_service, mock_db):
        """Test successful transcoding job queueing."""
        video_id = str(uuid.uuid4())
        quality_presets = ["720p_30fps", "1080p_30fps"]
        
        # Mock video retrieval
        mock_video = Video(id=video_id, status=VideoStatus.processing)
        mock_db.get.return_value = mock_video
        
        # Mock quality preset service
        available_presets = [
            {"name": "720p_30fps", "resolution": "1280x720", "framerate": 30, "bitrate": 2500},
            {"name": "1080p_30fps", "resolution": "1920x1080", "framerate": 30, "bitrate": 5000}
        ]
        upload_service.quality_preset_service.get_available_presets_for_video = AsyncMock(
            return_value=available_presets
        )
        
        # Mock transcoding service
        upload_service.transcoding_service.queue_transcoding_job = AsyncMock()
        
        # Call the method
        await upload_service._queue_transcoding_jobs(video_id, quality_presets)
        
        # Verify transcoding jobs were queued
        assert upload_service.transcoding_service.queue_transcoding_job.call_count == 2
        
        # Verify video status update
        assert mock_video.status == VideoStatus.transcoding
        mock_db.commit.assert_called_once()
    
    def test_get_upload_progress_success(self, upload_service):
        """Test successful upload progress retrieval."""
        # Create mock session
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())
        session = UploadSession(session_id, video_id, str(uuid.uuid4()), {'total_chunks': 10})
        session.total_size = 1024 * 1024  # 1MB
        session.uploaded_size = 512 * 1024  # 512KB
        session.chunks_received = 5
        upload_service.active_sessions[session_id] = session
        
        # Call the method
        progress = upload_service.get_upload_progress(session_id)
        
        # Verify progress data
        assert progress is not None
        assert progress['session_id'] == session_id
        assert progress['video_id'] == video_id
        assert progress['chunks_received'] == 5
        assert progress['total_chunks'] == 10
        assert progress['uploaded_size'] == 512 * 1024
        assert progress['total_size'] == 1024 * 1024
        assert progress['progress_percent'] == 50.0
    
    def test_get_upload_progress_session_not_found(self, upload_service):
        """Test upload progress retrieval with invalid session ID."""
        progress = upload_service.get_upload_progress("invalid-session")
        assert progress is None
    
    def test_get_upload_progress_zero_size(self, upload_service):
        """Test upload progress with zero total size."""
        # Create mock session with zero size
        session_id = str(uuid.uuid4())
        session = UploadSession(session_id, str(uuid.uuid4()), str(uuid.uuid4()), {})
        session.total_size = 0
        session.uploaded_size = 0
        upload_service.active_sessions[session_id] = session
        
        # Call the method
        progress = upload_service.get_upload_progress(session_id)
        
        # Verify progress data
        assert progress['progress_percent'] == 0


class TestUploadSession:
    """Test cases for UploadSession class."""
    
    def test_upload_session_creation(self):
        """Test UploadSession creation."""
        session_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        metadata = {'filename': 'test.mp4', 'size': 1024}
        
        session = UploadSession(session_id, video_id, user_id, metadata)
        
        assert session.session_id == session_id
        assert session.video_id == video_id
        assert session.user_id == user_id
        assert session.metadata == metadata
        assert session.chunks_received == 0
        assert session.uploaded_size == 0
        assert session.s3_session is None
        assert session.temp_file_path is None
        assert isinstance(session.created_at, datetime)


class TestVideoMetadata:
    """Test cases for VideoMetadata class."""
    
    def test_video_metadata_creation(self):
        """Test VideoMetadata creation."""
        metadata = VideoMetadata(
            title="Test Video",
            description="Test description",
            tags=["test", "video"]
        )
        
        assert metadata.title == "Test Video"
        assert metadata.description == "Test description"
        assert metadata.tags == ["test", "video"]
    
    def test_video_metadata_defaults(self):
        """Test VideoMetadata with default values."""
        metadata = VideoMetadata(title="Test Video")
        
        assert metadata.title == "Test Video"
        assert metadata.description is None
        assert metadata.tags == []


class TestChunkResult:
    """Test cases for ChunkResult class."""
    
    def test_chunk_result_success(self):
        """Test ChunkResult for successful chunk."""
        result = ChunkResult(1, True, "Success")
        
        assert result.chunk_number == 1
        assert result.success is True
        assert result.message == "Success"
    
    def test_chunk_result_failure(self):
        """Test ChunkResult for failed chunk."""
        result = ChunkResult(2, False, "Error occurred")
        
        assert result.chunk_number == 2
        assert result.success is False
        assert result.message == "Error occurred"
    
    def test_chunk_result_no_message(self):
        """Test ChunkResult without message."""
        result = ChunkResult(3, True)
        
        assert result.chunk_number == 3
        assert result.success is True
        assert result.message is None


if __name__ == "__main__":
    pytest.main([__file__])