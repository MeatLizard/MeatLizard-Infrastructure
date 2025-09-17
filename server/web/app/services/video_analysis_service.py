"""
Video Analysis Service

Provides video file validation and metadata extraction using FFprobe.
Validates format, size, duration limits and extracts technical metadata.
"""
import os
import json
import asyncio
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile
from server.web.app.services.base_service import BaseService
from server.web.app.config import settings


@dataclass
class VideoAnalysis:
    """Video analysis results"""
    duration_seconds: float
    width: int
    height: int
    framerate: float
    codec: str
    bitrate: int
    format_name: str
    file_size: int
    is_valid: bool
    error_message: Optional[str] = None


class VideoValidationError(Exception):
    """Raised when video validation fails"""
    pass


class VideoAnalysisService(BaseService):
    """Service for video file validation and analysis"""
    
    # Supported video formats
    SUPPORTED_FORMATS = ['mp4', 'mov', 'avi', 'mkv', 'webm']
    SUPPORTED_CODECS = ['h264', 'h265', 'hevc', 'vp8', 'vp9', 'av1']
    
    def __init__(self):
        self.ffprobe_path = self._find_ffprobe()
        
    def _find_ffprobe(self) -> str:
        """Find FFprobe executable"""
        # Try common locations
        possible_paths = [
            'ffprobe',  # In PATH
            '/usr/bin/ffprobe',
            '/usr/local/bin/ffprobe',
            '/opt/homebrew/bin/ffprobe',  # macOS Homebrew
            'C:\\ffmpeg\\bin\\ffprobe.exe',  # Windows
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run([path, '-version'], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=5)
                if result.returncode == 0:
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        raise RuntimeError("FFprobe not found. Please install FFmpeg.")
    
    async def validate_upload_file(self, file: UploadFile) -> bool:
        """
        Validate uploaded file before processing.
        
        Requirements: 1.2, 2.1
        """
        try:
            # Check file extension
            if not file.filename:
                raise VideoValidationError("No filename provided")
            
            extension = file.filename.lower().split('.')[-1]
            if extension not in self.SUPPORTED_FORMATS:
                raise VideoValidationError(
                    f"Unsupported format: {extension}. "
                    f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
                )
            
            # Check file size
            if hasattr(file, 'size') and file.size:
                if file.size > settings.MAX_VIDEO_SIZE:
                    raise VideoValidationError(
                        f"File too large: {file.size / (1024**3):.1f}GB. "
                        f"Maximum size: {settings.MAX_VIDEO_SIZE / (1024**3):.1f}GB"
                    )
            
            # Check MIME type
            if file.content_type and not file.content_type.startswith('video/'):
                raise VideoValidationError(f"Invalid MIME type: {file.content_type}")
            
            return True
            
        except VideoValidationError:
            raise
        except Exception as e:
            raise VideoValidationError(f"Validation error: {str(e)}")
    
    def validate_file_info(self, filename: str, file_size: int, mime_type: str = None) -> bool:
        """
        Validate file information before upload.
        
        Requirements: 1.2, 2.1, 2.2
        """
        try:
            # Check filename
            if not filename:
                raise VideoValidationError("No filename provided")
            
            # Check file extension
            extension = filename.lower().split('.')[-1]
            if extension not in self.SUPPORTED_FORMATS:
                raise VideoValidationError(
                    f"Unsupported format: {extension}. "
                    f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"
                )
            
            # Check file size (max 10GB)
            if file_size > settings.MAX_VIDEO_SIZE:
                raise VideoValidationError(
                    f"File too large: {file_size / (1024**3):.1f}GB. "
                    f"Maximum size: {settings.MAX_VIDEO_SIZE / (1024**3):.1f}GB"
                )
            
            # Check minimum file size (1MB)
            min_size = 1024 * 1024  # 1MB
            if file_size < min_size:
                raise VideoValidationError(f"File too small: {file_size} bytes. Minimum: {min_size} bytes")
            
            # Check MIME type if provided
            if mime_type and not mime_type.startswith('video/'):
                raise VideoValidationError(f"Invalid MIME type: {mime_type}")
            
            return True
            
        except VideoValidationError:
            raise
        except Exception as e:
            raise VideoValidationError(f"Validation error: {str(e)}")
    
    async def analyze_video_file(self, file_path: str) -> VideoAnalysis:
        """
        Analyze video file and extract metadata using FFprobe.
        
        Requirements: 1.2, 2.1, 2.2
        """
        if not os.path.exists(file_path):
            raise VideoValidationError(f"File not found: {file_path}")
        
        try:
            # Run FFprobe to get video information
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "FFprobe failed"
                raise VideoValidationError(f"Failed to analyze video: {error_msg}")
            
            # Parse FFprobe output
            probe_data = json.loads(stdout.decode())
            
            return self._parse_ffprobe_output(probe_data, file_path)
            
        except json.JSONDecodeError as e:
            raise VideoValidationError(f"Failed to parse FFprobe output: {str(e)}")
        except Exception as e:
            raise VideoValidationError(f"Video analysis failed: {str(e)}")
    
    def _parse_ffprobe_output(self, probe_data: Dict[str, Any], file_path: str) -> VideoAnalysis:
        """Parse FFprobe JSON output into VideoAnalysis object"""
        
        try:
            format_info = probe_data.get('format', {})
            streams = probe_data.get('streams', [])
            
            # Find video stream
            video_stream = None
            for stream in streams:
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                raise VideoValidationError("No video stream found in file")
            
            # Extract basic information
            duration = float(format_info.get('duration', 0))
            file_size = int(format_info.get('size', 0))
            format_name = format_info.get('format_name', '')
            
            # Extract video stream information
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            codec = video_stream.get('codec_name', '').lower()
            bitrate = int(video_stream.get('bit_rate', 0))
            
            # Calculate framerate
            framerate = self._calculate_framerate(video_stream)
            
            # Validate extracted data
            self._validate_video_properties(duration, width, height, codec, format_name)
            
            return VideoAnalysis(
                duration_seconds=duration,
                width=width,
                height=height,
                framerate=framerate,
                codec=codec,
                bitrate=bitrate,
                format_name=format_name,
                file_size=file_size,
                is_valid=True
            )
            
        except Exception as e:
            return VideoAnalysis(
                duration_seconds=0,
                width=0,
                height=0,
                framerate=0,
                codec='',
                bitrate=0,
                format_name='',
                file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                is_valid=False,
                error_message=str(e)
            )
    
    def _calculate_framerate(self, video_stream: Dict[str, Any]) -> float:
        """Calculate framerate from video stream data"""
        
        # Try different framerate fields
        framerate_fields = ['r_frame_rate', 'avg_frame_rate', 'time_base']
        
        for field in framerate_fields:
            if field in video_stream:
                framerate_str = video_stream[field]
                if '/' in framerate_str:
                    try:
                        num, den = framerate_str.split('/')
                        if int(den) != 0:
                            return float(num) / float(den)
                    except (ValueError, ZeroDivisionError):
                        continue
                else:
                    try:
                        return float(framerate_str)
                    except ValueError:
                        continue
        
        # Default framerate if none found
        return 30.0
    
    def _validate_video_properties(self, duration: float, width: int, height: int, 
                                 codec: str, format_name: str) -> None:
        """Validate extracted video properties against requirements"""
        
        # Check duration (max 4 hours)
        if duration > settings.MAX_VIDEO_DURATION:
            raise VideoValidationError(
                f"Video too long: {duration/3600:.1f} hours. "
                f"Maximum duration: {settings.MAX_VIDEO_DURATION/3600:.1f} hours"
            )
        
        # Check minimum duration (1 second)
        if duration < 1.0:
            raise VideoValidationError(f"Video too short: {duration:.1f} seconds. Minimum: 1 second")
        
        # Check resolution
        if width < 1 or height < 1:
            raise VideoValidationError(f"Invalid resolution: {width}x{height}")
        
        # Check maximum resolution (8K)
        max_width, max_height = 7680, 4320  # 8K
        if width > max_width or height > max_height:
            raise VideoValidationError(
                f"Resolution too high: {width}x{height}. "
                f"Maximum: {max_width}x{max_height}"
            )
        
        # Check codec support
        if codec and codec not in self.SUPPORTED_CODECS:
            # Warning but not error - we can still transcode
            pass
    
    def get_quality_presets_for_source(self, width: int, height: int, framerate: float) -> List[str]:
        """
        Determine available quality presets based on source video properties.
        
        Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
        """
        presets = []
        
        # Determine source resolution category
        if height >= 1440:  # 1440p or higher
            presets.extend(['480p_30fps', '720p_30fps', '1080p_30fps', '1440p_30fps'])
            if framerate > 50:
                presets.extend(['480p_60fps', '720p_60fps', '1080p_60fps', '1440p_60fps'])
        elif height >= 1080:  # 1080p
            presets.extend(['480p_30fps', '720p_30fps', '1080p_30fps'])
            if framerate > 50:
                presets.extend(['480p_60fps', '720p_60fps', '1080p_60fps'])
        elif height >= 720:  # 720p
            presets.extend(['480p_30fps', '720p_30fps'])
            if framerate > 50:
                presets.extend(['480p_60fps', '720p_60fps'])
        else:  # 480p or lower
            presets.append('480p_30fps')
            if framerate > 50:
                presets.append('480p_60fps')
        
        return presets
    
    def get_resolution_info(self, preset: str) -> Tuple[int, int, int]:
        """Get width, height, and framerate for a quality preset"""
        
        preset_map = {
            '480p_30fps': (854, 480, 30),
            '480p_60fps': (854, 480, 60),
            '720p_30fps': (1280, 720, 30),
            '720p_60fps': (1280, 720, 60),
            '1080p_30fps': (1920, 1080, 30),
            '1080p_60fps': (1920, 1080, 60),
            '1440p_30fps': (2560, 1440, 30),
            '1440p_60fps': (2560, 1440, 60),
        }
        
        return preset_map.get(preset, (1280, 720, 30))  # Default to 720p30
    
    async def validate_and_analyze(self, file_path: str) -> VideoAnalysis:
        """
        Complete validation and analysis workflow.
        
        Requirements: 1.2, 2.1, 2.2
        """
        # First validate file exists and basic properties
        if not os.path.exists(file_path):
            raise VideoValidationError(f"File not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        
        # Validate file info
        self.validate_file_info(filename, file_size)
        
        # Analyze video content
        analysis = await self.analyze_video_file(file_path)
        
        if not analysis.is_valid:
            raise VideoValidationError(analysis.error_message or "Video analysis failed")
        
        return analysis


# Dependency for FastAPI
def get_video_analysis_service() -> VideoAnalysisService:
    return VideoAnalysisService()