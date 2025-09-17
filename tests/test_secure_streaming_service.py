"""
Tests for Secure Streaming Service
"""
import pytest
import uuid
import json
import hmac
import hashlib
import base64
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from server.web.app.services.secure_streaming_service import SecureStreamingService
from server.web.app.models import Video, VideoVisibility, VideoStatus, User, ViewSession, TranscodingJob


class TestSecureStreamingService:
    
    @pytest.fixture
    def service(self):
        return SecureStreamingService()
    
    @pytest.fixture
    def mock_video(self):
        return Video(
            id=uuid.uuid4(),
            creator_id=uuid.uuid4(),
            title="Test Video",
            description="Test Description",
            original_filename="test.mp4",
            original_s3_key="videos/test.mp4",
            file_size=1000000,
            duration_seconds=120,
            status=VideoStatus.ready,
            visibility=VideoVisibility.public,
            created_at=datetime.utcnow(),
            transcoding_jobs=[]
        )
    
    @pytest.fixture
    def mock_transcoding_job(self):
        return TranscodingJob(
            id=uuid.uuid4(),
            video_id=uuid.uuid4(),
            quality_preset="720p_30fps",
            target_resolution="1280x720",
            target_framerate=30,
            target_bitrate=2500000,
            status="completed",
            hls_manifest_s3_key="transcoded/video/720p/playlist.m3u8",
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def mock_user(self):
        return User(
            id=uuid.uuid4(),
            display_label="Test User",
            email="test@example.com",
            created_at=datetime.utcnow()
        )
    
    @pytest.mark.asyncio
    async def test_generate_streaming_manifest_success(self, service, mock_video, mock_transcoding_job):
        """Test successful streaming manifest generation"""
        mock_video.transcoding_jobs = [mock_transcoding_job]
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock video query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            mock_session.execute.return_value = mock_result
            
            # Mock access control
            with patch('server.web.app.services.secure_streaming_service.VideoAccessControlService') as mock_access:
                mock_access_instance = AsyncMock()
                mock_access.return_value = mock_access_instance
                mock_access_instance.check_video_access.return_value = {"has_access": True}
                
                # Mock session creation
                with patch.object(service, '_create_streaming_session', return_value="test_session_token"):
                    result = await service.generate_streaming_manifest(
                        video_id=mock_video.id,
                        user_id=uuid.uuid4()
                    )
                
                assert result["success"] is True
                assert result["video_id"] == str(mock_video.id)
                assert result["session_token"] == "test_session_token"
                assert "streams" in result
                assert "720p_30fps" in result["streams"]
    
    @pytest.mark.asyncio
    async def test_generate_streaming_manifest_access_denied(self, service, mock_video):
        """Test streaming manifest generation with access denied"""
        with patch('server.web.app.services.secure_streaming_service.VideoAccessControlService') as mock_access:
            mock_access_instance = AsyncMock()
            mock_access.return_value = mock_access_instance
            mock_access_instance.check_video_access.return_value = {
                "has_access": False,
                "reason": "insufficient_permissions",
                "message": "Access denied"
            }
            
            result = await service.generate_streaming_manifest(
                video_id=mock_video.id,
                user_id=uuid.uuid4()
            )
            
            assert result["success"] is False
            assert result["error"] == "insufficient_permissions"
    
    @pytest.mark.asyncio
    async def test_validate_streaming_access_success(self, service, mock_video):
        """Test successful streaming access validation"""
        session_token = "test_session_token"
        mock_session = ViewSession(
            id=uuid.uuid4(),
            video_id=mock_video.id,
            user_id=uuid.uuid4(),
            session_token=session_token,
            started_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_db_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_db_session
            
            # Mock session query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_session
            mock_db_session.execute.return_value = mock_result
            
            result = await service.validate_streaming_access(
                video_id=mock_video.id,
                quality="720p_30fps",
                session_token=session_token,
                user_id=mock_session.user_id
            )
            
            assert result["valid"] is True
            assert result["session_id"] == str(mock_session.id)
    
    @pytest.mark.asyncio
    async def test_validate_streaming_access_invalid_session(self, service, mock_video):
        """Test streaming access validation with invalid session"""
        with patch.object(service, 'get_db_session') as mock_db:
            mock_db_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_db_session
            
            # Mock session query returning None
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db_session.execute.return_value = mock_result
            
            result = await service.validate_streaming_access(
                video_id=mock_video.id,
                quality="720p_30fps",
                session_token="invalid_token"
            )
            
            assert result["valid"] is False
            assert result["error"] == "invalid_session"
    
    @pytest.mark.asyncio
    async def test_validate_streaming_access_expired_session(self, service, mock_video):
        """Test streaming access validation with expired session"""
        session_token = "test_session_token"
        mock_session = ViewSession(
            id=uuid.uuid4(),
            video_id=mock_video.id,
            user_id=uuid.uuid4(),
            session_token=session_token,
            started_at=datetime.utcnow() - timedelta(hours=3),  # Expired
            last_heartbeat=datetime.utcnow() - timedelta(hours=3)
        )
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_db_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_db_session
            
            # Mock session query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_session
            mock_db_session.execute.return_value = mock_result
            
            result = await service.validate_streaming_access(
                video_id=mock_video.id,
                quality="720p_30fps",
                session_token=session_token
            )
            
            assert result["valid"] is False
            assert result["error"] == "session_expired"
    
    @pytest.mark.asyncio
    async def test_generate_signed_url(self, service):
        """Test signed URL generation"""
        video_id = uuid.uuid4()
        quality = "720p_30fps"
        session_token = "test_session_token"
        
        signed_url = await service.generate_signed_url(
            video_id=video_id,
            quality=quality,
            session_token=session_token,
            expires_in_minutes=60
        )
        
        assert f"/api/stream/{video_id}/{quality}" in signed_url
        assert "token=" in signed_url
        assert "expires=" in signed_url
        assert "signature=" in signed_url
    
    @pytest.mark.asyncio
    async def test_validate_signed_url_success(self, service):
        """Test successful signed URL validation"""
        video_id = uuid.uuid4()
        quality = "720p_30fps"
        session_token = "test_session_token"
        expires = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        
        # Generate valid signature
        payload = {
            "video_id": str(video_id),
            "quality": quality,
            "session_token": session_token,
            "expires_at": expires
        }
        signature = service._generate_signature(payload)
        
        # Mock session validation
        with patch.object(service, 'validate_streaming_access') as mock_validate:
            mock_validate.return_value = {"valid": True, "session_id": "test_session_id"}
            
            result = await service.validate_signed_url(
                video_id=video_id,
                quality=quality,
                token=session_token,
                expires=expires,
                signature=signature
            )
            
            assert result["valid"] is True
    
    @pytest.mark.asyncio
    async def test_validate_signed_url_expired(self, service):
        """Test signed URL validation with expired URL"""
        video_id = uuid.uuid4()
        quality = "720p_30fps"
        session_token = "test_session_token"
        expires = int((datetime.utcnow() - timedelta(hours=1)).timestamp())  # Expired
        
        result = await service.validate_signed_url(
            video_id=video_id,
            quality=quality,
            token=session_token,
            expires=expires,
            signature="invalid_signature"
        )
        
        assert result["valid"] is False
        assert result["error"] == "url_expired"
    
    @pytest.mark.asyncio
    async def test_validate_signed_url_invalid_signature(self, service):
        """Test signed URL validation with invalid signature"""
        video_id = uuid.uuid4()
        quality = "720p_30fps"
        session_token = "test_session_token"
        expires = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
        
        result = await service.validate_signed_url(
            video_id=video_id,
            quality=quality,
            token=session_token,
            expires=expires,
            signature="invalid_signature"
        )
        
        assert result["valid"] is False
        assert result["error"] == "invalid_signature"
    
    @pytest.mark.asyncio
    async def test_revoke_streaming_session_success(self, service, mock_user):
        """Test successful session revocation"""
        session_token = "test_session_token"
        mock_session = ViewSession(
            id=uuid.uuid4(),
            video_id=uuid.uuid4(),
            user_id=mock_user.id,
            session_token=session_token,
            started_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_db_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_db_session
            
            # Mock session query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_session
            mock_db_session.execute.return_value = mock_result
            
            result = await service.revoke_streaming_session(
                session_token=session_token,
                user_id=mock_user.id
            )
            
            assert result["success"] is True
            assert mock_session.ended_at is not None
    
    @pytest.mark.asyncio
    async def test_revoke_streaming_session_unauthorized(self, service, mock_user):
        """Test session revocation by unauthorized user"""
        session_token = "test_session_token"
        other_user_id = uuid.uuid4()
        mock_session = ViewSession(
            id=uuid.uuid4(),
            video_id=uuid.uuid4(),
            user_id=mock_user.id,
            session_token=session_token,
            started_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_db_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_db_session
            
            # Mock session query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_session
            mock_db_session.execute.return_value = mock_result
            
            result = await service.revoke_streaming_session(
                session_token=session_token,
                user_id=other_user_id
            )
            
            assert result["success"] is False
            assert result["error"] == "unauthorized"
    
    def test_generate_signature(self, service):
        """Test signature generation"""
        payload = {
            "video_id": "test_video_id",
            "quality": "720p_30fps",
            "session_token": "test_token",
            "expires_at": 1234567890
        }
        
        signature1 = service._generate_signature(payload)
        signature2 = service._generate_signature(payload)
        
        # Same payload should generate same signature
        assert signature1 == signature2
        
        # Different payload should generate different signature
        payload["quality"] = "1080p_30fps"
        signature3 = service._generate_signature(payload)
        assert signature1 != signature3
    
    def test_generate_session_token(self, service):
        """Test session token generation"""
        token1 = service._generate_session_token()
        token2 = service._generate_session_token()
        
        # Tokens should be unique
        assert token1 != token2
        
        # Tokens should be URL-safe base64
        import base64
        try:
            base64.urlsafe_b64decode(token1 + '==')  # Add padding
            base64.urlsafe_b64decode(token2 + '==')
        except Exception:
            pytest.fail("Session tokens should be valid URL-safe base64")
    
    def test_select_recommended_quality(self, service):
        """Test quality recommendation logic"""
        qualities = [
            {"preset": "480p_30fps", "resolution": "854x480", "bitrate": 1000000, "framerate": 30},
            {"preset": "720p_30fps", "resolution": "1280x720", "bitrate": 2500000, "framerate": 30},
            {"preset": "1080p_30fps", "resolution": "1920x1080", "bitrate": 5000000, "framerate": 30}
        ]
        
        # Test with 720p preference
        recommended = service._select_recommended_quality(qualities, "720p_30fps")
        assert recommended == "720p_30fps"
        
        # Test with no preference (should default to 720p)
        recommended = service._select_recommended_quality(qualities, None)
        assert recommended == "720p_30fps"
        
        # Test with unavailable preference (should default to 720p)
        recommended = service._select_recommended_quality(qualities, "4k_60fps")
        assert recommended == "720p_30fps"
        
        # Test with no 720p available
        qualities_no_720p = [q for q in qualities if "720p" not in q["preset"]]
        recommended = service._select_recommended_quality(qualities_no_720p, None)
        assert recommended == "480p_30fps"  # Should pick highest available