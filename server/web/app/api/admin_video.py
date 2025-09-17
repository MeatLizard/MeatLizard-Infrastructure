"""
Admin video management API endpoints.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..dependencies import get_db, get_current_user
from ..models import User, VideoStatus, VideoVisibility
from ..services.admin_video_service import AdminVideoService


router = APIRouter(prefix="/admin/videos", tags=["admin-videos"])


class BulkVideoUpdateRequest(BaseModel):
    video_ids: List[str]
    visibility: Optional[str] = None


class TranscodingJobRetryRequest(BaseModel):
    job_id: str


# Dependency to check admin permissions
async def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the current user has admin permissions."""
    # TODO: Implement proper admin role checking
    # For now, we'll assume all authenticated users are admins
    # In production, this should check for admin role/permissions
    return current_user


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get comprehensive video platform statistics for admin dashboard."""
    service = AdminVideoService()
    stats = await service.get_video_dashboard_stats(db)
    return stats


@router.get("/list")
async def get_videos_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    creator: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get paginated list of videos with filtering and sorting."""
    
    # Validate enum values
    status_filter = None
    if status:
        try:
            status_filter = VideoStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    visibility_filter = None
    if visibility:
        try:
            visibility_filter = VideoVisibility(visibility)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid visibility: {visibility}")
    
    # Validate sort parameters
    valid_sort_fields = ['created_at', 'updated_at', 'title', 'file_size', 'duration_seconds']
    if sort_by not in valid_sort_fields:
        raise HTTPException(status_code=400, detail=f"Invalid sort field: {sort_by}")
    
    if sort_order not in ['asc', 'desc']:
        raise HTTPException(status_code=400, detail=f"Invalid sort order: {sort_order}")
    
    service = AdminVideoService()
    result = await service.get_videos_list(
        db=db,
        page=page,
        per_page=per_page,
        status_filter=status_filter,
        visibility_filter=visibility_filter,
        creator_filter=creator,
        search_query=search,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    return result


@router.get("/{video_id}/details")
async def get_video_details(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get detailed information about a specific video."""
    
    try:
        video_uuid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid video ID format")
    
    service = AdminVideoService()
    video_details = await service.get_video_details(db, video_uuid)
    
    if not video_details:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return video_details


@router.post("/transcoding/retry")
async def retry_transcoding_job(
    request: TranscodingJobRetryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Retry a failed transcoding job."""
    
    try:
        job_uuid = uuid.UUID(request.job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    service = AdminVideoService()
    success = await service.retry_failed_transcoding_job(db, job_uuid)
    
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or not in failed state")
    
    return {"message": "Transcoding job queued for retry", "job_id": request.job_id}


@router.post("/bulk/update-visibility")
async def bulk_update_visibility(
    request: BulkVideoUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Update visibility for multiple videos."""
    
    if not request.visibility:
        raise HTTPException(status_code=400, detail="Visibility is required")
    
    try:
        visibility = VideoVisibility(request.visibility)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid visibility: {request.visibility}")
    
    # Convert string IDs to UUIDs
    try:
        video_uuids = [uuid.UUID(vid_id) for vid_id in request.video_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid video ID format")
    
    service = AdminVideoService()
    updated_count = await service.bulk_update_video_visibility(db, video_uuids, visibility)
    
    return {
        "message": f"Updated visibility for {updated_count} videos",
        "updated_count": updated_count,
        "visibility": request.visibility
    }


@router.post("/bulk/delete")
async def bulk_delete_videos(
    request: BulkVideoUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Mark multiple videos as deleted."""
    
    # Convert string IDs to UUIDs
    try:
        video_uuids = [uuid.UUID(vid_id) for vid_id in request.video_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid video ID format")
    
    service = AdminVideoService()
    deleted_count = await service.bulk_delete_videos(db, video_uuids)
    
    return {
        "message": f"Marked {deleted_count} videos as deleted",
        "deleted_count": deleted_count
    }


@router.get("/storage/report")
async def get_storage_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Generate detailed storage usage report."""
    
    service = AdminVideoService()
    report = await service.get_storage_usage_report(db)
    return report


@router.get("/transcoding/queue-status")
async def get_transcoding_queue_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get current transcoding queue status and performance metrics."""
    
    service = AdminVideoService()
    status = await service.get_transcoding_queue_status(db)
    return status


@router.get("/cleanup/recommendations")
async def get_cleanup_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get recommendations for storage cleanup."""
    
    # This could include:
    # - Videos marked as deleted but not cleaned up
    # - Failed transcoding jobs older than X days
    # - Orphaned transcoding outputs
    # - Large videos with low view counts
    
    service = AdminVideoService()
    
    # Get videos marked as deleted
    deleted_videos = await service.get_videos_list(
        db=db,
        page=1,
        per_page=100,
        status_filter=VideoStatus.deleted
    )
    
    # Get failed transcoding jobs
    from datetime import datetime, timedelta
    from sqlalchemy import select, and_
    from ..models import TranscodingJob, TranscodingStatus
    
    old_failed_jobs_query = select(TranscodingJob).where(
        and_(
            TranscodingJob.status == TranscodingStatus.failed,
            TranscodingJob.created_at < datetime.utcnow() - timedelta(days=7)
        )
    ).limit(50)
    
    result = await db.execute(old_failed_jobs_query)
    old_failed_jobs = result.scalars().all()
    
    recommendations = {
        'deleted_videos_to_cleanup': {
            'count': len(deleted_videos['videos']),
            'estimated_storage_gb': sum(v['file_size_mb'] for v in deleted_videos['videos']) / 1024
        },
        'old_failed_jobs_to_remove': {
            'count': len(old_failed_jobs),
            'jobs': [
                {
                    'id': str(job.id),
                    'video_id': str(job.video_id),
                    'quality_preset': job.quality_preset,
                    'created_at': job.created_at.isoformat(),
                    'error_message': job.error_message
                }
                for job in old_failed_jobs
            ]
        }
    }
    
    return recommendations


@router.get("/users/management-data")
async def get_user_management_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get user management data for admin dashboard."""
    
    service = AdminVideoService()
    data = await service.get_user_management_data(db)
    return data


@router.post("/users/{user_id}/manage-access")
async def manage_user_access(
    user_id: str,
    action: str,
    reason: Optional[str] = None,
    duration_hours: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Manage user access (suspend, ban, activate)."""
    
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    valid_actions = ['suspend', 'ban', 'activate']
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")
    
    service = AdminVideoService()
    result = await service.manage_user_access(
        db=db,
        user_id=user_uuid,
        action=action,
        reason=reason,
        duration_hours=duration_hours
    )
    
    if not result['success']:
        raise HTTPException(status_code=404, detail=result['message'])
    
    return result


@router.get("/moderation/reports-summary")
async def get_moderation_reports_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get summary of content reports for admin dashboard."""
    
    service = AdminVideoService()
    summary = await service.get_content_reports_summary(db)
    return summary