"""
Cache Monitoring Service

Provides comprehensive monitoring and alerting for cache performance,
including metrics collection, performance analysis, and optimization recommendations.
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.redis_client import RedisClient, get_redis_client
from server.web.app.services.video_cache_service import VideoCacheService
from server.web.app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CacheMetric:
    """Cache performance metric"""
    timestamp: datetime
    metric_name: str
    value: float
    tags: Dict[str, str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'metric_name': self.metric_name,
            'value': self.value,
            'tags': self.tags or {}
        }


@dataclass
class CacheAlert:
    """Cache performance alert"""
    timestamp: datetime
    level: AlertLevel
    message: str
    metric_name: str
    current_value: float
    threshold: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'message': self.message,
            'metric_name': self.metric_name,
            'current_value': self.current_value,
            'threshold': self.threshold
        }


@dataclass
class PerformanceThresholds:
    """Performance monitoring thresholds"""
    hit_rate_warning: float = 70.0      # Hit rate below 70% triggers warning
    hit_rate_critical: float = 50.0     # Hit rate below 50% triggers critical alert
    response_time_warning: float = 100.0  # Response time above 100ms triggers warning
    response_time_critical: float = 500.0  # Response time above 500ms triggers critical alert
    memory_usage_warning: float = 80.0   # Memory usage above 80% triggers warning
    memory_usage_critical: float = 95.0  # Memory usage above 95% triggers critical alert
    error_rate_warning: float = 5.0     # Error rate above 5% triggers warning
    error_rate_critical: float = 10.0   # Error rate above 10% triggers critical alert


class CacheMonitoringService(BaseService):
    """Service for monitoring cache performance and generating alerts"""
    
    def __init__(self, db: AsyncSession, redis_client: RedisClient = None):
        self.db = db
        self.redis = redis_client
        self.thresholds = PerformanceThresholds()
        self.metrics_history: List[CacheMetric] = []
        self.alerts_history: List[CacheAlert] = []
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
    
    async def _get_redis(self) -> RedisClient:
        """Get Redis client instance"""
        if self.redis is None:
            self.redis = await get_redis_client()
        return self.redis
    
    async def start_monitoring(self, interval_seconds: int = 60):
        """
        Start continuous cache monitoring
        
        Args:
            interval_seconds: Monitoring interval in seconds
        """
        if self._is_monitoring:
            logger.warning("Cache monitoring is already running")
            return
        
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )
        logger.info(f"Started cache monitoring with {interval_seconds}s interval")
    
    async def stop_monitoring(self):
        """Stop cache monitoring"""
        if not self._is_monitoring:
            return
        
        self._is_monitoring = False
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                logger.info("Cache monitoring task cancelled")
        
        logger.info("Cache monitoring stopped")
    
    async def _monitoring_loop(self, interval_seconds: int):
        """Main monitoring loop"""
        while self._is_monitoring:
            try:
                # Collect metrics
                await self._collect_metrics()
                
                # Check for alerts
                await self._check_alerts()
                
                # Clean up old data
                await self._cleanup_old_data()
                
                # Wait for next interval
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("Cache monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cache monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def _collect_metrics(self):
        """Collect cache performance metrics"""
        redis = await self._get_redis()
        timestamp = datetime.utcnow()
        
        try:
            # Get Redis info
            redis_info = await redis.client.info()
            
            # Collect basic Redis metrics
            metrics = [
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="redis_used_memory_bytes",
                    value=float(redis_info.get('used_memory', 0))
                ),
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="redis_connected_clients",
                    value=float(redis_info.get('connected_clients', 0))
                ),
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="redis_total_commands_processed",
                    value=float(redis_info.get('total_commands_processed', 0))
                ),
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="redis_keyspace_hits",
                    value=float(redis_info.get('keyspace_hits', 0))
                ),
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="redis_keyspace_misses",
                    value=float(redis_info.get('keyspace_misses', 0))
                )
            ]
            
            # Calculate hit rate
            hits = redis_info.get('keyspace_hits', 0)
            misses = redis_info.get('keyspace_misses', 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0.0
            
            metrics.append(CacheMetric(
                timestamp=timestamp,
                metric_name="cache_hit_rate_percent",
                value=hit_rate
            ))
            
            # Get application-level cache stats
            app_hits = await redis.get("cache:stats:hits", default=0)
            app_misses = await redis.get("cache:stats:misses", default=0)
            app_sets = await redis.get("cache:stats:sets", default=0)
            app_errors = await redis.get("cache:stats:errors", default=0)
            
            app_total = app_hits + app_misses
            app_hit_rate = (app_hits / app_total * 100) if app_total > 0 else 0.0
            app_error_rate = (app_errors / (app_total + app_errors) * 100) if (app_total + app_errors) > 0 else 0.0
            
            metrics.extend([
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="app_cache_hits",
                    value=float(app_hits)
                ),
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="app_cache_misses",
                    value=float(app_misses)
                ),
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="app_cache_sets",
                    value=float(app_sets)
                ),
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="app_cache_errors",
                    value=float(app_errors)
                ),
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="app_cache_hit_rate_percent",
                    value=app_hit_rate
                ),
                CacheMetric(
                    timestamp=timestamp,
                    metric_name="app_cache_error_rate_percent",
                    value=app_error_rate
                )
            ])
            
            # Store metrics in history
            self.metrics_history.extend(metrics)
            
            # Store metrics in Redis for persistence
            for metric in metrics:
                key = f"metrics:{metric.metric_name}:{int(timestamp.timestamp())}"
                await redis.set(key, metric.value, expire=86400)  # Keep for 24 hours
            
        except Exception as e:
            logger.error(f"Error collecting cache metrics: {e}")
    
    async def _check_alerts(self):
        """Check metrics against thresholds and generate alerts"""
        if not self.metrics_history:
            return
        
        # Get latest metrics
        latest_metrics = {}
        for metric in reversed(self.metrics_history):
            if metric.metric_name not in latest_metrics:
                latest_metrics[metric.metric_name] = metric
        
        # Check hit rate
        hit_rate_metric = latest_metrics.get("app_cache_hit_rate_percent")
        if hit_rate_metric:
            if hit_rate_metric.value < self.thresholds.hit_rate_critical:
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    f"Cache hit rate critically low: {hit_rate_metric.value:.1f}%",
                    hit_rate_metric.metric_name,
                    hit_rate_metric.value,
                    self.thresholds.hit_rate_critical
                )
            elif hit_rate_metric.value < self.thresholds.hit_rate_warning:
                await self._create_alert(
                    AlertLevel.WARNING,
                    f"Cache hit rate below threshold: {hit_rate_metric.value:.1f}%",
                    hit_rate_metric.metric_name,
                    hit_rate_metric.value,
                    self.thresholds.hit_rate_warning
                )
        
        # Check error rate
        error_rate_metric = latest_metrics.get("app_cache_error_rate_percent")
        if error_rate_metric:
            if error_rate_metric.value > self.thresholds.error_rate_critical:
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    f"Cache error rate critically high: {error_rate_metric.value:.1f}%",
                    error_rate_metric.metric_name,
                    error_rate_metric.value,
                    self.thresholds.error_rate_critical
                )
            elif error_rate_metric.value > self.thresholds.error_rate_warning:
                await self._create_alert(
                    AlertLevel.WARNING,
                    f"Cache error rate above threshold: {error_rate_metric.value:.1f}%",
                    error_rate_metric.metric_name,
                    error_rate_metric.value,
                    self.thresholds.error_rate_warning
                )
        
        # Check memory usage
        memory_metric = latest_metrics.get("redis_used_memory_bytes")
        if memory_metric:
            # Get max memory from Redis config (simplified - in production you'd get this from Redis)
            max_memory = 1024 * 1024 * 1024  # Assume 1GB max for example
            memory_usage_percent = (memory_metric.value / max_memory) * 100
            
            if memory_usage_percent > self.thresholds.memory_usage_critical:
                await self._create_alert(
                    AlertLevel.CRITICAL,
                    f"Redis memory usage critically high: {memory_usage_percent:.1f}%",
                    "redis_memory_usage_percent",
                    memory_usage_percent,
                    self.thresholds.memory_usage_critical
                )
            elif memory_usage_percent > self.thresholds.memory_usage_warning:
                await self._create_alert(
                    AlertLevel.WARNING,
                    f"Redis memory usage above threshold: {memory_usage_percent:.1f}%",
                    "redis_memory_usage_percent",
                    memory_usage_percent,
                    self.thresholds.memory_usage_warning
                )
    
    async def _create_alert(
        self,
        level: AlertLevel,
        message: str,
        metric_name: str,
        current_value: float,
        threshold: float
    ):
        """Create and store an alert"""
        alert = CacheAlert(
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold
        )
        
        self.alerts_history.append(alert)
        
        # Store alert in Redis
        redis = await self._get_redis()
        alert_key = f"alerts:{int(alert.timestamp.timestamp())}"
        await redis.set(alert_key, alert.to_dict(), expire=604800)  # Keep for 7 days
        
        # Log the alert
        log_level = logging.CRITICAL if level == AlertLevel.CRITICAL else logging.WARNING
        logger.log(log_level, f"Cache Alert [{level.value.upper()}]: {message}")
    
    async def _cleanup_old_data(self):
        """Clean up old metrics and alerts from memory"""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Clean up metrics history
        self.metrics_history = [
            metric for metric in self.metrics_history
            if metric.timestamp > cutoff_time
        ]
        
        # Clean up alerts history
        self.alerts_history = [
            alert for alert in self.alerts_history
            if alert.timestamp > cutoff_time
        ]
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current cache performance metrics
        
        Returns:
            Dictionary with current metrics
        """
        redis = await self._get_redis()
        
        try:
            # Get Redis info
            redis_info = await redis.client.info()
            
            # Get application stats
            app_hits = await redis.get("cache:stats:hits", default=0)
            app_misses = await redis.get("cache:stats:misses", default=0)
            app_sets = await redis.get("cache:stats:sets", default=0)
            app_errors = await redis.get("cache:stats:errors", default=0)
            
            # Calculate rates
            app_total = app_hits + app_misses
            app_hit_rate = (app_hits / app_total * 100) if app_total > 0 else 0.0
            app_error_rate = (app_errors / (app_total + app_errors) * 100) if (app_total + app_errors) > 0 else 0.0
            
            redis_hits = redis_info.get('keyspace_hits', 0)
            redis_misses = redis_info.get('keyspace_misses', 0)
            redis_total = redis_hits + redis_misses
            redis_hit_rate = (redis_hits / redis_total * 100) if redis_total > 0 else 0.0
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'redis_metrics': {
                    'used_memory_bytes': redis_info.get('used_memory', 0),
                    'used_memory_human': redis_info.get('used_memory_human', 'N/A'),
                    'connected_clients': redis_info.get('connected_clients', 0),
                    'total_commands_processed': redis_info.get('total_commands_processed', 0),
                    'keyspace_hits': redis_hits,
                    'keyspace_misses': redis_misses,
                    'hit_rate_percent': round(redis_hit_rate, 2)
                },
                'application_metrics': {
                    'cache_hits': app_hits,
                    'cache_misses': app_misses,
                    'cache_sets': app_sets,
                    'cache_errors': app_errors,
                    'hit_rate_percent': round(app_hit_rate, 2),
                    'error_rate_percent': round(app_error_rate, 2),
                    'total_requests': app_total
                },
                'performance_status': {
                    'hit_rate_status': self._get_status_level(app_hit_rate, self.thresholds.hit_rate_warning, self.thresholds.hit_rate_critical, reverse=True),
                    'error_rate_status': self._get_status_level(app_error_rate, self.thresholds.error_rate_warning, self.thresholds.error_rate_critical),
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {'error': str(e)}
    
    def _get_status_level(self, value: float, warning_threshold: float, critical_threshold: float, reverse: bool = False) -> str:
        """Get status level based on thresholds"""
        if reverse:
            # For metrics where lower values are worse (like hit rate)
            if value < critical_threshold:
                return "critical"
            elif value < warning_threshold:
                return "warning"
            else:
                return "ok"
        else:
            # For metrics where higher values are worse (like error rate)
            if value > critical_threshold:
                return "critical"
            elif value > warning_threshold:
                return "warning"
            else:
                return "ok"
    
    async def get_metrics_history(
        self,
        metric_name: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get historical metrics data
        
        Args:
            metric_name: Specific metric to retrieve (None for all)
            hours: Number of hours of history to retrieve
            
        Returns:
            List of metric dictionaries
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        filtered_metrics = [
            metric for metric in self.metrics_history
            if metric.timestamp > cutoff_time and (
                metric_name is None or metric.metric_name == metric_name
            )
        ]
        
        return [metric.to_dict() for metric in filtered_metrics]
    
    async def get_alerts_history(
        self,
        level: Optional[AlertLevel] = None,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get historical alerts data
        
        Args:
            level: Specific alert level to retrieve (None for all)
            hours: Number of hours of history to retrieve
            
        Returns:
            List of alert dictionaries
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        filtered_alerts = [
            alert for alert in self.alerts_history
            if alert.timestamp > cutoff_time and (
                level is None or alert.level == level
            )
        ]
        
        return [alert.to_dict() for alert in filtered_alerts]
    
    async def get_performance_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get performance optimization recommendations based on metrics
        
        Returns:
            List of recommendation dictionaries
        """
        recommendations = []
        
        # Get current metrics
        current_metrics = await self.get_current_metrics()
        
        if 'error' in current_metrics:
            return recommendations
        
        app_metrics = current_metrics.get('application_metrics', {})
        redis_metrics = current_metrics.get('redis_metrics', {})
        
        # Check hit rate
        hit_rate = app_metrics.get('hit_rate_percent', 0)
        if hit_rate < self.thresholds.hit_rate_warning:
            recommendations.append({
                'type': 'performance',
                'priority': 'high' if hit_rate < self.thresholds.hit_rate_critical else 'medium',
                'title': 'Low Cache Hit Rate',
                'description': f'Current hit rate is {hit_rate:.1f}%. Consider increasing cache TTL or implementing cache warming.',
                'actions': [
                    'Review cache TTL settings',
                    'Implement cache warming for popular content',
                    'Analyze cache miss patterns',
                    'Consider increasing cache memory allocation'
                ]
            })
        
        # Check error rate
        error_rate = app_metrics.get('error_rate_percent', 0)
        if error_rate > self.thresholds.error_rate_warning:
            recommendations.append({
                'type': 'reliability',
                'priority': 'high' if error_rate > self.thresholds.error_rate_critical else 'medium',
                'title': 'High Cache Error Rate',
                'description': f'Current error rate is {error_rate:.1f}%. Investigate Redis connectivity and configuration.',
                'actions': [
                    'Check Redis server health',
                    'Review Redis connection pool settings',
                    'Analyze error logs for patterns',
                    'Consider implementing circuit breaker pattern'
                ]
            })
        
        # Check memory usage
        used_memory = redis_metrics.get('used_memory_bytes', 0)
        if used_memory > 0:
            # Simplified memory check - in production you'd get max memory from Redis config
            estimated_max = 1024 * 1024 * 1024  # 1GB
            memory_usage_percent = (used_memory / estimated_max) * 100
            
            if memory_usage_percent > self.thresholds.memory_usage_warning:
                recommendations.append({
                    'type': 'capacity',
                    'priority': 'high' if memory_usage_percent > self.thresholds.memory_usage_critical else 'medium',
                    'title': 'High Memory Usage',
                    'description': f'Redis memory usage is {memory_usage_percent:.1f}%. Consider optimizing cache usage.',
                    'actions': [
                        'Review cache TTL settings to reduce memory usage',
                        'Implement cache eviction policies',
                        'Consider increasing Redis memory allocation',
                        'Analyze large cache entries for optimization'
                    ]
                })
        
        return recommendations
    
    async def update_thresholds(self, new_thresholds: Dict[str, float]) -> bool:
        """
        Update performance monitoring thresholds
        
        Args:
            new_thresholds: Dictionary with new threshold values
            
        Returns:
            True if successful, False otherwise
        """
        try:
            for key, value in new_thresholds.items():
                if hasattr(self.thresholds, key):
                    setattr(self.thresholds, key, float(value))
            
            logger.info(f"Updated cache monitoring thresholds: {new_thresholds}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating thresholds: {e}")
            return False


# Dependency for FastAPI
async def get_cache_monitoring_service(db: AsyncSession) -> CacheMonitoringService:
    """Get cache monitoring service instance"""
    return CacheMonitoringService(db)