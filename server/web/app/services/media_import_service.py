"""
Media Import Service with yt-dlp integration.
Handles downloading and importing media from external platforms.
"""
import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, AsyncIterator, Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models import ImportJob, ImportPreset, Video, User, ImportStatus
from .base_service import BaseService

# Import video upload service conditionally to avoid circular imports
try:
    from .video_upload_service import VideoUploadService
except ImportError:
    VideoUploadService = None

logger = logging.getLogger(__name__)

class MediaInfo(BaseModel):
    """Media information extracted from yt-dlp"""
    title: str
    description: Optional[str] = None
    uploader: str
    upload_date: Optional[datetime] = None
    duration: Optional[float] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    thumbnail_url: Optional[str] = None
    source_url: str
    platform: str
    available_formats: List[Dict[str, Any]] = Field(default_factory=list)

class ImportConfig(BaseModel):
    """Configuration for media import"""
    max_height: Optional[int] = None  # 480, 720, 1080, 1440, 2160
    max_fps: Optional[int] = None     # 30, 60
    max_filesize: Optional[str] = None # "500M", "2G"
    audio_only: bool = False
    audio_format: str = "mp3"         # mp3, flac, aac
    preferred_codec: Optional[str] = None # h264, h265, vp9
    quality_presets: List[str] = Field(default_factory=list)   # Which transcoded qualities to generate
    preserve_metadata: bool = True
    auto_publish: bool = False
    category: Optional[str] = None

class DownloadResult(BaseModel):
    """Result of media download operation"""
    success: bool
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class MediaExtractionError(Exception):
    """Exception raised when media extraction fails"""
    pass

class MediaImportService(BaseService):
    """Service for importing media from external platforms using yt-dlp"""
    
    def __init__(self, db: AsyncSession, ytdlp_path: str = "yt-dlp"):
        super().__init__(db)
        self.ytdlp_path = ytdlp_path
        self.supported_platforms = [
            "youtube.com", "youtu.be", "tiktok.com", "instagram.com", 
            "twitter.com", "x.com", "vimeo.com", "dailymotion.com",
            "twitch.tv", "reddit.com", "facebook.com"
        ]
        self.video_upload_service = VideoUploadService(db) if VideoUploadService else None
    
    async def extract_media_info(self, url: str) -> MediaInfo:
        """Extract metadata and available formats from URL using yt-dlp"""
        try:
            cmd = [
                self.ytdlp_path, "--dump-json", "--no-download", 
                "--flat-playlist", url
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise MediaExtractionError(f"Failed to extract media info: {error_msg}")
            
            # Parse JSON output
            info_data = json.loads(stdout.decode())
            
            # Extract platform from URL
            platform = self._extract_platform(url)
            
            # Convert to MediaInfo
            media_info = MediaInfo(
                title=info_data.get("title", "Unknown Title"),
                description=info_data.get("description"),
                uploader=info_data.get("uploader", "Unknown"),
                upload_date=self._parse_upload_date(info_data.get("upload_date")),
                duration=info_data.get("duration"),
                view_count=info_data.get("view_count"),
                like_count=info_data.get("like_count"),
                thumbnail_url=info_data.get("thumbnail"),
                source_url=url,
                platform=platform,
                available_formats=info_data.get("formats", [])
            )
            
            return media_info
            
        except json.JSONDecodeError as e:
            raise MediaExtractionError(f"Failed to parse media info JSON: {str(e)}")
        except Exception as e:
            raise MediaExtractionError(f"Unexpected error during media extraction: {str(e)}")
    
    async def download_media(self, url: str, import_config: ImportConfig, 
                           output_dir: Optional[str] = None) -> DownloadResult:
        """Download media with specified quality and format settings"""
        try:
            # Create temporary directory if none provided
            if output_dir is None:
                output_dir = tempfile.mkdtemp(prefix="media_import_")
            
            # Build output template
            output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
            
            # Build yt-dlp command
            cmd = [
                self.ytdlp_path,
                "--format", self._build_format_selector(import_config),
                "--output", output_template,
                "--write-info-json",
                "--write-thumbnail",
                "--no-playlist",  # Download single video only
            ]
            
            # Add audio-only options
            if import_config.audio_only:
                cmd.extend(["--extract-audio", "--audio-format", import_config.audio_format])
            
            # Add file size limit
            if import_config.max_filesize:
                cmd.extend(["--max-filesize", import_config.max_filesize])
            
            cmd.append(url)
            
            # Execute download
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=output_dir
            )
            
            result = await self._monitor_download_progress(process, url, output_dir)
            return result
            
        except Exception as e:
            logger.error(f"Download failed for {url}: {str(e)}")
            return DownloadResult(
                success=False,
                error_message=f"Download failed: {str(e)}"
            )
    
    async def create_import_job(self, url: str, config: ImportConfig, 
                              user_id: str, discord_channel_id: Optional[str] = None,
                              discord_message_id: Optional[str] = None) -> ImportJob:
        """Create a new import job"""
        try:
            # Extract media info first
            media_info = await self.extract_media_info(url)
            
            # Create import job
            import_job = ImportJob(
                source_url=url,
                platform=media_info.platform,
                import_config=config.dict(),
                requested_by=user_id,
                original_title=media_info.title,
                original_description=media_info.description,
                original_uploader=media_info.uploader,
                original_upload_date=media_info.upload_date,
                original_duration=int(media_info.duration) if media_info.duration else None,
                original_view_count=media_info.view_count,
                original_like_count=media_info.like_count,
                discord_channel_id=discord_channel_id,
                discord_message_id=discord_message_id
            )
            
            self.db.add(import_job)
            await self.db.commit()
            await self.db.refresh(import_job)
            
            return import_job
            
        except Exception as e:
            logger.error(f"Failed to create import job for {url}: {str(e)}")
            raise
    
    async def process_import_job(self, job_id: str) -> bool:
        """Process an import job"""
        try:
            # Get job
            result = await self.db.execute(
                select(ImportJob).where(ImportJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"Import job {job_id} not found")
                return False
            
            # Update status to downloading
            await self._update_job_status(job_id, ImportStatus.downloading, 10)
            
            # Parse import config
            config = ImportConfig(**job.import_config)
            
            # Download media
            download_result = await self.download_media(job.source_url, config)
            
            if not download_result.success:
                await self._update_job_status(
                    job_id, ImportStatus.failed, 0, download_result.error_message
                )
                return False
            
            # Update status to processing
            await self._update_job_status(job_id, ImportStatus.processing, 50)
            
            # Create video record
            video = await self._create_video_from_import(job, download_result.file_path, config)
            
            if not video:
                await self._update_job_status(
                    job_id, ImportStatus.failed, 0, "Failed to create video record"
                )
                return False
            
            # Update job with video ID
            await self.db.execute(
                update(ImportJob)
                .where(ImportJob.id == job_id)
                .values(
                    video_id=video.id,
                    downloaded_file_path=download_result.file_path
                )
            )
            
            # Complete job
            await self._update_job_status(job_id, ImportStatus.completed, 100)
            
            # Clean up temporary files
            if download_result.file_path and os.path.exists(download_result.file_path):
                try:
                    os.remove(download_result.file_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {download_result.file_path}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process import job {job_id}: {str(e)}")
            await self._update_job_status(
                job_id, ImportStatus.failed, 0, f"Processing failed: {str(e)}"
            )
            return False
    
    async def get_import_jobs(self, user_id: Optional[str] = None, 
                            status: Optional[ImportStatus] = None,
                            limit: int = 50, offset: int = 0) -> List[ImportJob]:
        """Get import jobs with optional filtering"""
        query = select(ImportJob)
        
        if user_id:
            query = query.where(ImportJob.requested_by == user_id)
        
        if status:
            query = query.where(ImportJob.status == status)
        
        query = query.order_by(ImportJob.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def create_import_preset(self, name: str, description: str, 
                                 config: ImportConfig, user_id: str) -> ImportPreset:
        """Create a new import preset"""
        preset = ImportPreset(
            name=name,
            description=description,
            config=config.dict(),
            created_by=user_id
        )
        
        self.db.add(preset)
        await self.db.commit()
        await self.db.refresh(preset)
        
        return preset
    
    async def get_import_presets(self, user_id: Optional[str] = None) -> List[ImportPreset]:
        """Get import presets"""
        query = select(ImportPreset)
        
        if user_id:
            query = query.where(ImportPreset.created_by == user_id)
        
        query = query.order_by(ImportPreset.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    def is_supported_url(self, url: str) -> bool:
        """Check if URL is from a supported platform"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            
            return any(platform in domain for platform in self.supported_platforms)
        except Exception:
            return False
    
    def _extract_platform(self, url: str) -> str:
        """Extract platform name from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            
            # Map domains to platform names
            platform_map = {
                "youtube.com": "YouTube",
                "youtu.be": "YouTube",
                "tiktok.com": "TikTok",
                "instagram.com": "Instagram",
                "twitter.com": "Twitter",
                "x.com": "Twitter",
                "vimeo.com": "Vimeo",
                "dailymotion.com": "Dailymotion",
                "twitch.tv": "Twitch",
                "reddit.com": "Reddit",
                "facebook.com": "Facebook"
            }
            
            for platform_domain, platform_name in platform_map.items():
                if platform_domain in domain:
                    return platform_name
            
            return domain
            
        except Exception:
            return "Unknown"
    
    def _parse_upload_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse upload date from yt-dlp format (YYYYMMDD)"""
        if not date_str:
            return None
        
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            return None
    
    def _build_format_selector(self, config: ImportConfig) -> str:
        """Build yt-dlp format selector based on import configuration"""
        if config.audio_only:
            return "bestaudio"
        
        format_parts = []
        
        if config.max_height:
            format_parts.append(f"height<={config.max_height}")
        
        if config.max_fps:
            format_parts.append(f"fps<={config.max_fps}")
        
        if config.preferred_codec:
            format_parts.append(f"vcodec:{config.preferred_codec}")
        
        if format_parts:
            return f"best[{']['.join(format_parts)}]"
        
        return "best"
    
    async def _monitor_download_progress(self, process: asyncio.subprocess.Process, 
                                       url: str, output_dir: str) -> DownloadResult:
        """Monitor download progress and return result"""
        try:
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown download error"
                return DownloadResult(
                    success=False,
                    error_message=error_msg
                )
            
            # Find downloaded file
            downloaded_files = []
            for file_path in Path(output_dir).glob("*"):
                if file_path.is_file() and not file_path.name.endswith(('.info.json', '.jpg', '.png', '.webp')):
                    downloaded_files.append(str(file_path))
            
            if not downloaded_files:
                return DownloadResult(
                    success=False,
                    error_message="No media file found after download"
                )
            
            # Return the first (and usually only) downloaded file
            return DownloadResult(
                success=True,
                file_path=downloaded_files[0]
            )
            
        except Exception as e:
            return DownloadResult(
                success=False,
                error_message=f"Download monitoring failed: {str(e)}"
            )
    
    async def _update_job_status(self, job_id: str, status: ImportStatus, 
                               progress: int, error_message: Optional[str] = None):
        """Update import job status"""
        update_data = {
            "status": status,
            "progress_percent": progress
        }
        
        if status == ImportStatus.downloading and not hasattr(self, '_job_started'):
            update_data["started_at"] = datetime.utcnow()
            self._job_started = True
        
        if status in [ImportStatus.completed, ImportStatus.failed]:
            update_data["completed_at"] = datetime.utcnow()
        
        if error_message:
            update_data["error_message"] = error_message
        
        await self.db.execute(
            update(ImportJob)
            .where(ImportJob.id == job_id)
            .values(**update_data)
        )
        await self.db.commit()
    
    async def _create_video_from_import(self, job: ImportJob, file_path: str, 
                                      config: ImportConfig) -> Optional[Video]:
        """Create video record from imported media"""
        try:
            # Get file info
            file_size = os.path.getsize(file_path)
            
            # Create video metadata
            video_data = {
                "title": job.original_title or "Imported Video",
                "description": job.original_description,
                "category": config.category,
                "visibility": "public" if config.auto_publish else "private",
                "tags": [f"imported", f"source:{job.platform.lower()}"]
            }
            
            # Use video upload service to handle the file
            # This will handle S3 upload, transcoding, etc.
            if self.video_upload_service:
                video = await self.video_upload_service.create_video_from_file(
                    file_path=file_path,
                    original_filename=f"{job.original_title}.mp4",
                    creator_id=job.requested_by,
                    metadata=video_data,
                    quality_presets=config.quality_presets or ["720p_30fps"]
                )
            else:
                # Fallback if video upload service is not available
                from ..models import Video, VideoStatus
                video = Video(
                    creator_id=job.requested_by,
                    title=job.original_title or "Imported Video",
                    description=job.original_description,
                    original_filename=f"{job.original_title}.mp4",
                    original_s3_key=f"imported/{job.id}.mp4",
                    file_size=file_size,
                    duration_seconds=0,
                    status=VideoStatus.ready
                )
                self.db.add(video)
                await self.db.commit()
                await self.db.refresh(video)
            
            return video
            
        except Exception as e:
            logger.error(f"Failed to create video from import: {str(e)}")
            return None