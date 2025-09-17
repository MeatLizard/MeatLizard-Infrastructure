"""
Video Upload API Endpoints

Provides REST API endpoints for video upload functionality including:
- Multipart upload initiation
- Chunk upload processing  
- Upload completion and cancellation
- Upload progress tracking
"""
import os
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.video_upload_service import (
    VideoUploadService, 
    VideoMetadata,
    get_video_upload_service
)
from server.web.app.services.video_analysis_service import (
    VideoAnalysisService,
    VideoValidationError,
    get_video_analysis_service
)
from server.web.app.services.quality_preset_service import (
    QualityPresetService,
    SourceVideoInfo,
    get_quality_preset_service
)
from server.web.app.services.video_s3_service import VideoS3Service, get_video_s3_service
from server.web.app.models import User
from server.web.app.middleware.permissions import get_current_user

router = APIRouter(prefix="/api/video", tags=["video-upload"])


# Request/Response Models
class InitiateUploadRequest(BaseModel):
    title: str
    description: str = None
    tags: List[str] = []
    filename: str
    file_size: int
    mime_type: str = "video/mp4"
    total_chunks: int = 1


class InitiateUploadResponse(BaseModel):
    session_id: str
    video_id: str
    upload_url: str = None  # For direct S3 uploads if implemented
    chunk_size: int = 5242880  # 5MB default chunk size


class ChunkUploadResponse(BaseModel):
    chunk_number: int
    success: bool
    message: str = None


class CompleteUploadRequest(BaseModel):
    quality_presets: List[str] = ["720p_30fps"]


class CompleteUploadResponse(BaseModel):
    video_id: str
    status: str
    message: str


class UploadProgressResponse(BaseModel):
    session_id: str
    video_id: str
    chunks_received: int
    total_chunks: int
    uploaded_size: int
    total_size: int
    progress_percent: float
    created_at: str


class VideoAnalysisResponse(BaseModel):
    duration_seconds: float
    width: int
    height: int
    framerate: float
    codec: str
    bitrate: int
    format_name: str
    file_size: int
    is_valid: bool
    error_message: str = None
    available_presets: List[str] = []


class ValidateFileRequest(BaseModel):
    filename: str
    file_size: int
    mime_type: str = None


@router.post("/upload/initiate", response_model=InitiateUploadResponse)
async def initiate_upload(
    request: InitiateUploadRequest,
    user: User = Depends(get_current_user),
    service: VideoUploadService = Depends(get_video_upload_service)
):
    """
    Initiate a multipart video upload session.
    
    This endpoint creates a new upload session and video record, validates the file
    information, and prepares for chunk-based upload.
    
    Requirements: 1.1, 1.2, 1.3
    """
    try:
        # Create video metadata
        metadata = VideoMetadata(
            title=request.title,
            description=request.description,
            tags=request.tags
        )
        
        # Prepare file info
        file_info = {
            'filename': request.filename,
            'size': request.file_size,
            'mime_type': request.mime_type,
            'total_chunks': request.total_chunks,
            'extension': request.filename.split('.')[-1].lower()
        }
        
        # Initiate upload session
        session = await service.initiate_upload(str(user.id), metadata, file_info)
        
        return InitiateUploadResponse(
            session_id=session.session_id,
            video_id=session.video_id,
            chunk_size=5242880  # 5MB chunks
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate upload: {str(e)}")


@router.post("/upload/{session_id}/chunk/{chunk_number}", response_model=ChunkUploadResponse)
async def upload_chunk(
    session_id: str,
    chunk_number: int,
    chunk: UploadFile = File(...),
    user: User = Depends(get_current_user),
    service: VideoUploadService = Depends(get_video_upload_service)
):
    """
    Upload a single chunk of video data.
    
    This endpoint processes individual chunks of the video file, supporting
    resumable uploads and progress tracking.
    
    Requirements: 1.3, 1.4
    """
    try:
        # Read chunk data
        chunk_data = await chunk.read()
        
        # Process chunk
        result = await service.process_chunk(session_id, chunk_data, chunk_number)
        
        return ChunkUploadResponse(
            chunk_number=result.chunk_number,
            success=result.success,
            message=result.message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload chunk: {str(e)}")


@router.post("/upload/{session_id}/complete", response_model=CompleteUploadResponse)
async def complete_upload(
    session_id: str,
    request: CompleteUploadRequest,
    user: User = Depends(get_current_user),
    service: VideoUploadService = Depends(get_video_upload_service)
):
    """
    Complete the multipart upload and trigger transcoding.
    
    This endpoint finalizes the upload process, moves the file to permanent storage,
    and initiates transcoding jobs for the specified quality presets.
    
    Requirements: 1.4, 1.5
    """
    try:
        # Complete upload
        video = await service.complete_upload(session_id, request.quality_presets)
        
        return CompleteUploadResponse(
            video_id=str(video.id),
            status=video.status.value,
            message="Upload completed successfully. Transcoding will begin shortly."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete upload: {str(e)}")


@router.delete("/upload/{session_id}")
async def cancel_upload(
    session_id: str,
    user: User = Depends(get_current_user),
    service: VideoUploadService = Depends(get_video_upload_service)
):
    """
    Cancel an active upload session and cleanup resources.
    
    This endpoint cancels the upload, removes temporary files, and updates
    the video status appropriately.
    
    Requirements: 1.5
    """
    try:
        success = await service.cancel_upload(session_id)
        
        if success:
            return {"message": "Upload cancelled successfully"}
        else:
            raise HTTPException(status_code=404, detail="Upload session not found")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel upload: {str(e)}")


@router.get("/upload/{session_id}/progress", response_model=UploadProgressResponse)
async def get_upload_progress(
    session_id: str,
    user: User = Depends(get_current_user),
    service: VideoUploadService = Depends(get_video_upload_service)
):
    """
    Get upload progress information for an active session.
    
    This endpoint provides real-time progress information including
    chunks received, bytes uploaded, and completion percentage.
    
    Requirements: 1.3
    """
    try:
        progress = service.get_upload_progress(session_id)
        
        if progress is None:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        return UploadProgressResponse(**progress)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get upload progress: {str(e)}")


@router.post("/upload/simple")
async def simple_upload(
    title: str = Form(...),
    description: str = Form(None),
    tags: str = Form(""),  # Comma-separated tags
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    service: VideoUploadService = Depends(get_video_upload_service)
):
    """
    Simple single-file upload endpoint for smaller videos.
    
    This endpoint provides a simpler upload method for videos that don't
    require chunked upload (typically smaller files).
    
    Requirements: 1.1, 1.2
    """
    try:
        # Parse tags
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
        
        # Create metadata
        metadata = VideoMetadata(
            title=title,
            description=description,
            tags=tag_list
        )
        
        # Get file info
        file_content = await file.read()
        file_info = {
            'filename': file.filename,
            'size': len(file_content),
            'mime_type': file.content_type or 'video/mp4',
            'total_chunks': 1,
            'extension': file.filename.split('.')[-1].lower()
        }
        
        # Initiate upload
        session = await service.initiate_upload(str(user.id), metadata, file_info)
        
        # Upload single chunk
        await service.process_chunk(session.session_id, file_content, 1)
        
        # Complete upload
        video = await service.complete_upload(session.session_id, ["720p_30fps"])
        
        return {
            "video_id": str(video.id),
            "status": video.status.value,
            "message": "Video uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/validate", response_model=Dict[str, Any])
async def validate_file_info(
    request: ValidateFileRequest,
    user: User = Depends(get_current_user),
    analysis_service: VideoAnalysisService = Depends(get_video_analysis_service)
):
    """
    Validate file information before upload.
    
    This endpoint validates file format, size, and other constraints
    without requiring the actual file upload.
    
    Requirements: 1.2, 2.1, 2.2
    """
    try:
        # Validate file info
        is_valid = analysis_service.validate_file_info(
            request.filename, 
            request.file_size, 
            request.mime_type
        )
        
        # Get available quality presets based on filename (estimate)
        extension = request.filename.lower().split('.')[-1]
        
        return {
            "valid": is_valid,
            "message": "File validation passed",
            "supported_formats": analysis_service.SUPPORTED_FORMATS,
            "max_size_gb": settings.MAX_VIDEO_SIZE / (1024**3),
            "max_duration_hours": settings.MAX_VIDEO_DURATION / 3600
        }
        
    except VideoValidationError as e:
        return {
            "valid": False,
            "message": str(e),
            "supported_formats": analysis_service.SUPPORTED_FORMATS,
            "max_size_gb": settings.MAX_VIDEO_SIZE / (1024**3),
            "max_duration_hours": settings.MAX_VIDEO_DURATION / 3600
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/analyze", response_model=VideoAnalysisResponse)
async def analyze_uploaded_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    analysis_service: VideoAnalysisService = Depends(get_video_analysis_service),
    preset_service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Analyze uploaded video file and extract metadata.
    
    This endpoint accepts a video file, validates it, and extracts
    technical metadata including resolution, framerate, codec, etc.
    
    Requirements: 1.2, 2.1, 2.2
    """
    temp_file_path = None
    
    try:
        # Validate upload file
        await analysis_service.validate_upload_file(file)
        
        # Save file temporarily for analysis
        temp_dir = os.path.join(settings.MEDIA_STORAGE_PATH, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        import uuid
        temp_filename = f"analyze_{uuid.uuid4()}.{file.filename.split('.')[-1]}"
        temp_file_path = os.path.join(temp_dir, temp_filename)
        
        # Write file content
        content = await file.read()
        with open(temp_file_path, 'wb') as f:
            f.write(content)
        
        # Analyze video
        analysis = await analysis_service.analyze_video_file(temp_file_path)
        
        # Get available quality presets using the preset service
        available_presets = []
        if analysis.is_valid:
            source_info = SourceVideoInfo(
                width=analysis.width,
                height=analysis.height,
                framerate=analysis.framerate,
                bitrate=analysis.bitrate,
                duration_seconds=analysis.duration_seconds
            )
            preset_responses = preset_service.get_available_presets_for_source(source_info)
            available_presets = [p.name for p in preset_responses]
        
        return VideoAnalysisResponse(
            duration_seconds=analysis.duration_seconds,
            width=analysis.width,
            height=analysis.height,
            framerate=analysis.framerate,
            codec=analysis.codec,
            bitrate=analysis.bitrate,
            format_name=analysis.format_name,
            file_size=analysis.file_size,
            is_valid=analysis.is_valid,
            error_message=analysis.error_message,
            available_presets=available_presets
        )
        
    except VideoValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass  # Ignore cleanup errors


@router.get("/presets/{width}x{height}/{framerate}")
async def get_quality_presets(
    width: int,
    height: int,
    framerate: float,
    user: User = Depends(get_current_user),
    preset_service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Get available quality presets for given source video dimensions.
    
    This endpoint returns the quality presets that can be generated
    based on the source video resolution and framerate.
    
    Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
    """
    try:
        source_info = SourceVideoInfo(
            width=width,
            height=height,
            framerate=framerate
        )
        
        presets = preset_service.get_available_presets_for_source(source_info)
        defaults = preset_service.get_default_presets_for_source(source_info)
        
        preset_details = []
        for preset in presets:
            preset_details.append({
                "preset": preset.name,
                "width": preset.width,
                "height": preset.height,
                "framerate": int(preset.framerate.replace('fps', '')),
                "description": preset.description,
                "is_default": preset.is_default,
                "is_recommended": preset.is_recommended,
                "estimated_file_size_mb": preset.estimated_file_size_mb,
                "estimated_processing_time_minutes": preset.estimated_processing_time_minutes
            })
        
        return {
            "source_resolution": f"{width}x{height}",
            "source_framerate": framerate,
            "available_presets": preset_details,
            "recommended_presets": defaults,
            "default_preset": defaults[0] if defaults else "720p_30fps"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get presets: {str(e)}")


@router.get("/s3/status")
async def get_s3_status(
    user: User = Depends(get_current_user),
    s3_service: VideoS3Service = Depends(get_video_s3_service)
):
    """
    Get S3 service status and configuration.
    
    This endpoint provides information about S3 availability and configuration
    for debugging and monitoring purposes.
    
    Requirements: 1.4, 1.5
    """
    try:
        return {
            "s3_available": s3_service.is_available(),
            "bucket_name": s3_service.bucket_name,
            "region": s3_service.region,
            "message": "S3 service is available" if s3_service.is_available() else "S3 service not configured"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get S3 status: {str(e)}")


@router.post("/s3/cleanup")
async def cleanup_old_uploads(
    days_old: int = 7,
    user: User = Depends(get_current_user),
    s3_service: VideoS3Service = Depends(get_video_s3_service)
):
    """
    Cleanup old incomplete multipart uploads.
    
    This endpoint removes incomplete uploads older than the specified number of days
    to free up storage space and reduce costs.
    
    Requirements: 1.5
    """
    try:
        if not s3_service.is_available():
            raise HTTPException(status_code=503, detail="S3 service not available")
        
        cleaned_count = await s3_service.cleanup_old_uploads(days_old)
        
        return {
            "message": f"Cleaned up {cleaned_count} old uploads",
            "cleaned_count": cleaned_count,
            "days_old": days_old
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.get("/s3/incomplete-uploads")
async def list_incomplete_uploads(
    user: User = Depends(get_current_user),
    s3_service: VideoS3Service = Depends(get_video_s3_service)
):
    """
    List incomplete multipart uploads.
    
    This endpoint provides information about incomplete uploads for monitoring
    and debugging purposes.
    
    Requirements: 1.5
    """
    try:
        if not s3_service.is_available():
            raise HTTPException(status_code=503, detail="S3 service not available")
        
        uploads = await s3_service.list_incomplete_uploads()
        
        return {
            "incomplete_uploads": uploads,
            "count": len(uploads)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list uploads: {str(e)}")