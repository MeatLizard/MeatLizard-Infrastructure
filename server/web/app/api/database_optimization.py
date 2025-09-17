"""
Database Optimization API

Provides endpoints for database performance monitoring, index management,
and query optimization for the video platform.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.database_optimization_service import (
    DatabaseOptimizationService,
    get_database_optimization_service,
    IndexRecommendation
)

router = APIRouter(prefix="/api/database", tags=["database-optimization"])


class QueryAnalysisRequest(BaseModel):
    """Request model for query analysis"""
    query: str
    parameters: Optional[Dict[str, Any]] = None


class IndexCreationRequest(BaseModel):
    """Request model for index creation"""
    recommendations: List[Dict[str, Any]]
    force_create: bool = False


class OptimizationConfigRequest(BaseModel):
    """Request model for optimization configuration"""
    slow_query_threshold_ms: Optional[int] = None
    cache_hit_ratio_min: Optional[float] = None
    connection_limit_percent: Optional[int] = None
    enable_monitoring: Optional[bool] = None


@router.get("/statistics")
async def get_database_statistics(
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Get comprehensive database performance statistics"""
    try:
        stats = await db_service.get_database_statistics()
        return {
            "statistics": stats.to_dict(),
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get database statistics: {str(e)}")


@router.get("/indexes")
async def get_existing_indexes(
    table_name: Optional[str] = Query(None, description="Filter by table name"),
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Get existing database indexes"""
    try:
        indexes = await db_service.check_existing_indexes()
        
        if table_name:
            indexes = {table_name: indexes.get(table_name, [])}
        
        return {"indexes": indexes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get indexes: {str(e)}")


@router.get("/recommendations/indexes")
async def get_index_recommendations(
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Get index recommendations based on video platform query patterns"""
    try:
        recommendations = await db_service.analyze_video_query_patterns()
        
        return {
            "recommendations": [rec.to_dict() for rec in recommendations],
            "total_count": len(recommendations),
            "high_impact_count": len([r for r in recommendations if r.estimated_benefit > 0.8])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get index recommendations: {str(e)}")


@router.post("/indexes/create")
async def create_indexes(
    request: IndexCreationRequest,
    background_tasks: BackgroundTasks,
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Create recommended database indexes"""
    try:
        # Convert request data to IndexRecommendation objects
        recommendations = []
        for rec_data in request.recommendations:
            recommendation = IndexRecommendation(
                table_name=rec_data['table_name'],
                columns=rec_data['columns'],
                index_type=rec_data.get('index_type', 'btree'),
                reason=rec_data.get('reason', 'Manual creation'),
                estimated_benefit=rec_data.get('estimated_benefit', 0.5),
                query_patterns=rec_data.get('query_patterns', [])
            )
            recommendations.append(recommendation)
        
        # Create indexes in background for long-running operations
        if len(recommendations) > 3:
            background_tasks.add_task(
                db_service.create_recommended_indexes,
                recommendations
            )
            return {
                "success": True,
                "message": f"Index creation started in background for {len(recommendations)} indexes",
                "background_task": True
            }
        else:
            # Create indexes synchronously for small batches
            results = await db_service.create_recommended_indexes(recommendations)
            return {
                "success": True,
                "results": results,
                "background_task": False
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create indexes: {str(e)}")


@router.post("/query/analyze")
async def analyze_query_performance(
    request: QueryAnalysisRequest,
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Analyze performance of a specific query"""
    try:
        metric = await db_service.analyze_query_performance(
            request.query,
            request.parameters
        )
        
        return {
            "analysis": metric.to_dict(),
            "optimization_suggestions": db_service._get_query_optimization_suggestions(metric)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze query: {str(e)}")


@router.get("/queries/slow")
async def get_slow_queries(
    hours: int = Query(24, ge=1, le=168, description="Hours of history to analyze"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of queries to return"),
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Get analysis of slow queries"""
    try:
        slow_queries = await db_service.analyze_slow_queries(hours)
        
        return {
            "slow_queries": slow_queries[:limit],
            "total_count": len(slow_queries),
            "analysis_period_hours": hours
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get slow queries: {str(e)}")


@router.get("/tables/statistics")
async def get_table_statistics(
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Get detailed statistics for video platform tables"""
    try:
        stats = await db_service.get_table_statistics()
        return {"table_statistics": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get table statistics: {str(e)}")


@router.get("/configuration/recommendations")
async def get_configuration_recommendations(
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Get database configuration optimization recommendations"""
    try:
        recommendations = await db_service.optimize_database_settings()
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration recommendations: {str(e)}")


@router.get("/report/optimization")
async def get_optimization_report(
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Generate comprehensive database optimization report"""
    try:
        report = await db_service.get_optimization_report()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate optimization report: {str(e)}")


@router.get("/performance/score")
async def get_performance_score(
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Get database performance score and key metrics"""
    try:
        db_stats = await db_service.get_database_statistics()
        slow_queries = await db_service.analyze_slow_queries(hours=1)
        
        score = db_service._calculate_optimization_score(db_stats, slow_queries)
        
        return {
            "performance_score": score,
            "score_breakdown": {
                "cache_hit_ratio": db_stats.cache_hit_ratio,
                "avg_query_time_ms": db_stats.avg_query_time_ms,
                "slow_queries_count": len(slow_queries),
                "active_connections": db_stats.active_connections
            },
            "status": "excellent" if score >= 90 else "good" if score >= 75 else "fair" if score >= 60 else "poor",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance score: {str(e)}")


@router.get("/monitoring/metrics")
async def get_monitoring_metrics(
    hours: int = Query(24, ge=1, le=168, description="Hours of metrics to retrieve"),
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Get database monitoring metrics over time"""
    try:
        # Get recent query metrics
        cutoff_time = "2024-01-01T00:00:00Z"  # In real implementation, calculate from hours
        
        metrics = [
            metric.to_dict() for metric in db_service._query_metrics
            # Filter by time in real implementation
        ]
        
        # Calculate aggregated metrics
        if metrics:
            avg_execution_time = sum(m['execution_time_ms'] for m in metrics) / len(metrics)
            slow_query_count = len([m for m in metrics if m['execution_time_ms'] > 1000])
        else:
            avg_execution_time = 0.0
            slow_query_count = 0
        
        return {
            "metrics": metrics[-100:],  # Return last 100 metrics
            "summary": {
                "total_queries": len(metrics),
                "avg_execution_time_ms": round(avg_execution_time, 2),
                "slow_queries_count": slow_query_count,
                "monitoring_period_hours": hours
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get monitoring metrics: {str(e)}")


@router.put("/configuration/thresholds")
async def update_performance_thresholds(
    config: OptimizationConfigRequest,
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Update database performance monitoring thresholds"""
    try:
        # Update thresholds
        if config.slow_query_threshold_ms is not None:
            db_service.thresholds['slow_query_ms'] = config.slow_query_threshold_ms
        
        if config.cache_hit_ratio_min is not None:
            db_service.thresholds['cache_hit_ratio_min'] = config.cache_hit_ratio_min
        
        if config.connection_limit_percent is not None:
            db_service.thresholds['connection_limit'] = config.connection_limit_percent
        
        return {
            "success": True,
            "message": "Performance thresholds updated",
            "current_thresholds": db_service.thresholds
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update thresholds: {str(e)}")


@router.get("/health")
async def get_database_health(
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Get database health status"""
    try:
        stats = await db_service.get_database_statistics()
        
        # Determine health status
        health_issues = []
        
        if stats.cache_hit_ratio < 0.9:
            health_issues.append("Low cache hit ratio")
        
        if stats.avg_query_time_ms > 100:
            health_issues.append("High average query time")
        
        if stats.slow_queries_count > 10:
            health_issues.append("Multiple slow queries detected")
        
        health_status = "healthy" if not health_issues else "degraded" if len(health_issues) <= 2 else "unhealthy"
        
        return {
            "status": health_status,
            "issues": health_issues,
            "metrics": {
                "cache_hit_ratio": stats.cache_hit_ratio,
                "avg_query_time_ms": stats.avg_query_time_ms,
                "active_connections": stats.active_connections,
                "slow_queries_count": stats.slow_queries_count
            },
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database health check failed: {str(e)}")


@router.post("/maintenance/vacuum")
async def run_vacuum_analyze(
    table_name: Optional[str] = Query(None, description="Specific table to vacuum (optional)"),
    background_tasks: BackgroundTasks,
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Run VACUUM ANALYZE on database tables"""
    try:
        async def vacuum_task():
            try:
                if table_name:
                    query = f"VACUUM ANALYZE {table_name}"
                else:
                    query = "VACUUM ANALYZE"
                
                await db_service.db.execute(query)
                await db_service.db.commit()
                
            except Exception as e:
                logger.error(f"Vacuum operation failed: {e}")
        
        # Run vacuum in background
        background_tasks.add_task(vacuum_task)
        
        return {
            "success": True,
            "message": f"VACUUM ANALYZE started for {'table ' + table_name if table_name else 'all tables'}",
            "background_task": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start vacuum operation: {str(e)}")


@router.get("/video-platform/optimization")
async def get_video_platform_optimization(
    db_service: DatabaseOptimizationService = Depends(get_database_optimization_service)
):
    """Get video platform specific optimization recommendations"""
    try:
        # Get video-specific recommendations
        index_recommendations = await db_service.analyze_video_query_patterns()
        table_stats = await db_service.get_table_statistics()
        
        # Video platform specific analysis
        video_tables = ['videos', 'view_sessions', 'video_comments', 'video_likes', 'transcoding_jobs']
        video_table_stats = {k: v for k, v in table_stats.items() if k in video_tables}
        
        # Calculate video platform health score
        total_video_size = sum(
            stats.get('total_size_bytes', 0) 
            for stats in video_table_stats.values()
        )
        
        video_recommendations = [
            rec for rec in index_recommendations 
            if rec.table_name in video_tables
        ]
        
        return {
            "video_platform_health": {
                "total_video_data_size_mb": round(total_video_size / (1024 * 1024), 2),
                "video_tables_count": len(video_table_stats),
                "optimization_opportunities": len(video_recommendations)
            },
            "table_statistics": video_table_stats,
            "optimization_recommendations": [rec.to_dict() for rec in video_recommendations[:10]],
            "priority_actions": [
                {
                    "action": "Create GIN index on videos.tags",
                    "priority": "high",
                    "reason": "Optimize video search by tags"
                },
                {
                    "action": "Create composite index on view_sessions (video_id, started_at)",
                    "priority": "high", 
                    "reason": "Optimize video analytics queries"
                },
                {
                    "action": "Create index on videos (visibility, status, created_at)",
                    "priority": "medium",
                    "reason": "Optimize public video listing"
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get video platform optimization: {str(e)}")