"""
Mock implementations for FFmpeg service for testing.
"""
import asyncio
import json
import os
import tempfile
from typing import Dict, List, Optional, Any, AsyncIterator
from unittest.mock import MagicMock, AsyncMock


class MockFFmpegProcess:
    """Mock FFmpeg process for testing."""
    
    def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self.stdout_data = stdout
        self.stderr_data = stderr
        self.stderr = MagicMock()
        self.stderr.readline = AsyncMock()
        
    async def communicate(self):
        """Mock communicate method."""
        # Simulate processing time
        await asyncio.sleep(0.01)
        return self.stdout_data, self.stderr_data
    
    async def wait(self):
        """Mock wait method."""
        await asyncio.sleep(0.01)
        return self.returncode


class MockFFmpegService:
    """Mock implementation of FFmpegService for testing."""
    
    def __init__(self, ffmpeg_path: str = "mock-ffmpeg", ffprobe_path: str = "mock-ffprobe"):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        
        # Configuration for testing
        self.analysis_results: Dict[str, Dict] = {}
        self.transcoding_failure_rate = 0.0
        self.analysis_failure_rate = 0.0
        self.processing_delay = 0.01  # Seconds
        
        # Statistics
        self.analysis_count = 0
        self.transcoding_count = 0
        self.thumbnail_count = 0
        self.hls_generation_count = 0
    
    def set_analysis_result(self, file_path: str, result: Dict):
        """Set mock analysis result for a file."""
        self.analysis_results[file_path] = result
    
    def set_transcoding_failure_rate(self, rate: float):
        """Set transcoding failure rate (0.0 to 1.0)."""
        self.transcoding_failure_rate = max(0.0, min(1.0, rate))
    
    def set_analysis_failure_rate(self, rate: float):
        """Set analysis failure rate (0.0 to 1.0)."""
        self.analysis_failure_rate = max(0.0, min(1.0, rate))
    
    def set_processing_delay(self, delay: float):
        """Set processing delay in seconds."""
        self.processing_delay = max(0.0, delay)
    
    async def analyze_video(self, input_path: str) -> Dict[str, Any]:
        """Mock video analysis."""
        self.analysis_count += 1
        
        # Simulate processing delay
        await asyncio.sleep(self.processing_delay)
        
        # Simulate failure rate
        import random
        if random.random() < self.analysis_failure_rate:
            raise Exception("Mock FFprobe analysis failure")
        
        # Return predefined result or default
        if input_path in self.analysis_results:
            return self.analysis_results[input_path]
        
        # Default mock result
        return {
            "width": 1920,
            "height": 1080,
            "framerate": 30.0,
            "duration": 120.5,
            "bitrate": 5000000,
            "codec": "h264",
            "file_size": 100 * 1024 * 1024,  # 100MB
            "has_audio": True
        }
    
    def _build_ffmpeg_command(self, input_path: str, output_path: str, 
                            target_resolution: str, target_framerate: int, 
                            target_bitrate: int) -> List[str]:
        """Mock FFmpeg command building."""
        return [
            self.ffmpeg_path,
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-maxrate", f"{target_bitrate}k",
            "-bufsize", f"{target_bitrate * 2}k",
            "-vf", f"scale={target_resolution}",
            "-r", str(target_framerate),
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-y",
            output_path
        ]
    
    async def transcode_video(self, input_path: str, output_path: str, 
                            target_resolution: str, target_framerate: int, 
                            target_bitrate: int) -> AsyncIterator[int]:
        """Mock video transcoding with progress."""
        self.transcoding_count += 1
        
        # Simulate failure rate
        import random
        if random.random() < self.transcoding_failure_rate:
            raise Exception("Mock FFmpeg transcoding failure")
        
        # Simulate transcoding progress
        total_frames = 3600  # Mock 2 minutes at 30fps
        frames_per_update = 100
        
        for frame in range(0, total_frames, frames_per_update):
            # Simulate processing time
            await asyncio.sleep(self.processing_delay)
            
            progress = min(100, int((frame / total_frames) * 100))
            yield progress
        
        # Final progress
        yield 100
        
        # Create mock output file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(b"mock transcoded video data")
    
    def _build_hls_command(self, input_path: str, output_dir: str, 
                         segment_duration: int = 6) -> List[str]:
        """Mock HLS command building."""
        return [
            self.ffmpeg_path,
            "-i", input_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-f", "hls",
            "-hls_time", str(segment_duration),
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", f"{output_dir}/segment_%03d.ts",
            f"{output_dir}/playlist.m3u8"
        ]
    
    async def generate_hls_segments(self, input_path: str, output_dir: str, 
                                  segment_duration: int = 6) -> tuple[str, List[str]]:
        """Mock HLS segment generation."""
        self.hls_generation_count += 1
        
        # Simulate processing delay
        await asyncio.sleep(self.processing_delay * 5)  # HLS takes longer
        
        # Simulate failure rate
        import random
        if random.random() < self.transcoding_failure_rate:
            raise Exception("Mock HLS generation failure")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Create mock playlist
        manifest_path = os.path.join(output_dir, "playlist.m3u8")
        playlist_content = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            f"#EXT-X-TARGETDURATION:{segment_duration}",
            "#EXT-X-MEDIA-SEQUENCE:0"
        ]
        
        # Create mock segments
        segment_paths = []
        num_segments = 20  # Mock 20 segments
        
        for i in range(num_segments):
            segment_filename = f"segment_{i:03d}.ts"
            segment_path = os.path.join(output_dir, segment_filename)
            segment_paths.append(segment_path)
            
            # Create mock segment file
            with open(segment_path, 'wb') as f:
                f.write(f"mock segment {i} data".encode())
            
            # Add to playlist
            playlist_content.append(f"#EXTINF:{segment_duration:.1f},")
            playlist_content.append(segment_filename)
        
        playlist_content.append("#EXT-X-ENDLIST")
        
        # Write playlist
        with open(manifest_path, 'w') as f:
            f.write("\n".join(playlist_content))
        
        return manifest_path, segment_paths
    
    async def generate_thumbnails(self, input_path: str, output_dir: str, 
                                timestamps: List[float], width: int = 320, 
                                height: int = 180) -> List[str]:
        """Mock thumbnail generation."""
        self.thumbnail_count += len(timestamps)
        
        # Simulate processing delay
        await asyncio.sleep(self.processing_delay * len(timestamps))
        
        # Simulate failure rate
        import random
        if random.random() < self.transcoding_failure_rate:
            raise Exception("Mock thumbnail generation failure")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        thumbnail_paths = []
        
        for i, timestamp in enumerate(timestamps):
            thumbnail_filename = f"thumb_{i:02d}_{timestamp:.1f}s.jpg"
            thumbnail_path = os.path.join(output_dir, thumbnail_filename)
            thumbnail_paths.append(thumbnail_path)
            
            # Create mock thumbnail file
            with open(thumbnail_path, 'wb') as f:
                f.write(f"mock thumbnail {i} at {timestamp}s".encode())
        
        return thumbnail_paths
    
    async def validate_output(self, output_path: str) -> bool:
        """Mock output validation."""
        # Simulate processing delay
        await asyncio.sleep(self.processing_delay)
        
        # Check if file exists
        if not os.path.exists(output_path):
            return False
        
        # Mock validation - check file size
        file_size = os.path.getsize(output_path)
        return file_size > 0
    
    async def get_file_size(self, file_path: str) -> int:
        """Mock file size retrieval."""
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics for testing."""
        return {
            'analysis_count': self.analysis_count,
            'transcoding_count': self.transcoding_count,
            'thumbnail_count': self.thumbnail_count,
            'hls_generation_count': self.hls_generation_count,
            'transcoding_failure_rate': self.transcoding_failure_rate,
            'analysis_failure_rate': self.analysis_failure_rate
        }
    
    def reset_statistics(self):
        """Reset statistics counters."""
        self.analysis_count = 0
        self.transcoding_count = 0
        self.thumbnail_count = 0
        self.hls_generation_count = 0


class MockFFprobeService:
    """Mock FFprobe service for testing."""
    
    def __init__(self):
        self.probe_results: Dict[str, Dict] = {}
        self.failure_rate = 0.0
        self.processing_delay = 0.01
    
    def set_probe_result(self, file_path: str, result: Dict):
        """Set mock probe result for a file."""
        self.probe_results[file_path] = result
    
    def set_failure_rate(self, rate: float):
        """Set probe failure rate (0.0 to 1.0)."""
        self.failure_rate = max(0.0, min(1.0, rate))
    
    async def probe_file(self, file_path: str) -> Dict[str, Any]:
        """Mock file probing."""
        # Simulate processing delay
        await asyncio.sleep(self.processing_delay)
        
        # Simulate failure rate
        import random
        if random.random() < self.failure_rate:
            raise Exception("Mock FFprobe failure")
        
        # Return predefined result or default
        if file_path in self.probe_results:
            return self.probe_results[file_path]
        
        # Default mock probe result
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
                    "codec_name": "aac",
                    "bit_rate": "128000"
                }
            ],
            "format": {
                "duration": "120.5",
                "size": "104857600",  # 100MB
                "bit_rate": "6989473",
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2"
            }
        }


def create_mock_ffmpeg_service(**kwargs) -> MockFFmpegService:
    """Factory function to create mock FFmpeg service."""
    return MockFFmpegService(**kwargs)


def create_mock_ffprobe_service(**kwargs) -> MockFFprobeService:
    """Factory function to create mock FFprobe service."""
    return MockFFprobeService(**kwargs)


# Utility functions for creating test fixtures

def create_sample_video_analysis() -> Dict[str, Any]:
    """Create sample video analysis result."""
    return {
        "width": 1920,
        "height": 1080,
        "framerate": 30.0,
        "duration": 120.5,
        "bitrate": 5000000,
        "codec": "h264",
        "file_size": 100 * 1024 * 1024,
        "has_audio": True
    }


def create_sample_ffprobe_output() -> Dict[str, Any]:
    """Create sample FFprobe JSON output."""
    return {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30/1",
                "avg_frame_rate": "30/1",
                "bit_rate": "5000000",
                "duration": "120.5"
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "bit_rate": "128000",
                "duration": "120.5"
            }
        ],
        "format": {
            "filename": "/path/to/video.mp4",
            "nb_streams": 2,
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": "120.5",
            "size": "104857600",
            "bit_rate": "6989473"
        }
    }


def create_test_video_formats() -> List[Dict[str, Any]]:
    """Create test video formats for various scenarios."""
    return [
        {
            "name": "1080p_30fps",
            "width": 1920,
            "height": 1080,
            "framerate": 30.0,
            "duration": 120.0,
            "bitrate": 5000000,
            "codec": "h264"
        },
        {
            "name": "720p_60fps",
            "width": 1280,
            "height": 720,
            "framerate": 60.0,
            "duration": 180.0,
            "bitrate": 3000000,
            "codec": "h264"
        },
        {
            "name": "4k_30fps",
            "width": 3840,
            "height": 2160,
            "framerate": 30.0,
            "duration": 300.0,
            "bitrate": 15000000,
            "codec": "h265"
        },
        {
            "name": "480p_30fps",
            "width": 854,
            "height": 480,
            "framerate": 30.0,
            "duration": 60.0,
            "bitrate": 1000000,
            "codec": "h264"
        }
    ]