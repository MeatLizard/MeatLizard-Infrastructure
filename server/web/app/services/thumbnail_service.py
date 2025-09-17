"""
Thumbnail Generation Service

Handles thumbnail generation and management including:
- FFmpeg integration for thumbnail extraction at multiple timestamps
- Thumbnail selection interface for creators
- S3 storage for thumbnail images
- Default thumbnail selection logic
"""
import os
import uuid
import asyncio
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from pydantic import BaseModel

from server.web.app.models import Video, User
from server.web.app.services.base_service import BaseService
from server.web.app.services.video_s3_service import VideoS3Service
from server.web.app.config import settings


@dataclass
class ThumbnailInfo:
    """Thumbnail information"""
    timestamp: float
    filename: str
    s3_key: str
    local_path: Optional[str] = None
    width: int = 0
    height: int = 0
    file_size: int = 0
    is_selected: bool = False


class ThumbnailRequest(BaseModel):
    """Request model for thumbnail generation"""
    timestamps: List[float]
    width: int = 320
    height: int = 180
    quality: int = 85


class ThumbnailResponse(BaseModel):
    """Response model for thumbnail information"""
    timestamp: float
    filename: str
    url: str
    width: int
    height: int
    file_size: int
    is_selected: bool


class ThumbnailSelectionRequest(BaseModel):
    """Request model for thumbnail selection"""
    selected_timestamp: float


class ThumbnailGenerationError(Exception):
    """Raised when thumbnail generation fails"""
    pass


class ThumbnailService(BaseService):
    """Service for handling thumbnail generation and management"""
    
    # Default thumbnail timestamps (as percentages of video duration)
    DEFAULT_TIMESTAMPS = [0.1, 0.25, 0.5, 0.75, 0.9]  # 10%, 25%, 50%, 75%, 90%
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.s3_service = VideoS3Service()
        self.ffmpeg_path = self._find_ffmpeg()
        
    def _find_ffmpeg(self) -> str:
        """Find FFmpeg executable"""
        # Try common locations
        possible_paths = [
            'ffmpeg',  # In PATH
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg',  # macOS Homebrew
            'C:\\ffmpeg\\bin\\ffmpeg.exe',  # Windows
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
        
        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")
    
    async def generate_thumbnails_for_video(
        self, 
        video_id: str, 
        video_path: str, 
        timestamps: Optional[List[float]] = None,
        width: int = 320,
        height: int = 180
    ) -> List[ThumbnailInfo]:
        """
        Generate thumbnails for a video at specified timestamps.
        
        Requirements: 3.2, 3.3, 3.4
        """
        # Get video record
        video = await self.db.get(Video, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Use default timestamps if none provided
        if timestamps is None:
            duration = float(video.duration_seconds) if video.duration_seconds else 60.0
            timestamps = [duration * pct for pct in self.DEFAULT_TIMESTAMPS]
        
        # Validate video file exists
        if not os.path.exists(video_path):
            raise ThumbnailGenerationError(f"Video file not found: {video_path}")
        
        # Create thumbnails directory
        thumbnails_dir = os.path.join(settings.MEDIA_STORAGE_PATH, 'thumbnails', str(video_id))
        os.makedirs(thumbnails_dir, exist_ok=True)
        
        thumbnails = []
        
        for i, timestamp in enumerate(timestamps):
            try:
                thumbnail_info = await self._generate_single_thumbnail(
                    video_id=video_id,
                    video_path=video_path,
                    timestamp=timestamp,
                    output_dir=thumbnails_dir,
                    width=width,
                    height=height,
                    index=i
                )
                thumbnails.append(thumbnail_info)
                
            except Exception as e:
                print(f"Failed to generate thumbnail at {timestamp}s: {str(e)}")
                continue
        
        if not thumbnails:
            raise ThumbnailGenerationError("Failed to generate any thumbnails")
        
        # Set default selected thumbnail (middle one)
        if thumbnails:
            middle_index = len(thumbnails) // 2
            thumbnails[middle_index].is_selected = True
            
            # Update video record with selected thumbnail
            video.thumbnail_s3_key = thumbnails[middle_index].s3_key
            await self.db.commit()
        
        return thumbnails
    
    async def _generate_single_thumbnail(
        self,
        video_id: str,
        video_path: str,
        timestamp: float,
        output_dir: str,
        width: int,
        height: int,
        index: int
    ) -> ThumbnailInfo:
        """Generate a single thumbnail at the specified timestamp"""
        
        # Generate filename
        timestamp_str = f"{timestamp:.1f}".replace('.', '_')
        filename = f"thumb_{index:02d}_{timestamp_str}s.jpg"
        output_path = os.path.join(output_dir, filename)
        
        # FFmpeg command to extract thumbnail
        cmd = [
            self.ffmpeg_path,
            '-i', video_path,
            '-ss', str(timestamp),
            '-vframes', '1',
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
            '-q:v', '2',  # High quality
            '-y',  # Overwrite output file
            output_path
        ]
        
        # Execute FFmpeg command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "FFmpeg thumbnail generation failed"
            raise ThumbnailGenerationError(f"Failed to generate thumbnail: {error_msg}")
        
        # Verify thumbnail was created
        if not os.path.exists(output_path):
            raise ThumbnailGenerationError(f"Thumbnail file not created: {output_path}")
        
        # Get file info
        file_size = os.path.getsize(output_path)
        
        # Generate S3 key
        s3_key = f"thumbnails/{video_id}/{filename}"
        
        # Upload to S3 if available
        if self.s3_service.is_available():
            try:
                await self._upload_thumbnail_to_s3(output_path, s3_key)
            except Exception as e:
                print(f"Failed to upload thumbnail to S3: {str(e)}")
                # Continue with local storage
        
        return ThumbnailInfo(
            timestamp=timestamp,
            filename=filename,
            s3_key=s3_key,
            local_path=output_path,
            width=width,
            height=height,
            file_size=file_size,
            is_selected=False
        )
    
    async def _upload_thumbnail_to_s3(self, local_path: str, s3_key: str) -> None:
        """Upload thumbnail to S3 storage"""
        
        try:
            with open(local_path, 'rb') as f:
                file_content = f.read()
            
            # Upload to S3
            await self.s3_service.upload_file_content(
                content=file_content,
                key=s3_key,
                content_type='image/jpeg'
            )
            
        except Exception as e:
            raise ThumbnailGenerationError(f"Failed to upload thumbnail to S3: {str(e)}")
    
    async def get_video_thumbnails(self, video_id: str) -> List[ThumbnailResponse]:
        """Get all thumbnails for a video"""
        
        # Get video record
        video = await self.db.get(Video, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Check local thumbnails directory
        thumbnails_dir = os.path.join(settings.MEDIA_STORAGE_PATH, 'thumbnails', str(video_id))
        
        thumbnails = []
        
        if os.path.exists(thumbnails_dir):
            for filename in sorted(os.listdir(thumbnails_dir)):
                if filename.endswith('.jpg'):
                    file_path = os.path.join(thumbnails_dir, filename)
                    file_size = os.path.getsize(file_path)
                    
                    # Extract timestamp from filename
                    timestamp = self._extract_timestamp_from_filename(filename)
                    
                    # Generate URL
                    if self.s3_service.is_available():
                        s3_key = f"thumbnails/{video_id}/{filename}"
                        url = await self.s3_service.get_file_url(s3_key)
                    else:
                        url = f"/api/video/thumbnails/{video_id}/{filename}"
                    
                    # Check if this is the selected thumbnail
                    is_selected = video.thumbnail_s3_key and filename in video.thumbnail_s3_key
                    
                    thumbnail = ThumbnailResponse(
                        timestamp=timestamp,
                        filename=filename,
                        url=url,
                        width=320,  # Default width
                        height=180,  # Default height
                        file_size=file_size,
                        is_selected=is_selected
                    )
                    
                    thumbnails.append(thumbnail)
        
        return thumbnails
    
    def _extract_timestamp_from_filename(self, filename: str) -> float:
        """Extract timestamp from thumbnail filename"""
        try:
            # Expected format: thumb_XX_YY_Ys.jpg
            parts = filename.replace('.jpg', '').split('_')
            if len(parts) >= 3:
                timestamp_str = parts[2] + '.' + parts[3] if len(parts) > 3 else parts[2]
                return float(timestamp_str.replace('s', ''))
        except (ValueError, IndexError):
            pass
        
        return 0.0
    
    async def select_thumbnail(self, video_id: str, timestamp: float, user_id: str) -> ThumbnailResponse:
        """
        Select a thumbnail as the primary thumbnail for a video.
        
        Requirements: 3.3, 3.4
        """
        # Get video record
        video = await self.db.get(Video, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Verify ownership
        if str(video.creator_id) != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this video")
        
        # Find thumbnail with matching timestamp
        thumbnails = await self.get_video_thumbnails(video_id)
        selected_thumbnail = None
        
        for thumbnail in thumbnails:
            if abs(thumbnail.timestamp - timestamp) < 0.1:  # Allow small tolerance
                selected_thumbnail = thumbnail
                break
        
        if not selected_thumbnail:
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        
        # Update video record
        video.thumbnail_s3_key = f"thumbnails/{video_id}/{selected_thumbnail.filename}"
        video.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        # Return updated thumbnail info
        selected_thumbnail.is_selected = True
        return selected_thumbnail
    
    async def regenerate_thumbnails(
        self, 
        video_id: str, 
        user_id: str,
        custom_timestamps: Optional[List[float]] = None
    ) -> List[ThumbnailResponse]:
        """
        Regenerate thumbnails for a video with custom timestamps.
        
        Requirements: 3.2, 3.3
        """
        # Get video record
        video = await self.db.get(Video, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Verify ownership
        if str(video.creator_id) != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this video")
        
        # Find original video file
        video_path = None
        
        # Check local storage first
        original_dir = os.path.join(settings.MEDIA_STORAGE_PATH, 'originals')
        for ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
            potential_path = os.path.join(original_dir, f"{video_id}.{ext}")
            if os.path.exists(potential_path):
                video_path = potential_path
                break
        
        if not video_path:
            # Try to download from S3 if available
            if self.s3_service.is_available() and video.original_s3_key:
                try:
                    temp_dir = os.path.join(settings.MEDIA_STORAGE_PATH, 'temp')
                    os.makedirs(temp_dir, exist_ok=True)
                    video_path = os.path.join(temp_dir, f"{video_id}_temp.mp4")
                    
                    await self.s3_service.download_file(video.original_s3_key, video_path)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to download video: {str(e)}")
            else:
                raise HTTPException(status_code=404, detail="Original video file not found")
        
        try:
            # Clear existing thumbnails
            await self._clear_existing_thumbnails(video_id)
            
            # Generate new thumbnails
            thumbnail_infos = await self.generate_thumbnails_for_video(
                video_id=video_id,
                video_path=video_path,
                timestamps=custom_timestamps
            )
            
            # Convert to response format
            thumbnails = []
            for info in thumbnail_infos:
                url = f"/api/video/thumbnails/{video_id}/{info.filename}"
                if self.s3_service.is_available():
                    url = await self.s3_service.get_file_url(info.s3_key)
                
                thumbnail = ThumbnailResponse(
                    timestamp=info.timestamp,
                    filename=info.filename,
                    url=url,
                    width=info.width,
                    height=info.height,
                    file_size=info.file_size,
                    is_selected=info.is_selected
                )
                thumbnails.append(thumbnail)
            
            return thumbnails
            
        finally:
            # Clean up temporary video file if downloaded
            if video_path and 'temp' in video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except Exception:
                    pass  # Ignore cleanup errors
    
    async def _clear_existing_thumbnails(self, video_id: str) -> None:
        """Clear existing thumbnails for a video"""
        
        # Clear local thumbnails
        thumbnails_dir = os.path.join(settings.MEDIA_STORAGE_PATH, 'thumbnails', str(video_id))
        if os.path.exists(thumbnails_dir):
            for filename in os.listdir(thumbnails_dir):
                file_path = os.path.join(thumbnails_dir, filename)
                try:
                    os.remove(file_path)
                except Exception:
                    pass  # Ignore errors
        
        # Clear S3 thumbnails if available
        if self.s3_service.is_available():
            try:
                await self.s3_service.delete_folder(f"thumbnails/{video_id}/")
            except Exception:
                pass  # Ignore errors
    
    async def get_thumbnail_file(self, video_id: str, filename: str) -> Tuple[bytes, str]:
        """Get thumbnail file content for serving"""
        
        # Try local storage first
        local_path = os.path.join(settings.MEDIA_STORAGE_PATH, 'thumbnails', str(video_id), filename)
        
        if os.path.exists(local_path):
            with open(local_path, 'rb') as f:
                content = f.read()
            return content, 'image/jpeg'
        
        # Try S3 storage
        if self.s3_service.is_available():
            try:
                s3_key = f"thumbnails/{video_id}/{filename}"
                content = await self.s3_service.get_file_content(s3_key)
                return content, 'image/jpeg'
            except Exception:
                pass
        
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    
    def get_default_thumbnail_timestamps(self, duration_seconds: float) -> List[float]:
        """Get default thumbnail timestamps for a video duration"""
        
        if duration_seconds <= 0:
            return [0.0]
        
        timestamps = []
        for pct in self.DEFAULT_TIMESTAMPS:
            timestamp = duration_seconds * pct
            # Ensure timestamp is within video bounds
            timestamp = max(0.0, min(timestamp, duration_seconds - 1.0))
            timestamps.append(timestamp)
        
        return timestamps
    
    async def auto_select_best_thumbnail(self, video_id: str) -> Optional[ThumbnailResponse]:
        """
        Automatically select the best thumbnail based on content analysis.
        
        This is a simplified implementation that selects the middle thumbnail.
        In a more sophisticated system, you could use image analysis to detect
        faces, interesting content, etc.
        
        Requirements: 3.4
        """
        thumbnails = await self.get_video_thumbnails(video_id)
        
        if not thumbnails:
            return None
        
        # Simple strategy: select middle thumbnail
        middle_index = len(thumbnails) // 2
        selected_thumbnail = thumbnails[middle_index]
        
        # Update selection
        video = await self.db.get(Video, video_id)
        if video:
            video.thumbnail_s3_key = f"thumbnails/{video_id}/{selected_thumbnail.filename}"
            await self.db.commit()
            
            selected_thumbnail.is_selected = True
        
        return selected_thumbnail


# Dependency for FastAPI
def get_thumbnail_service(db: AsyncSession) -> ThumbnailService:
    return ThumbnailService(db)