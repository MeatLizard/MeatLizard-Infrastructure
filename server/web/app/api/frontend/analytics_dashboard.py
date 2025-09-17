"""
Analytics Dashboard Frontend API

Provides frontend endpoints for analytics dashboard pages and components.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...dependencies import get_current_user, get_db_session
from ...services.analytics_dashboard_service import AnalyticsDashboardService
from ...models import User


router = APIRouter(prefix="/dashboard", tags=["analytics_dashboard"])
templates = Jinja2Templates(directory="server/web/app/templates")


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard_page(
    request: Request,
    timeframe: str = Query("30d", regex="^(7d|30d|90d)$"),
    current_user: User = Depends(get_current_user)
):
    """Render the main analytics dashboard page"""
    try:
        dashboard_service = AnalyticsDashboardService()
        
        # Get dashboard data for the current user
        dashboard_data = await dashboard_service.get_creator_dashboard_data(
            current_user.id, 
            timeframe
        )
        
        return templates.TemplateResponse(
            "analytics_dashboard.html",
            {
                "request": request,
                "user": current_user,
                "dashboard_data": dashboard_data,
                "timeframe": timeframe,
                "page_title": "Analytics Dashboard"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load dashboard: {str(e)}")


@router.get("/video/{video_id}", response_class=HTMLResponse)
async def video_analytics_page(
    request: Request,
    video_id: UUID,
    timeframe: str = Query("7d", regex="^(1h|24h|7d|30d)$"),
    current_user: User = Depends(get_current_user)
):
    """Render detailed analytics page for a specific video"""
    try:
        dashboard_service = AnalyticsDashboardService()
        
        # Get video dashboard data
        video_data = await dashboard_service.get_video_dashboard_data(video_id, timeframe)
        
        if not video_data:
            raise HTTPException(status_code=404, detail="Video not found or no analytics data available")
        
        # TODO: Add permission check - user should own the video or be admin
        
        return templates.TemplateResponse(
            "video_analytics.html",
            {
                "request": request,
                "user": current_user,
                "video_data": video_data,
                "video_id": str(video_id),
                "timeframe": timeframe,
                "page_title": f"Video Analytics - {video_data.get('basic_metrics', {}).get('video_title', 'Unknown')}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load video analytics: {str(e)}")


@router.get("/api/data", response_model=dict)
async def get_dashboard_data(
    timeframe: str = Query("30d", regex="^(7d|30d|90d)$"),
    current_user: User = Depends(get_current_user)
):
    """API endpoint to get dashboard data (for AJAX updates)"""
    try:
        dashboard_service = AnalyticsDashboardService()
        
        dashboard_data = await dashboard_service.get_creator_dashboard_data(
            current_user.id, 
            timeframe
        )
        
        return {
            "success": True,
            "data": dashboard_data,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")


@router.get("/api/video/{video_id}/data", response_model=dict)
async def get_video_analytics_data(
    video_id: UUID,
    timeframe: str = Query("7d", regex="^(1h|24h|7d|30d)$"),
    current_user: User = Depends(get_current_user)
):
    """API endpoint to get video analytics data (for AJAX updates)"""
    try:
        dashboard_service = AnalyticsDashboardService()
        
        # TODO: Add permission check
        
        video_data = await dashboard_service.get_video_dashboard_data(video_id, timeframe)
        
        if not video_data:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return {
            "success": True,
            "data": video_data,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get video analytics data: {str(e)}")


@router.get("/api/realtime/{video_id}", response_model=dict)
async def get_realtime_analytics(
    video_id: UUID,
    current_user: User = Depends(get_current_user)
):
    """Get real-time analytics data for a video"""
    try:
        dashboard_service = AnalyticsDashboardService()
        
        # Use the analytics service for real-time data
        realtime_data = await dashboard_service.analytics_service.get_real_time_metrics(video_id)
        
        return {
            "success": True,
            "data": realtime_data,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get real-time data: {str(e)}")


@router.get("/admin/platform", response_class=HTMLResponse)
async def platform_analytics_page(
    request: Request,
    timeframe: str = Query("30d", regex="^(7d|30d|90d)$"),
    current_user: User = Depends(get_current_user)
):
    """Render platform-wide analytics page (admin only)"""
    try:
        # TODO: Add admin permission check
        
        dashboard_service = AnalyticsDashboardService()
        
        platform_data = await dashboard_service.get_platform_overview(timeframe)
        
        return templates.TemplateResponse(
            "platform_analytics.html",
            {
                "request": request,
                "user": current_user,
                "platform_data": platform_data,
                "timeframe": timeframe,
                "page_title": "Platform Analytics"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load platform analytics: {str(e)}")


@router.get("/api/export/{video_id}")
async def export_video_analytics(
    video_id: UUID,
    format: str = Query("json", regex="^(json|csv)$"),
    timeframe: str = Query("30d", regex="^(7d|30d|90d)$"),
    current_user: User = Depends(get_current_user)
):
    """Export video analytics data"""
    try:
        dashboard_service = AnalyticsDashboardService()
        
        # TODO: Add permission check
        
        export_data = await dashboard_service.analytics_service.export_analytics_data(
            video_id, 
            format
        )
        
        if format == "csv":
            # Return CSV response
            from fastapi.responses import Response
            import csv
            import io
            
            output = io.StringIO()
            if export_data:
                writer = csv.DictWriter(output, fieldnames=export_data.keys())
                writer.writeheader()
                writer.writerow(export_data)
            
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=video_{video_id}_analytics.csv"}
            )
        else:
            # Return JSON response
            return {
                "success": True,
                "data": export_data,
                "format": format,
                "video_id": str(video_id)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export analytics: {str(e)}")