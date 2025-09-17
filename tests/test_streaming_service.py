"""
Comprehensive unit tests for StreamingService.
"""
import pytest
import asyncio
import time
import hashlib
import hmac
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from server.web.app.services.streaming_service import StreamingService
from server.web.app.models import Video, VideoStatus, VideoVisibility, ViewSession, User


@pytest.fixture
async def mock_db():
    """Mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_services():
    """Mock dependent services."""
    services = {
        's3_service': MagicMock(),
        'hls_service': MagicMock()
    }
    return services


@pytest.fixture
async def streaming_service(mock_db, mock_services):
    """Create StreamingService with mocked dependencies."""
    service = StreamingService(mock_db)
    
    # Replace services with mocks
    for service_name, mock_service in mock_services.items():
        setattr(service, service_name, mock_service)
    
    return service


@pytest.fixture
def sample_video():
    """Sample video for testing."""
    return Video(
        id=str(uuid.uuid4()),
        creator_id=str(uuid.uuid4()),
        title="Test Video",
        description="A test video",
        status=VideoStatus.ready,
        visibility=VideoVisibility.public,
        duration_seconds=120
    )


@pytest.fixture
def sample_view_session():
    """Sample view session for testing."""
    return ViewSession(
        id=str(uuid.uuid4()),
        video_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        session_token="test-session-token",
        current_position_seconds=60.0,
        completion_percentage=50.0,
        quality_switches=2,
        buffering_events=1,
        started_at=datetime.utcnow(),
        last_heartbeat=datetime.utcnow()
    )


class TestStreamingService:
    """Test cases for StreamingService."""
    
    async def test_check_video_access_public_video(self, streaming_service, mock_db, sample_video):
        """Test access check for public video."""
        sample_video.visibility = VideoVisibility.public
        mock_db.get.return_value = sample_video
        
        result = await streaming_service.check_video_access(sample_video.id)
        
        assert result is True
        mock_db.get.assert_called_once_with(Video, sample_video.id)
    
    async def test_check_video_access_unlisted_video(self, streaming_service, mock_db, sample_video):
        """Test access check for unlisted video."""
        sample_video.visibility = VideoVisibility.unlisted
        mock_db.get.return_value = sample_video
        
        result = await streaming_service.check_video_access(sample_video.id)
        
        assert result is True
    
    async def test_check_video_access_private_video_owner(self, streaming_service, mock_db, sample_video):
        """Test access check for private video by owner."""
        sample_video.visibility = VideoVisibility.private
        mock_db.get.return_value = sample_video
        
        result = await streaming_service.check_video_access(sample_video.id, str(sample_video.creator_id))
        
        assert result is True
    
    async def test_check_video_access_private_video_unauthorized(self, streaming_service, mock_db, sample_video):
        """Test access check for private video by unauthorized user."""
        sample_video.visibility = VideoVisibility.private
        mock_db.get.return_value = sample_video
        
        with pytest.raises(HTTPException) as exc_info:
            await streaming_service.check_video_access(sample_video.id, str(uuid.uuid4()))
        
        assert exc_info.value.status_code == 403
        assert "Access denied" in str(exc_info.value.detail)
    
    async def test_check_video_access_private_video_anonymous(self, streaming_service, mock_db, sample_video):
        """Test access check for private video by anonymous user."""
        sample_video.visibility = VideoVisibility.private
        mock_db.get.return_value = sample_video
        
        with pytest.raises(HTTPException) as exc_info:
            await streaming_service.check_video_access(sample_video.id)
        
        assert exc_info.value.status_code == 401
        assert "Authentication required" in str(exc_info.value.detail)
    
    async def test_check_video_access_video_not_found(self, streaming_service, mock_db):
        """Test access check for non-existent video."""
        mock_db.get.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await streaming_service.check_video_access("non-existent-id")
        
        assert exc_info.value.status_code == 404
        assert "Video not found" in str(exc_info.value.detail)
    
    async def test_check_video_access_video_not_ready(self, streaming_service, mock_db, sample_video):
        """Test access check for video not ready for streaming."""
        sample_video.status = VideoStatus.processing
        mock_db.get.return_value = sample_video
        
        with pytest.raises(HTTPException) as exc_info:
            await streaming_service.check_video_access(sample_video.id)
        
        assert exc_info.value.status_code == 400
        assert "not ready for streaming" in str(exc_info.value.detail)
    
    @patch('server.web.app.config.settings')
    def test_generate_signed_streaming_url_master(self, mock_settings, streaming_service):
        """Test generating signed URL for master playlist."""
        mock_settings.SECRET_KEY = "test-secret-key"
        video_id = str(uuid.uuid4())
        
        # Mock HLS service
        streaming_service.hls_service.get_streaming_url.return_value = f"https://cdn.example.com/video/{video_id}/master.m3u8"
        
        signed_url = streaming_service.generate_signed_streaming_url(video_id)
        
        # Verify URL structure
        assert f"video/{video_id}" in signed_url
        assert "expires=" in signed_url
        assert "signature=" in signed_url
        
        # Verify HLS service call
        streaming_service.hls_service.get_streaming_url.assert_called_once_with(video_id, None)
    
    @patch('server.web.app.config.settings')
    def test_generate_signed_streaming_url_quality(self, mock_settings, streaming_service):
        """Test generating signed URL for specific quality."""
        mock_settings.SECRET_KEY = "test-secret-key"
        video_id = str(uuid.uuid4())
        quality = "720p_30fps"
        
        # Mock HLS service
        streaming_service.hls_service.get_streaming_url.return_value = f"https://cdn.example.com/video/{video_id}/{quality}/playlist.m3u8"
        
        signed_url = streaming_service.generate_signed_streaming_url(video_id, quality)
        
        # Verify URL structure
        assert f"video/{video_id}" in signed_url
        assert quality in signed_url
        assert "expires=" in signed_url
        assert "signature=" in signed_url
        
        # Verify HLS service call
        streaming_service.hls_service.get_streaming_url.assert_called_once_with(video_id, quality)
    
    @patch('server.web.app.config.settings')
    @patch('time.time')
    def test_validate_signed_url_success(self, mock_time, mock_settings, streaming_service):
        """Test successful signed URL validation."""
        mock_settings.SECRET_KEY = "test-secret-key"
        mock_time.return_value = 1000000000  # Fixed timestamp
        
        video_id = str(uuid.uuid4())
        quality = "720p_30fps"
        expires = 1000003600  # 1 hour in future
        
        # Generate expected signature
        resource = f"video/{video_id}/quality/{quality}"
        message = f"{resource}:{expires}".encode('utf-8')
        expected_signature = hmac.new(
            "test-secret-key".encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        
        result = streaming_service.validate_signed_url(video_id, quality, expires, expected_signature)
        
        assert result is True
    
    @patch('server.web.app.config.settings')
    @patch('time.time')
    def test_validate_signed_url_expired(self, mock_time, mock_settings, streaming_service):
        """Test validation of expired signed URL."""
        mock_settings.SECRET_KEY = "test-secret-key"
        mock_time.return_value = 1000003600  # Current time after expiration
        
        video_id = str(uuid.uuid4())
        expires = 1000000000  # Expired timestamp
        signature = "valid-signature"
        
        with pytest.raises(HTTPException) as exc_info:
            streaming_service.validate_signed_url(video_id, None, expires, signature)
        
        assert exc_info.value.status_code == 410
        assert "expired" in str(exc_info.value.detail)
    
    @patch('server.web.app.config.settings')
    @patch('time.time')
    def test_validate_signed_url_invalid_signature(self, mock_time, mock_settings, streaming_service):
        """Test validation with invalid signature."""
        mock_settings.SECRET_KEY = "test-secret-key"
        mock_time.return_value = 1000000000
        
        video_id = str(uuid.uuid4())
        expires = 1000003600  # Valid expiration
        invalid_signature = "invalid-signature"
        
        with pytest.raises(HTTPException) as exc_info:
            streaming_service.validate_signed_url(video_id, None, expires, invalid_signature)
        
        assert exc_info.value.status_code == 403
        assert "Invalid" in str(exc_info.value.detail)
    
    async def test_get_quality_recommendation_bandwidth_based(self, streaming_service):
        """Test quality recommendation based on bandwidth."""
        video_id = str(uuid.uuid4())
        bandwidth_kbps = 3000  # 3 Mbps
        
        # Mock available qualities
        qualities = [
            {"height": 480, "framerate": 30, "quality_preset": "480p_30fps"},
            {"height": 720, "framerate": 30, "quality_preset": "720p_30fps"},
            {"height": 1080, "framerate": 30, "quality_preset": "1080p_30fps"}
        ]
        streaming_service.hls_service.get_available_qualities = AsyncMock(return_value=qualities)
        
        result = await streaming_service.get_quality_recommendation(video_id, bandwidth_kbps)
        
        # Should recommend 720p for 3 Mbps bandwidth
        assert result["recommended"]["height"] == 720
        assert result["bandwidth_kbps"] == bandwidth_kbps
        assert result["available_qualities"] == qualities
        assert result["auto_switch_enabled"] is True
    
    async def test_get_quality_recommendation_mobile_device(self, streaming_service):
        """Test quality recommendation for mobile device."""
        video_id = str(uuid.uuid4())
        device_type = "mobile"
        
        # Mock available qualities
        qualities = [
            {"height": 480, "framerate": 30, "quality_preset": "480p_30fps"},
            {"height": 720, "framerate": 30, "quality_preset": "720p_30fps"},
            {"height": 1080, "framerate": 30, "quality_preset": "1080p_30fps"}
        ]
        streaming_service.hls_service.get_available_qualities = AsyncMock(return_value=qualities)
        
        result = await streaming_service.get_quality_recommendation(video_id, device_type=device_type)
        
        # Should recommend 720p or lower for mobile
        assert result["recommended"]["height"] <= 720
        assert result["device_type"] == device_type
    
    async def test_get_quality_recommendation_no_qualities(self, streaming_service):
        """Test quality recommendation when no qualities available."""
        video_id = str(uuid.uuid4())
        
        # Mock no available qualities
        streaming_service.hls_service.get_available_qualities = AsyncMock(return_value=[])
        
        with pytest.raises(HTTPException) as exc_info:
            await streaming_service.get_quality_recommendation(video_id)
        
        assert exc_info.value.status_code == 404
        assert "No qualities available" in str(exc_info.value.detail)
    
    @patch('hashlib.sha256')
    async def test_create_viewing_session_success(self, mock_sha256, streaming_service, mock_db):
        """Test successful viewing session creation."""
        video_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        ip_address = "192.168.1.1"
        user_agent = "Mozilla/5.0"
        
        # Mock hash generation
        mock_hash = MagicMock()
        mock_hash.hexdigest.return_value = "mocked-hash"
        mock_sha256.return_value = mock_hash
        
        # Mock database operations
        mock_db.refresh.side_effect = lambda obj: setattr(obj, 'id', str(uuid.uuid4()))
        
        result = await streaming_service.create_viewing_session(
            video_id, user_id, ip_address, user_agent
        )
        
        # Verify session creation
        assert isinstance(result, ViewSession)
        assert result.video_id == video_id
        assert result.user_id == user_id
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    async def test_create_viewing_session_anonymous(self, streaming_service, mock_db):
        """Test viewing session creation for anonymous user."""
        video_id = str(uuid.uuid4())
        
        result = await streaming_service.create_viewing_session(video_id)
        
        # Verify session creation
        assert isinstance(result, ViewSession)
        assert result.video_id == video_id
        assert result.user_id is None
    
    async def test_get_streaming_manifest_success(self, streaming_service, mock_db, sample_video):
        """Test successful streaming manifest generation."""
        user_id = str(uuid.uuid4())
        session_token = "test-session-token"
        
        # Mock video access check
        streaming_service.check_video_access = AsyncMock(return_value=True)
        mock_db.get.return_value = sample_video
        
        # Mock available qualities
        qualities = [
            {"quality_preset": "720p_30fps", "height": 720},
            {"quality_preset": "1080p_30fps", "height": 1080}
        ]
        streaming_service.hls_service.get_available_qualities = AsyncMock(return_value=qualities)
        
        # Mock signed URL generation
        streaming_service.generate_signed_streaming_url = MagicMock(
            side_effect=lambda vid, qual=None: f"https://cdn.example.com/signed/{qual or 'master'}"
        )
        
        result = await streaming_service.get_streaming_manifest(
            sample_video.id, user_id, session_token=session_token
        )
        
        # Verify manifest structure
        assert result["video_id"] == sample_video.id
        assert result["title"] == sample_video.title
        assert result["duration"] == sample_video.duration_seconds
        assert result["session_token"] == session_token
        assert "master_playlist_url" in result
        assert len(result["qualities"]) == 2
        
        # Verify each quality has signed URL
        for quality in result["qualities"]:
            assert "signed_url" in quality
    
    async def test_get_user_resume_position_with_history(self, streaming_service, mock_db, sample_view_session):
        """Test getting resume position with viewing history."""
        video_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_view_session
        mock_db.execute.return_value = mock_result
        
        result = await streaming_service.get_user_resume_position(video_id, user_id)
        
        # Verify resume position
        assert result["has_resume_position"] is True
        assert result["resume_position"] == sample_view_session.current_position_seconds
        assert result["completion_percentage"] == sample_view_session.completion_percentage
    
    async def test_get_user_resume_position_no_history(self, streaming_service, mock_db):
        """Test getting resume position with no viewing history."""
        video_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        
        # Mock database query returning no results
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        result = await streaming_service.get_user_resume_position(video_id, user_id)
        
        # Verify no resume position
        assert result["has_resume_position"] is False
        assert result["resume_position"] == 0
        assert result["completion_percentage"] == 0
    
    async def test_get_user_resume_position_completed_video(self, streaming_service, mock_db, sample_view_session):
        """Test getting resume position for completed video."""
        video_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        
        # Set completion percentage to 95% (completed)
        sample_view_session.completion_percentage = 95
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_view_session
        mock_db.execute.return_value = mock_result
        
        result = await streaming_service.get_user_resume_position(video_id, user_id)
        
        # Should not offer resume for completed video
        assert result["has_resume_position"] is False
        assert result["resume_position"] == 0
    
    async def test_update_viewing_progress_success(self, streaming_service, mock_db, sample_view_session):
        """Test successful viewing progress update."""
        session_token = "test-session-token"
        video_id = str(uuid.uuid4())
        
        progress_data = {
            'current_position_seconds': 90.0,
            'completion_percentage': 75.0,
            'quality_switches': 3,
            'buffering_events': 2
        }
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_view_session
        mock_db.execute.return_value = mock_result
        
        result = await streaming_service.update_viewing_progress(session_token, video_id, progress_data)
        
        # Verify progress update
        assert result.current_position_seconds == 90.0
        assert result.completion_percentage == 75.0
        assert result.quality_switches == 3
        assert result.buffering_events == 2
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    async def test_update_viewing_progress_session_not_found(self, streaming_service, mock_db):
        """Test viewing progress update with invalid session."""
        session_token = "invalid-session-token"
        video_id = str(uuid.uuid4())
        progress_data = {}
        
        # Mock database query returning no results
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(HTTPException) as exc_info:
            await streaming_service.update_viewing_progress(session_token, video_id, progress_data)
        
        assert exc_info.value.status_code == 404
        assert "Viewing session not found" in str(exc_info.value.detail)
    
    async def test_end_viewing_session_success(self, streaming_service, mock_db, sample_view_session):
        """Test successful viewing session end."""
        session_token = "test-session-token"
        video_id = str(uuid.uuid4())
        
        final_data = {
            'current_position_seconds': 120.0,
            'completion_percentage': 100.0,
            'quality_switches': 4,
            'buffering_events': 3
        }
        
        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_view_session
        mock_db.execute.return_value = mock_result
        
        result = await streaming_service.end_viewing_session(session_token, video_id, final_data)
        
        # Verify session end
        assert result.current_position_seconds == 120.0
        assert result.completion_percentage == 100.0
        assert result.ended_at is not None
        
        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    async def test_end_viewing_session_not_found(self, streaming_service, mock_db):
        """Test ending non-existent viewing session."""
        session_token = "invalid-session-token"
        video_id = str(uuid.uuid4())
        final_data = {}
        
        # Mock database query returning no results
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        with pytest.raises(HTTPException) as exc_info:
            await streaming_service.end_viewing_session(session_token, video_id, final_data)
        
        assert exc_info.value.status_code == 404
        assert "Viewing session not found" in str(exc_info.value.detail)


if __name__ == "__main__":
    pytest.main([__file__])