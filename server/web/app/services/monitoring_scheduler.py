"""
Monitoring Scheduler Service

Runs periodic monitoring checks and sends alerts when thresholds are exceeded.
This service should be run as a background task or separate process.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from .system_monitoring_service import SystemMonitoringService


logger = logging.getLogger(__name__)


class MonitoringScheduler:
    """Scheduler for periodic monitoring checks and alerting"""
    
    def __init__(self):
        self.monitoring_service = SystemMonitoringService()
        self.is_running = False
        self.tasks = []
        
        # Monitoring intervals (in seconds)
        self.intervals = {
            'health_check': 60,        # Every minute
            'transcoding_check': 300,  # Every 5 minutes
            'storage_check': 1800,     # Every 30 minutes
            'streaming_check': 180,    # Every 3 minutes
            'cleanup_check': 86400     # Every 24 hours
        }
        
        # Track last run times
        self.last_runs = {
            'health_check': datetime.min,
            'transcoding_check': datetime.min,
            'storage_check': datetime.min,
            'streaming_check': datetime.min,
            'cleanup_check': datetime.min
        }
        
        # Alert cooldown to prevent spam (in seconds)
        self.alert_cooldowns = {}
        self.cooldown_duration = 3600  # 1 hour
    
    async def start(self):
        """Start the monitoring scheduler"""
        if self.is_running:
            logger.warning("Monitoring scheduler is already running")
            return
        
        self.is_running = True
        logger.info("Starting monitoring scheduler")
        
        # Start monitoring tasks
        self.tasks = [
            asyncio.create_task(self._run_periodic_checks()),
            asyncio.create_task(self._run_health_monitor()),
            asyncio.create_task(self._run_alert_processor())
        ]
        
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("Monitoring scheduler tasks cancelled")
        except Exception as e:
            logger.error(f"Error in monitoring scheduler: {e}")
        finally:
            self.is_running = False
    
    async def stop(self):
        """Stop the monitoring scheduler"""
        if not self.is_running:
            return
        
        logger.info("Stopping monitoring scheduler")
        self.is_running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
    
    async def _run_periodic_checks(self):
        """Run periodic monitoring checks"""
        while self.is_running:
            try:
                current_time = datetime.utcnow()
                
                # Check if it's time to run each monitoring check
                for check_name, interval in self.intervals.items():
                    last_run = self.last_runs[check_name]
                    if (current_time - last_run).total_seconds() >= interval:
                        await self._run_monitoring_check(check_name)
                        self.last_runs[check_name] = current_time
                
                # Sleep for a short interval before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in periodic checks: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _run_monitoring_check(self, check_name: str):
        """Run a specific monitoring check"""
        try:
            logger.debug(f"Running monitoring check: {check_name}")
            
            if check_name == 'health_check':
                await self._check_system_health()
            elif check_name == 'transcoding_check':
                await self._check_transcoding_jobs()
            elif check_name == 'storage_check':
                await self._check_storage_usage()
            elif check_name == 'streaming_check':
                await self._check_streaming_performance()
            elif check_name == 'cleanup_check':
                await self._run_cleanup()
            
        except Exception as e:
            logger.error(f"Error in monitoring check {check_name}: {e}")
    
    async def _check_system_health(self):
        """Check overall system health"""
        try:
            health_data = await self.monitoring_service.get_system_health_overview()
            
            # Send alerts for any critical or high severity issues
            for alert in health_data.get('alerts', []):
                if alert['severity'] in ['critical', 'high']:
                    await self._send_alert_if_not_in_cooldown(alert)
            
            # Log system status
            status = health_data['overall_status']
            if status != 'healthy':
                logger.warning(f"System health status: {status}")
            
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
    
    async def _check_transcoding_jobs(self):
        """Check transcoding job status"""
        try:
            transcoding_data = await self.monitoring_service.monitor_transcoding_jobs()
            
            # Send alerts for transcoding issues
            for alert in transcoding_data.get('alerts', []):
                await self._send_alert_if_not_in_cooldown(alert)
            
            # Log transcoding metrics
            failure_rate = transcoding_data.get('failure_rate_percent', 0)
            queued_jobs = transcoding_data.get('queued_jobs', 0)
            
            if failure_rate > 5:
                logger.warning(f"High transcoding failure rate: {failure_rate}%")
            
            if queued_jobs > 20:
                logger.warning(f"High number of queued transcoding jobs: {queued_jobs}")
            
        except Exception as e:
            logger.error(f"Error checking transcoding jobs: {e}")
    
    async def _check_storage_usage(self):
        """Check storage usage"""
        try:
            storage_data = await self.monitoring_service.monitor_storage_usage()
            
            # Send alerts for storage issues
            for alert in storage_data.get('alerts', []):
                await self._send_alert_if_not_in_cooldown(alert)
            
            # Log storage metrics
            usage_percent = storage_data.get('usage_percentage', 0)
            if usage_percent > 70:
                logger.info(f"Storage usage: {usage_percent:.1f}%")
            
        except Exception as e:
            logger.error(f"Error checking storage usage: {e}")
    
    async def _check_streaming_performance(self):
        """Check streaming performance"""
        try:
            streaming_data = await self.monitoring_service.monitor_streaming_performance()
            
            # Send alerts for streaming issues
            for alert in streaming_data.get('alerts', []):
                await self._send_alert_if_not_in_cooldown(alert)
            
            # Log streaming metrics
            active_sessions = streaming_data.get('active_streaming_sessions', 0)
            error_rate = streaming_data.get('streaming_error_rate_percent', 0)
            
            if active_sessions > 100:
                logger.info(f"High number of active streaming sessions: {active_sessions}")
            
            if error_rate > 2:
                logger.warning(f"High streaming error rate: {error_rate}%")
            
        except Exception as e:
            logger.error(f"Error checking streaming performance: {e}")
    
    async def _run_cleanup(self):
        """Run data cleanup"""
        try:
            logger.info("Running scheduled data cleanup")
            cleanup_result = await self.monitoring_service.cleanup_old_data(days_to_keep=90)
            
            deleted_count = cleanup_result.get('total_deleted', 0)
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old records")
            
        except Exception as e:
            logger.error(f"Error running cleanup: {e}")
    
    async def _send_alert_if_not_in_cooldown(self, alert: Dict[str, Any]):
        """Send alert if not in cooldown period"""
        alert_key = f"{alert['type']}_{alert['severity']}"
        current_time = datetime.utcnow()
        
        # Check if alert is in cooldown
        if alert_key in self.alert_cooldowns:
            last_sent = self.alert_cooldowns[alert_key]
            if (current_time - last_sent).total_seconds() < self.cooldown_duration:
                logger.debug(f"Alert {alert_key} is in cooldown, skipping")
                return
        
        # Send alert
        try:
            await self.monitoring_service.send_alert_notification(alert)
            self.alert_cooldowns[alert_key] = current_time
            logger.info(f"Sent alert: {alert['type']} - {alert['message']}")
        except Exception as e:
            logger.error(f"Error sending alert {alert_key}: {e}")
    
    async def _run_health_monitor(self):
        """Continuously monitor critical system health"""
        while self.is_running:
            try:
                # Quick health check for critical issues
                # This runs more frequently than the main health check
                
                # Check for stuck transcoding jobs
                await self._check_stuck_transcoding_jobs()
                
                # Check for system resource issues
                await self._check_system_resources()
                
                await asyncio.sleep(120)  # Check every 2 minutes
                
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(300)  # Wait longer on error
    
    async def _check_stuck_transcoding_jobs(self):
        """Check for transcoding jobs that may be stuck"""
        try:
            # This would check for jobs that have been processing for too long
            # and send alerts or attempt recovery
            pass
        except Exception as e:
            logger.error(f"Error checking stuck transcoding jobs: {e}")
    
    async def _check_system_resources(self):
        """Check system resource usage"""
        try:
            # This would check CPU, memory, disk usage
            # and send alerts if thresholds are exceeded
            pass
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
    
    async def _run_alert_processor(self):
        """Process and manage alerts"""
        while self.is_running:
            try:
                # Clean up old alert cooldowns
                current_time = datetime.utcnow()
                expired_cooldowns = []
                
                for alert_key, last_sent in self.alert_cooldowns.items():
                    if (current_time - last_sent).total_seconds() > self.cooldown_duration * 2:
                        expired_cooldowns.append(alert_key)
                
                for alert_key in expired_cooldowns:
                    del self.alert_cooldowns[alert_key]
                
                await asyncio.sleep(3600)  # Clean up every hour
                
            except Exception as e:
                logger.error(f"Error in alert processor: {e}")
                await asyncio.sleep(1800)  # Wait longer on error
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        return {
            'is_running': self.is_running,
            'last_runs': {k: v.isoformat() if v != datetime.min else None for k, v in self.last_runs.items()},
            'active_tasks': len(self.tasks),
            'alert_cooldowns': len(self.alert_cooldowns),
            'intervals': self.intervals
        }


# Global scheduler instance
monitoring_scheduler = MonitoringScheduler()


async def start_monitoring_scheduler():
    """Start the global monitoring scheduler"""
    await monitoring_scheduler.start()


async def stop_monitoring_scheduler():
    """Stop the global monitoring scheduler"""
    await monitoring_scheduler.stop()


def get_monitoring_scheduler_status():
    """Get the status of the global monitoring scheduler"""
    return monitoring_scheduler.get_status()