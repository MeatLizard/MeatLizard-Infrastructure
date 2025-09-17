"""
Video Upload Service

Handles video file uploads with multipart upload support, validation, and S3 integration.
"""
import os
import uuid
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile, HTTPException, Depends
import aiofiles

from server.web.app.models import User, Video, VideoStatus
from server.web.app.services.base_service import BaseService
from server.web.app.services.video_analysis_service import VideoAnalysisService, VideoValidationError
from server.web.app.services.video_s3_service import VideoS3Service, S3UploadSession
from server.web.app.services.video_metadata_service import VideoMetadataService, VideoMetadataInput
from server.web.app.services.thumbnail_service import ThumbnailService
from server.web.app.services.video_transcoding_service import VideoTranscodingService
from server.web.app.services.quality_preset_service import QualityPresetService
from server.web.app.db import get_db
from server.web.app.config import settings


class UploadSession:
    """Represents an active multipart upload session"""
    def __init__(self, session_id: str, video_id: str, user_id: str, metadata: Dict[str, Any]):
        self.session_id = session_id
        self.video_id = video_id
        self.user_id = user_id
        self.metadata = metadata
        self.chunks_received = 0
        self.total_chunks = metadata.get('total_chunks', 0)
        self.total_size = metadata.get('total_size', 0)
        self.uploaded_size = 0
        self.created_at = datetime.utcnow()
        self.s3_session: Optional[S3UploadSession] = None
        self.temp_file_path = None


class VideoMetadata:
    """Video metadata for upload"""
    def __init__(self, title: str, description: str = None, tags: List[str] = None):
        self.title = title
        self.description = description
        self.tags = tags or []


class ChunkResult:
    """Result of chunk processing"""
    def __init__(self, chunk_number: int, success: bool, message: str = None):
        self.chunk_number = chunk_number
        self.success = success
        self.message = message


class VideoUploadService(BaseService):
    """Service for handling video uploads with multipart support"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.active_sessions: Dict[str, UploadSession] = {}
        self.analysis_service = VideoAnalysisService()
        self.s3_service = VideoS3Service()
        self.metadata_service = VideoMetadataService(db)
        self.thumbnail_service = ThumbnailService(db)
        self.transcoding_service = VideoTranscodingService(db, settings.REDIS_URL)
        self.quality_preset_service = QualityPresetService(db)

    
    async def initiate_upload(self, user_id: str, metadata: VideoMetadata, file_info: Dict[str, Any]) -> UploadSession:
        """Initialize multipart upload session"""
        
        # Validate file info using analysis service
        try:
            self.analysis_service.validate_file_info(
                file_info['filename'], 
                file_info['size'], 
                file_info.get('mime_type')
            )
        except VideoValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Create video record
        video_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        # Generate S3 key
        s3_key = self.s3_service.generate_video_key(video_id, file_info['filename'])
        
        video = Video(
            id=video_id,
            creator_id=user_id,
            title=metadata.title,
            description=metadata.description,
            tags=metadata.tags,
            original_filename=file_info['filename'],
            original_s3_key=s3_key,
            file_size=file_info['size'],
            duration_seconds=0,  # Will be updated after analysis
            status=VideoStatus.uploading
        )
        
        self.db.add(video)
        await self.db.commit()
        
        # Create upload session
        session = UploadSession(
            session_id=session_id,
            video_id=video_id,
            user_id=user_id,
            metadata={
                'filename': file_info['filename'],
                'size': file_info['size'],
                'total_chunks': file_info.get('total_chunks', 1),
                'mime_type': file_info.get('mime_type', 'video/mp4')
            }
        )
        
        # Initialize S3 multipart upload if available
        if self.s3_service.is_available():
            try:
                s3_session = await self.s3_service.initiate_multipart_upload(
                    video_id,
                    file_info['filename'],
                    file_info.get('mime_type', 'video/mp4')
                )
                session.s3_session = s3_session
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to initialize S3 upload: {str(e)}")
        else:
            # Create temporary file for local storage
            temp_dir = os.path.join(settings.MEDIA_STORAGE_PATH, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            session.temp_file_path = os.path.join(temp_dir, f"{session_id}.tmp")
        
        self.active_sessions[session_id] = session
        return session
    
    async def create_video_from_file(self, file_path: str, original_filename: str, 
                                   creator_id: str, metadata: Dict[str, Any],
                                   quality_presets: List[str] = None) -> Video:
        """Create video record from existing file (for imports)"""
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                raise HTTPException(status_code=400, detail="File not found")
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Analyze video file
            analysis_result = await self.analysis_service.analyze_video_file(file_path)
            
            # Generate video ID and S3 key
            video_id = str(uuid.uuid4())
            s3_key = self.s3_service.generate_video_key(video_id, original_filename)
            
            # Create video record
            video = Video(
                id=video_id,
                creator_id=creator_id,
                title=metadata.get('title', 'Imported Video'),
                description=metadata.get('description'),
                tags=metadata.get('tags', []),
                category=metadata.get('category'),
                original_filename=original_filename,
                original_s3_key=s3_key,
                file_size=file_size,
                duration_seconds=int(analysis_result.duration) if analysis_result.duration else 0,
                source_resolution=analysis_result.resolution,
                source_framerate=int(analysis_result.framerate) if analysis_result.framerate else None,
                source_codec=analysis_result.codec,
                source_bitrate=analysis_result.bitrate,
                status=VideoStatus.processing,
                visibility=metadata.get('visibility', 'private')
            )
            
            self.db.add(video)
            await self.db.commit()
            await self.db.refresh(video)
            
            # Upload to S3
            if self.s3_service.is_available():
                await self.s3_service.upload_file(file_path, s3_key)
            
            # Generate thumbnails
            try:
                await self.thumbnail_service.generate_thumbnails(video_id, file_path)
            except Exception as e:
                # Log error but don't fail the import
                print(f"Failed to generate thumbnails for {video_id}: {e}")
            
            # Queue transcoding jobs
            if quality_presets:
                for preset in quality_presets:
                    try:
                        await self.transcoding_service.queue_transcoding_job(video_id, preset)
                    except Exception as e:
                        print(f"Failed to queue transcoding job for {video_id}, preset {preset}: {e}")
            
            # Update video status
            video.status = VideoStatus.ready if not quality_presets else VideoStatus.transcoding
            await self.db.commit()
            
            return video
            
        except Exception as e:
            # Clean up on error
            if 'video' in locals():
                await self.db.delete(video)
                await self.db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to create video from file: {str(e)}")
    
    async def process_chunk(self, upload_id: str, chunk_data: bytes, chunk_number: int) -> ChunkResult:
        """Process individual upload chunk"""
        
        if upload_id not in self.active_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        session = self.active_sessions[upload_id]
        
        try:
            if self.s3_service.is_available() and session.s3_session:
                # Upload chunk to S3
                await self.s3_service.upload_part(
                    session.s3_session,
                    chunk_number,
                    chunk_data
                )
            else:
                # Write chunk to temporary file
                async with aiofiles.open(session.temp_file_path, 'ab') as f:
                    await f.write(chunk_data)
            
            session.chunks_received += 1
            session.uploaded_size += len(chunk_data)
            
            return ChunkResult(
                chunk_number=chunk_number,
                success=True,
                message=f"Chunk {chunk_number} uploaded successfully"
            )
            
        except Exception as e:
            return ChunkResult(
                chunk_number=chunk_number,
                success=False,
                message=f"Failed to upload chunk {chunk_number}: {str(e)}"
            )
    
    async def complete_upload(self, upload_id: str, quality_presets: List[str]) -> Video:
        """Complete upload and initiate transcoding"""
        
        if upload_id not in self.active_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        session = self.active_sessions[upload_id]
        
        try:
            final_path = None
            
            # Complete S3 multipart upload or move temp file
            if self.s3_service.is_available() and session.s3_session:
                # Complete S3 multipart upload
                result = await self.s3_service.complete_multipart_upload(session.s3_session)
                if not result.success:
                    raise Exception(result.error_message or "S3 upload completion failed")
            else:
                # Move temp file to final location
                final_dir = os.path.join(settings.MEDIA_STORAGE_PATH, 'originals')
                os.makedirs(final_dir, exist_ok=True)
                final_path = os.path.join(final_dir, f"{session.video_id}.{session.metadata['filename'].split('.')[-1]}")
                
                if os.path.exists(session.temp_file_path):
                    os.rename(session.temp_file_path, final_path)
            
            # Update video status and analyze video
            video = await self.db.get(Video, session.video_id)
            if video:
                video.status = VideoStatus.processing
                
                # Analyze video if using local storage
                if not self.s3_service.is_available() and final_path:
                    try:
                        analysis = await self.analysis_service.analyze_video_file(final_path)
                        if analysis.is_valid:
                            video.duration_seconds = int(analysis.duration_seconds)
                            video.source_resolution = f"{analysis.width}x{analysis.height}"
                            video.source_framerate = int(analysis.framerate)
                            video.source_codec = analysis.codec
                            video.source_bitrate = analysis.bitrate
                        else:
                            video.status = VideoStatus.failed
                    except Exception as e:
                        print(f"Video analysis failed: {str(e)}")
                        # Continue without analysis data
                
                await self.db.commit()
                
                # Generate thumbnails if video analysis was successful
                if not self.s3_service.is_available() and final_path:
                    try:
                        await self.thumbnail_service.generate_thumbnails_for_video(
                            video_id=session.video_id,
                            video_path=final_path
                        )
                    except Exception as e:
                        print(f"Thumbnail generation failed: {str(e)}")
                        # Continue without thumbnails
                
                # Queue transcoding jobs for quality presets
                if quality_presets:
                    await self._queue_transcoding_jobs(session.video_id, quality_presets)
                
            # Clean up session
            del self.active_sessions[upload_id]
            
            return video
            
        except Exception as e:
            # Clean up failed upload
            await self.cancel_upload(upload_id)
            raise HTTPException(status_code=500, detail=f"Failed to complete upload: {str(e)}")
    
    async def cancel_upload(self, upload_id: str) -> bool:
        """Cancel upload and cleanup resources"""
        
        if upload_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[upload_id]
        
        try:
            # Cancel S3 multipart upload
            if self.s3_service.is_available() and session.s3_session:
                await self.s3_service.abort_multipart_upload(session.s3_session)
            
            # Remove temp file
            if session.temp_file_path and os.path.exists(session.temp_file_path):
                os.remove(session.temp_file_path)
            
            # Update video status to failed
            video = await self.db.get(Video, session.video_id)
            if video:
                video.status = VideoStatus.failed
                await self.db.commit()
            
            # Clean up session
            del self.active_sessions[upload_id]
            
            return True
            
        except Exception as e:
            print(f"Error during upload cancellation: {str(e)}")
            return False
    
    def _validate_file_info(self, file_info: Dict[str, Any]) -> bool:
        """Validate file information"""
        
        # Check required fields
        required_fields = ['filename', 'size']
        for field in required_fields:
            if field not in file_info:
                return False
        
        # Check file size (max 10GB)
        max_size = 10 * 1024 * 1024 * 1024  # 10GB
        if file_info['size'] > max_size:
            return False
        
        # Check file extension
        allowed_extensions = ['mp4', 'mov', 'avi', 'mkv', 'webm']
        filename = file_info['filename'].lower()
        if not any(filename.endswith(f'.{ext}') for ext in allowed_extensions):
            return False
        
        return True
    
    async def _queue_transcoding_jobs(self, video_id: str, quality_presets: List[str]):
        """Queue transcoding jobs for the uploaded video."""
        try:
            # Get video information for preset generation
            video = await self.db.get(Video, video_id)
            if not video:
                return
            
            # Generate quality presets based on source video
            available_presets = await self.quality_preset_service.get_available_presets_for_video(video_id)
            
            for preset_name in quality_presets:
                # Find matching preset
                preset = next((p for p in available_presets if p["name"] == preset_name), None)
                if not preset:
                    continue
                
                # Queue transcoding job
                await self.transcoding_service.queue_transcoding_job(
                    video_id=video_id,
                    quality_preset=preset_name,
                    target_resolution=preset["resolution"],
                    target_framerate=preset["framerate"],
                    target_bitrate=preset["bitrate"]
                )
            
            # Update video status to transcoding
            video.status = VideoStatus.transcoding
            await self.db.commit()
            
        except Exception as e:
            print(f"Failed to queue transcoding jobs for video {video_id}: {str(e)}")
    
    def get_upload_progress(self, upload_id: str) -> Dict[str, Any]:
        """Get upload progress information"""
        
        if upload_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[upload_id]
        
        progress_percent = 0
        if session.total_size > 0:
            progress_percent = (session.uploaded_size / session.total_size) * 100
        
        return {
            'session_id': session.session_id,
            'video_id': session.video_id,
            'chunks_received': session.chunks_received,
            'total_chunks': session.metadata.get('total_chunks', 0),
            'uploaded_size': session.uploaded_size,
            'total_size': session.total_size,
            'progress_percent': min(progress_percent, 100),
            'created_at': session.created_at.isoformat()
        }


# Dependency for FastAPI
def get_video_upload_service(db: AsyncSession = Depends(get_db)) -> VideoUploadService:
    return VideoUploadService(db)