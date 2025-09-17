"""
Tests for Media Import Service.
"""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Mock the video upload service import to avoid dependency issues
with patch.dict('sys.modules', {'server.web.app.services.video_upload_service': Mock()}):
    from server.web.app.services.media_import_service import (
        MediaImportService, ImportConfig, MediaInfo, MediaExtractionError, DownloadResult
    )
from server.web.app.models import ImportJob, ImportPreset, ImportStatus, User


class TestMediaImportService:
    """Test cases for MediaImportService"""
    
    @pytest.fixture
    async def service(self, db_session):
        """Create MediaImportService instance"""
        return MediaImportService(db_session)
    
    @pytest.fixture
    def sample_media_info(self):
        """Sample media info for testing"""
        return MediaInfo(
            title="Test Video",
            description="Test description",
            uploader="Test Uploader",
            upload_date=datetime(2024, 1, 15),
            duration=120.0,
            view_count=1000,
            like_count=50,
            thumbnail_url="https://example.com/thumb.jpg",
            source_url="https://youtube.com/watch?v=test",
            platform="YouTube",
            available_formats=[
                {"format_id": "720p", "ext": "mp4", "resolution": "1280x720"},
                {"format_id": "480p", "ext": "mp4", "resolution": "854x480"}
            ]
        )
    
    @pytest.fixture
    def sample_import_config(self):
        """Sample import config for testing"""
        return ImportConfig(
            max_height=720,
            max_fps=30,
            audio_only=False,
            quality_presets=["720p_30fps"],
            preserve_metadata=True,
            auto_publish=False
        )
    
    def test_is_supported_url(self, service):
        """Test URL platform support detection"""
        # Supported URLs
        assert service.is_supported_url("https://youtube.com/watch?v=test")
        assert service.is_supported_url("https://youtu.be/test")
        assert service.is_supported_url("https://tiktok.com/@user/video/123")
        assert service.is_supported_url("https://instagram.com/p/test")
        assert service.is_supported_url("https://twitter.com/user/status/123")
        assert service.is_supported_url("https://x.com/user/status/123")
        
        # Unsupported URLs
        assert not service.is_supported_url("https://example.com/video")
        assert not service.is_supported_url("https://unsupported.com")
        assert not service.is_supported_url("invalid-url")
    
    def test_extract_platform(self, service):
        """Test platform extraction from URLs"""
        assert service._extract_platform("https://youtube.com/watch?v=test") == "YouTube"
        assert service._extract_platform("https://youtu.be/test") == "YouTube"
        assert service._extract_platform("https://tiktok.com/@user/video/123") == "TikTok"
        assert service._extract_platform("https://instagram.com/p/test") == "Instagram"
        assert service._extract_platform("https://twitter.com/user/status/123") == "Twitter"
        assert service._extract_platform("https://x.com/user/status/123") == "Twitter"
        assert service._extract_platform("https://vimeo.com/123") == "Vimeo"
        assert service._extract_platform("https://example.com") == "example.com"
    
    def test_parse_upload_date(self, service):
        """Test upload date parsing"""
        # Valid date
        date = service._parse_upload_date("20240115")
        assert date == datetime(2024, 1, 15)
        
        # Invalid date
        assert service._parse_upload_date("invalid") is None
        assert service._parse_upload_date(None) is None
        assert service._parse_upload_date("") is None
    
    def test_build_format_selector(self, service):
        """Test yt-dlp format selector building"""
        # Audio only
        config = ImportConfig(audio_only=True)
        assert service._build_format_selector(config) == "bestaudio"
        
        # Video with height limit
        config = ImportConfig(max_height=720)
        assert service._build_format_selector(config) == "best[height<=720]"
        
        # Video with multiple constraints
        config = ImportConfig(max_height=1080, max_fps=30, preferred_codec="h264")
        selector = service._build_format_selector(config)
        assert "height<=1080" in selector
        assert "fps<=30" in selector
        assert "vcodec:h264" in selector
        
        # Default (no constraints)
        config = ImportConfig()
        assert service._build_format_selector(config) == "best"
    
    @patch('asyncio.create_subprocess_exec')
    async def test_extract_media_info_success(self, mock_subprocess, service, sample_media_info):
        """Test successful media info extraction"""
        # Mock subprocess
        mock_process = Mock()
        mock_process.communicate = AsyncMock(return_value=(
            b'{"title": "Test Video", "uploader": "Test Uploader", "duration": 120}',
            b''
        ))
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        # Test extraction
        result = await service.extract_media_info("https://youtube.com/watch?v=test")
        
        assert result.title == "Test Video"
        assert result.uploader == "Test Uploader"
        assert result.duration == 120
        assert result.platform == "YouTube"
    
    @patch('asyncio.create_subprocess_exec')
    async def test_extract_media_info_failure(self, mock_subprocess, service):
        """Test media info extraction failure"""
        # Mock subprocess failure
        mock_process = Mock()
        mock_process.communicate = AsyncMock(return_value=(b'', b'Error message'))
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process
        
        # Test extraction failure
        with pytest.raises(MediaExtractionError):
            await service.extract_media_info("https://youtube.com/watch?v=test")
    
    @patch('asyncio.create_subprocess_exec')
    async def test_download_media_success(self, mock_subprocess, service, sample_import_config):
        """Test successful media download"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
            temp_file.write(b"fake video data")
            temp_path = temp_file.name
        
        try:
            # Mock subprocess
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(b'Download completed', b''))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            # Mock file creation
            with patch('pathlib.Path.glob') as mock_glob:
                mock_file = Mock()
                mock_file.is_file.return_value = True
                mock_file.name = "test_video.mp4"
                mock_glob.return_value = [mock_file]
                
                with patch('str') as mock_str:
                    mock_str.return_value = temp_path
                    
                    # Test download
                    result = await service.download_media(
                        "https://youtube.com/watch?v=test",
                        sample_import_config,
                        os.path.dirname(temp_path)
                    )
                    
                    assert result.success is True
                    assert result.file_path == temp_path
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @patch('asyncio.create_subprocess_exec')
    async def test_download_media_failure(self, mock_subprocess, service, sample_import_config):
        """Test media download failure"""
        # Mock subprocess failure
        mock_process = Mock()
        mock_process.communicate = AsyncMock(return_value=(b'', b'Download failed'))
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process
        
        # Test download failure
        result = await service.download_media(
            "https://youtube.com/watch?v=test",
            sample_import_config
        )
        
        assert result.success is False
        assert "Download failed" in result.error_message
    
    async def test_create_import_job(self, service, sample_import_config, db_session):
        """Test import job creation"""
        # Create test user
        user = User(
            display_label="Test User",
            email="test@example.com"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Mock extract_media_info
        with patch.object(service, 'extract_media_info') as mock_extract:
            mock_extract.return_value = MediaInfo(
                title="Test Video",
                uploader="Test Uploader",
                platform="YouTube",
                source_url="https://youtube.com/watch?v=test"
            )
            
            # Create import job
            job = await service.create_import_job(
                url="https://youtube.com/watch?v=test",
                config=sample_import_config,
                user_id=str(user.id)
            )
            
            assert job.source_url == "https://youtube.com/watch?v=test"
            assert job.platform == "YouTube"
            assert job.status == ImportStatus.queued
            assert job.requested_by == user.id
            assert job.original_title == "Test Video"
            assert job.original_uploader == "Test Uploader"
    
    async def test_create_import_preset(self, service, sample_import_config, db_session):
        """Test import preset creation"""
        # Create test user
        user = User(
            display_label="Test User",
            email="test@example.com"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Create import preset
        preset = await service.create_import_preset(
            name="Test Preset",
            description="Test description",
            config=sample_import_config,
            user_id=str(user.id)
        )
        
        assert preset.name == "Test Preset"
        assert preset.description == "Test description"
        assert preset.created_by == user.id
        assert preset.config == sample_import_config.dict()
    
    async def test_get_import_jobs(self, service, sample_import_config, db_session):
        """Test getting import jobs"""
        # Create test user
        user = User(
            display_label="Test User",
            email="test@example.com"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Create test import job
        job = ImportJob(
            source_url="https://youtube.com/watch?v=test",
            platform="YouTube",
            import_config=sample_import_config.dict(),
            requested_by=user.id,
            status=ImportStatus.queued
        )
        db_session.add(job)
        await db_session.commit()
        
        # Get jobs
        jobs = await service.get_import_jobs(user_id=str(user.id))
        
        assert len(jobs) == 1
        assert jobs[0].source_url == "https://youtube.com/watch?v=test"
        assert jobs[0].requested_by == user.id
    
    async def test_get_import_presets(self, service, sample_import_config, db_session):
        """Test getting import presets"""
        # Create test user
        user = User(
            display_label="Test User",
            email="test@example.com"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Create test import preset
        preset = ImportPreset(
            name="Test Preset",
            description="Test description",
            config=sample_import_config.dict(),
            created_by=user.id
        )
        db_session.add(preset)
        await db_session.commit()
        
        # Get presets
        presets = await service.get_import_presets(user_id=str(user.id))
        
        assert len(presets) == 1
        assert presets[0].name == "Test Preset"
        assert presets[0].created_by == user.id


class TestImportConfig:
    """Test cases for ImportConfig model"""
    
    def test_default_config(self):
        """Test default import configuration"""
        config = ImportConfig()
        
        assert config.max_height is None
        assert config.max_fps is None
        assert config.max_filesize is None
        assert config.audio_only is False
        assert config.audio_format == "mp3"
        assert config.preferred_codec is None
        assert config.quality_presets == []
        assert config.preserve_metadata is True
        assert config.auto_publish is False
        assert config.category is None
    
    def test_audio_only_config(self):
        """Test audio-only import configuration"""
        config = ImportConfig(
            audio_only=True,
            audio_format="flac"
        )
        
        assert config.audio_only is True
        assert config.audio_format == "flac"
    
    def test_quality_limited_config(self):
        """Test quality-limited import configuration"""
        config = ImportConfig(
            max_height=720,
            max_fps=30,
            preferred_codec="h264",
            quality_presets=["720p_30fps", "480p_30fps"]
        )
        
        assert config.max_height == 720
        assert config.max_fps == 30
        assert config.preferred_codec == "h264"
        assert config.quality_presets == ["720p_30fps", "480p_30fps"]


class TestMediaInfo:
    """Test cases for MediaInfo model"""
    
    def test_media_info_creation(self):
        """Test MediaInfo model creation"""
        info = MediaInfo(
            title="Test Video",
            uploader="Test Uploader",
            source_url="https://youtube.com/watch?v=test",
            platform="YouTube"
        )
        
        assert info.title == "Test Video"
        assert info.uploader == "Test Uploader"
        assert info.source_url == "https://youtube.com/watch?v=test"
        assert info.platform == "YouTube"
        assert info.description is None
        assert info.available_formats == []
    
    def test_media_info_with_metadata(self):
        """Test MediaInfo with full metadata"""
        info = MediaInfo(
            title="Test Video",
            description="Test description",
            uploader="Test Uploader",
            upload_date=datetime(2024, 1, 15),
            duration=120.0,
            view_count=1000,
            like_count=50,
            thumbnail_url="https://example.com/thumb.jpg",
            source_url="https://youtube.com/watch?v=test",
            platform="YouTube",
            available_formats=[
                {"format_id": "720p", "ext": "mp4"}
            ]
        )
        
        assert info.description == "Test description"
        assert info.upload_date == datetime(2024, 1, 15)
        assert info.duration == 120.0
        assert info.view_count == 1000
        assert info.like_count == 50
        assert info.thumbnail_url == "https://example.com/thumb.jpg"
        assert len(info.available_formats) == 1