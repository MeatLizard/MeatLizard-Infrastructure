"""
Cache Management API

Provides endpoints for managing video metadata cache, including
cache statistics, warming operations, and performance monitoring.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.video_cache_service import VideoCacheService, get_video_cache_service
from server.web.app.services.cache_warming_service import CacheWarmingService, get_cache_warming_service
from server.web.app.services.cache_monitoring_service import CacheMonitoringService, get_cache_monitoring_service

router = APIRouter(prefix="/api/cache", tags=["cache"])


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics"""
    cache_performance: Dict[str, Any]
    redis_info: Dict[str, Any]
    instance_stats: Dict[str, Any]


class WarmingRequest(BaseModel):
    """Request model for cache warming operations"""
    video_ids: Optional[List[str]] = None
    user_id: Optional[str] = None
    strategy: Optional[str] = None
    limit: Optional[int] = 50


class WarmingStatusResponse(BaseModel):
    """Response model for warming status"""
    is_running: bool
    active_strategies: int
    strategies: Dict[str, Any]


class MonitoringConfigRequest(BaseModel):
    """Request model for monitoring configuration"""
    hit_rate_warning: Optional[float] = None
    hit_rate_critical: Optional[float] = None
    error_rate_warning: Optional[float] = None
    error_rate_critical: Optional[float] = None
    memory_usage_warning: Optional[float] = None
    memory_usage_critical: Optional[float] = None


@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    cache_service: VideoCacheService = Depends(get_video_cache_service)
):
    """Get cache performance statistics"""
    try:
        stats = await cache_service.get_cache_stats()
        return CacheStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.get("/metrics/current")
async def get_current_metrics(
    monitoring_service: CacheMonitoringService = Depends(get_cache_monitoring_service)
):
    """Get current cache performance metrics"""
    try:
        metrics = await monitoring_service.get_current_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get current metrics: {str(e)}")


@router.get("/metrics/history")
async def get_metrics_history(
    metric_name: Optional[str] = Query(None, description="Specific metric name to retrieve"),
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve"),
    monitoring_service: CacheMonitoringService = Depends(get_cache_monitoring_service)
):
    """Get historical cache metrics"""
    try:
        history = await monitoring_service.get_metrics_history(metric_name, hours)
        return {"metrics": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics history: {str(e)}")


@router.get("/alerts")
async def get_alerts_history(
    level: Optional[str] = Query(None, description="Alert level filter (info, warning, critical)"),
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve"),
    monitoring_service: CacheMonitoringService = Depends(get_cache_monitoring_service)
):
    """Get cache alerts history"""
    try:
        from server.web.app.services.cache_monitoring_service import AlertLevel
        
        alert_level = None
        if level:
            try:
                alert_level = AlertLevel(level.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid alert level: {level}")
        
        alerts = await monitoring_service.get_alerts_history(alert_level, hours)
        return {"alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts history: {str(e)}")


@router.get("/recommendations")
async def get_performance_recommendations(
    monitoring_service: CacheMonitoringService = Depends(get_cache_monitoring_service)
):
    """Get performance optimization recommendations"""
    try:
        recommendations = await monitoring_service.get_performance_recommendations()
        return {"recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.post("/warm")
async def warm_cache(
    request: WarmingRequest,
    cache_service: VideoCacheService = Depends(get_video_cache_service),
    warming_service: CacheWarmingService = Depends(get_cache_warming_service)
):
    """Warm cache for specific videos or strategies"""
    try:
        results = {}
        
        if request.video_ids:
            # Warm specific videos
            warmed_count = 0
            for video_id in request.video_ids:
                if await cache_service.warm_cache_for_video(video_id):
                    warmed_count += 1
            results["videos_warmed"] = warmed_count
            results["total_requested"] = len(request.video_ids)
        
        elif request.user_id:
            # Warm user's videos
            warmed_count = await warming_service.warm_user_videos(
                request.user_id, 
                request.limit or 20
            )
            results["user_videos_warmed"] = warmed_count
        
        elif request.strategy:
            # Force execute specific strategy
            strategy_results = await warming_service.force_warm_all_strategies()
            if request.strategy in strategy_results:
                results["strategy_warmed"] = strategy_results[request.strategy]
            else:
                raise HTTPException(status_code=400, detail=f"Unknown strategy: {request.strategy}")
        
        else:
            # Warm popular videos
            warmed_count = await cache_service.warm_popular_videos_cache(request.limit or 50)
            results["popular_videos_warmed"] = warmed_count
        
        return {"success": True, "results": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to warm cache: {str(e)}")


@router.get("/warming/status", response_model=WarmingStatusResponse)
async def get_warming_status(
    warming_service: CacheWarmingService = Depends(get_cache_warming_service)
):
    """Get cache warming status"""
    try:
        status = await warming_service.get_warming_status()
        return WarmingStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get warming status: {str(e)}")


@router.post("/warming/start")
async def start_cache_warming(
    warming_service: CacheWarmingService = Depends(get_cache_warming_service)
):
    """Start cache warming scheduler"""
    try:
        await warming_service.start_warming_scheduler()
        return {"success": True, "message": "Cache warming scheduler started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start warming scheduler: {str(e)}")


@router.post("/warming/stop")
async def stop_cache_warming(
    warming_service: CacheWarmingService = Depends(get_cache_warming_service)
):
    """Stop cache warming scheduler"""
    try:
        await warming_service.stop_warming_scheduler()
        return {"success": True, "message": "Cache warming scheduler stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop warming scheduler: {str(e)}")


@router.post("/monitoring/start")
async def start_cache_monitoring(
    interval_seconds: int = Query(60, ge=10, le=3600, description="Monitoring interval in seconds"),
    monitoring_service: CacheMonitoringService = Depends(get_cache_monitoring_service)
):
    """Start cache performance monitoring"""
    try:
        await monitoring_service.start_monitoring(interval_seconds)
        return {"success": True, "message": f"Cache monitoring started with {interval_seconds}s interval"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")


@router.post("/monitoring/stop")
async def stop_cache_monitoring(
    monitoring_service: CacheMonitoringService = Depends(get_cache_monitoring_service)
):
    """Stop cache performance monitoring"""
    try:
        await monitoring_service.stop_monitoring()
        return {"success": True, "message": "Cache monitoring stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop monitoring: {str(e)}")


@router.put("/monitoring/config")
async def update_monitoring_config(
    config: MonitoringConfigRequest,
    monitoring_service: CacheMonitoringService = Depends(get_cache_monitoring_service)
):
    """Update cache monitoring configuration"""
    try:
        # Convert request to dictionary, excluding None values
        config_dict = {k: v for k, v in config.dict().items() if v is not None}
        
        if not config_dict:
            raise HTTPException(status_code=400, detail="No configuration parameters provided")
        
        success = await monitoring_service.update_thresholds(config_dict)
        if success:
            return {"success": True, "message": "Monitoring configuration updated"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update configuration")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update monitoring config: {str(e)}")


@router.delete("/clear")
async def clear_cache(
    confirm: bool = Query(False, description="Confirmation required to clear cache"),
    cache_service: VideoCacheService = Depends(get_video_cache_service)
):
    """Clear all cache entries (use with caution!)"""
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Cache clearing requires confirmation. Set confirm=true to proceed."
        )
    
    try:
        success = await cache_service.clear_all_cache()
        if success:
            return {"success": True, "message": "All cache entries cleared"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear cache")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/video/{video_id}")
async def get_video_cache_info(
    video_id: str,
    cache_service: VideoCacheService = Depends(get_video_cache_service)
):
    """Get cache information for a specific video"""
    try:
        # Check if video is cached
        cached_metadata = await cache_service.get_video_metadata(video_id)
        
        if cached_metadata:
            return {
                "cached": True,
                "metadata": cached_metadata,
                "cached_at": cached_metadata.get("cached_at")
            }
        else:
            return {
                "cached": False,
                "metadata": None,
                "cached_at": None
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get video cache info: {str(e)}")


@router.delete("/video/{video_id}")
async def invalidate_video_cache(
    video_id: str,
    cache_service: VideoCacheService = Depends(get_video_cache_service)
):
    """Invalidate cache for a specific video"""
    try:
        success = await cache_service.invalidate_video_metadata(video_id)
        if success:
            return {"success": True, "message": f"Cache invalidated for video {video_id}"}
        else:
            return {"success": False, "message": f"No cache found for video {video_id}"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to invalidate video cache: {str(e)}")


@router.post("/video/{video_id}/warm")
async def warm_video_cache(
    video_id: str,
    cache_service: VideoCacheService = Depends(get_video_cache_service)
):
    """Warm cache for a specific video"""
    try:
        success = await cache_service.warm_cache_for_video(video_id)
        if success:
            return {"success": True, "message": f"Cache warmed for video {video_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found or failed to warm")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to warm video cache: {str(e)}")


@router.get("/popular-tags")
async def get_cached_popular_tags(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of tags to return"),
    cache_service: VideoCacheService = Depends(get_video_cache_service)
):
    """Get cached popular tags"""
    try:
        tags = await cache_service.get_popular_tags(limit)
        return {"tags": tags or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get popular tags: {str(e)}")


@router.get("/trending")
async def get_cached_trending_videos(
    timeframe: str = Query("24h", regex="^(1h|24h|7d)$", description="Time period for trending videos"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of videos to return"),
    cache_service: VideoCacheService = Depends(get_video_cache_service)
):
    """Get cached trending videos"""
    try:
        videos = await cache_service.get_trending_videos(timeframe, limit)
        return {"videos": videos or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get trending videos: {str(e)}")