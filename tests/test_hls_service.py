"""
Tests for HLS service.
"""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from server.web.app.services.hls_service import HLSService


@pytest.fixture
def hls_service():
    """Create HLS service instance."""
    return HLSService(s3_bucket="test-bucket")


@pytest.fixture
def mock_s3_service():
    """Mock S3 service."""
    s3_mock = AsyncMock()
    s3_mock.upload_file = AsyncMock()
    s3_mock.get_file_content = AsyncMock()
    s3_mock.file_exists = AsyncMock()
    s3_mock.get_public_url = MagicMock()
    s3_mock.list_files_with_prefix = AsyncMock()
    s3_mock.delete_files_with_prefix = AsyncMock()
    return s3_mock


@pytest.fixture
def mock_ffmpeg_service():
    """Mock FFmpeg service."""
    ffmpeg_mock = AsyncMock()
    ffmpeg_mock.generate_hls_segments = AsyncMock()
    return ffmpeg_mock


class TestHLSService:
    """Test cases for HLSService."""
    
    @patch('server.web.app.services.hls_service.VideoS3Service')
    @patch('server.web.app.services.hls_service.FFmpegService')
    async def test_generate_hls_from_video_success(self, mock_ffmpeg_class, mock_s3_class, hls_service):
        """Test successful HLS generation from video."""
        # Setup mocks
        mock_ffmpeg = AsyncMock()
        mock_s3 = AsyncMock()
        mock_ffmpeg_class.return_value = mock_ffmpeg
        mock_s3_class.return_value = mock_s3
        
        hls_service.ffmpeg_service = mock_ffmpeg
        hls_service.s3_service = mock_s3
        
        # Mock FFmpeg response
        mock_ffmpeg.generate_hls_segments.return_value = (
            "/tmp/hls_test/playlist.m3u8",
            ["/tmp/hls_test/segment_000.ts", "/tmp/hls_test/segment_001.ts"]
        )
        
        # Mock cleanup
        with patch.object(hls_service, '_cleanup_temp_directory', new_callable=AsyncMock):
            # Call the method
            manifest_s3_key, segment_s3_keys = await hls_service.generate_hls_from_video(
                "/input.mp4", "test-video-id", "720p_30fps"
            )
        
        # Verify results
        assert manifest_s3_key == "transcoded/test-video-id/720p_30fps/segments/playlist.m3u8"
        assert len(segment_s3_keys) == 2
        assert all("transcoded/test-video-id/720p_30fps/segments/" in key for key in segment_s3_keys)
        
        # Verify S3 uploads
        assert mock_s3.upload_file.call_count == 3  # 1 manifest + 2 segments
    
    async def test_create_master_playlist(self, hls_service):
        """Test master playlist creation."""
        # Mock S3 service
        mock_s3 = AsyncMock()
        hls_service.s3_service = mock_s3
        
        quality_manifests = [
            {
                "quality_preset": "720p_30fps",
                "manifest_s3_key": "transcoded/test-video/720p_30fps/segments/playlist.m3u8",
                "resolution": "1280x720",
                "bitrate": 2500,
                "framerate": 30
            },
            {
                "quality_preset": "480p_30fps",
                "manifest_s3_key": "transcoded/test-video/480p_30fps/segments/playlist.m3u8",
                "resolution": "854x480",
                "bitrate": 1500,
                "framerate": 30
            }
        ]
        
        # Mock file operations
        with patch('builtins.open', create=True) as mock_open, \
             patch('os.unlink') as mock_unlink:
            
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            # Call the method
            master_s3_key = await hls_service.create_master_playlist("test-video", quality_manifests)
        
        # Verify result
        assert master_s3_key == "transcoded/test-video/master.m3u8"
        
        # Verify file operations
        mock_open.assert_called_once()
        mock_file.write.assert_called_once()
        mock_s3.upload_file.assert_called_once()
        mock_unlink.assert_called_once()
        
        # Verify playlist content structure
        written_content = mock_file.write.call_args[0][0]
        assert "#EXTM3U" in written_content
        assert "#EXT-X-VERSION:3" in written_content
        assert "#EXT-X-STREAM-INF" in written_content
        assert "BANDWIDTH=2500000" in written_content
        assert "RESOLUTION=1280x720" in written_content
        assert "720p_30fps/segments/playlist.m3u8" in written_content
    
    async def test_validate_hls_segments_success(self, hls_service):
        """Test successful HLS segment validation."""
        # Mock S3 service
        mock_s3 = AsyncMock()
        hls_service.s3_service = mock_s3
        
        # Mock manifest content
        manifest_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXTINF:6.0,
segment_000.ts
#EXTINF:6.0,
segment_001.ts
#EXT-X-ENDLIST"""
        
        mock_s3.get_file_content.return_value = manifest_content
        mock_s3.file_exists.return_value = True
        
        # Call the method
        result = await hls_service.validate_hls_segments("test/manifest.m3u8")
        
        # Verify result
        assert result is True
        
        # Verify S3 calls
        mock_s3.get_file_content.assert_called_once_with("test/manifest.m3u8")
        assert mock_s3.file_exists.call_count == 2  # 2 segments
    
    async def test_validate_hls_segments_missing_segment(self, hls_service):
        """Test HLS segment validation with missing segment."""
        # Mock S3 service
        mock_s3 = AsyncMock()
        hls_service.s3_service = mock_s3
        
        # Mock manifest content
        manifest_content = """#EXTM3U
#EXT-X-VERSION:3
#EXTINF:6.0,
segment_000.ts
#EXTINF:6.0,
segment_001.ts"""
        
        mock_s3.get_file_content.return_value = manifest_content
        mock_s3.file_exists.side_effect = [True, False]  # Second segment missing
        
        # Call the method
        result = await hls_service.validate_hls_segments("test/manifest.m3u8")
        
        # Verify result
        assert result is False
    
    async def test_get_segment_info(self, hls_service):
        """Test getting segment information from manifest."""
        # Mock S3 service
        mock_s3 = AsyncMock()
        hls_service.s3_service = mock_s3
        
        # Mock manifest content
        manifest_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXTINF:6.0,
segment_000.ts
#EXTINF:5.5,
segment_001.ts
#EXTINF:4.2,
segment_002.ts
#EXT-X-ENDLIST"""
        
        mock_s3.get_file_content.return_value = manifest_content
        
        # Call the method
        info = await hls_service.get_segment_info("test/manifest.m3u8")
        
        # Verify result
        assert info["segment_count"] == 3
        assert info["total_duration"] == 15.7  # 6.0 + 5.5 + 4.2
        assert info["segment_duration"] == 6.0
        assert len(info["segments"]) == 3
        assert info["segments"][0]["filename"] == "segment_000.ts"
        assert info["segments"][0]["duration"] == 6.0
    
    def test_get_streaming_url_with_quality(self, hls_service):
        """Test getting streaming URL for specific quality."""
        # Mock S3 service
        mock_s3 = MagicMock()
        hls_service.s3_service = mock_s3
        mock_s3.get_public_url.return_value = "https://cdn.example.com/video.m3u8"
        
        # Call the method
        url = hls_service.get_streaming_url("test-video", "720p_30fps")
        
        # Verify result
        mock_s3.get_public_url.assert_called_once_with(
            "transcoded/test-video/720p_30fps/segments/playlist.m3u8"
        )
        assert url == "https://cdn.example.com/video.m3u8"
    
    def test_get_streaming_url_master_playlist(self, hls_service):
        """Test getting streaming URL for master playlist."""
        # Mock S3 service
        mock_s3 = MagicMock()
        hls_service.s3_service = mock_s3
        mock_s3.get_public_url.return_value = "https://cdn.example.com/master.m3u8"
        
        # Call the method
        url = hls_service.get_streaming_url("test-video")
        
        # Verify result
        mock_s3.get_public_url.assert_called_once_with("transcoded/test-video/master.m3u8")
        assert url == "https://cdn.example.com/master.m3u8"
    
    async def test_get_available_qualities(self, hls_service):
        """Test getting available quality variants."""
        # Mock S3 service
        mock_s3 = AsyncMock()
        hls_service.s3_service = mock_s3
        
        # Mock S3 file listing
        mock_s3.list_files_with_prefix.return_value = [
            "transcoded/test-video/720p_30fps/segments/playlist.m3u8",
            "transcoded/test-video/720p_30fps/segments/segment_000.ts",
            "transcoded/test-video/480p_30fps/segments/playlist.m3u8",
            "transcoded/test-video/480p_30fps/segments/segment_000.ts"
        ]
        
        mock_s3.get_public_url.return_value = "https://cdn.example.com/playlist.m3u8"
        
        # Call the method
        qualities = await hls_service.get_available_qualities("test-video")
        
        # Verify result
        assert len(qualities) == 2
        
        # Check 720p quality (should be first due to sorting)
        quality_720p = qualities[0]
        assert quality_720p["quality_preset"] == "720p_30fps"
        assert quality_720p["width"] == 1280
        assert quality_720p["height"] == 720
        assert quality_720p["framerate"] == 30
        assert quality_720p["resolution"] == "1280x720"
        
        # Check 480p quality
        quality_480p = qualities[1]
        assert quality_480p["quality_preset"] == "480p_30fps"
        assert quality_480p["height"] == 480
    
    def test_parse_quality_preset_standard(self, hls_service):
        """Test parsing standard quality preset."""
        result = hls_service._parse_quality_preset("720p_30fps")
        
        assert result["width"] == 1280
        assert result["height"] == 720
        assert result["framerate"] == 30
        assert result["resolution"] == "1280x720"
    
    def test_parse_quality_preset_60fps(self, hls_service):
        """Test parsing 60fps quality preset."""
        result = hls_service._parse_quality_preset("1080p_60fps")
        
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert result["framerate"] == 60
        assert result["resolution"] == "1920x1080"
    
    def test_parse_quality_preset_invalid(self, hls_service):
        """Test parsing invalid quality preset returns defaults."""
        result = hls_service._parse_quality_preset("invalid_preset")
        
        assert result["width"] == 1280
        assert result["height"] == 720
        assert result["framerate"] == 30
        assert result["resolution"] == "1280x720"
    
    async def test_cleanup_hls_files_specific_quality(self, hls_service):
        """Test cleaning up HLS files for specific quality."""
        # Mock S3 service
        mock_s3 = AsyncMock()
        hls_service.s3_service = mock_s3
        
        # Call the method
        await hls_service.cleanup_hls_files("test-video", "720p_30fps")
        
        # Verify S3 call
        mock_s3.delete_files_with_prefix.assert_called_once_with(
            "transcoded/test-video/720p_30fps/segments/"
        )
    
    async def test_cleanup_hls_files_all_qualities(self, hls_service):
        """Test cleaning up all HLS files for video."""
        # Mock S3 service
        mock_s3 = AsyncMock()
        hls_service.s3_service = mock_s3
        
        # Call the method
        await hls_service.cleanup_hls_files("test-video")
        
        # Verify S3 call
        mock_s3.delete_files_with_prefix.assert_called_once_with("transcoded/test-video/")


if __name__ == "__main__":
    pytest.main([__file__])