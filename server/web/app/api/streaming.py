"""
API endpoints for video streaming and HLS management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Header
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional
import uuid
import hashlib
import hmac
import time
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from server.web.app.db import get_db_session
from server.web.app.models import Video, VideoStatus, VideoVisibility, TranscodingJob, TranscodingStatus, ViewSession, User
from server.web.app.services.hls_service import HLSService
from server.web.app.services.video_s3_service import VideoS3Service
from server.web.app.services.streaming_service import StreamingService
from server.web.app.config import settings

router = APIRouter(prefix="/api/streaming", tags=["streaming"])

async def get_hls_service() -> HLSService:
    """Dependency to get HLS service."""
    return HLSService(settings.S3_BUCKET_NAME)

async def get_s3_service() -> VideoS3Service:
    """Dependency to get S3 service."""
    return VideoS3Service(settings.S3_BUCKET_NAME)

async def get_streaming_service(db: AsyncSession = Depends(get_db_session)) -> StreamingService:
    """Dependency to get streaming service."""
    return StreamingService(db)

@router.get("/videos/{video_id}/manifest")
async def get_video_manifest(
    video_id: str,
    request: Request,
    quality: Optional[str] = None,
    user_id: Optional[str] = None,
    session_token: Optional[str] = None,
    streaming_service: StreamingService = Depends(get_streaming_service)
):
    """
    Get HLS manifest for video streaming with access control.
    
    Args:
        video_id: Video identifier
        quality: Specific quality preset (optional)
        user_id: User identifier for access control (optional)
        session_token: Viewing session token (optional)
    
    Returns:
        Streaming manifest with signed URLs
    """
    try:
        # Get client IP for access control
        client_ip = request.client.host
        
        # Get streaming manifest with access control
        manifest = await streaming_service.get_streaming_manifest(
            video_id=video_id,
            user_id=user_id,
            quality=quality,
            session_token=session_token
        )
        
        return manifest
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get video manifest for {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get video manifest"
        )

@router.get("/videos/{video_id}/qualities")
async def get_available_qualities(
    video_id: str,
    request: Request,
    user_id: Optional[str] = None,
    bandwidth_kbps: Optional[int] = None,
    device_type: Optional[str] = None,
    streaming_service: StreamingService = Depends(get_streaming_service),
    db: AsyncSession = Depends(get_db_session),
    hls_service: HLSService = Depends(get_hls_service)
):
    """
    Get available quality variants with recommendations.
    
    Args:
        video_id: Video identifier
        user_id: User identifier for access control
        bandwidth_kbps: Available bandwidth for quality recommendation
        device_type: Device type (mobile, tablet, desktop)
    
    Returns:
        Available qualities with recommendations and transcoding status
    """
    try:
        # Check access permissions
        await streaming_service.check_video_access(video_id, user_id)
        
        # Get quality recommendation
        recommendation = await streaming_service.get_quality_recommendation(
            video_id=video_id,
            bandwidth_kbps=bandwidth_kbps,
            device_type=device_type
        )
        
        # Get transcoding job status for each quality
        result = await db.execute(
            select(TranscodingJob).where(TranscodingJob.video_id == video_id)
        )
        transcoding_jobs = result.scalars().all()
        
        # Enhance quality info with transcoding status
        for quality in recommendation["available_qualities"]:
            quality_preset = quality["quality_preset"]
            job = next((j for j in transcoding_jobs if j.quality_preset == quality_preset), None)
            
            if job:
                quality["transcoding_status"] = job.status.value
                quality["progress_percent"] = job.progress_percent
                quality["file_size"] = job.output_file_size
                quality["completed_at"] = job.completed_at.isoformat() if job.completed_at else None
            else:
                quality["transcoding_status"] = "not_started"
                quality["progress_percent"] = 0
        
        return {
            "video_id": video_id,
            "recommendation": recommendation,
            "master_playlist_url": streaming_service.generate_signed_streaming_url(video_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get available qualities for {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get available qualities"
        )

@router.post("/videos/{video_id}/signed-url")
async def generate_signed_streaming_url(
    video_id: str,
    request: Request,
    quality: Optional[str] = None,
    expires_in: int = 7200,
    user_id: Optional[str] = None,
    streaming_service: StreamingService = Depends(get_streaming_service)
):
    """
    Generate signed URL for secure video streaming.
    
    Args:
        video_id: Video identifier
        quality: Specific quality preset (optional, defaults to master playlist)
        expires_in: URL expiration time in seconds (default: 2 hours)
        user_id: User identifier for access control
    
    Returns:
        Signed streaming URL with expiration info
    """
    try:
        # Check access permissions
        await streaming_service.check_video_access(video_id, user_id)
        
        # Generate signed URL
        signed_url = streaming_service.generate_signed_streaming_url(
            video_id=video_id,
            quality=quality,
            expires_in=expires_in
        )
        
        return {
            "video_id": video_id,
            "quality": quality,
            "signed_url": signed_url,
            "expires_in": expires_in,
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in),
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate signed URL for video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate signed streaming URL"
        )

@router.post("/videos/{video_id}/sessions")
async def create_viewing_session(
    video_id: str,
    request: Request,
    user_id: Optional[str] = None,
    user_agent: Optional[str] = Header(None),
    streaming_service: StreamingService = Depends(get_streaming_service)
):
    """
    Create a new viewing session for progress tracking.
    
    Args:
        video_id: Video identifier
        user_id: User identifier (optional for anonymous viewing)
        user_agent: Client user agent string
    
    Returns:
        Viewing session information
    """
    try:
        # Check access permissions
        await streaming_service.check_video_access(video_id, user_id)
        
        # Get client IP
        client_ip = request.client.host
        
        # Create viewing session
        view_session = await streaming_service.create_viewing_session(
            video_id=video_id,
            user_id=user_id,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        return {
            "session_id": str(view_session.id),
            "session_token": view_session.session_token,
            "video_id": video_id,
            "user_id": user_id,
            "started_at": view_session.started_at.isoformat(),
            "current_position": view_session.current_position_seconds
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create viewing session for video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create viewing session"
        )

@router.get("/bandwidth-test")
async def bandwidth_detection_endpoint(
    request: Request,
    test_size_kb: int = 100
):
    """
    Bandwidth detection endpoint for quality recommendation.
    
    Args:
        test_size_kb: Size of test data in KB (default: 100KB)
    
    Returns:
        Test data for bandwidth measurement
    """
    try:
        # Limit test size to prevent abuse
        test_size_kb = min(test_size_kb, 1000)  # Max 1MB
        
        # Generate test data
        test_data = "0" * (test_size_kb * 1024)
        
        # Add timing headers for client-side calculation
        response = JSONResponse({
            "test_size_bytes": len(test_data),
            "test_size_kb": test_size_kb,
            "server_timestamp": time.time(),
            "data": test_data
        })
        
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
        
    except Exception as e:
        logger.error(f"Bandwidth test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bandwidth test failed"
        )

@router.get("/videos/{video_id}/recommendation")
async def get_quality_recommendation(
    video_id: str,
    request: Request,
    bandwidth_kbps: Optional[int] = None,
    device_type: Optional[str] = None,
    user_id: Optional[str] = None,
    streaming_service: StreamingService = Depends(get_streaming_service)
):
    """
    Get quality recommendation based on bandwidth and device.
    
    Args:
        video_id: Video identifier
        bandwidth_kbps: Available bandwidth in kbps
        device_type: Device type (mobile, tablet, desktop)
        user_id: User identifier for access control
    
    Returns:
        Quality recommendation with reasoning
    """
    try:
        # Check access permissions
        await streaming_service.check_video_access(video_id, user_id)
        
        # Get quality recommendation
        recommendation = await streaming_service.get_quality_recommendation(
            video_id=video_id,
            bandwidth_kbps=bandwidth_kbps,
            device_type=device_type
        )
        
        return {
            "video_id": video_id,
            "recommendation": recommendation,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get quality recommendation for video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quality recommendation"
        )

@router.post("/videos/{video_id}/progress")
async def update_viewing_progress(
    video_id: str,
    progress_data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Update viewing progress for a session.
    
    Args:
        video_id: Video identifier
        progress_data: Progress information including session_token, position, etc.
    
    Returns:
        Updated progress information
    """
    try:
        session_token = progress_data.get('session_token')
        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session token required"
            )
        
        # Find viewing session
        result = await db.execute(
            select(ViewSession).where(
                ViewSession.session_token == session_token,
                ViewSession.video_id == video_id
            )
        )
        view_session = result.scalar_one_or_none()
        
        if not view_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Viewing session not found"
            )
        
        # Update progress
        current_position = progress_data.get('current_position_seconds', 0)
        completion_percentage = progress_data.get('completion_percentage', 0)
        quality_switches = progress_data.get('quality_switches', 0)
        buffering_events = progress_data.get('buffering_events', 0)
        
        # Calculate watch time increment
        time_since_last_update = (datetime.utcnow() - view_session.last_heartbeat).total_seconds()
        watch_time_increment = min(time_since_last_update, 15)  # Cap at 15 seconds
        
        # Update session
        view_session.current_position_seconds = current_position
        view_session.completion_percentage = completion_percentage
        view_session.total_watch_time_seconds += watch_time_increment
        view_session.quality_switches = quality_switches
        view_session.buffering_events = buffering_events
        view_session.last_heartbeat = datetime.utcnow()
        
        await db.commit()
        
        return {
            "session_id": str(view_session.id),
            "video_id": video_id,
            "current_position": view_session.current_position_seconds,
            "completion_percentage": view_session.completion_percentage,
            "total_watch_time": view_session.total_watch_time_seconds,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update viewing progress for video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update viewing progress"
        )

@router.get("/videos/{video_id}/sessions/{session_token}")
async def get_viewing_session(
    video_id: str,
    session_token: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get viewing session information.
    
    Args:
        video_id: Video identifier
        session_token: Session token
    
    Returns:
        Viewing session details
    """
    try:
        # Find viewing session
        result = await db.execute(
            select(ViewSession).where(
                ViewSession.session_token == session_token,
                ViewSession.video_id == video_id
            )
        )
        view_session = result.scalar_one_or_none()
        
        if not view_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Viewing session not found"
            )
        
        return {
            "session_id": str(view_session.id),
            "session_token": view_session.session_token,
            "video_id": video_id,
            "user_id": str(view_session.user_id) if view_session.user_id else None,
            "current_position": view_session.current_position_seconds,
            "completion_percentage": view_session.completion_percentage,
            "total_watch_time": view_session.total_watch_time_seconds,
            "quality_switches": view_session.quality_switches,
            "buffering_events": view_session.buffering_events,
            "started_at": view_session.started_at.isoformat(),
            "last_heartbeat": view_session.last_heartbeat.isoformat(),
            "ended_at": view_session.ended_at.isoformat() if view_session.ended_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get viewing session {session_token}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get viewing session"
        )

@router.post("/videos/{video_id}/sessions/{session_token}/end")
async def end_viewing_session(
    video_id: str,
    session_token: str,
    final_data: dict,
    db: AsyncSession = Depends(get_db_session)
):
    """
    End a viewing session and record final statistics.
    
    Args:
        video_id: Video identifier
        session_token: Session token
        final_data: Final viewing statistics
    
    Returns:
        Final session summary
    """
    try:
        # Find viewing session
        result = await db.execute(
            select(ViewSession).where(
                ViewSession.session_token == session_token,
                ViewSession.video_id == video_id
            )
        )
        view_session = result.scalar_one_or_none()
        
        if not view_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Viewing session not found"
            )
        
        # Update final statistics
        view_session.current_position_seconds = final_data.get('current_position_seconds', view_session.current_position_seconds)
        view_session.completion_percentage = final_data.get('completion_percentage', view_session.completion_percentage)
        view_session.quality_switches = final_data.get('quality_switches', view_session.quality_switches)
        view_session.buffering_events = final_data.get('buffering_events', view_session.buffering_events)
        view_session.ended_at = datetime.utcnow()
        
        await db.commit()
        
        return {
            "session_id": str(view_session.id),
            "video_id": video_id,
            "total_watch_time": view_session.total_watch_time_seconds,
            "completion_percentage": view_session.completion_percentage,
            "quality_switches": view_session.quality_switches,
            "buffering_events": view_session.buffering_events,
            "session_duration": (view_session.ended_at - view_session.started_at).total_seconds(),
            "ended_at": view_session.ended_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to end viewing session {session_token}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end viewing session"
        )

@router.get("/users/{user_id}/viewing-history")
async def get_viewing_history(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get user's viewing history.
    
    Args:
        user_id: User identifier
        limit: Maximum number of records to return
        offset: Number of records to skip
    
    Returns:
        List of viewing history entries
    """
    try:
        # Get viewing sessions for user
        result = await db.execute(
            select(ViewSession, Video)
            .join(Video, ViewSession.video_id == Video.id)
            .where(ViewSession.user_id == user_id)
            .order_by(ViewSession.last_heartbeat.desc())
            .limit(limit)
            .offset(offset)
        )
        
        sessions_and_videos = result.all()
        
        history = []
        for session, video in sessions_and_videos:
            history.append({
                "session_id": str(session.id),
                "video_id": str(video.id),
                "video_title": video.title,
                "video_duration": video.duration_seconds,
                "current_position": session.current_position_seconds,
                "completion_percentage": session.completion_percentage,
                "total_watch_time": session.total_watch_time_seconds,
                "last_watched": session.last_heartbeat.isoformat(),
                "can_resume": session.current_position_seconds > 0 and session.completion_percentage < 95,
                "thumbnail_url": f"/api/videos/{video.id}/thumbnail" if video.thumbnail_s3_key else None
            })
        
        return {
            "user_id": user_id,
            "history": history,
            "limit": limit,
            "offset": offset,
            "total_count": len(history)  # TODO: Add proper count query
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get viewing history for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get viewing history"
        )

@router.get("/videos/{video_id}/resume-position")
async def get_resume_position(
    video_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get resume position for a video for a specific user.
    
    Args:
        video_id: Video identifier
        user_id: User identifier
    
    Returns:
        Resume position information
    """
    try:
        # Get most recent viewing session for this user and video
        result = await db.execute(
            select(ViewSession)
            .where(
                ViewSession.video_id == video_id,
                ViewSession.user_id == user_id
            )
            .order_by(ViewSession.last_heartbeat.desc())
            .limit(1)
        )
        
        latest_session = result.scalar_one_or_none()
        
        if not latest_session:
            return {
                "video_id": video_id,
                "user_id": user_id,
                "has_resume_position": False,
                "resume_position": 0,
                "completion_percentage": 0
            }
        
        # Only offer resume if user watched more than 30 seconds and less than 95%
        can_resume = (
            latest_session.current_position_seconds > 30 and 
            latest_session.completion_percentage < 95
        )
        
        return {
            "video_id": video_id,
            "user_id": user_id,
            "has_resume_position": can_resume,
            "resume_position": latest_session.current_position_seconds if can_resume else 0,
            "completion_percentage": latest_session.completion_percentage,
            "last_watched": latest_session.last_heartbeat.isoformat(),
            "total_watch_time": latest_session.total_watch_time_seconds
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get resume position for video {video_id}, user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get resume position"
        )

@router.get("/videos/{video_id}/stream")
async def stream_video(
    video_id: str,
    request: Request,
    quality: Optional[str] = None,
    expires: Optional[int] = None,
    signature: Optional[str] = None,
    user_id: Optional[str] = None,
    streaming_service: StreamingService = Depends(get_streaming_service),
    hls_service: HLSService = Depends(get_hls_service)
):
    """
    Stream video with access control and signed URL validation.
    
    Args:
        video_id: Video identifier
        quality: Specific quality preset
        expires: URL expiration timestamp (for signed URLs)
        signature: URL signature (for signed URLs)
        user_id: User identifier for access control
    
    Returns:
        Redirect to streaming URL or direct stream
    """
    try:
        # Validate signed URL if provided
        if expires and signature:
            streaming_service.validate_signed_url(video_id, quality, expires, signature)
        else:
            # Check access permissions for non-signed requests
            await streaming_service.check_video_access(video_id, user_id)
        
        # Get streaming URL and redirect
        if expires and signature:
            # For signed URLs, redirect to S3 directly
            streaming_url = hls_service.get_streaming_url(video_id, quality)
        else:
            # Generate new signed URL for security
            streaming_url = streaming_service.generate_signed_streaming_url(video_id, quality)
        
        return RedirectResponse(url=streaming_url, status_code=302)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream video {video_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stream video"
        )

@router.get("/videos/{video_id}/segments/{quality}/{segment_name}")
async def get_video_segment(
    video_id: str,
    quality: str,
    segment_name: str,
    db: AsyncSession = Depends(get_db_session),
    s3_service: VideoS3Service = Depends(get_s3_service)
):
    """Get a specific HLS segment (for direct serving if needed)."""
    try:
        # Validate video exists
        video = await db.get(Video, video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Check video visibility
        if video.visibility == VideoVisibility.private:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Video is private"
            )
        
        # Construct S3 key for segment
        segment_s3_key = f"transcoded/{video_id}/{quality}/segments/{segment_name}"
        
        # Check if segment exists
        if not await s3_service.file_exists(segment_s3_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Segment not found"
            )
        
        # Generate signed URL for segment
        signed_url = await s3_service.generate_presigned_url(segment_s3_key, expires_in=3600)
        
        return RedirectResponse(url=signed_url, status_code=302)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video segment: {str(e)}"
        )

@router.get("/videos/{video_id}/info")
async def get_streaming_info(
    video_id: str,
    db: AsyncSession = Depends(get_db_session),
    hls_service: HLSService = Depends(get_hls_service)
):
    """Get comprehensive streaming information for a video."""
    try:
        # Get video details
        video = await db.get(Video, video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Get available qualities
        qualities = await hls_service.get_available_qualities(video_id)
        
        # Get segment info for each quality
        for quality in qualities:
            quality_preset = quality["quality_preset"]
            manifest_s3_key = f"transcoded/{video_id}/{quality_preset}/segments/playlist.m3u8"
            segment_info = await hls_service.get_segment_info(manifest_s3_key)
            quality.update(segment_info)
        
        return {
            "video_id": video_id,
            "title": video.title,
            "description": video.description,
            "duration": video.duration_seconds,
            "status": video.status.value,
            "visibility": video.visibility.value,
            "source_resolution": video.source_resolution,
            "source_framerate": video.source_framerate,
            "file_size": video.file_size,
            "created_at": video.created_at.isoformat(),
            "qualities": qualities,
            "master_playlist_url": hls_service.get_streaming_url(video_id),
            "thumbnail_url": f"/api/videos/{video_id}/thumbnail" if video.thumbnail_s3_key else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get streaming info: {str(e)}"
        )

@router.post("/videos/{video_id}/master-playlist")
async def create_master_playlist(
    video_id: str,
    db: AsyncSession = Depends(get_db_session),
    hls_service: HLSService = Depends(get_hls_service)
):
    """Create or update master playlist for adaptive streaming."""
    try:
        # Validate video exists
        video = await db.get(Video, video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Get completed transcoding jobs
        result = await db.execute(
            select(TranscodingJob).where(
                TranscodingJob.video_id == video_id,
                TranscodingJob.status == TranscodingStatus.completed
            )
        )
        completed_jobs = result.scalars().all()
        
        if not completed_jobs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No completed transcoding jobs found for video"
            )
        
        # Prepare quality manifests
        quality_manifests = []
        for job in completed_jobs:
            quality_manifests.append({
                "quality_preset": job.quality_preset,
                "manifest_s3_key": job.hls_manifest_s3_key,
                "resolution": job.target_resolution,
                "bitrate": job.target_bitrate,
                "framerate": job.target_framerate
            })
        
        # Create master playlist
        master_s3_key = await hls_service.create_master_playlist(video_id, quality_manifests)
        
        return {
            "video_id": video_id,
            "master_playlist_s3_key": master_s3_key,
            "master_playlist_url": hls_service.get_streaming_url(video_id),
            "qualities_count": len(quality_manifests)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create master playlist: {str(e)}"
        )