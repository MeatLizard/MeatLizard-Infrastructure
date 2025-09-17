"""
Comprehensive unit tests for VideoAnalysisService.
"""
import pytest
import asyncio
import os
import json
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path
from fastapi import UploadFile

from server.web.app.services.video_analysis_service import (
    VideoAnalysisService, 
    VideoAnalysis, 
    VideoValidationError
)


@pytest.fixture
def analysis_service():
    """Create VideoAnalysisService instance."""
    with patch.object(VideoAnalysisService, '_find_ffprobe', return_value='ffprobe'):
        return VideoAnalysisService()


@pytest.fixture
def sample_ffprobe_output():
    """Sample FFprobe JSON output for testing."""
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30/1",
                "bit_rate": "5000000"
            },
            {
                "codec_type": "audio",
                "codec_name": "aac"
            }
        ],
        "format": {
            "duration": "120.5",
            "size": "75000000",
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2"
        }
    }


@pytest.fixture
def mock_upload_file():
    """Mock UploadFile for testing."""
    file = MagicMock(spec=UploadFile)
    file.filename = "test_video.mp4"
    file.size = 1024 * 1024 * 100  # 100MB
    file.content_type = "video/mp4"
    return file


class TestVideoAnalysisService:
    """Test cases for VideoAnalysisService."""
    
    def test_find_ffprobe_success(self):
        """Test successful FFprobe detection."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            service = VideoAnalysisService()
            assert service.ffprobe_path == 'ffprobe'
    
    def test_find_ffprobe_not_found(self):
        """Test FFprobe not found error."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="FFprobe not found"):
                VideoAnalysisService()
    
    async def test_validate_upload_file_success(self, analysis_service, mock_upload_file):
        """Test successful upload file validation."""
        with patch('server.web.app.config.settings') as mock_settings:
            mock_settings.MAX_VIDEO_SIZE = 10 * 1024 * 1024 * 1024  # 10GB
            
            result = await analysis_service.validate_upload_file(mock_upload_file)
            assert result is True
    
    async def test_validate_upload_file_no_filename(self, analysis_service):
        """Test upload file validation with no filename."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = None
        
        with pytest.raises(VideoValidationError, match="No filename provided"):
            await analysis_service.validate_upload_file(mock_file)
    
    async def test_validate_upload_file_unsupported_format(self, analysis_service):
        """Test upload file validation with unsupported format."""
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test_video.txt"
        
        with pytest.raises(VideoValidationError, match="Unsupported format"):
            await analysis_service.validate_upload_file(mock_file)
    
    async def test_validate_upload_file_too_large(self, analysis_service, mock_upload_file):
        """Test upload file validation with file too large."""
        with patch('server.web.app.config.settings') as mock_settings:
            mock_settings.MAX_VIDEO_SIZE = 1024 * 1024  # 1MB limit
            mock_upload_file.size = 10 * 1024 * 1024  # 10MB file
            
            with pytest.raises(VideoValidationError, match="File too large"):
                await analysis_service.validate_upload_file(mock_upload_file)
    
    async def test_validate_upload_file_invalid_mime_type(self, analysis_service, mock_upload_file):
        """Test upload file validation with invalid MIME type."""
        mock_upload_file.content_type = "text/plain"
        
        with pytest.raises(VideoValidationError, match="Invalid MIME type"):
            await analysis_service.validate_upload_file(mock_upload_file)
    
    def test_validate_file_info_success(self, analysis_service):
        """Test successful file info validation."""
        with patch('server.web.app.config.settings') as mock_settings:
            mock_settings.MAX_VIDEO_SIZE = 10 * 1024 * 1024 * 1024  # 10GB
            
            result = analysis_service.validate_file_info(
                "test_video.mp4", 
                100 * 1024 * 1024,  # 100MB
                "video/mp4"
            )
            assert result is True
    
    def test_validate_file_info_no_filename(self, analysis_service):
        """Test file info validation with no filename."""
        with pytest.raises(VideoValidationError, match="No filename provided"):
            analysis_service.validate_file_info("", 1024 * 1024)
    
    def test_validate_file_info_unsupported_format(self, analysis_service):
        """Test file info validation with unsupported format."""
        with pytest.raises(VideoValidationError, match="Unsupported format"):
            analysis_service.validate_file_info("test.txt", 1024 * 1024)
    
    def test_validate_file_info_too_large(self, analysis_service):
        """Test file info validation with file too large."""
        with patch('server.web.app.config.settings') as mock_settings:
            mock_settings.MAX_VIDEO_SIZE = 1024 * 1024  # 1MB limit
            
            with pytest.raises(VideoValidationError, match="File too large"):
                analysis_service.validate_file_info("test.mp4", 10 * 1024 * 1024)
    
    def test_validate_file_info_too_small(self, analysis_service):
        """Test file info validation with file too small."""
        with pytest.raises(VideoValidationError, match="File too small"):
            analysis_service.validate_file_info("test.mp4", 1024)  # 1KB (too small)
    
    def test_validate_file_info_invalid_mime_type(self, analysis_service):
        """Test file info validation with invalid MIME type."""
        with pytest.raises(VideoValidationError, match="Invalid MIME type"):
            analysis_service.validate_file_info("test.mp4", 10 * 1024 * 1024, "text/plain")
    
    @patch('os.path.exists')
    @patch('asyncio.create_subprocess_exec')
    async def test_analyze_video_file_success(self, mock_subprocess, mock_exists, 
                                            analysis_service, sample_ffprobe_output):
        """Test successful video file analysis."""
        mock_exists.return_value = True
        
        # Mock FFprobe process
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            json.dumps(sample_ffprobe_output).encode(),
            b""
        )
        mock_subprocess.return_value = mock_process
        
        result = await analysis_service.analyze_video_file("/fake/path.mp4")
        
        # Verify analysis result
        assert isinstance(result, VideoAnalysis)
        assert result.is_valid is True
        assert result.width == 1920
        assert result.height == 1080
        assert result.duration_seconds == 120.5
        assert result.codec == "h264"
        assert result.framerate == 30.0
        assert result.bitrate == 5000000
    
    @patch('os.path.exists')
    async def test_analyze_video_file_not_found(self, mock_exists, analysis_service):
        """Test video file analysis with file not found."""
        mock_exists.return_value = False
        
        with pytest.raises(VideoValidationError, match="File not found"):
            await analysis_service.analyze_video_file("/fake/path.mp4")
    
    @patch('os.path.exists')
    @patch('asyncio.create_subprocess_exec')
    async def test_analyze_video_file_ffprobe_error(self, mock_subprocess, mock_exists, analysis_service):
        """Test video file analysis with FFprobe error."""
        mock_exists.return_value = True
        
        # Mock FFprobe process failure
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"FFprobe error")
        mock_subprocess.return_value = mock_process
        
        with pytest.raises(VideoValidationError, match="Failed to analyze video"):
            await analysis_service.analyze_video_file("/fake/path.mp4")
    
    @patch('os.path.exists')
    @patch('asyncio.create_subprocess_exec')
    async def test_analyze_video_file_invalid_json(self, mock_subprocess, mock_exists, analysis_service):
        """Test video file analysis with invalid JSON output."""
        mock_exists.return_value = True
        
        # Mock FFprobe process with invalid JSON
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"invalid json", b"")
        mock_subprocess.return_value = mock_process
        
        with pytest.raises(VideoValidationError, match="Failed to parse FFprobe output"):
            await analysis_service.analyze_video_file("/fake/path.mp4")
    
    def test_parse_ffprobe_output_success(self, analysis_service, sample_ffprobe_output):
        """Test successful FFprobe output parsing."""
        with patch('os.path.getsize', return_value=75000000):
            result = analysis_service._parse_ffprobe_output(sample_ffprobe_output, "/fake/path.mp4")
            
            assert result.is_valid is True
            assert result.width == 1920
            assert result.height == 1080
            assert result.duration_seconds == 120.5
            assert result.codec == "h264"
            assert result.framerate == 30.0
            assert result.bitrate == 5000000
            assert result.file_size == 75000000
    
    def test_parse_ffprobe_output_no_video_stream(self, analysis_service):
        """Test FFprobe output parsing with no video stream."""
        ffprobe_output = {
            "streams": [
                {"codec_type": "audio", "codec_name": "aac"}
            ],
            "format": {"duration": "120.5", "size": "75000000"}
        }
        
        with patch('os.path.getsize', return_value=75000000):
            result = analysis_service._parse_ffprobe_output(ffprobe_output, "/fake/path.mp4")
            
            assert result.is_valid is False
            assert "No video stream found" in result.error_message
    
    def test_parse_ffprobe_output_invalid_data(self, analysis_service):
        """Test FFprobe output parsing with invalid data."""
        ffprobe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": "invalid",  # Invalid width
                    "height": 1080
                }
            ],
            "format": {"duration": "120.5", "size": "75000000"}
        }
        
        with patch('os.path.getsize', return_value=75000000):
            result = analysis_service._parse_ffprobe_output(ffprobe_output, "/fake/path.mp4")
            
            assert result.is_valid is False
            assert result.error_message is not None
    
    def test_calculate_framerate_r_frame_rate(self, analysis_service):
        """Test framerate calculation from r_frame_rate."""
        video_stream = {"r_frame_rate": "30/1"}
        
        result = analysis_service._calculate_framerate(video_stream)
        assert result == 30.0
    
    def test_calculate_framerate_avg_frame_rate(self, analysis_service):
        """Test framerate calculation from avg_frame_rate."""
        video_stream = {"avg_frame_rate": "25/1"}
        
        result = analysis_service._calculate_framerate(video_stream)
        assert result == 25.0
    
    def test_calculate_framerate_60fps(self, analysis_service):
        """Test framerate calculation for 60fps."""
        video_stream = {"r_frame_rate": "60/1"}
        
        result = analysis_service._calculate_framerate(video_stream)
        assert result == 60.0
    
    def test_calculate_framerate_fractional(self, analysis_service):
        """Test framerate calculation with fractional values."""
        video_stream = {"r_frame_rate": "30000/1001"}  # ~29.97 fps
        
        result = analysis_service._calculate_framerate(video_stream)
        assert abs(result - 29.97) < 0.1
    
    def test_calculate_framerate_invalid(self, analysis_service):
        """Test framerate calculation with invalid data."""
        video_stream = {"r_frame_rate": "invalid/data"}
        
        result = analysis_service._calculate_framerate(video_stream)
        assert result == 30.0  # Default value
    
    def test_calculate_framerate_no_data(self, analysis_service):
        """Test framerate calculation with no framerate data."""
        video_stream = {}
        
        result = analysis_service._calculate_framerate(video_stream)
        assert result == 30.0  # Default value
    
    def test_validate_video_properties_success(self, analysis_service):
        """Test successful video properties validation."""
        with patch('server.web.app.config.settings') as mock_settings:
            mock_settings.MAX_VIDEO_DURATION = 4 * 3600  # 4 hours
            
            # Should not raise exception
            analysis_service._validate_video_properties(
                duration=120.0,
                width=1920,
                height=1080,
                codec="h264",
                format_name="mp4"
            )
    
    def test_validate_video_properties_too_long(self, analysis_service):
        """Test video properties validation with video too long."""
        with patch('server.web.app.config.settings') as mock_settings:
            mock_settings.MAX_VIDEO_DURATION = 3600  # 1 hour
            
            with pytest.raises(VideoValidationError, match="Video too long"):
                analysis_service._validate_video_properties(
                    duration=7200.0,  # 2 hours
                    width=1920,
                    height=1080,
                    codec="h264",
                    format_name="mp4"
                )
    
    def test_validate_video_properties_too_short(self, analysis_service):
        """Test video properties validation with video too short."""
        with pytest.raises(VideoValidationError, match="Video too short"):
            analysis_service._validate_video_properties(
                duration=0.5,  # 0.5 seconds
                width=1920,
                height=1080,
                codec="h264",
                format_name="mp4"
            )
    
    def test_validate_video_properties_invalid_resolution(self, analysis_service):
        """Test video properties validation with invalid resolution."""
        with pytest.raises(VideoValidationError, match="Invalid resolution"):
            analysis_service._validate_video_properties(
                duration=120.0,
                width=0,  # Invalid width
                height=1080,
                codec="h264",
                format_name="mp4"
            )
    
    def test_validate_video_properties_resolution_too_high(self, analysis_service):
        """Test video properties validation with resolution too high."""
        with pytest.raises(VideoValidationError, match="Resolution too high"):
            analysis_service._validate_video_properties(
                duration=120.0,
                width=8000,  # Too high
                height=4500,  # Too high
                codec="h264",
                format_name="mp4"
            )
    
    def test_get_quality_presets_for_source_1440p_30fps(self, analysis_service):
        """Test quality presets for 1440p 30fps source."""
        presets = analysis_service.get_quality_presets_for_source(2560, 1440, 30.0)
        
        expected = ['480p_30fps', '720p_30fps', '1080p_30fps', '1440p_30fps']
        assert presets == expected
    
    def test_get_quality_presets_for_source_1440p_60fps(self, analysis_service):
        """Test quality presets for 1440p 60fps source."""
        presets = analysis_service.get_quality_presets_for_source(2560, 1440, 60.0)
        
        expected = [
            '480p_30fps', '720p_30fps', '1080p_30fps', '1440p_30fps',
            '480p_60fps', '720p_60fps', '1080p_60fps', '1440p_60fps'
        ]
        assert presets == expected
    
    def test_get_quality_presets_for_source_1080p_30fps(self, analysis_service):
        """Test quality presets for 1080p 30fps source."""
        presets = analysis_service.get_quality_presets_for_source(1920, 1080, 30.0)
        
        expected = ['480p_30fps', '720p_30fps', '1080p_30fps']
        assert presets == expected
    
    def test_get_quality_presets_for_source_1080p_60fps(self, analysis_service):
        """Test quality presets for 1080p 60fps source."""
        presets = analysis_service.get_quality_presets_for_source(1920, 1080, 60.0)
        
        expected = [
            '480p_30fps', '720p_30fps', '1080p_30fps',
            '480p_60fps', '720p_60fps', '1080p_60fps'
        ]
        assert presets == expected
    
    def test_get_quality_presets_for_source_720p_30fps(self, analysis_service):
        """Test quality presets for 720p 30fps source."""
        presets = analysis_service.get_quality_presets_for_source(1280, 720, 30.0)
        
        expected = ['480p_30fps', '720p_30fps']
        assert presets == expected
    
    def test_get_quality_presets_for_source_720p_60fps(self, analysis_service):
        """Test quality presets for 720p 60fps source."""
        presets = analysis_service.get_quality_presets_for_source(1280, 720, 60.0)
        
        expected = ['480p_30fps', '720p_30fps', '480p_60fps', '720p_60fps']
        assert presets == expected
    
    def test_get_quality_presets_for_source_480p_30fps(self, analysis_service):
        """Test quality presets for 480p 30fps source."""
        presets = analysis_service.get_quality_presets_for_source(854, 480, 30.0)
        
        expected = ['480p_30fps']
        assert presets == expected
    
    def test_get_quality_presets_for_source_480p_60fps(self, analysis_service):
        """Test quality presets for 480p 60fps source."""
        presets = analysis_service.get_quality_presets_for_source(854, 480, 60.0)
        
        expected = ['480p_30fps', '480p_60fps']
        assert presets == expected
    
    def test_get_resolution_info_480p_30fps(self, analysis_service):
        """Test resolution info for 480p 30fps."""
        width, height, framerate = analysis_service.get_resolution_info('480p_30fps')
        
        assert width == 854
        assert height == 480
        assert framerate == 30
    
    def test_get_resolution_info_720p_60fps(self, analysis_service):
        """Test resolution info for 720p 60fps."""
        width, height, framerate = analysis_service.get_resolution_info('720p_60fps')
        
        assert width == 1280
        assert height == 720
        assert framerate == 60
    
    def test_get_resolution_info_1080p_30fps(self, analysis_service):
        """Test resolution info for 1080p 30fps."""
        width, height, framerate = analysis_service.get_resolution_info('1080p_30fps')
        
        assert width == 1920
        assert height == 1080
        assert framerate == 30
    
    def test_get_resolution_info_1440p_60fps(self, analysis_service):
        """Test resolution info for 1440p 60fps."""
        width, height, framerate = analysis_service.get_resolution_info('1440p_60fps')
        
        assert width == 2560
        assert height == 1440
        assert framerate == 60
    
    def test_get_resolution_info_unknown_preset(self, analysis_service):
        """Test resolution info for unknown preset."""
        width, height, framerate = analysis_service.get_resolution_info('unknown_preset')
        
        # Should return default 720p 30fps
        assert width == 1280
        assert height == 720
        assert framerate == 30
    
    @patch('os.path.exists')
    @patch('os.path.getsize')
    async def test_validate_and_analyze_success(self, mock_getsize, mock_exists, analysis_service):
        """Test successful complete validation and analysis."""
        mock_exists.return_value = True
        mock_getsize.return_value = 100 * 1024 * 1024  # 100MB
        
        # Mock the analysis method
        mock_analysis = VideoAnalysis(
            duration_seconds=120.0,
            width=1920,
            height=1080,
            framerate=30.0,
            codec="h264",
            bitrate=5000000,
            format_name="mp4",
            file_size=100 * 1024 * 1024,
            is_valid=True
        )
        analysis_service.analyze_video_file = AsyncMock(return_value=mock_analysis)
        
        with patch('server.web.app.config.settings') as mock_settings:
            mock_settings.MAX_VIDEO_SIZE = 10 * 1024 * 1024 * 1024  # 10GB
            
            result = await analysis_service.validate_and_analyze("/fake/test_video.mp4")
            
            assert result.is_valid is True
            assert result.width == 1920
            assert result.height == 1080
    
    @patch('os.path.exists')
    async def test_validate_and_analyze_file_not_found(self, mock_exists, analysis_service):
        """Test validation and analysis with file not found."""
        mock_exists.return_value = False
        
        with pytest.raises(VideoValidationError, match="File not found"):
            await analysis_service.validate_and_analyze("/fake/nonexistent.mp4")
    
    @patch('os.path.exists')
    @patch('os.path.getsize')
    async def test_validate_and_analyze_invalid_analysis(self, mock_getsize, mock_exists, analysis_service):
        """Test validation and analysis with invalid analysis result."""
        mock_exists.return_value = True
        mock_getsize.return_value = 100 * 1024 * 1024  # 100MB
        
        # Mock invalid analysis
        mock_analysis = VideoAnalysis(
            duration_seconds=0,
            width=0,
            height=0,
            framerate=0,
            codec="",
            bitrate=0,
            format_name="",
            file_size=0,
            is_valid=False,
            error_message="Analysis failed"
        )
        analysis_service.analyze_video_file = AsyncMock(return_value=mock_analysis)
        
        with patch('server.web.app.config.settings') as mock_settings:
            mock_settings.MAX_VIDEO_SIZE = 10 * 1024 * 1024 * 1024  # 10GB
            
            with pytest.raises(VideoValidationError, match="Analysis failed"):
                await analysis_service.validate_and_analyze("/fake/test_video.mp4")


class TestVideoAnalysis:
    """Test cases for VideoAnalysis dataclass."""
    
    def test_video_analysis_creation(self):
        """Test VideoAnalysis creation."""
        analysis = VideoAnalysis(
            duration_seconds=120.0,
            width=1920,
            height=1080,
            framerate=30.0,
            codec="h264",
            bitrate=5000000,
            format_name="mp4",
            file_size=100000000,
            is_valid=True
        )
        
        assert analysis.duration_seconds == 120.0
        assert analysis.width == 1920
        assert analysis.height == 1080
        assert analysis.framerate == 30.0
        assert analysis.codec == "h264"
        assert analysis.bitrate == 5000000
        assert analysis.format_name == "mp4"
        assert analysis.file_size == 100000000
        assert analysis.is_valid is True
        assert analysis.error_message is None
    
    def test_video_analysis_with_error(self):
        """Test VideoAnalysis creation with error."""
        analysis = VideoAnalysis(
            duration_seconds=0,
            width=0,
            height=0,
            framerate=0,
            codec="",
            bitrate=0,
            format_name="",
            file_size=0,
            is_valid=False,
            error_message="Test error"
        )
        
        assert analysis.is_valid is False
        assert analysis.error_message == "Test error"


class TestVideoValidationError:
    """Test cases for VideoValidationError exception."""
    
    def test_video_validation_error_creation(self):
        """Test VideoValidationError creation."""
        error = VideoValidationError("Test error message")
        
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


if __name__ == "__main__":
    pytest.main([__file__])