"""
HLS (HTTP Live Streaming) service for adaptive video streaming.
"""
import os
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from server.web.app.services.base_service import BaseService
from server.web.app.services.video_s3_service import VideoS3Service
from server.web.app.services.ffmpeg_service import FFmpegService

logger = logging.getLogger(__name__)

class HLSService(BaseService):
    """Service for HLS manifest and segment management."""
    
    def __init__(self, s3_bucket: str = "meatlizard-video-storage"):
        self.s3_service = VideoS3Service(s3_bucket)
        self.ffmpeg_service = FFmpegService()
        
    async def generate_hls_from_video(self, input_path: str, video_id: str, 
                                    quality_preset: str, segment_duration: int = 6) -> Tuple[str, List[str]]:
        """
        Generate HLS segments and manifest from a video file.
        Returns tuple of (manifest_s3_key, segment_s3_keys).
        """
        try:
            # Create temporary directory for HLS output
            temp_dir = f"/tmp/hls_{video_id}_{quality_preset}"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Generate HLS segments using FFmpeg
            manifest_path, segment_paths = await self.ffmpeg_service.generate_hls_segments(
                input_path, temp_dir, segment_duration
            )
            
            # Upload manifest and segments to S3
            base_s3_key = f"transcoded/{video_id}/{quality_preset}/segments"
            
            # Upload manifest
            manifest_s3_key = f"{base_s3_key}/playlist.m3u8"
            await self.s3_service.upload_file(manifest_path, manifest_s3_key)
            
            # Upload segments
            segment_s3_keys = []
            for segment_path in segment_paths:
                segment_name = os.path.basename(segment_path)
                segment_s3_key = f"{base_s3_key}/{segment_name}"
                await self.s3_service.upload_file(segment_path, segment_s3_key)
                segment_s3_keys.append(segment_s3_key)
            
            # Clean up temporary files
            await self._cleanup_temp_directory(temp_dir)
            
            logger.info(f"Generated HLS for video {video_id}, quality {quality_preset}: "
                       f"manifest and {len(segment_s3_keys)} segments")
            
            return manifest_s3_key, segment_s3_keys
            
        except Exception as e:
            logger.error(f"Failed to generate HLS for video {video_id}: {e}")
            raise
    
    async def create_master_playlist(self, video_id: str, quality_manifests: List[Dict[str, any]]) -> str:
        """
        Create master playlist that references multiple quality variants.
        
        Args:
            video_id: Video identifier
            quality_manifests: List of dicts with keys: quality_preset, manifest_s3_key, 
                             resolution, bitrate, framerate
        
        Returns:
            S3 key of the master playlist
        """
        try:
            # Generate master playlist content
            playlist_content = "#EXTM3U\n#EXT-X-VERSION:3\n\n"
            
            for manifest in quality_manifests:
                resolution = manifest["resolution"]  # e.g., "1280x720"
                bitrate = manifest["bitrate"] * 1000  # Convert to bits per second
                framerate = manifest.get("framerate", 30)
                
                # Add stream info
                playlist_content += f"#EXT-X-STREAM-INF:BANDWIDTH={bitrate},"
                playlist_content += f"RESOLUTION={resolution},"
                playlist_content += f"FRAME-RATE={framerate}\n"
                
                # Add relative path to quality-specific playlist
                quality_preset = manifest["quality_preset"]
                playlist_content += f"{quality_preset}/segments/playlist.m3u8\n\n"
            
            # Save to temporary file
            temp_file = f"/tmp/master_{video_id}.m3u8"
            with open(temp_file, 'w') as f:
                f.write(playlist_content)
            
            # Upload to S3
            master_s3_key = f"transcoded/{video_id}/master.m3u8"
            await self.s3_service.upload_file(temp_file, master_s3_key)
            
            # Clean up
            os.unlink(temp_file)
            
            logger.info(f"Created master playlist for video {video_id} with {len(quality_manifests)} qualities")
            return master_s3_key
            
        except Exception as e:
            logger.error(f"Failed to create master playlist for video {video_id}: {e}")
            raise
    
    async def validate_hls_segments(self, manifest_s3_key: str) -> bool:
        """
        Validate that all segments referenced in a manifest exist in S3.
        """
        try:
            # Download manifest content
            manifest_content = await self.s3_service.get_file_content(manifest_s3_key)
            if not manifest_content:
                return False
            
            # Parse manifest to find segment references
            segment_keys = []
            base_path = "/".join(manifest_s3_key.split("/")[:-1])  # Remove filename
            
            for line in manifest_content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # This is a segment reference
                    segment_key = f"{base_path}/{line}"
                    segment_keys.append(segment_key)
            
            # Check if all segments exist
            for segment_key in segment_keys:
                if not await self.s3_service.file_exists(segment_key):
                    logger.warning(f"Missing HLS segment: {segment_key}")
                    return False
            
            logger.info(f"Validated HLS manifest {manifest_s3_key}: {len(segment_keys)} segments OK")
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate HLS segments for {manifest_s3_key}: {e}")
            return False
    
    async def get_segment_info(self, manifest_s3_key: str) -> Dict[str, any]:
        """
        Get information about HLS segments from a manifest.
        """
        try:
            manifest_content = await self.s3_service.get_file_content(manifest_s3_key)
            if not manifest_content:
                return {}
            
            info = {
                "segment_count": 0,
                "total_duration": 0.0,
                "segment_duration": 0.0,
                "segments": []
            }
            
            current_duration = 0.0
            
            for line in manifest_content.split('\n'):
                line = line.strip()
                
                if line.startswith('#EXTINF:'):
                    # Extract segment duration
                    duration_str = line.split(':')[1].split(',')[0]
                    current_duration = float(duration_str)
                    info["total_duration"] += current_duration
                    
                elif line and not line.startswith('#'):
                    # This is a segment file
                    info["segments"].append({
                        "filename": line,
                        "duration": current_duration
                    })
                    info["segment_count"] += 1
                    
                elif line.startswith('#EXT-X-TARGETDURATION:'):
                    # Target segment duration
                    info["segment_duration"] = float(line.split(':')[1])
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get segment info for {manifest_s3_key}: {e}")
            return {}
    
    async def cleanup_hls_files(self, video_id: str, quality_preset: str = None):
        """
        Clean up HLS files for a video or specific quality.
        """
        try:
            if quality_preset:
                # Clean up specific quality
                base_key = f"transcoded/{video_id}/{quality_preset}/segments/"
                await self.s3_service.delete_files_with_prefix(base_key)
                logger.info(f"Cleaned up HLS files for video {video_id}, quality {quality_preset}")
            else:
                # Clean up all HLS files for video
                base_key = f"transcoded/{video_id}/"
                await self.s3_service.delete_files_with_prefix(base_key)
                logger.info(f"Cleaned up all HLS files for video {video_id}")
                
        except Exception as e:
            logger.error(f"Failed to cleanup HLS files for video {video_id}: {e}")
            raise
    
    async def _cleanup_temp_directory(self, temp_dir: str):
        """Clean up temporary directory and all its contents."""
        try:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")
    
    def get_streaming_url(self, video_id: str, quality_preset: str = None) -> str:
        """
        Get streaming URL for a video.
        
        Args:
            video_id: Video identifier
            quality_preset: Specific quality, or None for master playlist
        
        Returns:
            CDN URL for streaming
        """
        if quality_preset:
            # URL for specific quality
            s3_key = f"transcoded/{video_id}/{quality_preset}/segments/playlist.m3u8"
        else:
            # URL for master playlist (adaptive streaming)
            s3_key = f"transcoded/{video_id}/master.m3u8"
        
        return self.s3_service.get_public_url(s3_key)
    
    async def get_available_qualities(self, video_id: str) -> List[Dict[str, any]]:
        """
        Get list of available quality variants for a video.
        """
        try:
            # List all quality directories
            prefix = f"transcoded/{video_id}/"
            files = await self.s3_service.list_files_with_prefix(prefix)
            
            qualities = []
            quality_dirs = set()
            
            for file_key in files:
                # Extract quality preset from path
                parts = file_key.replace(prefix, "").split("/")
                if len(parts) >= 2 and parts[1] == "segments":
                    quality_preset = parts[0]
                    if quality_preset not in quality_dirs:
                        quality_dirs.add(quality_preset)
                        
                        # Parse quality info from preset name
                        quality_info = self._parse_quality_preset(quality_preset)
                        quality_info["quality_preset"] = quality_preset
                        quality_info["streaming_url"] = self.get_streaming_url(video_id, quality_preset)
                        qualities.append(quality_info)
            
            # Sort by resolution (highest first)
            qualities.sort(key=lambda q: q.get("height", 0), reverse=True)
            return qualities
            
        except Exception as e:
            logger.error(f"Failed to get available qualities for video {video_id}: {e}")
            return []
    
    def _parse_quality_preset(self, quality_preset: str) -> Dict[str, any]:
        """
        Parse quality preset string to extract resolution and framerate.
        
        Example: "720p_30fps" -> {"width": 1280, "height": 720, "framerate": 30}
        """
        try:
            parts = quality_preset.split("_")
            
            # Parse resolution
            resolution_part = parts[0]  # e.g., "720p"
            height = int(resolution_part.replace("p", ""))
            
            # Calculate width based on 16:9 aspect ratio
            width = int(height * 16 / 9)
            
            # Parse framerate
            framerate = 30  # default
            if len(parts) > 1:
                framerate_part = parts[1]  # e.g., "30fps"
                framerate = int(framerate_part.replace("fps", ""))
            
            return {
                "width": width,
                "height": height,
                "framerate": framerate,
                "resolution": f"{width}x{height}"
            }
            
        except Exception:
            # Return defaults if parsing fails
            return {
                "width": 1280,
                "height": 720,
                "framerate": 30,
                "resolution": "1280x720"
            }