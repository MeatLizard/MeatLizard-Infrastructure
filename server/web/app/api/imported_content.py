"""
Imported Content Management API endpoints.
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db, get_current_user
from ..models import User, VideoStatus, VideoVisibility
from ..services.imported_content_service import ImportedContentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/imported-content", tags=["imported_content"])

# Request/Response Models

class UpdateVideoMetadataRequest(BaseModel):
    """Request model for updating video metadata"""
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=5000)
    tags: Optional[List[str]] = None
    category: Optional[str] = Field(None, max_length=50)
    visibility: Optional[VideoVisibility] = None

class BulkUpdateRequest(BaseModel):
    """Request model for bulk updates"""
    video_ids: List[str] = Field(..., min_items=1, max_items=100)
    visibility: Optional[VideoVisibility] = None
    category: Optional[str] = Field(None, max_length=50)

class AttributionResponse(BaseModel):
    """Response model for attribution information"""
    source_url: str
    platform: str
    original_title: Optional[str] = None
    original_uploader: Optional[str] = None
    original_upload_date: Optional[str] = None
    original_duration: Optional[int] = None
    original_view_count: Optional[int] = None
    original_like_count: Optional[int] = None
    import_date: str
    imported_by: Optional[str] = None

class ImportedVideoResponse(BaseModel):
    """Response model for imported video"""
    id: str
    title: str
    description: Optional[str] = None
    status: VideoStatus
    visibility: VideoVisibility
    created_at: str
    duration_seconds: int
    file_size: int
    thumbnail_s3_key: Optional[str] = None
    attribution: AttributionResponse
    import_job: dict

class ComplianceCheckResponse(BaseModel):
    """Response model for compliance check"""
    video_id: str
    compliant: bool
    issues: List[str]
    attribution_complete: bool
    recommendations: List[str]

# API Endpoints

@router.get("/videos", response_model=List[ImportedVideoResponse])
async def get_imported_videos(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    status: Optional[VideoStatus] = Query(None, description="Filter by video status"),
    limit: int = Query(50, ge=1, le=100, description="Number of videos to return"),
    offset: int = Query(0, ge=0, description="Number of videos to skip"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get imported videos for current user"""
    try:
        service = ImportedContentService(db)
        
        videos = await service.get_imported_videos(
            user_id=str(current_user.id),
            platform=platform,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return [ImportedVideoResponse(**video) for video in videos]
        
    except Exception as e:
        logger.error(f"Failed to get imported videos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get imported videos"
        )

@router.get("/videos/{video_id}")
async def get_imported_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific imported video with full details"""
    try:
        service = ImportedContentService(db)
        
        video = await service.get_imported_video_by_id(str(video_id))
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Check if user owns the video
        if video["creator"] and video["creator"]["id"] != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this video"
            )
        
        return video
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get imported video: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get imported video"
        )

@router.put("/videos/{video_id}")
async def update_imported_video(
    video_id: UUID,
    request: UpdateVideoMetadataRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update imported video metadata"""
    try:
        service = ImportedContentService(db)
        
        success = await service.update_imported_video_metadata(
            video_id=str(video_id),
            title=request.title,
            description=request.description,
            tags=request.tags,
            category=request.category,
            visibility=request.visibility,
            user_id=str(current_user.id)
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found or not authorized"
            )
        
        return {"message": "Video updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update imported video: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update video"
        )

@router.delete("/videos/{video_id}")
async def delete_imported_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete imported video"""
    try:
        service = ImportedContentService(db)
        
        success = await service.delete_imported_video(
            video_id=str(video_id),
            user_id=str(current_user.id)
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found or not authorized"
            )
        
        return {"message": "Video deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete imported video: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete video"
        )

@router.post("/videos/bulk-update")
async def bulk_update_videos(
    request: BulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk update multiple imported videos"""
    try:
        service = ImportedContentService(db)
        
        updated_count = await service.bulk_update_imported_videos(
            video_ids=request.video_ids,
            visibility=request.visibility,
            category=request.category,
            user_id=str(current_user.id)
        )
        
        return {
            "message": f"Updated {updated_count} videos successfully",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Failed to bulk update videos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk update videos"
        )

@router.get("/statistics")
async def get_import_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days to include in statistics"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get import statistics for current user"""
    try:
        service = ImportedContentService(db)
        
        stats = await service.get_import_statistics(
            user_id=str(current_user.id),
            days=days
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get import statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get import statistics"
        )

@router.get("/videos/{video_id}/compliance", response_model=ComplianceCheckResponse)
async def check_video_compliance(
    video_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check copyright compliance for imported video"""
    try:
        service = ImportedContentService(db)
        
        compliance = await service.check_copyright_compliance(str(video_id))
        
        return ComplianceCheckResponse(**compliance)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to check video compliance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check video compliance"
        )

@router.get("/videos/{video_id}/attribution")
async def get_video_attribution(
    video_id: UUID,
    format_type: str = Query("standard", regex="^(standard|youtube|academic)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate attribution text for imported video"""
    try:
        service = ImportedContentService(db)
        
        attribution_text = await service.generate_attribution_text(
            video_id=str(video_id),
            format_type=format_type
        )
        
        return {
            "video_id": str(video_id),
            "format_type": format_type,
            "attribution_text": attribution_text
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to generate attribution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate attribution text"
        )

@router.get("/organize")
async def organize_imported_content(
    organization_type: str = Query("platform", regex="^(platform|date|uploader|status)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Organize imported content by various criteria"""
    try:
        service = ImportedContentService(db)
        
        organized_content = await service.organize_imported_content(
            organization_type=organization_type,
            user_id=str(current_user.id)
        )
        
        return organized_content
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to organize content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to organize imported content"
        )

# Admin endpoints (require admin permissions)

@router.get("/admin/videos")
async def admin_get_all_imported_videos(
    platform: Optional[str] = Query(None),
    status: Optional[VideoStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all imported videos (admin only)"""
    # TODO: Add admin permission check
    try:
        service = ImportedContentService(db)
        
        videos = await service.get_imported_videos(
            platform=platform,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return videos
        
    except Exception as e:
        logger.error(f"Failed to get all imported videos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get imported videos"
        )

@router.get("/admin/statistics")
async def admin_get_global_statistics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get global import statistics (admin only)"""
    # TODO: Add admin permission check
    try:
        service = ImportedContentService(db)
        
        stats = await service.get_import_statistics(days=days)
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get global statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get global statistics"
        )