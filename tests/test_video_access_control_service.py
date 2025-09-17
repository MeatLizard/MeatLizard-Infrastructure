"""
Tests for Video Access Control Service
"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from server.web.app.services.video_access_control_service import VideoAccessControlService
from server.web.app.models import Video, VideoVisibility, VideoStatus, User, VideoPermission


class TestVideoAccessControlService:
    
    @pytest.fixture
    def service(self):
        return VideoAccessControlService()
    
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
    async def test_check_video_access_public_video(self, service, mock_video):
        """Test access check for public video"""
        mock_video.visibility = VideoVisibility.public
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock database query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            mock_session.execute.return_value = mock_result
            
            result = await service.check_video_access(
                video_id=mock_video.id,
                user_id=None
            )
            
            assert result["has_access"] is True
            assert result["reason"] == "public_video"
    
    @pytest.mark.asyncio
    async def test_check_video_access_unlisted_video(self, service, mock_video):
        """Test access check for unlisted video"""
        mock_video.visibility = VideoVisibility.unlisted
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock database query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            mock_session.execute.return_value = mock_result
            
            result = await service.check_video_access(
                video_id=mock_video.id,
                user_id=None
            )
            
            assert result["has_access"] is True
            assert result["reason"] == "unlisted_video"
    
    @pytest.mark.asyncio
    async def test_check_video_access_private_video_no_auth(self, service, mock_video):
        """Test access check for private video without authentication"""
        mock_video.visibility = VideoVisibility.private
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock database query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            mock_session.execute.return_value = mock_result
            
            result = await service.check_video_access(
                video_id=mock_video.id,
                user_id=None
            )
            
            assert result["has_access"] is False
            assert result["reason"] == "authentication_required"
    
    @pytest.mark.asyncio
    async def test_check_video_access_private_video_creator(self, service, mock_video):
        """Test access check for private video by creator"""
        mock_video.visibility = VideoVisibility.private
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock database query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            mock_session.execute.return_value = mock_result
            
            result = await service.check_video_access(
                video_id=mock_video.id,
                user_id=mock_video.creator_id
            )
            
            assert result["has_access"] is True
            assert result["reason"] == "video_creator"
    
    @pytest.mark.asyncio
    async def test_check_video_access_private_video_insufficient_permissions(self, service, mock_video):
        """Test access check for private video with insufficient permissions"""
        mock_video.visibility = VideoVisibility.private
        other_user_id = uuid.uuid4()
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock video query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            
            # Mock permission query (no permission found)
            mock_permission_result = AsyncMock()
            mock_permission_result.scalar_one_or_none.return_value = None
            
            mock_session.execute.side_effect = [mock_result, mock_permission_result]
            
            with patch.object(service, '_check_explicit_permission', return_value=False):
                with patch.object(service, '_check_channel_access', return_value=False):
                    result = await service.check_video_access(
                        video_id=mock_video.id,
                        user_id=other_user_id
                    )
            
            assert result["has_access"] is False
            assert result["reason"] == "insufficient_permissions"
    
    @pytest.mark.asyncio
    async def test_check_video_access_video_not_found(self, service):
        """Test access check for non-existent video"""
        video_id = uuid.uuid4()
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock database query returning None
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            
            result = await service.check_video_access(
                video_id=video_id,
                user_id=None
            )
            
            assert result["has_access"] is False
            assert result["reason"] == "video_not_found"
    
    @pytest.mark.asyncio
    async def test_check_video_access_video_not_ready(self, service, mock_video, mock_user):
        """Test access check for video that's not ready"""
        mock_video.status = VideoStatus.processing
        other_user_id = uuid.uuid4()
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock database query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            mock_session.execute.return_value = mock_result
            
            result = await service.check_video_access(
                video_id=mock_video.id,
                user_id=other_user_id
            )
            
            assert result["has_access"] is False
            assert result["reason"] == "video_not_ready"
    
    @pytest.mark.asyncio
    async def test_grant_video_permission_success(self, service, mock_video, mock_user):
        """Test successful permission granting"""
        granted_by_id = mock_video.creator_id
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock video query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            mock_session.execute.return_value = mock_result
            
            with patch.object(service, 'check_video_access', return_value={"has_access": True}):
                result = await service.grant_video_permission(
                    video_id=mock_video.id,
                    user_id=mock_user.id,
                    granted_by=granted_by_id,
                    permission_type="view"
                )
            
            assert result["success"] is True
            assert "permission_id" in result
    
    @pytest.mark.asyncio
    async def test_grant_video_permission_insufficient_permissions(self, service, mock_video, mock_user):
        """Test permission granting with insufficient permissions"""
        other_user_id = uuid.uuid4()
        
        with patch.object(service, 'check_video_access', return_value={"has_access": False}):
            result = await service.grant_video_permission(
                video_id=mock_video.id,
                user_id=mock_user.id,
                granted_by=other_user_id,
                permission_type="view"
            )
            
            assert result["success"] is False
            assert "Insufficient permissions" in result["message"]
    
    @pytest.mark.asyncio
    async def test_update_video_visibility_success(self, service, mock_video):
        """Test successful visibility update"""
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock video query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            mock_session.execute.return_value = mock_result
            
            with patch.object(service, '_log_visibility_change'):
                result = await service.update_video_visibility(
                    video_id=mock_video.id,
                    new_visibility=VideoVisibility.private,
                    updated_by=mock_video.creator_id
                )
            
            assert result["success"] is True
            assert result["old_visibility"] == "public"
            assert result["new_visibility"] == "private"
    
    @pytest.mark.asyncio
    async def test_update_video_visibility_not_creator(self, service, mock_video):
        """Test visibility update by non-creator"""
        other_user_id = uuid.uuid4()
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock video query
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_video
            mock_session.execute.return_value = mock_result
            
            result = await service.update_video_visibility(
                video_id=mock_video.id,
                new_visibility=VideoVisibility.private,
                updated_by=other_user_id
            )
            
            assert result["success"] is False
            assert "Only video creator" in result["message"]
    
    @pytest.mark.asyncio
    async def test_revoke_video_permission_success(self, service, mock_video, mock_user):
        """Test successful permission revocation"""
        mock_permission = VideoPermission(
            id=uuid.uuid4(),
            video_id=mock_video.id,
            user_id=mock_user.id,
            permission_type="view",
            granted_by=mock_video.creator_id,
            created_at=datetime.utcnow()
        )
        
        with patch.object(service, 'get_db_session') as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock video query
            mock_video_result = AsyncMock()
            mock_video_result.scalar_one_or_none.return_value = mock_video
            
            # Mock permission query
            mock_permission_result = AsyncMock()
            mock_permission_result.scalar_one_or_none.return_value = mock_permission
            
            mock_session.execute.side_effect = [mock_video_result, mock_permission_result]
            
            result = await service.revoke_video_permission(
                video_id=mock_video.id,
                user_id=mock_user.id,
                revoked_by=mock_video.creator_id
            )
            
            assert result["success"] is True
            assert "Permission revoked successfully" in result["message"]
    
    def test_hash_ip_address(self, service):
        """Test IP address hashing"""
        ip = "192.168.1.1"
        hashed = service._hash_ip_address(ip)
        
        assert len(hashed) == 16
        assert hashed != ip
        
        # Same IP should produce same hash
        hashed2 = service._hash_ip_address(ip)
        assert hashed == hashed2