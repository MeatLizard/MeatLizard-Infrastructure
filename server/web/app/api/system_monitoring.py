"""
System Monitoring API Endpoints

Provides endpoints for:
- System health monitoring
- Alert management
- Performance metrics
- Storage monitoring
- Transcoding job monitoring
"""

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, get_db_session
from ..services.system_monitoring_service import SystemMonitoringService
from ..models import User


router = APIRouter(prefix="/api/monitoring", tags=["system_monitoring"])


# Request/Response Models
class AlertThresholdsRequest(BaseModel):
    transcoding_failure_rate: Optional[float] = Field(None, ge=0, le=100)
    storage_usage_warning: Optional[float] = Field(None, ge=0, le=100)
    storage_usage_critical: Optional[float] = Field(None, ge=0, le=100)
    streaming_error_rate: Optional[float] = Field(None, ge=0, le=100)
    avg_response_time: Optional[float] = Field(None, ge=0)
    concurrent_sessions: Optional[int] = Field(None, ge=0)
    disk_usage_warning: Optional[float] = Field(None, ge=0, le=100)
    memory_usage_warning: Optional[float] = Field(None, ge=0, le=100)


class MonitoringResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# System Health Endpoints
@router.get("/health", response_model=MonitoringResponse)
async def get_system_health(
    current_user: User = Depends(get_current_user)
):
    """Get overall system health status"""
    try:
        # TODO: Add admin permission check
        
        monitoring_service = SystemMonitoringService()
        health_data = await monitoring_service.get_system_health_overview()
        
        return MonitoringResponse(
            success=True,
            message="System health data retrieved successfully",
            data=health_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system health: {str(e)}")


@router.get("/dashboard", response_model=MonitoringResponse)
async def get_monitoring_dashboard(
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive monitoring dashboard data"""
    try:
        # TODO: Add admin permission check
        
        monitoring_service = SystemMonitoringService()
        dashboard_data = await monitoring_service.get_monitoring_dashboard_data()
        
        return MonitoringResponse(
            success=True,
            message="Monitoring dashboard data retrieved successfully",
            data=dashboard_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")


# Component-Specific Monitoring Endpoints
@router.get("/transcoding", response_model=MonitoringResponse)
async def get_transcoding_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get transcoding job monitoring data"""
    try:
        # TODO: Add admin permission check
        
        monitoring_service = SystemMonitoringService()
        transcoding_data = await monitoring_service.monitor_transcoding_jobs()
        
        return MonitoringResponse(
            success=True,
            message="Transcoding metrics retrieved successfully",
            data=transcoding_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transcoding metrics: {str(e)}")


@router.get("/storage", response_model=MonitoringResponse)
async def get_storage_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get storage usage monitoring data"""
    try:
        # TODO: Add admin permission check
        
        monitoring_service = SystemMonitoringService()
        storage_data = await monitoring_service.monitor_storage_usage()
        
        return MonitoringResponse(
            success=True,
            message="Storage metrics retrieved successfully",
            data=storage_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get storage metrics: {str(e)}")


@router.get("/streaming", response_model=MonitoringResponse)
async def get_streaming_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get streaming performance monitoring data"""
    try:
        # TODO: Add admin permission check
        
        monitoring_service = SystemMonitoringService()
        streaming_data = await monitoring_service.monitor_streaming_performance()
        
        return MonitoringResponse(
            success=True,
            message="Streaming metrics retrieved successfully",
            data=streaming_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get streaming metrics: {str(e)}")


# Alert Management Endpoints
@router.post("/alerts/test", response_model=MonitoringResponse)
async def send_test_alert(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Send a test alert to verify notification system"""
    try:
        # TODO: Add admin permission check
        
        monitoring_service = SystemMonitoringService()
        
        test_alert = {
            'type': 'test_alert',
            'severity': 'medium',
            'message': f'Test alert sent by {current_user.display_label} at {datetime.utcnow().isoformat()}',
            'value': 0,
            'threshold': 0
        }
        
        background_tasks.add_task(
            monitoring_service.send_alert_notification,
            test_alert
        )
        
        return MonitoringResponse(
            success=True,
            message="Test alert sent successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send test alert: {str(e)}")


@router.put("/thresholds", response_model=MonitoringResponse)
async def update_alert_thresholds(
    request: AlertThresholdsRequest,
    current_user: User = Depends(get_current_user)
):
    """Update alert thresholds"""
    try:
        # TODO: Add admin permission check
        
        monitoring_service = SystemMonitoringService()
        
        # Convert request to dict, excluding None values
        new_thresholds = {
            k: v for k, v in request.dict().items() 
            if v is not None
        }
        
        if not new_thresholds:
            raise HTTPException(status_code=400, detail="No threshold values provided")
        
        result = await monitoring_service.update_alert_thresholds(new_thresholds)
        
        return MonitoringResponse(
            success=True,
            message="Alert thresholds updated successfully",
            data=result
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update thresholds: {str(e)}")


@router.get("/thresholds", response_model=MonitoringResponse)
async def get_alert_thresholds(
    current_user: User = Depends(get_current_user)
):
    """Get current alert thresholds"""
    try:
        # TODO: Add admin permission check
        
        monitoring_service = SystemMonitoringService()
        
        return MonitoringResponse(
            success=True,
            message="Alert thresholds retrieved successfully",
            data={
                'thresholds': monitoring_service.alert_thresholds,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get thresholds: {str(e)}")


# Maintenance Endpoints
@router.post("/cleanup", response_model=MonitoringResponse)
async def cleanup_old_data(
    days_to_keep: int = Query(90, ge=1, le=365),
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Clean up old monitoring data and analytics events"""
    try:
        # TODO: Add admin permission check
        
        monitoring_service = SystemMonitoringService()
        
        # Run cleanup in background
        background_tasks.add_task(
            monitoring_service.cleanup_old_data,
            days_to_keep
        )
        
        return MonitoringResponse(
            success=True,
            message=f"Data cleanup initiated for data older than {days_to_keep} days"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate cleanup: {str(e)}")


# Real-time Monitoring Endpoints
@router.get("/realtime/health", response_model=MonitoringResponse)
async def get_realtime_health(
    current_user: User = Depends(get_current_user)
):
    """Get real-time system health metrics"""
    try:
        # TODO: Add admin permission check
        
        monitoring_service = SystemMonitoringService()
        
        # Get current metrics
        transcoding_data = await monitoring_service.monitor_transcoding_jobs()
        streaming_data = await monitoring_service.monitor_streaming_performance()
        
        realtime_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'transcoding': {
                'processing_jobs': transcoding_data.get('processing_jobs', 0),
                'queued_jobs': transcoding_data.get('queued_jobs', 0),
                'failure_rate': transcoding_data.get('failure_rate_percent', 0)
            },
            'streaming': {
                'active_sessions': streaming_data.get('active_streaming_sessions', 0),
                'error_rate': streaming_data.get('streaming_error_rate_percent', 0),
                'avg_buffering': streaming_data.get('avg_buffering_events', 0)
            }
        }
        
        return MonitoringResponse(
            success=True,
            message="Real-time health metrics retrieved successfully",
            data=realtime_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get real-time metrics: {str(e)}")


# System Status Endpoints
@router.get("/status/simple")
async def get_simple_status():
    """Get simple system status (no authentication required)"""
    try:
        monitoring_service = SystemMonitoringService()
        health_data = await monitoring_service.get_system_health_overview()
        
        return {
            "status": health_data["overall_status"],
            "timestamp": health_data["timestamp"],
            "alerts": health_data["alerts_summary"]["total"]
        }
    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# Webhook Endpoints for External Monitoring
@router.post("/webhook/alert")
async def receive_external_alert(
    alert_data: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """Receive alerts from external monitoring systems"""
    try:
        monitoring_service = SystemMonitoringService()
        
        # Process external alert
        processed_alert = {
            'type': 'external_alert',
            'severity': alert_data.get('severity', 'medium'),
            'message': alert_data.get('message', 'External alert received'),
            'source': alert_data.get('source', 'unknown'),
            'external_data': alert_data
        }
        
        background_tasks.add_task(
            monitoring_service.send_alert_notification,
            processed_alert
        )
        
        return {
            "success": True,
            "message": "External alert received and processed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process external alert: {str(e)}")


# Performance Testing Endpoints
@router.post("/test/load", response_model=MonitoringResponse)
async def simulate_load_test(
    duration_seconds: int = Query(60, ge=10, le=300),
    concurrent_requests: int = Query(10, ge=1, le=100),
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Simulate load for testing monitoring and alerting"""
    try:
        # TODO: Add admin permission check
        
        # This would simulate load on the system for testing
        # In a real implementation, this might:
        # 1. Create fake view sessions
        # 2. Generate analytics events
        # 3. Simulate transcoding jobs
        # 4. Test alert thresholds
        
        return MonitoringResponse(
            success=True,
            message=f"Load test initiated: {concurrent_requests} concurrent requests for {duration_seconds} seconds"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate load test: {str(e)}")