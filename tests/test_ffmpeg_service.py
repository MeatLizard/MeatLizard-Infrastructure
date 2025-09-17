"""
Tests for FFmpeg service.
"""
import pytest
import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from server.web.app.services.ffmpeg_service import FFmpegService


@pytest.fixture
def ffmpeg_service():
    """Create FFmpeg service instance."""
    return FFmpegService(ffmpeg_path="ffmpeg", ffprobe_path="ffprobe")


@pytest.fixture
def temp_video_file():
    """Create a temporary video file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        # Write some dummy data
        f.write(b"fake video data")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestFFmpegService:
    """Test cases for FFmpegService."""
    
    @patch('asyncio.create_subprocess_exec')
    async def test_analyze_video_success(self, mock_subprocess, ffmpeg_service):
        """Test successful video analysis."""
        # Mock FFprobe output
        probe_output = {
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                    "codec_name": "h264"
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac"
                }
            ],
            "format": {
                "duration": "120.5",
                "bit_rate": "5000000",
                "size": "75000000"
            }
        }
        
        # Mock process
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            str(probe_output).replace("'", '"').encode(),
            b""
        )
        mock_subprocess.return_value = mock_process
        
        # Call the method
        with patch('json.loads', return_value=probe_output):
            result = await ffmpeg_service.analyze_video("/fake/path.mp4")
        
        # Verify result
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert result["framerate"] == 30.0
        assert result["duration"] == 120.5
        assert result["bitrate"] == 5000000
        assert result["codec"] == "h264"
        assert result["file_size"] == 75000000
        assert result["has_audio"] is True
    
    @patch('asyncio.create_subprocess_exec')
    async def test_analyze_video_failure(self, mock_subprocess, ffmpeg_service):
        """Test video analysis failure."""
        # Mock failed process
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"FFprobe error")
        mock_subprocess.return_value = mock_process
        
        # Call the method and expect exception
        with pytest.raises(Exception, match="FFprobe failed"):
            await ffmpeg_service.analyze_video("/fake/path.mp4")
    
    def test_build_ffmpeg_command(self, ffmpeg_service):
        """Test FFmpeg command generation."""
        cmd = ffmpeg_service._build_ffmpeg_command(
            input_path="/input.mp4",
            output_path="/output.mp4",
            target_resolution="1280x720",
            target_framerate=30,
            target_bitrate=2500
        )
        
        # Verify command structure
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert "/input.mp4" in cmd
        assert "/output.mp4" in cmd
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-maxrate" in cmd
        assert "2500k" in cmd
        assert "-r" in cmd
        assert "30" in cmd
    
    @patch('asyncio.create_subprocess_exec')
    @patch('server.web.app.services.ffmpeg_service.FFmpegService.analyze_video')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('os.path.getsize')
    async def test_transcode_video_success(self, mock_getsize, mock_exists, 
                                         mock_makedirs, mock_analyze, 
                                         mock_subprocess, ffmpeg_service):
        """Test successful video transcoding."""
        # Mock video analysis
        mock_analyze.return_value = {"duration": 100.0}
        
        # Mock file operations
        mock_exists.return_value = True
        mock_getsize.return_value = 1024000
        
        # Mock FFmpeg process with progress output
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        
        # Mock stderr output with progress
        progress_lines = [
            b"frame=  100 fps= 25 q=23.0 size=    1024kB time=00:00:04.00 bitrate=2097.2kbits/s speed=   1x\n",
            b"frame=  500 fps= 25 q=23.0 size=    5120kB time=00:00:20.00 bitrate=2097.2kbits/s speed=   1x\n",
            b"frame= 2500 fps= 25 q=23.0 size=   25600kB time=00:01:40.00 bitrate=2097.2kbits/s speed=   1x\n",
            b""  # End of output
        ]
        
        async def mock_readline():
            for line in progress_lines:
                yield line
        
        mock_process.stderr.readline = AsyncMock(side_effect=mock_readline().__anext__)
        mock_subprocess.return_value = mock_process
        
        # Call the method
        progress_values = []
        async for progress in ffmpeg_service.transcode_video(
            "/input.mp4", "/output.mp4", "1280x720", 30, 2500
        ):
            progress_values.append(progress)
        
        # Verify progress was reported
        assert len(progress_values) > 0
        assert progress_values[-1] == 100  # Final progress should be 100%
    
    def test_build_hls_command(self, ffmpeg_service):
        """Test HLS command generation."""
        cmd = ffmpeg_service._build_hls_command(
            input_path="/input.mp4",
            output_dir="/output",
            segment_duration=6
        )
        
        # Verify command structure
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert "/input.mp4" in cmd
        assert "-f" in cmd
        assert "hls" in cmd
        assert "-hls_time" in cmd
        assert "6" in cmd
        assert "/output/playlist.m3u8" in cmd
    
    @patch('asyncio.create_subprocess_exec')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('os.listdir')
    async def test_generate_hls_segments_success(self, mock_listdir, mock_exists, 
                                               mock_makedirs, mock_subprocess, 
                                               ffmpeg_service):
        """Test successful HLS segment generation."""
        # Mock file operations
        mock_exists.return_value = True
        mock_listdir.return_value = ["segment_000.ts", "segment_001.ts", "segment_002.ts"]
        
        # Mock FFmpeg process
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process
        
        # Call the method
        manifest_path, segment_paths = await ffmpeg_service.generate_hls_segments(
            "/input.mp4", "/output"
        )
        
        # Verify results
        assert manifest_path == "/output/playlist.m3u8"
        assert len(segment_paths) == 3
        assert all(path.endswith(".ts") for path in segment_paths)
    
    @patch('asyncio.create_subprocess_exec')
    @patch('os.makedirs')
    async def test_generate_thumbnails_success(self, mock_makedirs, mock_subprocess, 
                                             ffmpeg_service):
        """Test successful thumbnail generation."""
        # Mock FFmpeg processes (one for each thumbnail)
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = mock_process
        
        # Mock file existence
        with patch('os.path.exists', return_value=True):
            # Call the method
            thumbnail_paths = await ffmpeg_service.generate_thumbnails(
                "/input.mp4", "/output", [10.0, 30.0, 60.0]
            )
        
        # Verify results
        assert len(thumbnail_paths) == 3
        assert all("thumb_" in path for path in thumbnail_paths)
    
    @patch('server.web.app.services.ffmpeg_service.FFmpegService.analyze_video')
    async def test_validate_output_success(self, mock_analyze, ffmpeg_service):
        """Test successful output validation."""
        # Mock successful analysis
        mock_analyze.return_value = {"duration": 100.0, "width": 1280}
        
        # Call the method
        result = await ffmpeg_service.validate_output("/output.mp4")
        
        # Verify result
        assert result is True
    
    @patch('server.web.app.services.ffmpeg_service.FFmpegService.analyze_video')
    async def test_validate_output_failure(self, mock_analyze, ffmpeg_service):
        """Test output validation failure."""
        # Mock failed analysis
        mock_analyze.side_effect = Exception("Invalid video")
        
        # Call the method
        result = await ffmpeg_service.validate_output("/output.mp4")
        
        # Verify result
        assert result is False
    
    @patch('os.path.getsize')
    async def test_get_file_size_success(self, mock_getsize, ffmpeg_service):
        """Test successful file size retrieval."""
        mock_getsize.return_value = 1024000
        
        result = await ffmpeg_service.get_file_size("/test.mp4")
        
        assert result == 1024000
    
    @patch('os.path.getsize')
    async def test_get_file_size_failure(self, mock_getsize, ffmpeg_service):
        """Test file size retrieval failure."""
        mock_getsize.side_effect = OSError("File not found")
        
        result = await ffmpeg_service.get_file_size("/test.mp4")
        
        assert result == 0


if __name__ == "__main__":
    pytest.main([__file__])