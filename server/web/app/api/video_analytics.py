"""
Video Analytics API Endpoints

Provides endpoints for:
- Recording analytics events
- Retrieving video analytics data
- Creator dashboard analytics
- Real-time metrics
- Analytics data export
"""

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, get_db_session
from ..services.video_analytics_service import VideoAnalyticsService
from ..models import User


router = APIRouter(prefix="/api/analytics", tags=["video_analytics"])


# Request/Response Models
class ViewEventRequest(BaseModel):
    video_id: UUID
    event_data: Dict[str, Any] = Field(default_factory=dict)


class EngagementEventRequest(BaseModel):
    video_id: UUID
    event_type: str = Field(..., description="Type of engagement: like, comment, share, etc.")
    event_data: Dict[str, Any] = Field(default_factory=dict)


class PerformanceEventRequest(BaseModel):
    video_id: UUID
    session_id: UUID
    event_type: str = Field(..., description="Type of performance event: buffering, quality_switch, error")
    event_data: Dict[str, Any] = Field(default_factory=dict)


class PlaybackProgressRequest(BaseModel):
    session_id: UUID
    current_position: int = Field(..., description="Current playback position in seconds")
    quality: str = Field(..., description="Current video quality")
    buffering_events: int = Field(default=0)
    quality_switches: int = Field(default=0)


class AnalyticsResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# Analytics Event Recording Endpoints
@router.post("/events/view", response_model=AnalyticsResponse)
async def record_view_event(
    request: ViewEventRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Record a video view event"""
    try:
        analytics_service = VideoAnalyticsService()
        
        # Add timestamp and user agent to event data
        event_data = {
            **request.event_data,
            "timestamp": datetime.utcnow().isoformat(),
            "user_agent": request.event_data.get("user_agent"),
            "ip_address": request.event_data.get("ip_address")
        }
        
        # Record event in background
        background_tasks.add_task(
            analytics_service.record_view_event,
            request.video_id,
            current_user.id if current_user else None,
            event_data
        )
        
        return AnalyticsResponse(
            success=True,
            message="View event recorded successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record view event: {str(e)}")


@router.post("/events/engagement", response_model=AnalyticsResponse)
async def record_engagement_event(
    request: EngagementEventRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Record a user engagement event"""
    try:
        analytics_service = VideoAnalyticsService()
        
        event_data = {
            **request.event_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        background_tasks.add_task(
            analytics_service.record_engagement_event,
            request.video_id,
            current_user.id if current_user else None,
            request.event_type,
            event_data
        )
        
        return AnalyticsResponse(
            success=True,
            message="Engagement event recorded successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record engagement event: {str(e)}")


@router.post("/events/performance", response_model=AnalyticsResponse)
async def record_performance_event(
    request: PerformanceEventRequest,
    background_tasks: BackgroundTasks
):
    """Record a video performance event"""
    try:
        analytics_service = VideoAnalyticsService()
        
        event_data = {
            **request.event_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        background_tasks.add_task(
            analytics_service.record_performance_event,
            request.video_id,
            request.session_id,
            request.event_type,
            event_data
        )
        
        return AnalyticsResponse(
            success=True,
            message="Performance event recorded successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record performance event: {str(e)}")


@router.post("/playback/progress", response_model=AnalyticsResponse)
async def update_playback_progress(
    request: PlaybackProgressRequest,
    background_tasks: BackgroundTasks
):
    """Update viewing session playback progress"""
    try:
        analytics_service = VideoAnalyticsService()
        
        background_tasks.add_task(
            analytics_service.record_playback_progress,
            request.session_id,
            request.current_position,
            request.quality,
            request.buffering_events,
            request.quality_switches
        )
        
        return AnalyticsResponse(
            success=True,
            message="Playback progress updated successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update playback progress: {str(e)}")


# Analytics Data Retrieval Endpoints
@router.get("/video/{video_id}")
async def get_video_analytics(
    video_id: UUID,
    timeframe: str = Query("7d", regex="^(1h|24h|7d|30d)$"),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive analytics for a specific video"""
    try:
        analytics_service = VideoAnalyticsService()
        
        # TODO: Add permission check - user should own the video or be admin
        
        analytics_data = await analytics_service.get_video_analytics(video_id, timeframe)
        
        if not analytics_data:
            raise HTTPException(status_code=404, detail="Video not found or no analytics data available")
        
        return AnalyticsResponse(
            success=True,
            message="Analytics data retrieved successfully",
            data=analytics_data
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analytics: {str(e)}")


@router.get("/creator/{creator_id}")
async def get_creator_analytics(
    creator_id: UUID,
    timeframe: str = Query("30d", regex="^(7d|30d|90d)$"),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive analytics for a content creator"""
    try:
        # Check if user is requesting their own analytics or is admin
        if current_user.id != creator_id:
            # TODO: Add admin check
            raise HTTPException(status_code=403, detail="Access denied")
        
        analytics_service = VideoAnalyticsService()
        analytics_data = await analytics_service.get_creator_analytics(creator_id, timeframe)
        
        return AnalyticsResponse(
            success=True,
            message="Creator analytics retrieved successfully",
            data=analytics_data
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve creator analytics: {str(e)}")


@router.get("/video/{video_id}/realtime")
async def get_real_time_metrics(
    video_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """Get real-time metrics for a video"""
    try:
        analytics_service = VideoAnalyticsService()
        
        # TODO: Add permission check
        
        metrics = await analytics_service.get_real_time_metrics(video_id)
        
        return AnalyticsResponse(
            success=True,
            message="Real-time metrics retrieved successfully",
            data=metrics
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve real-time metrics: {str(e)}")


@router.get("/video/{video_id}/export")
async def export_analytics_data(
    video_id: UUID,
    format: str = Query("json", regex="^(json|csv)$"),
    current_user: User = Depends(get_current_user)
):
    """Export analytics data for a video"""
    try:
        analytics_service = VideoAnalyticsService()
        
        # TODO: Add permission check
        
        export_data = await analytics_service.export_analytics_data(video_id, format)
        
        return AnalyticsResponse(
            success=True,
            message=f"Analytics data exported in {format} format",
            data=export_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export analytics data: {str(e)}")


# Dashboard Endpoints
@router.get("/dashboard/overview")
async def get_dashboard_overview(
    timeframe: str = Query("7d", regex="^(1h|24h|7d|30d)$"),
    current_user: User = Depends(get_current_user)
):
    """Get overview analytics for the current user's dashboard"""
    try:
        analytics_service = VideoAnalyticsService()
        
        # Get creator analytics for the current user
        analytics_data = await analytics_service.get_creator_analytics(current_user.id, timeframe)
        
        return AnalyticsResponse(
            success=True,
            message="Dashboard overview retrieved successfully",
            data=analytics_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dashboard overview: {str(e)}")


# Batch Analytics Endpoints
@router.post("/events/batch")
async def record_batch_events(
    events: list[Dict[str, Any]],
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user)
):
    """Record multiple analytics events in batch"""
    try:
        analytics_service = VideoAnalyticsService()
        
        # Process each event
        for event in events:
            event_type = event.get("type")
            video_id = UUID(event.get("video_id"))
            event_data = event.get("data", {})
            
            if event_type == "view":
                background_tasks.add_task(
                    analytics_service.record_view_event,
                    video_id,
                    current_user.id if current_user else None,
                    event_data
                )
            elif event_type == "engagement":
                background_tasks.add_task(
                    analytics_service.record_engagement_event,
                    video_id,
                    current_user.id if current_user else None,
                    event.get("engagement_type", "unknown"),
                    event_data
                )
            elif event_type == "performance":
                session_id = UUID(event.get("session_id"))
                background_tasks.add_task(
                    analytics_service.record_performance_event,
                    video_id,
                    session_id,
                    event.get("performance_type", "unknown"),
                    event_data
                )
        
        return AnalyticsResponse(
            success=True,
            message=f"Batch of {len(events)} events recorded successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record batch events: {str(e)}")