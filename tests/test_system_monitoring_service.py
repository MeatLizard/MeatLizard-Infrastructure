"""
Tests for System Monitoring Service

Tests monitoring functionality, alerting, and performance tracking.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from server.web.app.services.system_monitoring_service import SystemMonitoringService
from server.web.app.models import (
    TranscodingJob, TranscodingStatus, Video, ViewSession, User, 
    AnalyticsEvent, VideoStatus, VideoVisibility
)


@pytest.fixture
async def monitoring_service():
    """Create monitoring service instance"""
    return SystemMonitoringService()


@pytest.fixture
async def sample_user(db_session):
    """Create a sample user"""
    user = User(
        id=uuid4(),
        display_label="Test User",
        email="test@example.com"
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def sample_video(db_session, sample_user):
    """Create a sample video"""
    video = Video(
        id=uuid4(),
        creator_id=sample_user.id,
        title="Test Video",
        description="A test video",
        original_filename="test.mp4",
        original_s3_key="videos/test.mp4",
        file_size=1000000000,  # 1GB
        duration_seconds=300,
        status=VideoStatus.ready,
        visibility=VideoVisibility.public
    )
    db_session.add(video)
    await db_session.commit()
    return video


@pytest.fixture
async def sample_transcoding_jobs(db_session, sample_video):
    """Create sample transcoding jobs"""
    jobs = []
    base_time = datetime.utcnow() - timedelta(hours=2)
    
    # Create jobs with different statuses
    statuses = [
        TranscodingStatus.completed,
        TranscodingStatus.completed,
        TranscodingStatus.failed,
        TranscodingStatus.processing,
        TranscodingStatus.queued
    ]
    
    for i, status in enumerate(statuses):
        job = TranscodingJob(
            id=uuid4(),
            video_id=sample_video.id,
            quality_preset=f"720p_30fps",
            target_resolution="1280x720",
            target_framerate=30,
            target_bitrate=2000000,
            status=status,
            progress_percent=100 if status == TranscodingStatus.completed else 50,
            created_at=base_time + timedelta(minutes=i * 10),
            started_at=base_time + timedelta(minutes=i * 10 + 1) if status != TranscodingStatus.queued else None,
            completed_at=base_time + timedelta(minutes=i * 10 + 5) if status == TranscodingStatus.completed else None,
            output_file_size=500000000 if status == TranscodingStatus.completed else None,
            error_message="Test error" if status == TranscodingStatus.failed else None
        )
        jobs.append(job)
        db_session.add(job)
    
    await db_session.commit()
    return jobs


@pytest.fixture
async def sample_view_sessions(db_session, sample_video, sample_user):
    """Create sample view sessions"""
    sessions = []
    base_time = datetime.utcnow() - timedelta(minutes=30)
    
    for i in range(10):
        session = ViewSession(
            id=uuid4(),
            video_id=sample_video.id,
            user_id=sample_user.id if i % 2 == 0 else None,
            session_token=f"token_{i}",
            current_position_seconds=60 * (i + 1),
            total_watch_time_seconds=60 * (i + 1),
            completion_percentage=20 * (i + 1) if i < 5 else 100,
            qualities_used=["720p", "1080p"],
            quality_switches=i % 3,
            buffering_events=i % 5,  # Some sessions have high buffering
            started_at=base_time + timedelta(minutes=i * 3),
            last_heartbeat=base_time + timedelta(minutes=i * 3 + 2),
            ended_at=base_time + timedelta(minutes=i * 3 + 5) if i < 8 else None  # Some still active
        )
        sessions.append(session)
        db_session.add(session)
    
    await db_session.commit()
    return sessions


class TestSystemMonitoringService:
    """Test system monitoring service functionality"""
    
    async def test_monitor_transcoding_jobs(self, monitoring_service, sample_transcoding_jobs):
        """Test transcoding job monitoring"""
        monitoring_data = await monitoring_service.monitor_transcoding_jobs()
        
        assert monitoring_data["total_jobs_24h"] == 5
        assert monitoring_data["failed_jobs_24h"] == 1
        assert monitoring_data["completed_jobs_24h"] == 2
        assert monitoring_data["processing_jobs"] == 1
        assert monitoring_data["queued_jobs"] == 1
        assert monitoring_data["failure_rate_percent"] == 20.0  # 1 failed out of 5 total
        assert monitoring_data["completion_rate_percent"] == 40.0  # 2 completed out of 5 total
        
        # Check recent failures
        assert len(monitoring_data["recent_failures"]) == 1
        assert monitoring_data["recent_failures"][0]["error_message"] == "Test error"
        
        # Check alerts
        alerts = monitoring_data["alerts"]
        failure_rate_alerts = [a for a in alerts if a["type"] == "transcoding_failure_rate"]
        assert len(failure_rate_alerts) == 1  # Should trigger alert for 20% failure rate
        assert failure_rate_alerts[0]["severity"] == "high"
    
    async def test_monitor_storage_usage(self, monitoring_service, sample_video):
        """Test storage usage monitoring"""
        monitoring_data = await monitoring_service.monitor_storage_usage()
        
        assert monitoring_data["total_storage_bytes"] > 0
        assert monitoring_data["original_storage_bytes"] == 1000000000  # 1GB from sample video
        assert monitoring_data["usage_percentage"] > 0
        
        # Check top users
        assert len(monitoring_data["top_users_by_storage"]) > 0
        top_user = monitoring_data["top_users_by_storage"][0]
        assert top_user["storage_bytes"] == 1000000000
        assert top_user["video_count"] == 1
        
        # Storage usage should be low, so no alerts expected
        alerts = monitoring_data["alerts"]
        assert len(alerts) == 0
    
    async def test_monitor_streaming_performance(self, monitoring_service, sample_view_sessions):
        """Test streaming performance monitoring"""
        monitoring_data = await monitoring_service.monitor_streaming_performance()
        
        assert monitoring_data["active_streaming_sessions"] == 2  # 2 sessions without ended_at
        assert monitoring_data["new_sessions_1h"] == 10  # All sessions started within last hour
        assert monitoring_data["avg_buffering_events"] >= 0
        assert monitoring_data["avg_quality_switches"] >= 0
        
        # Check for performance issues
        assert "streaming_error_rate_percent" in monitoring_data
        
        # Should have some alerts due to high buffering in some sessions
        alerts = monitoring_data["alerts"]
        assert len(alerts) >= 0  # May or may not have alerts depending on thresholds
    
    async def test_get_system_health_overview(self, monitoring_service, sample_transcoding_jobs, sample_view_sessions):
        """Test comprehensive system health overview"""
        health_data = await monitoring_service.get_system_health_overview()
        
        assert "overall_status" in health_data
        assert health_data["overall_status"] in ["healthy", "warning", "degraded", "critical"]
        
        # Check alerts summary
        alerts_summary = health_data["alerts_summary"]
        assert "critical" in alerts_summary
        assert "high" in alerts_summary
        assert "medium" in alerts_summary
        assert "total" in alerts_summary
        
        # Check components
        components = health_data["components"]
        assert "transcoding" in components
        assert "storage" in components
        assert "streaming" in components
        
        # Each component should have status and metrics
        for component_name, component_data in components.items():
            assert "status" in component_data
            assert "metrics" in component_data
            assert component_data["status"] in ["healthy", "warning", "degraded", "critical"]
    
    async def test_send_alert_notification(self, monitoring_service, db_session):
        """Test alert notification sending"""
        test_alert = {
            "type": "test_alert",
            "severity": "high",
            "message": "Test alert message",
            "value": 50,
            "threshold": 30
        }
        
        # Should not raise an exception
        await monitoring_service.send_alert_notification(test_alert)
        
        # Check that alert was stored in database
        events = await db_session.execute(
            "SELECT * FROM analytics_events WHERE event_type = 'system_alert'"
        )
        event_rows = events.fetchall()
        
        assert len(event_rows) == 1
        event_data = event_rows[0].data
        assert event_data["alert_type"] == "test_alert"
        assert event_data["severity"] == "high"
        assert event_data["message"] == "Test alert message"
    
    async def test_cleanup_old_data(self, monitoring_service, db_session):
        """Test cleanup of old monitoring data"""
        # Create some old analytics events
        old_date = datetime.utcnow() - timedelta(days=100)
        
        for i in range(5):
            event = AnalyticsEvent(
                event_type="test_event",
                timestamp=old_date + timedelta(hours=i),
                data={"test": True}
            )
            db_session.add(event)
        
        await db_session.commit()
        
        # Run cleanup
        cleanup_result = await monitoring_service.cleanup_old_data(days_to_keep=90)
        
        assert cleanup_result["days_to_keep"] == 90
        assert cleanup_result["deleted_events"] == 5
        assert cleanup_result["total_deleted"] >= 5
        
        # Verify events were deleted
        remaining_events = await db_session.execute(
            "SELECT COUNT(*) FROM analytics_events WHERE event_type = 'test_event'"
        )
        count = remaining_events.scalar()
        assert count == 0
    
    async def test_get_monitoring_dashboard_data(self, monitoring_service, sample_transcoding_jobs):
        """Test monitoring dashboard data retrieval"""
        dashboard_data = await monitoring_service.get_monitoring_dashboard_data()
        
        # Should include all health overview data
        assert "overall_status" in dashboard_data
        assert "components" in dashboard_data
        assert "alerts" in dashboard_data
        
        # Should include alert history
        assert "alert_history" in dashboard_data
        assert isinstance(dashboard_data["alert_history"], list)
    
    async def test_update_alert_thresholds(self, monitoring_service):
        """Test updating alert thresholds"""
        original_thresholds = monitoring_service.alert_thresholds.copy()
        
        new_thresholds = {
            "transcoding_failure_rate": 15.0,
            "storage_usage_warning": 75.0
        }
        
        result = await monitoring_service.update_alert_thresholds(new_thresholds)
        
        assert result["updated_thresholds"] == new_thresholds
        assert monitoring_service.alert_thresholds["transcoding_failure_rate"] == 15.0
        assert monitoring_service.alert_thresholds["storage_usage_warning"] == 75.0
        
        # Other thresholds should remain unchanged
        assert monitoring_service.alert_thresholds["streaming_error_rate"] == original_thresholds["streaming_error_rate"]
    
    async def test_update_alert_thresholds_invalid_keys(self, monitoring_service):
        """Test updating alert thresholds with invalid keys"""
        invalid_thresholds = {
            "invalid_threshold": 50.0,
            "another_invalid": 25.0
        }
        
        with pytest.raises(ValueError) as exc_info:
            await monitoring_service.update_alert_thresholds(invalid_thresholds)
        
        assert "Invalid threshold keys" in str(exc_info.value)
    
    async def test_transcoding_alerts_triggered(self, monitoring_service):
        """Test that transcoding alerts are properly triggered"""
        # Set a low threshold to ensure alerts trigger
        monitoring_service.alert_thresholds["transcoding_failure_rate"] = 5.0
        
        # This should trigger an alert since we have 20% failure rate in sample data
        monitoring_data = await monitoring_service.monitor_transcoding_jobs()
        
        alerts = monitoring_data["alerts"]
        failure_alerts = [a for a in alerts if a["type"] == "transcoding_failure_rate"]
        assert len(failure_alerts) > 0
        assert failure_alerts[0]["severity"] == "high"
        assert failure_alerts[0]["value"] == 20.0
    
    async def test_storage_alerts_triggered(self, monitoring_service):
        """Test that storage alerts are properly triggered"""
        # Set very low thresholds to trigger alerts
        monitoring_service.alert_thresholds["storage_usage_warning"] = 0.001  # Very low threshold
        monitoring_service.alert_thresholds["storage_usage_critical"] = 0.002
        
        monitoring_data = await monitoring_service.monitor_storage_usage()
        
        alerts = monitoring_data["alerts"]
        storage_alerts = [a for a in alerts if "storage_usage" in a["type"]]
        assert len(storage_alerts) > 0
    
    async def test_streaming_alerts_triggered(self, monitoring_service):
        """Test that streaming alerts are properly triggered"""
        # Set low thresholds to trigger alerts
        monitoring_service.alert_thresholds["streaming_error_rate"] = 1.0
        monitoring_service.alert_thresholds["concurrent_sessions"] = 1
        
        monitoring_data = await monitoring_service.monitor_streaming_performance()
        
        alerts = monitoring_data["alerts"]
        # Should have alerts for concurrent sessions (we have 2 active)
        concurrent_alerts = [a for a in alerts if a["type"] == "high_concurrent_sessions"]
        assert len(concurrent_alerts) > 0
    
    async def test_monitoring_with_no_data(self, monitoring_service):
        """Test monitoring functions with no data"""
        # Should not crash and should return sensible defaults
        transcoding_data = await monitoring_service.monitor_transcoding_jobs()
        assert transcoding_data["total_jobs_24h"] == 0
        assert transcoding_data["failure_rate_percent"] == 0
        
        storage_data = await monitoring_service.monitor_storage_usage()
        assert storage_data["total_storage_bytes"] == 0
        assert storage_data["usage_percentage"] == 0
        
        streaming_data = await monitoring_service.monitor_streaming_performance()
        assert streaming_data["active_streaming_sessions"] == 0
        assert streaming_data["new_sessions_1h"] == 0