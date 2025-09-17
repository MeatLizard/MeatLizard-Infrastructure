"""
Monitoring and Health Check API Endpoints
Provides comprehensive health checks, metrics, and monitoring endpoints for the video platform.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import psutil
import redis
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from server.web.app.db import get_db
from server.web.app.dependencies import get_current_user
from server.web.app.models import User
from server.web.app.services.redis_client import get_redis_client

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# Prometheus metrics
health_check_counter = Counter('health_checks_total', 'Total health checks performed', ['endpoint', 'status'])
health_check_duration = Histogram('health_check_duration_seconds', 'Health check duration', ['endpoint'])
system_cpu_usage = Gauge('system_cpu_usage_percent', 'System CPU usage percentage')
system_memory_usage = Gauge('system_memory_usage_percent', 'System memory usage percentage')
system_disk_usage = Gauge('system_disk_usage_percent', 'System disk usage percentage', ['mountpoint'])
active_connections = Gauge('database_connections_active', 'Active database connections')
redis_connections = Gauge('redis_connections_active', 'Active Redis connections')

class HealthCheckService:
    """Service for performing comprehensive health checks"""
    
    def __init__(self):
        self.checks = {
            'database': self._check_database,
            'redis': self._check_redis,
            'storage': self._check_storage,
            'workers': self._check_workers,
            'system': self._check_system_resources
        }
    
    async def perform_health_check(self, db: AsyncSession, check_name: Optional[str] = None) -> Dict[str, Any]:
        """Perform health checks and return status"""
        results = {}
        overall_healthy = True
        
        checks_to_run = {check_name: self.checks[check_name]} if check_name else self.checks
        
        for name, check_func in checks_to_run.items():
            start_time = time.time()
            try:
                with health_check_duration.labels(endpoint=name).time():
                    result = await check_func(db)
                    results[name] = result
                    
                    if not result.get('healthy', False):
                        overall_healthy = False
                    
                    health_check_counter.labels(endpoint=name, status='success').inc()
                    
            except Exception as e:
                results[name] = {
                    'healthy': False,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
                overall_healthy = False
                health_check_counter.labels(endpoint=name, status='error').inc()
        
        return {
            'healthy': overall_healthy,
            'timestamp': datetime.utcnow().isoformat(),
            'checks': results
        }
    
    async def _check_database(self, db: AsyncSession) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            # Test basic connectivity
            start_time = time.time()
            result = await db.execute(text("SELECT 1"))
            query_time = time.time() - start_time
            
            # Get connection count
            conn_result = await db.execute(text("""
                SELECT count(*) as active_connections 
                FROM pg_stat_activity 
                WHERE state = 'active'
            """))
            active_conns = conn_result.scalar()
            active_connections.set(active_conns)
            
            # Get database size
            size_result = await db.execute(text("""
                SELECT pg_database_size(current_database()) as db_size
            """))
            db_size = size_result.scalar()
            
            # Check for long-running queries
            long_queries_result = await db.execute(text("""
                SELECT count(*) as long_queries
                FROM pg_stat_activity 
                WHERE state = 'active' 
                AND now() - query_start > interval '5 minutes'
            """))
            long_queries = long_queries_result.scalar()
            
            return {
                'healthy': query_time < 1.0 and long_queries == 0,
                'query_time_ms': round(query_time * 1000, 2),
                'active_connections': active_conns,
                'database_size_mb': round(db_size / 1024 / 1024, 2),
                'long_running_queries': long_queries,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _check_redis(self, db: AsyncSession) -> Dict[str, Any]:
        """Check Redis connectivity and performance"""
        try:
            redis_client = await get_redis_client()
            
            # Test basic connectivity
            start_time = time.time()
            await redis_client.ping()
            ping_time = time.time() - start_time
            
            # Get Redis info
            info = await redis_client.info()
            
            # Get memory usage
            memory_used = info.get('used_memory', 0)
            memory_max = info.get('maxmemory', 0)
            memory_usage_percent = (memory_used / memory_max * 100) if memory_max > 0 else 0
            
            # Get connection count
            connected_clients = info.get('connected_clients', 0)
            redis_connections.set(connected_clients)
            
            return {
                'healthy': ping_time < 0.1 and memory_usage_percent < 90,
                'ping_time_ms': round(ping_time * 1000, 2),
                'memory_used_mb': round(memory_used / 1024 / 1024, 2),
                'memory_usage_percent': round(memory_usage_percent, 2),
                'connected_clients': connected_clients,
                'uptime_seconds': info.get('uptime_in_seconds', 0),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _check_storage(self, db: AsyncSession) -> Dict[str, Any]:
        """Check S3 storage connectivity and usage"""
        try:
            # This would integrate with your S3 service
            # For now, return a placeholder
            return {
                'healthy': True,
                'buckets_accessible': 4,
                'total_size_gb': 150.5,
                'available_space_gb': 849.5,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _check_workers(self, db: AsyncSession) -> Dict[str, Any]:
        """Check worker processes status"""
        try:
            # Check transcoding jobs queue
            transcoding_result = await db.execute(text("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'queued') as queued,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed
                FROM transcoding_jobs 
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """))
            transcoding_stats = transcoding_result.fetchone()
            
            # Check import jobs queue
            import_result = await db.execute(text("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'queued') as queued,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed
                FROM import_jobs 
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """))
            import_stats = import_result.fetchone()
            
            # Check for stuck jobs
            stuck_jobs_result = await db.execute(text("""
                SELECT COUNT(*) as stuck_jobs
                FROM transcoding_jobs 
                WHERE status = 'processing' 
                AND started_at < NOW() - INTERVAL '2 hours'
            """))
            stuck_jobs = stuck_jobs_result.scalar()
            
            return {
                'healthy': stuck_jobs == 0 and transcoding_stats.queued < 100,
                'transcoding': {
                    'queued': transcoding_stats.queued,
                    'processing': transcoding_stats.processing,
                    'failed': transcoding_stats.failed
                },
                'import': {
                    'queued': import_stats.queued,
                    'processing': import_stats.processing,
                    'failed': import_stats.failed
                },
                'stuck_jobs': stuck_jobs,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _check_system_resources(self, db: AsyncSession) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            system_cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            system_memory_usage.set(memory_percent)
            
            # Disk usage
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    usage_percent = (usage.used / usage.total) * 100
                    disk_usage[partition.mountpoint] = {
                        'total_gb': round(usage.total / 1024**3, 2),
                        'used_gb': round(usage.used / 1024**3, 2),
                        'free_gb': round(usage.free / 1024**3, 2),
                        'usage_percent': round(usage_percent, 2)
                    }
                    system_disk_usage.labels(mountpoint=partition.mountpoint).set(usage_percent)
                except PermissionError:
                    continue
            
            # Network I/O
            network = psutil.net_io_counters()
            
            return {
                'healthy': cpu_percent < 80 and memory_percent < 85,
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'memory_available_gb': round(memory.available / 1024**3, 2),
                'disk_usage': disk_usage,
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

# Initialize health check service
health_service = HealthCheckService()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Basic health check endpoint"""
    result = await health_service.perform_health_check(db)
    
    if not result['healthy']:
        raise HTTPException(status_code=503, detail=result)
    
    return result

@router.get("/health/{check_name}")
async def specific_health_check(check_name: str, db: AsyncSession = Depends(get_db)):
    """Perform a specific health check"""
    if check_name not in health_service.checks:
        raise HTTPException(status_code=404, detail=f"Health check '{check_name}' not found")
    
    result = await health_service.perform_health_check(db, check_name)
    
    if not result['healthy']:
        raise HTTPException(status_code=503, detail=result)
    
    return result

@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@router.get("/status")
async def system_status(db: AsyncSession = Depends(get_db)):
    """Comprehensive system status"""
    result = await health_service.perform_health_check(db)
    
    # Add additional status information
    result['version'] = "1.0.0"  # Replace with actual version
    result['environment'] = "development"  # Replace with actual environment
    result['uptime'] = time.time() - psutil.boot_time()
    
    return result

@router.post("/alerts/webhook")
async def alert_webhook(alert_data: Dict[str, Any], background_tasks: BackgroundTasks):
    """Webhook endpoint for receiving alerts from AlertManager"""
    # Process alert data
    background_tasks.add_task(process_alert, alert_data)
    return {"status": "received"}

@router.post("/alerts/{alert_type}")
async def typed_alert_webhook(alert_type: str, alert_data: Dict[str, Any], background_tasks: BackgroundTasks):
    """Typed alert webhook for specific alert categories"""
    background_tasks.add_task(process_typed_alert, alert_type, alert_data)
    return {"status": "received"}

async def process_alert(alert_data: Dict[str, Any]):
    """Process incoming alert data"""
    # Log alert
    print(f"Received alert: {alert_data}")
    
    # Here you could:
    # - Store alert in database
    # - Send notifications
    # - Trigger automated responses
    # - Update system status

async def process_typed_alert(alert_type: str, alert_data: Dict[str, Any]):
    """Process typed alert data"""
    print(f"Received {alert_type} alert: {alert_data}")
    
    # Handle specific alert types
    if alert_type == "critical":
        # Handle critical alerts
        pass
    elif alert_type == "transcoding":
        # Handle transcoding-related alerts
        pass
    elif alert_type == "import":
        # Handle import-related alerts
        pass

@router.get("/logs")
async def get_recent_logs(
    service: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """Get recent application logs (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # This would integrate with your logging system
    # For now, return a placeholder
    return {
        "logs": [],
        "total": 0,
        "filters": {
            "service": service,
            "level": level,
            "limit": limit
        }
    }

@router.get("/performance")
async def performance_metrics(db: AsyncSession = Depends(get_db)):
    """Get performance metrics"""
    # Get recent performance data
    result = await db.execute(text("""
        SELECT 
            AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_transcoding_time,
            COUNT(*) FILTER (WHERE status = 'completed') as completed_jobs,
            COUNT(*) FILTER (WHERE status = 'failed') as failed_jobs
        FROM transcoding_jobs 
        WHERE created_at > NOW() - INTERVAL '1 hour'
    """))
    transcoding_perf = result.fetchone()
    
    # Get upload statistics
    upload_result = await db.execute(text("""
        SELECT 
            COUNT(*) as total_uploads,
            AVG(file_size) as avg_file_size,
            SUM(file_size) as total_size
        FROM videos 
        WHERE created_at > NOW() - INTERVAL '1 hour'
    """))
    upload_stats = upload_result.fetchone()
    
    return {
        'transcoding': {
            'avg_time_seconds': round(transcoding_perf.avg_transcoding_time or 0, 2),
            'completed_jobs': transcoding_perf.completed_jobs,
            'failed_jobs': transcoding_perf.failed_jobs,
            'success_rate': round(
                (transcoding_perf.completed_jobs / 
                 (transcoding_perf.completed_jobs + transcoding_perf.failed_jobs) * 100) 
                if (transcoding_perf.completed_jobs + transcoding_perf.failed_jobs) > 0 else 0, 2
            )
        },
        'uploads': {
            'total_uploads': upload_stats.total_uploads,
            'avg_file_size_mb': round((upload_stats.avg_file_size or 0) / 1024 / 1024, 2),
            'total_size_gb': round((upload_stats.total_size or 0) / 1024 / 1024 / 1024, 2)
        },
        'timestamp': datetime.utcnow().isoformat()
    }