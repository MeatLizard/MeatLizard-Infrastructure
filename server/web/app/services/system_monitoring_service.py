"""
System Monitoring and Alerting Service

Provides comprehensive system monitoring including:
- Transcoding job monitoring and failure alerts
- Storage usage tracking and quota management
- Performance monitoring for streaming endpoints
- Automated alerting for system issues
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    TranscodingJob, TranscodingStatus, Video, ViewSession, 
    SystemMetrics, AnalyticsEvent, User
)
from .base_service import BaseService


logger = logging.getLogger(__name__)


class SystemMonitoringService(BaseService):
    """Service for system monitoring and alerting"""
    
    def __init__(self):
        super().__init__()
        self.alert_thresholds = {
            'transcoding_failure_rate': 10.0,  # Percentage
            'storage_usage_warning': 80.0,     # Percentage
            'storage_usage_critical': 95.0,    # Percentage
            'streaming_error_rate': 5.0,       # Percentage
            'avg_response_time': 5000,         # Milliseconds
            'concurrent_sessions': 1000,       # Number of sessions
            'disk_usage_warning': 85.0,        # Percentage
            'memory_usage_warning': 90.0       # Percentage
        }
    
    async def monitor_transcoding_jobs(self) -> Dict[str, Any]:
        """Monitor transcoding job status and performance"""
        async with self.get_db_session() as db:
            # Get jobs from last 24 hours
            since = datetime.utcnow() - timedelta(hours=24)
            
            # Total jobs
            total_jobs_stmt = select(func.count(TranscodingJob.id)).where(
                TranscodingJob.created_at >= since
            )
            total_jobs_result = await db.execute(total_jobs_stmt)
            total_jobs = total_jobs_result.scalar() or 0
            
            # Failed jobs
            failed_jobs_stmt = select(func.count(TranscodingJob.id)).where(
                and_(
                    TranscodingJob.created_at >= since,
                    TranscodingJob.status == TranscodingStatus.failed
                )
            )
            failed_jobs_result = await db.execute(failed_jobs_stmt)
            failed_jobs = failed_jobs_result.scalar() or 0
            
            # Completed jobs
            completed_jobs_stmt = select(func.count(TranscodingJob.id)).where(
                and_(
                    TranscodingJob.created_at >= since,
                    TranscodingJob.status == TranscodingStatus.completed
                )
            )
            completed_jobs_result = await db.execute(completed_jobs_stmt)
            completed_jobs = completed_jobs_result.scalar() or 0
            
            # Processing jobs
            processing_jobs_stmt = select(func.count(TranscodingJob.id)).where(
                TranscodingJob.status == TranscodingStatus.processing
            )
            processing_jobs_result = await db.execute(processing_jobs_stmt)
            processing_jobs = processing_jobs_result.scalar() or 0
            
            # Queued jobs
            queued_jobs_stmt = select(func.count(TranscodingJob.id)).where(
                TranscodingJob.status == TranscodingStatus.queued
            )
            queued_jobs_result = await db.execute(queued_jobs_stmt)
            queued_jobs = queued_jobs_result.scalar() or 0
            
            # Calculate metrics
            failure_rate = (failed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            completion_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            
            # Get average processing time for completed jobs
            avg_time_stmt = select(
                func.avg(
                    func.extract('epoch', TranscodingJob.completed_at) - 
                    func.extract('epoch', TranscodingJob.started_at)
                )
            ).where(
                and_(
                    TranscodingJob.created_at >= since,
                    TranscodingJob.status == TranscodingStatus.completed,
                    TranscodingJob.started_at.is_not(None),
                    TranscodingJob.completed_at.is_not(None)
                )
            )
            avg_time_result = await db.execute(avg_time_stmt)
            avg_processing_time = avg_time_result.scalar() or 0
            
            # Get recent failed jobs for details
            failed_jobs_details_stmt = select(TranscodingJob).where(
                and_(
                    TranscodingJob.created_at >= since,
                    TranscodingJob.status == TranscodingStatus.failed
                )
            ).order_by(desc(TranscodingJob.created_at)).limit(10)
            failed_jobs_details_result = await db.execute(failed_jobs_details_stmt)
            failed_jobs_details = failed_jobs_details_result.scalars().all()
            
            monitoring_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'total_jobs_24h': total_jobs,
                'failed_jobs_24h': failed_jobs,
                'completed_jobs_24h': completed_jobs,
                'processing_jobs': processing_jobs,
                'queued_jobs': queued_jobs,
                'failure_rate_percent': failure_rate,
                'completion_rate_percent': completion_rate,
                'avg_processing_time_seconds': avg_processing_time,
                'recent_failures': [
                    {
                        'job_id': str(job.id),
                        'video_id': str(job.video_id),
                        'quality_preset': job.quality_preset,
                        'error_message': job.error_message,
                        'created_at': job.created_at.isoformat()
                    }
                    for job in failed_jobs_details
                ]
            }
            
            # Check for alerts
            alerts = []
            if failure_rate > self.alert_thresholds['transcoding_failure_rate']:
                alerts.append({
                    'type': 'transcoding_failure_rate',
                    'severity': 'high',
                    'message': f'Transcoding failure rate is {failure_rate:.1f}% (threshold: {self.alert_thresholds["transcoding_failure_rate"]}%)',
                    'value': failure_rate,
                    'threshold': self.alert_thresholds['transcoding_failure_rate']
                })
            
            if queued_jobs > 50:
                alerts.append({
                    'type': 'transcoding_queue_backlog',
                    'severity': 'medium',
                    'message': f'{queued_jobs} jobs queued for transcoding',
                    'value': queued_jobs,
                    'threshold': 50
                })
            
            monitoring_data['alerts'] = alerts
            
            return monitoring_data
    
    async def monitor_storage_usage(self) -> Dict[str, Any]:
        """Monitor storage usage and quota management"""
        async with self.get_db_session() as db:
            # Calculate total storage usage
            total_original_stmt = select(func.sum(Video.file_size)).where(
                Video.file_size.is_not(None)
            )
            total_original_result = await db.execute(total_original_stmt)
            total_original_bytes = total_original_result.scalar() or 0
            
            # Calculate transcoded storage (estimate based on jobs)
            total_transcoded_stmt = select(func.sum(TranscodingJob.output_file_size)).where(
                and_(
                    TranscodingJob.status == TranscodingStatus.completed,
                    TranscodingJob.output_file_size.is_not(None)
                )
            )
            total_transcoded_result = await db.execute(total_transcoded_stmt)
            total_transcoded_bytes = total_transcoded_result.scalar() or 0
            
            # Get storage by user
            user_storage_stmt = select(
                Video.creator_id,
                User.display_label,
                func.sum(Video.file_size).label('total_size'),
                func.count(Video.id).label('video_count')
            ).select_from(
                Video
            ).join(
                User, Video.creator_id == User.id
            ).where(
                Video.file_size.is_not(None)
            ).group_by(
                Video.creator_id, User.display_label
            ).order_by(
                desc('total_size')
            ).limit(10)
            
            user_storage_result = await db.execute(user_storage_stmt)
            user_storage = user_storage_result.all()
            
            # Calculate storage growth (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            growth_stmt = select(func.sum(Video.file_size)).where(
                and_(
                    Video.created_at >= thirty_days_ago,
                    Video.file_size.is_not(None)
                )
            )
            growth_result = await db.execute(growth_stmt)
            growth_bytes = growth_result.scalar() or 0
            
            total_storage_bytes = total_original_bytes + total_transcoded_bytes
            
            # Assume 1TB storage limit for now (this should be configurable)
            storage_limit_bytes = 1024 * 1024 * 1024 * 1024  # 1TB
            usage_percentage = (total_storage_bytes / storage_limit_bytes * 100) if storage_limit_bytes > 0 else 0
            
            monitoring_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'total_storage_bytes': total_storage_bytes,
                'total_storage_gb': total_storage_bytes / (1024**3),
                'original_storage_bytes': total_original_bytes,
                'transcoded_storage_bytes': total_transcoded_bytes,
                'storage_limit_bytes': storage_limit_bytes,
                'usage_percentage': usage_percentage,
                'growth_30d_bytes': growth_bytes,
                'growth_30d_gb': growth_bytes / (1024**3),
                'top_users_by_storage': [
                    {
                        'user_id': str(row.creator_id),
                        'display_name': row.display_label,
                        'storage_bytes': row.total_size,
                        'storage_gb': row.total_size / (1024**3),
                        'video_count': row.video_count
                    }
                    for row in user_storage
                ]
            }
            
            # Check for alerts
            alerts = []
            if usage_percentage > self.alert_thresholds['storage_usage_critical']:
                alerts.append({
                    'type': 'storage_usage_critical',
                    'severity': 'critical',
                    'message': f'Storage usage is {usage_percentage:.1f}% (critical threshold: {self.alert_thresholds["storage_usage_critical"]}%)',
                    'value': usage_percentage,
                    'threshold': self.alert_thresholds['storage_usage_critical']
                })
            elif usage_percentage > self.alert_thresholds['storage_usage_warning']:
                alerts.append({
                    'type': 'storage_usage_warning',
                    'severity': 'medium',
                    'message': f'Storage usage is {usage_percentage:.1f}% (warning threshold: {self.alert_thresholds["storage_usage_warning"]}%)',
                    'value': usage_percentage,
                    'threshold': self.alert_thresholds['storage_usage_warning']
                })
            
            monitoring_data['alerts'] = alerts
            
            return monitoring_data
    
    async def monitor_streaming_performance(self) -> Dict[str, Any]:
        """Monitor streaming endpoint performance"""
        async with self.get_db_session() as db:
            # Get streaming metrics from last hour
            since = datetime.utcnow() - timedelta(hours=1)
            
            # Active streaming sessions
            active_sessions_stmt = select(func.count(ViewSession.id)).where(
                and_(
                    ViewSession.last_heartbeat >= since,
                    ViewSession.ended_at.is_(None)
                )
            )
            active_sessions_result = await db.execute(active_sessions_stmt)
            active_sessions = active_sessions_result.scalar() or 0
            
            # Total sessions started in last hour
            new_sessions_stmt = select(func.count(ViewSession.id)).where(
                ViewSession.started_at >= since
            )
            new_sessions_result = await db.execute(new_sessions_stmt)
            new_sessions = new_sessions_result.scalar() or 0
            
            # Average buffering events per session
            avg_buffering_stmt = select(func.avg(ViewSession.buffering_events)).where(
                ViewSession.started_at >= since
            )
            avg_buffering_result = await db.execute(avg_buffering_stmt)
            avg_buffering = avg_buffering_result.scalar() or 0
            
            # Average quality switches per session
            avg_quality_switches_stmt = select(func.avg(ViewSession.quality_switches)).where(
                ViewSession.started_at >= since
            )
            avg_quality_switches_result = await db.execute(avg_quality_switches_stmt)
            avg_quality_switches = avg_quality_switches_result.scalar() or 0
            
            # Get performance events from analytics
            performance_events_stmt = select(func.count(AnalyticsEvent.id)).where(
                and_(
                    AnalyticsEvent.timestamp >= since,
                    AnalyticsEvent.event_type.like('video_performance_%')
                )
            )
            performance_events_result = await db.execute(performance_events_stmt)
            performance_events = performance_events_result.scalar() or 0
            
            # Calculate error rate (high buffering = poor performance)
            high_buffering_sessions_stmt = select(func.count(ViewSession.id)).where(
                and_(
                    ViewSession.started_at >= since,
                    ViewSession.buffering_events > 5  # More than 5 buffering events = poor performance
                )
            )
            high_buffering_result = await db.execute(high_buffering_sessions_stmt)
            high_buffering_sessions = high_buffering_result.scalar() or 0
            
            error_rate = (high_buffering_sessions / new_sessions * 100) if new_sessions > 0 else 0
            
            monitoring_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'active_streaming_sessions': active_sessions,
                'new_sessions_1h': new_sessions,
                'avg_buffering_events': avg_buffering,
                'avg_quality_switches': avg_quality_switches,
                'performance_events_1h': performance_events,
                'high_buffering_sessions': high_buffering_sessions,
                'streaming_error_rate_percent': error_rate
            }
            
            # Check for alerts
            alerts = []
            if active_sessions > self.alert_thresholds['concurrent_sessions']:
                alerts.append({
                    'type': 'high_concurrent_sessions',
                    'severity': 'medium',
                    'message': f'{active_sessions} concurrent streaming sessions (threshold: {self.alert_thresholds["concurrent_sessions"]})',
                    'value': active_sessions,
                    'threshold': self.alert_thresholds['concurrent_sessions']
                })
            
            if error_rate > self.alert_thresholds['streaming_error_rate']:
                alerts.append({
                    'type': 'streaming_error_rate',
                    'severity': 'high',
                    'message': f'Streaming error rate is {error_rate:.1f}% (threshold: {self.alert_thresholds["streaming_error_rate"]}%)',
                    'value': error_rate,
                    'threshold': self.alert_thresholds['streaming_error_rate']
                })
            
            if avg_buffering > 3:
                alerts.append({
                    'type': 'high_buffering_rate',
                    'severity': 'medium',
                    'message': f'Average buffering events per session: {avg_buffering:.1f}',
                    'value': avg_buffering,
                    'threshold': 3
                })
            
            monitoring_data['alerts'] = alerts
            
            return monitoring_data
    
    async def get_system_health_overview(self) -> Dict[str, Any]:
        """Get comprehensive system health overview"""
        # Run all monitoring checks
        transcoding_data = await self.monitor_transcoding_jobs()
        storage_data = await self.monitor_storage_usage()
        streaming_data = await self.monitor_streaming_performance()
        
        # Aggregate all alerts
        all_alerts = []
        all_alerts.extend(transcoding_data.get('alerts', []))
        all_alerts.extend(storage_data.get('alerts', []))
        all_alerts.extend(streaming_data.get('alerts', []))
        
        # Determine overall system health
        critical_alerts = [a for a in all_alerts if a['severity'] == 'critical']
        high_alerts = [a for a in all_alerts if a['severity'] == 'high']
        medium_alerts = [a for a in all_alerts if a['severity'] == 'medium']
        
        if critical_alerts:
            overall_status = 'critical'
        elif high_alerts:
            overall_status = 'degraded'
        elif medium_alerts:
            overall_status = 'warning'
        else:
            overall_status = 'healthy'
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': overall_status,
            'alerts_summary': {
                'critical': len(critical_alerts),
                'high': len(high_alerts),
                'medium': len(medium_alerts),
                'total': len(all_alerts)
            },
            'alerts': all_alerts,
            'components': {
                'transcoding': {
                    'status': 'critical' if any(a['severity'] == 'critical' for a in transcoding_data.get('alerts', [])) else 'healthy',
                    'metrics': transcoding_data
                },
                'storage': {
                    'status': 'critical' if any(a['severity'] == 'critical' for a in storage_data.get('alerts', [])) else 'healthy',
                    'metrics': storage_data
                },
                'streaming': {
                    'status': 'critical' if any(a['severity'] == 'critical' for a in streaming_data.get('alerts', [])) else 'healthy',
                    'metrics': streaming_data
                }
            }
        }
    
    async def send_alert_notification(self, alert: Dict[str, Any]) -> None:
        """Send alert notification (placeholder for actual notification system)"""
        # In a real implementation, this would send notifications via:
        # - Email
        # - Slack/Discord webhooks
        # - SMS
        # - Push notifications
        # - PagerDuty/OpsGenie
        
        logger.warning(f"SYSTEM ALERT [{alert['severity'].upper()}]: {alert['message']}")
        
        # Store alert in database for tracking
        async with self.get_db_session() as db:
            alert_event = AnalyticsEvent(
                event_type='system_alert',
                data={
                    'alert_type': alert['type'],
                    'severity': alert['severity'],
                    'message': alert['message'],
                    'value': alert.get('value'),
                    'threshold': alert.get('threshold')
                }
            )
            db.add(alert_event)
            await db.commit()
    
    async def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, Any]:
        """Clean up old monitoring data and analytics events"""
        async with self.get_db_session() as db:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Clean up old analytics events
            old_events_stmt = select(func.count(AnalyticsEvent.id)).where(
                AnalyticsEvent.timestamp < cutoff_date
            )
            old_events_result = await db.execute(old_events_stmt)
            old_events_count = old_events_result.scalar() or 0
            
            # Delete old events (in batches to avoid locking)
            batch_size = 1000
            deleted_events = 0
            
            while True:
                delete_stmt = select(AnalyticsEvent.id).where(
                    AnalyticsEvent.timestamp < cutoff_date
                ).limit(batch_size)
                delete_result = await db.execute(delete_stmt)
                event_ids = [row[0] for row in delete_result.fetchall()]
                
                if not event_ids:
                    break
                
                # Delete batch
                await db.execute(
                    AnalyticsEvent.__table__.delete().where(
                        AnalyticsEvent.id.in_(event_ids)
                    )
                )
                deleted_events += len(event_ids)
                await db.commit()
            
            # Clean up old system metrics
            old_metrics_stmt = select(func.count(SystemMetrics.id)).where(
                SystemMetrics.timestamp < cutoff_date
            )
            old_metrics_result = await db.execute(old_metrics_stmt)
            old_metrics_count = old_metrics_result.scalar() or 0
            
            # Delete old metrics
            await db.execute(
                SystemMetrics.__table__.delete().where(
                    SystemMetrics.timestamp < cutoff_date
                )
            )
            await db.commit()
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'days_to_keep': days_to_keep,
                'cutoff_date': cutoff_date.isoformat(),
                'deleted_events': deleted_events,
                'deleted_metrics': old_metrics_count,
                'total_deleted': deleted_events + old_metrics_count
            }
    
    async def get_monitoring_dashboard_data(self) -> Dict[str, Any]:
        """Get data for monitoring dashboard"""
        health_overview = await self.get_system_health_overview()
        
        # Add historical data for charts
        async with self.get_db_session() as db:
            # Get alert history for last 7 days
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            
            alert_history_stmt = select(
                func.date_trunc('day', AnalyticsEvent.timestamp).label('date'),
                func.count(AnalyticsEvent.id).label('alert_count')
            ).where(
                and_(
                    AnalyticsEvent.event_type == 'system_alert',
                    AnalyticsEvent.timestamp >= seven_days_ago
                )
            ).group_by(
                func.date_trunc('day', AnalyticsEvent.timestamp)
            ).order_by('date')
            
            alert_history_result = await db.execute(alert_history_stmt)
            alert_history = alert_history_result.all()
            
            health_overview['alert_history'] = [
                {
                    'date': row.date.strftime('%Y-%m-%d'),
                    'alert_count': row.alert_count
                }
                for row in alert_history
            ]
        
        return health_overview
    
    async def update_alert_thresholds(self, new_thresholds: Dict[str, float]) -> Dict[str, Any]:
        """Update alert thresholds"""
        # Validate thresholds
        valid_keys = set(self.alert_thresholds.keys())
        provided_keys = set(new_thresholds.keys())
        
        if not provided_keys.issubset(valid_keys):
            invalid_keys = provided_keys - valid_keys
            raise ValueError(f"Invalid threshold keys: {invalid_keys}")
        
        # Update thresholds
        self.alert_thresholds.update(new_thresholds)
        
        # Log the change
        logger.info(f"Alert thresholds updated: {new_thresholds}")
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'updated_thresholds': new_thresholds,
            'current_thresholds': self.alert_thresholds
        }