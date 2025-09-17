"""
FFmpeg integration service for video transcoding and HLS generation.
"""
import asyncio
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, AsyncIterator

from server.web.app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class FFmpegService(BaseService):
    """Service for FFmpeg video processing operations."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        
    async def analyze_video(self, input_path: str) -> Dict[str, any]:
        """Analyze video file and extract metadata."""
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                input_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"FFprobe failed: {stderr.decode()}")
            
            probe_data = json.loads(stdout.decode())
            
            # Extract video stream info
            video_stream = None
            audio_stream = None
            
            for stream in probe_data.get("streams", []):
                if stream.get("codec_type") == "video" and video_stream is None:
                    video_stream = stream
                elif stream.get("codec_type") == "audio" and audio_stream is None:
                    audio_stream = stream
            
            if not video_stream:
                raise Exception("No video stream found")
            
            # Parse video properties
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            
            # Parse framerate
            fps_str = video_stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                framerate = float(num) / float(den) if float(den) != 0 else 30.0
            else:
                framerate = float(fps_str)
            
            # Parse duration
            duration = float(probe_data.get("format", {}).get("duration", 0))
            
            # Parse bitrate
            bitrate = int(probe_data.get("format", {}).get("bit_rate", 0))
            
            return {
                "width": width,
                "height": height,
                "framerate": framerate,
                "duration": duration,
                "bitrate": bitrate,
                "codec": video_stream.get("codec_name"),
                "file_size": int(probe_data.get("format", {}).get("size", 0)),
                "has_audio": audio_stream is not None
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze video {input_path}: {e}")
            raise
    
    def _build_ffmpeg_command(self, input_path: str, output_path: str, 
                             target_resolution: str, target_framerate: int, 
                             target_bitrate: int, preset: str = "medium") -> List[str]:
        """Build FFmpeg command for transcoding."""
        width, height = map(int, target_resolution.split("x"))
        
        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", "23",
            "-maxrate", f"{target_bitrate}k",
            "-bufsize", f"{target_bitrate * 2}k",
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-r", str(target_framerate),
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
            "-movflags", "+faststart",
            "-f", "mp4",
            "-y",  # Overwrite output file
            output_path
        ]
        
        return cmd
    
    async def transcode_video(self, input_path: str, output_path: str,
                            target_resolution: str, target_framerate: int,
                            target_bitrate: int) -> AsyncIterator[int]:
        """
        Transcode video and yield progress percentage.
        """
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Get video duration for progress calculation
            video_info = await self.analyze_video(input_path)
            total_duration = video_info["duration"]
            
            cmd = self._build_ffmpeg_command(
                input_path, output_path, target_resolution, 
                target_framerate, target_bitrate
            )
            
            logger.info(f"Starting transcoding: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Monitor progress
            progress_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")
            
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                
                line_str = line.decode().strip()
                
                # Parse progress from FFmpeg output
                match = progress_pattern.search(line_str)
                if match and total_duration > 0:
                    hours, minutes, seconds = match.groups()
                    current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                    progress = min(100, int((current_time / total_duration) * 100))
                    yield progress
            
            await process.wait()
            
            if process.returncode != 0:
                stderr_output = await process.stderr.read()
                raise Exception(f"FFmpeg failed with code {process.returncode}: {stderr_output.decode()}")
            
            # Verify output file exists and has content
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise Exception("Output file was not created or is empty")
            
            yield 100  # Final progress
            
        except Exception as e:
            logger.error(f"Transcoding failed for {input_path}: {e}")
            raise
    
    def _build_hls_command(self, input_path: str, output_dir: str, 
                          segment_duration: int = 6) -> List[str]:
        """Build FFmpeg command for HLS segmentation."""
        playlist_path = os.path.join(output_dir, "playlist.m3u8")
        segment_pattern = os.path.join(output_dir, "segment_%03d.ts")
        
        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-c", "copy",  # Copy streams without re-encoding
            "-f", "hls",
            "-hls_time", str(segment_duration),
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", segment_pattern,
            "-y",
            playlist_path
        ]
        
        return cmd
    
    async def generate_hls_segments(self, input_path: str, output_dir: str,
                                  segment_duration: int = 6) -> Tuple[str, List[str]]:
        """
        Generate HLS segments and manifest from transcoded video.
        Returns tuple of (manifest_path, segment_paths).
        """
        try:
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            cmd = self._build_hls_command(input_path, output_dir, segment_duration)
            
            logger.info(f"Generating HLS segments: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"HLS generation failed: {stderr.decode()}")
            
            # Collect generated files
            manifest_path = os.path.join(output_dir, "playlist.m3u8")
            segment_paths = []
            
            if not os.path.exists(manifest_path):
                raise Exception("HLS manifest was not created")
            
            # Find all segment files
            for file in os.listdir(output_dir):
                if file.endswith(".ts"):
                    segment_paths.append(os.path.join(output_dir, file))
            
            segment_paths.sort()  # Ensure proper order
            
            if not segment_paths:
                raise Exception("No HLS segments were created")
            
            logger.info(f"Generated HLS manifest and {len(segment_paths)} segments")
            return manifest_path, segment_paths
            
        except Exception as e:
            logger.error(f"HLS generation failed for {input_path}: {e}")
            raise
    
    async def generate_thumbnails(self, input_path: str, output_dir: str,
                                timestamps: List[float], width: int = 320, 
                                height: int = 180) -> List[str]:
        """Generate thumbnail images at specified timestamps."""
        try:
            os.makedirs(output_dir, exist_ok=True)
            thumbnail_paths = []
            
            for i, timestamp in enumerate(timestamps):
                output_path = os.path.join(output_dir, f"thumb_{i:02d}.jpg")
                
                cmd = [
                    self.ffmpeg_path,
                    "-ss", str(timestamp),
                    "-i", input_path,
                    "-vframes", "1",
                    "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                    "-q:v", "2",
                    "-y",
                    output_path
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                await process.communicate()
                
                if process.returncode == 0 and os.path.exists(output_path):
                    thumbnail_paths.append(output_path)
                else:
                    logger.warning(f"Failed to generate thumbnail at {timestamp}s")
            
            return thumbnail_paths
            
        except Exception as e:
            logger.error(f"Thumbnail generation failed for {input_path}: {e}")
            raise
    
    async def validate_output(self, file_path: str) -> bool:
        """Validate that the output file is a valid video."""
        try:
            video_info = await self.analyze_video(file_path)
            return video_info["duration"] > 0 and video_info["width"] > 0
        except Exception:
            return False
    
    async def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes."""
        try:
            return os.path.getsize(file_path)
        except Exception:
            return 0