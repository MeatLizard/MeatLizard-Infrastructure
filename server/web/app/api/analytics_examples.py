"""
Example API endpoints demonstrating analytics collection and metrics aggregation.
Shows how to integrate analytics tracking with business logic.
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel

from ..db import get_db
from ..models import User, UserTier
from ..middleware.permissions import get_current_user_dep, get_tier_manager_dep
from ..services.analytics_collector import AnalyticsCollector, EventType, EventSeverity
from ..services.metrics_aggregator import MetricsAggregator, TimeGranularity
from ..services.tier_manager import TierManager

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


class AnalyticsEventRequest(BaseModel):
    """Request model for custom analytics events."""
    event_type: str
    properties: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class MetricsRequest(BaseModel):
    """Request model for metrics queries."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    granularity: Optional[str] = "day"
    filters: Optional[Dict[str, Any]] = None


@router.post("/track-event")
async def track_custom_event(
    request: Request,
    event_request: AnalyticsEventRequest,
    current_user: Optional[User] = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """
    Track a custom analytics event.
    
    This endpoint demonstrates:
    - Custom event tracking
    - User context integration
    - Request metadata capture
    """
    analytics = AnalyticsCollector(db)
    
    # Get request metadata
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    user_id = str(current_user.id) if current_user else None
    
    # Map string event type to enum (simplified)
    event_type_map = {
        "feature_used": EventType.FEATURE_USED,
        "search_performed": EventType.SEARCH_PERFORMED,
        "export_generated": EventType.EXPORT_GENERATED
    }
    
    event_type = event_type_map.get(event_request.event_type, EventType.FEATURE_USED)
    
    # Create and track event
    event = analytics.create_event(
        event_type=event_type,
        user_id=user_id,
        ip_address=client_ip,
        user_agent=user_agent,
        properties=event_request.properties or {},
        tags=event_request.tags or []
    )
    
    success = analytics.track_event(event)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track event"
        )
    
    return {
        "message": "Event tracked successfully",
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "timestamp": event.timestamp.isoformat()
    }


@router.get("/user-metrics")
async def get_user_metrics(
    request: Request,
    metrics_request: MetricsRequest = Depends(),
    current_user: Optional[User] = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive metrics for the current user.
    
    This endpoint demonstrates:
    - User-specific metrics calculation
    - Date range filtering
    - Comprehensive user analytics
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Parse date parameters
    start_date = None
    end_date = None
    
    if metrics_request.start_date:
        try:
            start_date = datetime.fromisoformat(metrics_request.start_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO format."
            )
    
    if metrics_request.end_date:
        try:
            end_date = datetime.fromisoformat(metrics_request.end_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO format."
            )
    
    # Calculate metrics
    aggregator = MetricsAggregator(db)
    user_id = str(current_user.id)
    
    metrics = aggregator.calculate_user_metrics(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )
    
    # Track this analytics request
    analytics = AnalyticsCollector(db)
    analytics.track_feature_usage(
        feature_name="user_metrics_view",
        user_id=user_id,
        properties={
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        },
        ip_address=request.client.host if request.client else None
    )
    
    return {
        "user_id": user_id,
        "metrics": metrics,
        "query_parameters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    }


@router.get("/system-metrics")
async def get_system_metrics(
    request: Request,
    metrics_request: MetricsRequest = Depends(),
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep),
    db: Session = Depends(get_db)
):
    """
    Get system-wide metrics (admin only).
    
    This endpoint demonstrates:
    - System-wide metrics calculation
    - Admin permission checking
    - Comprehensive system analytics
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Check if user has admin privileges (business tier for this example)
    user_id = str(current_user.id)
    user_tier = tier_manager.get_user_tier(user_id)
    
    if user_tier != UserTier.business:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    # Parse date parameters
    start_date = None
    end_date = None
    
    if metrics_request.start_date:
        start_date = datetime.fromisoformat(metrics_request.start_date)
    if metrics_request.end_date:
        end_date = datetime.fromisoformat(metrics_request.end_date)
    
    # Calculate system metrics
    aggregator = MetricsAggregator(db)
    
    metrics = aggregator.calculate_system_metrics(
        start_date=start_date,
        end_date=end_date
    )
    
    # Track admin access
    analytics = AnalyticsCollector(db)
    analytics.track_feature_usage(
        feature_name="system_metrics_view",
        user_id=user_id,
        properties={
            "admin_access": True,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        },
        ip_address=request.client.host if request.client else None
    )
    
    return {
        "system_metrics": metrics,
        "query_parameters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        },
        "generated_at": datetime.utcnow().isoformat()
    }


@router.get("/tier-metrics/{tier}")
async def get_tier_metrics(
    tier: str,
    request: Request,
    metrics_request: MetricsRequest = Depends(),
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep),
    db: Session = Depends(get_db)
):
    """
    Get metrics for a specific user tier.
    
    This endpoint demonstrates:
    - Tier-specific metrics calculation
    - Tier validation
    - Business intelligence analytics
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Validate tier parameter
    try:
        user_tier = UserTier(tier)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {tier}"
        )
    
    # Check permissions (business tier can view all, others can only view their own)
    user_id = str(current_user.id)
    current_user_tier = tier_manager.get_user_tier(user_id)
    
    if current_user_tier != UserTier.business and current_user_tier != user_tier:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view metrics for your own tier"
        )
    
    # Parse date parameters
    start_date = None
    end_date = None
    
    if metrics_request.start_date:
        start_date = datetime.fromisoformat(metrics_request.start_date)
    if metrics_request.end_date:
        end_date = datetime.fromisoformat(metrics_request.end_date)
    
    # Calculate tier metrics
    aggregator = MetricsAggregator(db)
    
    metrics = aggregator.calculate_tier_metrics(
        tier=user_tier,
        start_date=start_date,
        end_date=end_date
    )
    
    # Track tier metrics access
    analytics = AnalyticsCollector(db)
    analytics.track_feature_usage(
        feature_name="tier_metrics_view",
        user_id=user_id,
        properties={
            "viewed_tier": tier,
            "viewer_tier": current_user_tier.value,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        },
        ip_address=request.client.host if request.client else None
    )
    
    return {
        "tier": tier,
        "metrics": metrics,
        "viewer_tier": current_user_tier.value,
        "query_parameters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    }


@router.get("/conversion-metrics")
async def get_conversion_metrics(
    request: Request,
    metrics_request: MetricsRequest = Depends(),
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep),
    db: Session = Depends(get_db)
):
    """
    Get conversion metrics between tiers.
    
    This endpoint demonstrates:
    - Conversion rate calculation
    - Business intelligence metrics
    - Revenue optimization insights
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Check admin privileges
    user_id = str(current_user.id)
    user_tier = tier_manager.get_user_tier(user_id)
    
    if user_tier != UserTier.business:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Business tier required for conversion metrics"
        )
    
    # Parse date parameters
    start_date = None
    end_date = None
    
    if metrics_request.start_date:
        start_date = datetime.fromisoformat(metrics_request.start_date)
    if metrics_request.end_date:
        end_date = datetime.fromisoformat(metrics_request.end_date)
    
    # Calculate conversion metrics
    aggregator = MetricsAggregator(db)
    
    metrics = aggregator.calculate_conversion_metrics(
        start_date=start_date,
        end_date=end_date
    )
    
    # Track conversion metrics access
    analytics = AnalyticsCollector(db)
    analytics.track_feature_usage(
        feature_name="conversion_metrics_view",
        user_id=user_id,
        properties={
            "business_intelligence": True,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        },
        ip_address=request.client.host if request.client else None
    )
    
    return {
        "conversion_metrics": metrics,
        "insights": {
            "highest_conversion": max(
                metrics.get("conversion_rates", {}).items(),
                key=lambda x: x[1].get("rate_percentage", 0),
                default=("none", {"rate_percentage": 0})
            ),
            "total_conversions": sum(metrics.get("conversions", {}).values())
        },
        "query_parameters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    }


@router.get("/usage-report")
async def generate_usage_report(
    request: Request,
    tier: Optional[str] = None,
    format: str = "json",
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep),
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive usage report.
    
    This endpoint demonstrates:
    - Comprehensive reporting
    - Multiple output formats
    - Business analytics integration
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    user_id = str(current_user.id)
    user_tier = tier_manager.get_user_tier(user_id)
    
    # Validate tier parameter if provided
    report_tier = None
    if tier:
        try:
            report_tier = UserTier(tier)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tier: {tier}"
            )
        
        # Check permissions
        if user_tier != UserTier.business and user_tier != report_tier:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for tier report"
            )
    
    # Generate report
    aggregator = MetricsAggregator(db)
    
    if tier:
        report = aggregator.generate_usage_report(tier=report_tier)
    else:
        # User-specific report
        report = aggregator.generate_usage_report(user_id=user_id)
    
    # Track report generation
    analytics = AnalyticsCollector(db)
    analytics.track_feature_usage(
        feature_name="usage_report_generated",
        user_id=user_id,
        properties={
            "report_type": "tier" if tier else "user",
            "report_tier": tier,
            "format": format,
            "user_tier": user_tier.value
        },
        ip_address=request.client.host if request.client else None
    )
    
    if format == "json":
        return report
    else:
        # For other formats, you could implement CSV, PDF, etc.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JSON format is currently supported"
        )


@router.get("/dashboard-data")
async def get_dashboard_data(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep),
    db: Session = Depends(get_db)
):
    """
    Get dashboard data for analytics visualization.
    
    This endpoint demonstrates:
    - Dashboard data aggregation
    - Real-time analytics
    - User experience optimization
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    user_id = str(current_user.id)
    user_tier = tier_manager.get_user_tier(user_id)
    
    # Calculate various metrics for dashboard
    aggregator = MetricsAggregator(db)
    
    # Last 30 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # Get user metrics
    user_metrics = aggregator.calculate_user_metrics(user_id, start_date, end_date)
    
    # Get system metrics if admin
    system_metrics = None
    if user_tier == UserTier.business:
        system_metrics = aggregator.calculate_system_metrics(start_date, end_date)
    
    # Track dashboard access
    analytics = AnalyticsCollector(db)
    analytics.track_feature_usage(
        feature_name="analytics_dashboard_view",
        user_id=user_id,
        properties={
            "user_tier": user_tier.value,
            "has_system_access": user_tier == UserTier.business
        },
        ip_address=request.client.host if request.client else None
    )
    
    dashboard_data = {
        "user_metrics": user_metrics,
        "user_tier": user_tier.value,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": 30
        },
        "last_updated": datetime.utcnow().isoformat()
    }
    
    if system_metrics:
        dashboard_data["system_metrics"] = system_metrics
    
    return dashboard_data


@router.post("/flush-events")
async def flush_analytics_events(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep),
    db: Session = Depends(get_db)
):
    """
    Manually flush buffered analytics events (admin only).
    
    This endpoint demonstrates:
    - Manual event flushing
    - Admin operations
    - System maintenance
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    user_id = str(current_user.id)
    user_tier = tier_manager.get_user_tier(user_id)
    
    if user_tier != UserTier.business:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    # Flush events
    analytics = AnalyticsCollector(db)
    success = analytics.flush()
    
    # Track flush operation
    analytics.track_feature_usage(
        feature_name="analytics_flush_events",
        user_id=user_id,
        properties={
            "admin_operation": True,
            "flush_success": success
        },
        ip_address=request.client.host if request.client else None
    )
    
    return {
        "message": "Events flushed successfully" if success else "Failed to flush events",
        "success": success,
        "timestamp": datetime.utcnow().isoformat()
    }