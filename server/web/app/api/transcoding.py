"""
API endpoints for transcoding job management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any
import uuid

from server.web.app.db import get_db_session
from server.web.app.models import TranscodingJob, Video
from server.web.app.services.video_transcoding_service import VideoTranscodingService
from server.web.app.config import settings

router = APIRouter(prefix="/api/transcoding", tags=["transcoding"])

async def get_transcoding_service(db: AsyncSession = Depends(get_db_session)) -> VideoTranscodingService:
    """Dependency to get transcoding service."""
    return VideoTranscodingService(db, settings.REDIS_URL)

@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_transcoding_job(
    video_id: str,
    quality_preset: str,
    target_resolution: str,
    target_framerate: int,
    target_bitrate: int,
    transcoding_service: VideoTranscodingService = Depends(get_transcoding_service),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new transcoding job."""
    try:
        # Validate video exists
        video = await db.get(Video, video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Queue transcoding job
        job = await transcoding_service.queue_transcoding_job(
            video_id=video_id,
            quality_preset=quality_preset,
            target_resolution=target_resolution,
            target_framerate=target_framerate,
            target_bitrate=target_bitrate
        )
        
        return {
            "job_id": str(job.id),
            "video_id": video_id,
            "quality_preset": quality_preset,
            "status": job.status.value,
            "created_at": job.created_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transcoding job: {str(e)}"
        )

@router.get("/jobs/{job_id}")
async def get_transcoding_job(
    job_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get transcoding job details."""
    try:
        job = await db.get(TranscodingJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcoding job not found"
            )
        
        return {
            "job_id": str(job.id),
            "video_id": str(job.video_id),
            "quality_preset": job.quality_preset,
            "target_resolution": job.target_resolution,
            "target_framerate": job.target_framerate,
            "target_bitrate": job.target_bitrate,
            "status": job.status.value,
            "progress_percent": job.progress_percent,
            "error_message": job.error_message,
            "output_s3_key": job.output_s3_key,
            "hls_manifest_s3_key": job.hls_manifest_s3_key,
            "output_file_size": job.output_file_size,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transcoding job: {str(e)}"
        )

@router.get("/jobs")
async def list_transcoding_jobs(
    video_id: str = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session)
):
    """List transcoding jobs with optional filters."""
    try:
        query = select(TranscodingJob)
        
        if video_id:
            query = query.where(TranscodingJob.video_id == video_id)
        
        if status:
            query = query.where(TranscodingJob.status == status)
        
        query = query.order_by(TranscodingJob.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        return {
            "jobs": [
                {
                    "job_id": str(job.id),
                    "video_id": str(job.video_id),
                    "quality_preset": job.quality_preset,
                    "status": job.status.value,
                    "progress_percent": job.progress_percent,
                    "created_at": job.created_at.isoformat(),
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None
                }
                for job in jobs
            ],
            "total": len(jobs),
            "offset": offset,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list transcoding jobs: {str(e)}"
        )

@router.get("/queue/stats")
async def get_queue_stats(
    transcoding_service: VideoTranscodingService = Depends(get_transcoding_service)
):
    """Get transcoding queue statistics."""
    try:
        stats = await transcoding_service.get_queue_stats()
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue stats: {str(e)}"
        )

@router.post("/jobs/{job_id}/retry")
async def retry_transcoding_job(
    job_id: str,
    transcoding_service: VideoTranscodingService = Depends(get_transcoding_service),
    db: AsyncSession = Depends(get_db_session)
):
    """Manually retry a failed transcoding job."""
    try:
        job = await db.get(TranscodingJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcoding job not found"
            )
        
        if job.status not in ["failed", "completed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job can only be retried if it's failed or completed"
            )
        
        # Re-queue the job
        new_job = await transcoding_service.queue_transcoding_job(
            video_id=str(job.video_id),
            quality_preset=job.quality_preset,
            target_resolution=job.target_resolution,
            target_framerate=job.target_framerate,
            target_bitrate=job.target_bitrate
        )
        
        return {
            "message": "Job queued for retry",
            "new_job_id": str(new_job.id),
            "original_job_id": job_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry transcoding job: {str(e)}"
        )

@router.delete("/jobs/{job_id}")
async def cancel_transcoding_job(
    job_id: str,
    transcoding_service: VideoTranscodingService = Depends(get_transcoding_service),
    db: AsyncSession = Depends(get_db_session)
):
    """Cancel a queued or processing transcoding job."""
    try:
        job = await db.get(TranscodingJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcoding job not found"
            )
        
        if job.status in ["completed", "failed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel completed or failed job"
            )
        
        # Mark job as failed with cancellation message
        await transcoding_service.fail_job(job_id, "Job cancelled by user")
        
        return {"message": "Job cancelled successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel transcoding job: {str(e)}"
        )