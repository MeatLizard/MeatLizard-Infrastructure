"""
Video Thumbnails API Endpoints

Provides REST API endpoints for thumbnail management including:
- Thumbnail generation and regeneration
- Thumbnail selection and management
- Thumbnail serving and URLs
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.thumbnail_service import (
    ThumbnailService,
    ThumbnailRequest,
    ThumbnailResponse,
    ThumbnailSelectionRequest,
    get_thumbnail_service
)
from server.web.app.models import User
from server.web.app.middleware.permissions import get_current_user

router = APIRouter(prefix="/api/video/thumbnails", tags=["video-thumbnails"])


# Request/Response Models
class GenerateThumbnailsRequest(BaseModel):
    timestamps: Optional[List[float]] = None
    width: int = 320
    height: int = 180


class ThumbnailGenerationResponse(BaseModel):
    video_id: str
    thumbnails: List[ThumbnailResponse]
    selected_thumbnail: Optional[ThumbnailResponse] = None


@router.post("/videos/{video_id}/generate", response_model=ThumbnailGenerationResponse)
async def generate_video_thumbnails(
    video_id: str,
    request: GenerateThumbnailsRequest,
    user: User = Depends(get_current_user),
    service: ThumbnailService = Depends(get_thumbnail_service)
):
    """
    Generate thumbnails for a video at specified timestamps.
    
    This endpoint generates thumbnail images at multiple timestamps
    for video preview and selection purposes.
    
    Requirements: 3.2, 3.3
    """
    try:
        thumbnails = await service.regenerate_thumbnails(
            video_id=video_id,
            user_id=str(user.id),
            custom_timestamps=request.timestamps
        )
        
        # Find selected thumbnail
        selected_thumbnail = next((t for t in thumbnails if t.is_selected), None)
        
        return ThumbnailGenerationResponse(
            video_id=video_id,
            thumbnails=thumbnails,
            selected_thumbnail=selected_thumbnail
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate thumbnails: {str(e)}")


@router.get("/videos/{video_id}", response_model=List[ThumbnailResponse])
async def get_video_thumbnails(
    video_id: str,
    user: User = Depends(get_current_user),
    service: ThumbnailService = Depends(get_thumbnail_service)
):
    """
    Get all thumbnails for a video.
    
    This endpoint returns all available thumbnails for a video
    with their URLs and selection status.
    
    Requirements: 3.3, 3.4
    """
    try:
        thumbnails = await service.get_video_thumbnails(video_id)
        return thumbnails
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get thumbnails: {str(e)}")


@router.post("/videos/{video_id}/select", response_model=ThumbnailResponse)
async def select_video_thumbnail(
    video_id: str,
    request: ThumbnailSelectionRequest,
    user: User = Depends(get_current_user),
    service: ThumbnailService = Depends(get_thumbnail_service)
):
    """
    Select a thumbnail as the primary thumbnail for a video.
    
    This endpoint allows content creators to choose which thumbnail
    represents their video in listings and previews.
    
    Requirements: 3.3, 3.4
    """
    try:
        selected_thumbnail = await service.select_thumbnail(
            video_id=video_id,
            timestamp=request.selected_timestamp,
            user_id=str(user.id)
        )
        
        return selected_thumbnail
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to select thumbnail: {str(e)}")


@router.post("/videos/{video_id}/auto-select", response_model=ThumbnailResponse)
async def auto_select_best_thumbnail(
    video_id: str,
    user: User = Depends(get_current_user),
    service: ThumbnailService = Depends(get_thumbnail_service)
):
    """
    Automatically select the best thumbnail for a video.
    
    This endpoint uses content analysis to automatically choose
    the most appropriate thumbnail for the video.
    
    Requirements: 3.4
    """
    try:
        selected_thumbnail = await service.auto_select_best_thumbnail(video_id)
        
        if not selected_thumbnail:
            raise HTTPException(status_code=404, detail="No thumbnails available for auto-selection")
        
        return selected_thumbnail
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to auto-select thumbnail: {str(e)}")


@router.get("/{video_id}/{filename}")
async def serve_thumbnail_file(
    video_id: str,
    filename: str,
    service: ThumbnailService = Depends(get_thumbnail_service)
):
    """
    Serve thumbnail image file.
    
    This endpoint serves the actual thumbnail image files
    for display in web interfaces.
    
    Requirements: 3.3
    """
    try:
        content, content_type = await service.get_thumbnail_file(video_id, filename)
        
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "Content-Disposition": f"inline; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to serve thumbnail: {str(e)}")


@router.get("/videos/{video_id}/default-timestamps")
async def get_default_thumbnail_timestamps(
    video_id: str,
    user: User = Depends(get_current_user),
    service: ThumbnailService = Depends(get_thumbnail_service)
):
    """
    Get default thumbnail timestamps for a video.
    
    This endpoint returns the recommended timestamps for thumbnail
    generation based on the video duration.
    
    Requirements: 3.2, 3.4
    """
    try:
        # Get video to determine duration
        from server.web.app.models import Video
        video = await service.db.get(Video, video_id)
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        duration = float(video.duration_seconds) if video.duration_seconds else 60.0
        timestamps = service.get_default_thumbnail_timestamps(duration)
        
        return {
            "video_id": video_id,
            "duration_seconds": duration,
            "default_timestamps": timestamps,
            "timestamp_percentages": [t / duration * 100 for t in timestamps]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get default timestamps: {str(e)}")


@router.delete("/videos/{video_id}")
async def delete_video_thumbnails(
    video_id: str,
    user: User = Depends(get_current_user),
    service: ThumbnailService = Depends(get_thumbnail_service)
):
    """
    Delete all thumbnails for a video.
    
    This endpoint removes all thumbnail files associated with
    a video from both local and S3 storage.
    
    Requirements: 3.3
    """
    try:
        # Verify video ownership
        from server.web.app.models import Video
        video = await service.db.get(Video, video_id)
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        if str(video.creator_id) != str(user.id):
            raise HTTPException(status_code=403, detail="Not authorized to modify this video")
        
        # Clear thumbnails
        await service._clear_existing_thumbnails(video_id)
        
        # Update video record
        video.thumbnail_s3_key = None
        await service.db.commit()
        
        return {"message": "Thumbnails deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete thumbnails: {str(e)}")


@router.get("/videos/{video_id}/selected")
async def get_selected_thumbnail(
    video_id: str,
    user: User = Depends(get_current_user),
    service: ThumbnailService = Depends(get_thumbnail_service)
):
    """
    Get the currently selected thumbnail for a video.
    
    This endpoint returns information about the thumbnail
    that is currently selected as the primary thumbnail.
    
    Requirements: 3.4
    """
    try:
        thumbnails = await service.get_video_thumbnails(video_id)
        selected_thumbnail = next((t for t in thumbnails if t.is_selected), None)
        
        if not selected_thumbnail:
            return {"message": "No thumbnail selected", "selected_thumbnail": None}
        
        return {
            "video_id": video_id,
            "selected_thumbnail": selected_thumbnail
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get selected thumbnail: {str(e)}")


@router.post("/videos/{video_id}/regenerate-defaults", response_model=ThumbnailGenerationResponse)
async def regenerate_default_thumbnails(
    video_id: str,
    user: User = Depends(get_current_user),
    service: ThumbnailService = Depends(get_thumbnail_service)
):
    """
    Regenerate thumbnails using default timestamps.
    
    This endpoint regenerates thumbnails at the default timestamp
    positions (10%, 25%, 50%, 75%, 90% of video duration).
    
    Requirements: 3.2, 3.4
    """
    try:
        thumbnails = await service.regenerate_thumbnails(
            video_id=video_id,
            user_id=str(user.id),
            custom_timestamps=None  # Use defaults
        )
        
        # Find selected thumbnail
        selected_thumbnail = next((t for t in thumbnails if t.is_selected), None)
        
        return ThumbnailGenerationResponse(
            video_id=video_id,
            thumbnails=thumbnails,
            selected_thumbnail=selected_thumbnail
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to regenerate thumbnails: {str(e)}")


@router.get("/videos/{video_id}/stats")
async def get_thumbnail_stats(
    video_id: str,
    user: User = Depends(get_current_user),
    service: ThumbnailService = Depends(get_thumbnail_service)
):
    """
    Get statistics about video thumbnails.
    
    This endpoint provides information about thumbnail count,
    total file size, and other statistics.
    
    Requirements: 3.3
    """
    try:
        thumbnails = await service.get_video_thumbnails(video_id)
        
        total_size = sum(t.file_size for t in thumbnails)
        selected_count = sum(1 for t in thumbnails if t.is_selected)
        
        return {
            "video_id": video_id,
            "thumbnail_count": len(thumbnails),
            "total_file_size_bytes": total_size,
            "total_file_size_mb": total_size / (1024 * 1024),
            "selected_count": selected_count,
            "has_selected_thumbnail": selected_count > 0,
            "timestamps": [t.timestamp for t in thumbnails]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get thumbnail stats: {str(e)}")