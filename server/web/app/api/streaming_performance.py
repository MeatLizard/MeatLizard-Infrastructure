"""
Streaming Performance API

Provides endpoints for monitoring streaming performance, bandwidth optimization,
and CDN management for video delivery.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.streaming_performance_service import (
    StreamingPerformanceService, 
    get_streaming_performance_service
)
from server.web.app.services.cdn_service import CDNService, get_cdn_service

router = APIRouter(prefix="/api/streaming", tags=["streaming-performance"])


class BandwidthMeasurementRequest(BaseModel):
    """Request model for bandwidth measurement"""
    session_token: str
    video_id: str
    bandwidth_kbps: float
    quality: str
    buffer_seconds: float
    dropped_frames: int = 0
    timestamp: Optional[str] = None


class QualityRecommendationRequest(BaseModel):
    """Request model for quality recommendation"""
    session_token: str
    video_id: str
    current_quality: str
    target_buffer: float = 10.0


class CDNInvalidationRequest(BaseModel):
    """Request model for CDN cache invalidation"""
    paths: List[str]
    video_id: Optional[str] = None


@router.post("/bandwidth/measure")
async def record_bandwidth_measurement(
    request: BandwidthMeasurementRequest,
    performance_service: StreamingPerformanceService = Depends(get_streaming_performance_service)
):
    """Record bandwidth measurement from client"""
    try:
        measurement_data = {
            'bandwidth_kbps': request.bandwidth_kbps,
            'quality': request.quality,
            'buffer_seconds': request.buffer_seconds,
            'dropped_frames': request.dropped_frames
        }
        
        success = await performance_service.record_bandwidth_measurement(
            request.session_token,
            request.video_id,
            measurement_data
        )
        
        if success:
            return {"success": True, "message": "Bandwidth measurement recorded"}
        else:
            raise HTTPException(status_code=500, detail="Failed to record measurement")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record bandwidth measurement: {str(e)}")


@router.post("/quality/recommend")
async def get_quality_recommendation(
    request: QualityRecommendationRequest,
    performance_service: StreamingPerformanceService = Depends(get_streaming_performance_service)
):
    """Get quality recommendation based on performance"""
    try:
        recommendation = await performance_service.get_quality_recommendation(
            request.session_token,
            request.video_id,
            request.current_quality,
            request.target_buffer
        )
        
        return {
            "recommended_quality": recommendation.recommended_quality,
            "confidence": recommendation.confidence,
            "reason": recommendation.reason,
            "estimated_bitrate": recommendation.estimated_bitrate,
            "buffer_target": recommendation.buffer_target,
            "adaptive_enabled": recommendation.adaptive_enabled
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get quality recommendation: {str(e)}")


@router.get("/session/{session_token}/performance")
async def get_session_performance(
    session_token: str,
    video_id: str = Query(..., description="Video ID for the session"),
    performance_service: StreamingPerformanceService = Depends(get_streaming_performance_service)
):
    """Get performance summary for a viewing session"""
    try:
        summary = await performance_service.get_session_performance_summary(
            session_token,
            video_id
        )
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session performance: {str(e)}")


@router.get("/video/{video_id}/analytics")
async def get_video_performance_analytics(
    video_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of data to analyze"),
    performance_service: StreamingPerformanceService = Depends(get_streaming_performance_service)
):
    """Get performance analytics for a specific video"""
    try:
        analytics = await performance_service.get_video_performance_analytics(
            video_id,
            hours
        )
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get video analytics: {str(e)}")


@router.get("/alerts")
async def get_performance_alerts(
    video_id: Optional[str] = Query(None, description="Filter by video ID"),
    session_token: Optional[str] = Query(None, description="Filter by session token"),
    severity: Optional[str] = Query(None, description="Filter by severity (critical, warning, info)"),
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve"),
    performance_service: StreamingPerformanceService = Depends(get_streaming_performance_service)
):
    """Get performance alerts with optional filtering"""
    try:
        alerts = await performance_service.get_performance_alerts(
            video_id=video_id,
            session_token=session_token,
            severity=severity,
            hours=hours
        )
        
        return {"alerts": alerts}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance alerts: {str(e)}")


@router.get("/cdn/status")
async def get_cdn_status(
    cdn_service: CDNService = Depends(get_cdn_service)
):
    """Get CDN status and health information"""
    try:
        status = await cdn_service.get_cdn_status()
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get CDN status: {str(e)}")


@router.get("/cdn/edge-locations")
async def get_edge_locations(
    cdn_service: CDNService = Depends(get_cdn_service)
):
    """Get list of CDN edge locations"""
    try:
        locations = await cdn_service.get_edge_locations()
        return {"edge_locations": locations}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get edge locations: {str(e)}")


@router.get("/cdn/analytics")
async def get_streaming_analytics(
    video_id: Optional[str] = Query(None, description="Filter by video ID"),
    hours: int = Query(24, ge=1, le=168, description="Hours of data to retrieve"),
    cdn_service: CDNService = Depends(get_cdn_service)
):
    """Get CDN streaming analytics"""
    try:
        analytics = await cdn_service.get_streaming_analytics(video_id, hours)
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get streaming analytics: {str(e)}")


@router.post("/cdn/invalidate")
async def invalidate_cdn_cache(
    request: CDNInvalidationRequest,
    cdn_service: CDNService = Depends(get_cdn_service)
):
    """Invalidate CDN cache for specified paths"""
    try:
        if request.video_id:
            # Invalidate all cache for a specific video
            success = await cdn_service.invalidate_video_cache(request.video_id)
        else:
            # Invalidate specific paths
            success = await cdn_service.invalidate_cache(request.paths)
        
        if success:
            return {"success": True, "message": "Cache invalidation initiated"}
        else:
            raise HTTPException(status_code=500, detail="Failed to initiate cache invalidation")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to invalidate CDN cache: {str(e)}")


@router.get("/cdn/video/{video_id}/urls")
async def get_video_cdn_urls(
    video_id: str,
    quality: Optional[str] = Query(None, description="Specific quality preset"),
    user_id: Optional[str] = Query(None, description="User ID for access control"),
    ip_address: Optional[str] = Query(None, description="Client IP address"),
    cdn_service: CDNService = Depends(get_cdn_service)
):
    """Get CDN URLs for video streaming"""
    try:
        # Get HLS manifest URL
        manifest_url = await cdn_service.get_hls_manifest_url(
            video_id,
            quality=quality,
            user_id=user_id,
            ip_address=ip_address
        )
        
        # Get thumbnail URLs
        thumbnail_urls = {}
        for timestamp in ['10', '25', '50', '75', '90']:
            thumbnail_urls[f"{timestamp}%"] = await cdn_service.get_thumbnail_url(
                video_id,
                timestamp
            )
        
        return {
            "video_id": video_id,
            "manifest_url": manifest_url,
            "thumbnail_urls": thumbnail_urls,
            "quality": quality,
            "signed": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get CDN URLs: {str(e)}")


@router.get("/video/{video_id}/optimize")
async def get_optimization_recommendations(
    video_id: str,
    cdn_service: CDNService = Depends(get_cdn_service)
):
    """Get optimization recommendations for a video"""
    try:
        recommendations = await cdn_service.optimize_cache_settings(video_id)
        return recommendations
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get optimization recommendations: {str(e)}")


@router.post("/cdn/metrics/record")
async def record_streaming_metrics(
    video_id: str,
    metrics: Dict[str, Any],
    cdn_service: CDNService = Depends(get_cdn_service)
):
    """Record streaming performance metrics"""
    try:
        success = await cdn_service.record_streaming_metrics(video_id, metrics)
        
        if success:
            return {"success": True, "message": "Metrics recorded"}
        else:
            raise HTTPException(status_code=500, detail="Failed to record metrics")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record streaming metrics: {str(e)}")


@router.get("/performance/summary")
async def get_performance_summary(
    hours: int = Query(24, ge=1, le=168, description="Hours of data to analyze"),
    performance_service: StreamingPerformanceService = Depends(get_streaming_performance_service),
    cdn_service: CDNService = Depends(get_cdn_service)
):
    """Get overall streaming performance summary"""
    try:
        # Get CDN analytics
        cdn_analytics = await cdn_service.get_streaming_analytics(hours=hours)
        
        # Get CDN status
        cdn_status = await cdn_service.get_cdn_status()
        
        # Get recent alerts
        alerts = await performance_service.get_performance_alerts(hours=hours)
        
        # Calculate summary metrics
        total_alerts = len(alerts)
        critical_alerts = len([a for a in alerts if a.get('severity') == 'critical'])
        warning_alerts = len([a for a in alerts if a.get('severity') == 'warning'])
        
        return {
            "summary_period_hours": hours,
            "cdn_performance": {
                "status": cdn_status.get("overall_status", "unknown"),
                "cache_hit_ratio": cdn_analytics.get("average_cache_hit_ratio", 0.0),
                "average_latency_ms": cdn_analytics.get("average_latency_ms", 0.0),
                "bandwidth_mbps": cdn_analytics.get("average_bandwidth_mbps", 0.0),
                "edge_locations_active": cdn_status.get("edge_locations", {}).get("active", 0)
            },
            "alerts_summary": {
                "total": total_alerts,
                "critical": critical_alerts,
                "warning": warning_alerts,
                "info": total_alerts - critical_alerts - warning_alerts
            },
            "recommendations": [
                {
                    "type": "performance",
                    "priority": "high" if critical_alerts > 0 else "medium" if warning_alerts > 5 else "low",
                    "title": "Alert Management",
                    "description": f"System generated {total_alerts} alerts in the last {hours} hours",
                    "action": "Review and address critical alerts" if critical_alerts > 0 else "Monitor warning trends"
                }
            ] if total_alerts > 0 else [],
            "last_updated": cdn_status.get("last_updated")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance summary: {str(e)}")


@router.get("/health")
async def get_streaming_health():
    """Get streaming service health status"""
    try:
        return {
            "status": "healthy",
            "services": {
                "performance_monitoring": "active",
                "cdn_integration": "active",
                "bandwidth_optimization": "active"
            },
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")