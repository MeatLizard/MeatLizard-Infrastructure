"""
Tests for Streaming Performance Service

Tests streaming performance monitoring, bandwidth optimization,
and CDN integration functionality.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from server.web.app.services.streaming_performance_service import (
    StreamingPerformanceService,
    BandwidthMeasurement,
    QualityRecommendation,
    StreamingAlert,
    PerformanceLevel
)
from server.web.app.services.cdn_service import CDNService, CDNConfig, CDNProvider


@pytest.fixture
def mock_db_session():
    """Mock database session for testing"""
    return AsyncMock()


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    redis_client = AsyncMock()
    redis_client.is_connected = True
    return redis_client


@pytest.fixture
def performance_service(mock_db_session, mock_redis_client):
    """Streaming performance service instance for testing"""
    service = StreamingPerformanceService(mock_db_session, mock_redis_client)
    return service


@pytest.fixture
def cdn_service():
    """CDN service instance for testing"""
    config = CDNConfig(
        provider=CDNProvider.GENERIC,
        distribution_domain="test-cdn.example.com",
        origin_domain="origin.example.com",
        cache_behaviors={}
    )
    return CDNService(config)


@pytest.fixture
def sample_bandwidth_data():
    """Sample bandwidth measurement data"""
    return {
        'bandwidth_kbps': 2500.0,
        'quality': '720p_30fps',
        'buffer_seconds': 8.5,
        'dropped_frames': 0
    }


class TestStreamingPerformanceService:
    """Test cases for StreamingPerformanceService"""
    
    @pytest.mark.asyncio
    async def test_record_bandwidth_measurement(self, performance_service, mock_redis_client, sample_bandwidth_data):
        """Test recording bandwidth measurement"""
        # Setup
        session_token = 'test-session-123'
        video_id = 'test-video-456'
        mock_redis_client.set.return_value = True
        
        # Execute
        result = await performance_service.record_bandwidth_measurement(
            session_token,
            video_id,
            sample_bandwidth_data
        )
        
        # Verify
        assert result is True
        mock_redis_client.set.assert_called_once()
        
        # Check that measurement was added to in-memory cache
        assert len(performance_service._bandwidth_measurements) == 1
        measurement = performance_service._bandwidth_measurements[0]
        assert measurement.session_token == session_token
        assert measurement.video_id == video_id
        assert measurement.measured_kbps == 2500.0
        assert measurement.quality_used == '720p_30fps'
    
    @pytest.mark.asyncio
    async def test_bandwidth_measurement_creates_alert_for_low_buffer(self, performance_service, mock_redis_client):
        """Test that low buffer creates performance alert"""
        # Setup
        session_token = 'test-session-123'
        video_id = 'test-video-456'
        low_buffer_data = {
            'bandwidth_kbps': 2500.0,
            'quality': '720p_30fps',
            'buffer_seconds': 1.5,  # Below critical threshold
            'dropped_frames': 0
        }
        mock_redis_client.set.return_value = True
        
        # Execute
        await performance_service.record_bandwidth_measurement(
            session_token,
            video_id,
            low_buffer_data
        )
        
        # Verify alert was created
        assert len(performance_service._performance_alerts) == 1
        alert = performance_service._performance_alerts[0]
        assert alert.alert_type == 'buffer_underrun'
        assert alert.severity == 'critical'
        assert alert.session_token == session_token
    
    @pytest.mark.asyncio
    async def test_bandwidth_measurement_creates_alert_for_dropped_frames(self, performance_service, mock_redis_client):
        """Test that dropped frames create performance alert"""
        # Setup
        session_token = 'test-session-123'
        video_id = 'test-video-456'
        dropped_frames_data = {
            'bandwidth_kbps': 2500.0,
            'quality': '720p_30fps',
            'buffer_seconds': 8.0,
            'dropped_frames': 20  # Above critical threshold
        }
        mock_redis_client.set.return_value = True
        
        # Execute
        await performance_service.record_bandwidth_measurement(
            session_token,
            video_id,
            dropped_frames_data
        )
        
        # Verify alert was created
        assert len(performance_service._performance_alerts) == 1
        alert = performance_service._performance_alerts[0]
        assert alert.alert_type == 'dropped_frames'
        assert alert.severity == 'critical'
        assert alert.metrics['dropped_frames'] == 20
    
    @pytest.mark.asyncio
    async def test_get_quality_recommendation_step_down(self, performance_service):
        """Test quality recommendation stepping down due to poor performance"""
        # Setup - add measurements showing poor performance
        session_token = 'test-session-123'
        video_id = 'test-video-456'
        current_quality = '1080p_30fps'
        
        # Add measurements with low bandwidth and buffer issues
        for i in range(3):
            measurement = BandwidthMeasurement(
                timestamp=datetime.utcnow() - timedelta(seconds=30-i*10),
                session_token=session_token,
                video_id=video_id,
                measured_kbps=3000.0,  # Low for 1080p
                quality_used=current_quality,
                buffer_health=3.0,  # Low buffer
                dropped_frames=5
            )
            performance_service._bandwidth_measurements.append(measurement)
        
        # Execute
        recommendation = await performance_service.get_quality_recommendation(
            session_token,
            video_id,
            current_quality
        )
        
        # Verify
        assert recommendation.recommended_quality != current_quality
        assert recommendation.confidence > 0.8
        assert "stepping down" in recommendation.reason.lower()
        assert recommendation.estimated_bitrate < performance_service.quality_bitrates[current_quality]
    
    @pytest.mark.asyncio
    async def test_get_quality_recommendation_step_up(self, performance_service):
        """Test quality recommendation stepping up due to good performance"""
        # Setup - add measurements showing good performance
        session_token = 'test-session-123'
        video_id = 'test-video-456'
        current_quality = '720p_30fps'
        
        # Add measurements with high bandwidth and good buffer
        for i in range(3):
            measurement = BandwidthMeasurement(
                timestamp=datetime.utcnow() - timedelta(seconds=30-i*10),
                session_token=session_token,
                video_id=video_id,
                measured_kbps=8000.0,  # High bandwidth
                quality_used=current_quality,
                buffer_health=15.0,  # Good buffer
                dropped_frames=0
            )
            performance_service._bandwidth_measurements.append(measurement)
        
        # Execute
        recommendation = await performance_service.get_quality_recommendation(
            session_token,
            video_id,
            current_quality
        )
        
        # Verify
        assert recommendation.recommended_quality != current_quality
        assert recommendation.confidence > 0.8
        assert "stepping up" in recommendation.reason.lower()
        assert recommendation.estimated_bitrate > performance_service.quality_bitrates[current_quality]
    
    @pytest.mark.asyncio
    async def test_get_quality_recommendation_maintain(self, performance_service):
        """Test quality recommendation maintaining current quality"""
        # Setup - add measurements showing stable performance
        session_token = 'test-session-123'
        video_id = 'test-video-456'
        current_quality = '720p_30fps'
        
        # Add measurements with adequate performance
        for i in range(3):
            measurement = BandwidthMeasurement(
                timestamp=datetime.utcnow() - timedelta(seconds=30-i*10),
                session_token=session_token,
                video_id=video_id,
                measured_kbps=3500.0,  # Adequate for 720p
                quality_used=current_quality,
                buffer_health=8.0,  # Good buffer
                dropped_frames=0
            )
            performance_service._bandwidth_measurements.append(measurement)
        
        # Execute
        recommendation = await performance_service.get_quality_recommendation(
            session_token,
            video_id,
            current_quality
        )
        
        # Verify
        assert recommendation.recommended_quality == current_quality
        assert "maintaining" in recommendation.reason.lower()
    
    @pytest.mark.asyncio
    async def test_get_session_performance_summary(self, performance_service):
        """Test getting session performance summary"""
        # Setup
        session_token = 'test-session-123'
        video_id = 'test-video-456'
        
        # Add various measurements
        measurements = [
            BandwidthMeasurement(
                timestamp=datetime.utcnow() - timedelta(minutes=5),
                session_token=session_token,
                video_id=video_id,
                measured_kbps=2500.0,
                quality_used='720p_30fps',
                buffer_health=8.0,
                dropped_frames=0
            ),
            BandwidthMeasurement(
                timestamp=datetime.utcnow() - timedelta(minutes=3),
                session_token=session_token,
                video_id=video_id,
                measured_kbps=2800.0,
                quality_used='720p_30fps',
                buffer_health=6.0,
                dropped_frames=2
            ),
            BandwidthMeasurement(
                timestamp=datetime.utcnow() - timedelta(minutes=1),
                session_token=session_token,
                video_id=video_id,
                measured_kbps=3200.0,
                quality_used='1080p_30fps',
                buffer_health=10.0,
                dropped_frames=0
            )
        ]
        
        performance_service._bandwidth_measurements.extend(measurements)
        
        # Execute
        summary = await performance_service.get_session_performance_summary(
            session_token,
            video_id
        )
        
        # Verify
        assert summary['session_token'] == session_token
        assert summary['video_id'] == video_id
        assert summary['measurements_count'] == 3
        assert summary['bandwidth']['average_kbps'] == 2833.3  # (2500+2800+3200)/3
        assert summary['buffer']['min_seconds'] == 6.0
        assert summary['quality']['switches'] == 1  # 720p -> 1080p
        assert summary['issues']['dropped_frames'] == 2
        assert summary['performance_level'] in [level.value for level in PerformanceLevel]
    
    @pytest.mark.asyncio
    async def test_get_video_performance_analytics(self, performance_service):
        """Test getting video performance analytics"""
        # Setup
        video_id = 'test-video-456'
        
        # Add measurements for multiple sessions
        sessions = ['session-1', 'session-2', 'session-3']
        for session in sessions:
            for i in range(2):
                measurement = BandwidthMeasurement(
                    timestamp=datetime.utcnow() - timedelta(minutes=i*5),
                    session_token=session,
                    video_id=video_id,
                    measured_kbps=2500.0 + i*500,
                    quality_used='720p_30fps',
                    buffer_health=8.0 - i,
                    dropped_frames=i
                )
                performance_service._bandwidth_measurements.append(measurement)
        
        # Execute
        analytics = await performance_service.get_video_performance_analytics(
            video_id,
            hours=24
        )
        
        # Verify
        assert analytics['video_id'] == video_id
        assert analytics['total_sessions'] == 3
        assert analytics['total_measurements'] == 6
        assert 'bandwidth_stats' in analytics
        assert 'buffer_stats' in analytics
        assert 'quality_issues' in analytics
        assert 'performance_distribution' in analytics
        assert 'recommendations' in analytics
    
    def test_calculate_performance_level(self, performance_service):
        """Test performance level calculation"""
        # Test excellent performance
        level = performance_service._calculate_performance_level(
            avg_bandwidth=5000.0,
            min_buffer=10.0,
            dropped_frames=0,
            quality_switches=1
        )
        assert level == PerformanceLevel.EXCELLENT
        
        # Test poor performance
        level = performance_service._calculate_performance_level(
            avg_bandwidth=1000.0,
            min_buffer=1.0,  # Critical buffer
            dropped_frames=20,  # High drops
            quality_switches=5  # Too many switches
        )
        assert level == PerformanceLevel.POOR
    
    def test_calculate_bandwidth_stability(self, performance_service):
        """Test bandwidth stability calculation"""
        # Test stable bandwidth
        stable_bandwidths = [2500.0, 2520.0, 2480.0, 2510.0, 2490.0]
        stability = performance_service._calculate_bandwidth_stability(stable_bandwidths)
        assert stability in ['excellent', 'good']
        
        # Test unstable bandwidth
        unstable_bandwidths = [2500.0, 1500.0, 3500.0, 1000.0, 4000.0]
        stability = performance_service._calculate_bandwidth_stability(unstable_bandwidths)
        assert stability in ['fair', 'poor']
    
    @pytest.mark.asyncio
    async def test_get_performance_alerts_filtering(self, performance_service):
        """Test performance alerts filtering"""
        # Setup - add alerts
        alerts = [
            StreamingAlert(
                timestamp=datetime.utcnow() - timedelta(minutes=10),
                video_id='video-1',
                session_token='session-1',
                alert_type='buffer_low',
                severity='warning',
                message='Buffer running low',
                metrics={'buffer_seconds': 4.0}
            ),
            StreamingAlert(
                timestamp=datetime.utcnow() - timedelta(minutes=5),
                video_id='video-2',
                session_token='session-2',
                alert_type='dropped_frames',
                severity='critical',
                message='High frame drops',
                metrics={'dropped_frames': 20}
            )
        ]
        performance_service._performance_alerts.extend(alerts)
        
        # Test filtering by video_id
        video_alerts = await performance_service.get_performance_alerts(
            video_id='video-1',
            hours=1
        )
        assert len(video_alerts) == 1
        assert video_alerts[0]['video_id'] == 'video-1'
        
        # Test filtering by severity
        critical_alerts = await performance_service.get_performance_alerts(
            severity='critical',
            hours=1
        )
        assert len(critical_alerts) == 1
        assert critical_alerts[0]['severity'] == 'critical'


class TestCDNService:
    """Test cases for CDNService"""
    
    def test_get_cdn_url(self, cdn_service):
        """Test CDN URL generation"""
        s3_key = 'transcoded/video123/720p/playlist.m3u8'
        cdn_url = cdn_service.get_cdn_url(s3_key)
        
        assert cdn_url == 'https://test-cdn.example.com/transcoded/video123/720p/playlist.m3u8'
    
    def test_generate_signed_cdn_url(self, cdn_service):
        """Test signed CDN URL generation"""
        s3_key = 'transcoded/video123/720p/playlist.m3u8'
        signed_url = cdn_service.generate_signed_cdn_url(s3_key, expires_in=3600)
        
        assert 'test-cdn.example.com' in signed_url
        assert 'Expires=' in signed_url
        assert 'Signature=' in signed_url
    
    @pytest.mark.asyncio
    async def test_get_hls_manifest_url(self, cdn_service):
        """Test HLS manifest URL generation"""
        video_id = 'test-video-123'
        quality = '720p_30fps'
        
        manifest_url = await cdn_service.get_hls_manifest_url(
            video_id,
            quality=quality,
            user_id='user123',
            ip_address='192.168.1.1'
        )
        
        assert video_id in manifest_url
        assert quality in manifest_url
        assert 'playlist.m3u8' in manifest_url
    
    @pytest.mark.asyncio
    async def test_get_hls_segment_url(self, cdn_service):
        """Test HLS segment URL generation"""
        video_id = 'test-video-123'
        quality = '720p_30fps'
        segment_name = 'segment_001.ts'
        
        segment_url = await cdn_service.get_hls_segment_url(
            video_id,
            quality,
            segment_name,
            user_id='user123'
        )
        
        assert video_id in segment_url
        assert quality in segment_url
        assert segment_name in segment_url
    
    @pytest.mark.asyncio
    async def test_get_thumbnail_url(self, cdn_service):
        """Test thumbnail URL generation"""
        video_id = 'test-video-123'
        timestamp = '50'
        
        thumbnail_url = await cdn_service.get_thumbnail_url(video_id, timestamp)
        
        assert video_id in thumbnail_url
        assert timestamp in thumbnail_url
        assert 'thumb_' in thumbnail_url
        assert '.jpg' in thumbnail_url
    
    @pytest.mark.asyncio
    async def test_invalidate_cache(self, cdn_service, mock_redis_client):
        """Test CDN cache invalidation"""
        cdn_service.redis = mock_redis_client
        mock_redis_client.set.return_value = True
        
        paths = ['/video/123/*', '/thumbnails/123/*']
        result = await cdn_service.invalidate_cache(paths)
        
        assert result is True
        mock_redis_client.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_invalidate_video_cache(self, cdn_service, mock_redis_client):
        """Test video-specific cache invalidation"""
        cdn_service.redis = mock_redis_client
        mock_redis_client.set.return_value = True
        
        video_id = 'test-video-123'
        result = await cdn_service.invalidate_video_cache(video_id)
        
        assert result is True
        mock_redis_client.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_record_streaming_metrics(self, cdn_service, mock_redis_client):
        """Test recording streaming metrics"""
        cdn_service.redis = mock_redis_client
        mock_redis_client.set.return_value = True
        
        video_id = 'test-video-123'
        metrics = {
            'edge_location': 'us-east-1',
            'cache_hit_ratio': 0.85,
            'bandwidth_mbps': 10.5,
            'latency_ms': 15.0,
            'error_rate': 0.001,
            'concurrent_viewers': 50
        }
        
        result = await cdn_service.record_streaming_metrics(video_id, metrics)
        
        assert result is True
        mock_redis_client.set.assert_called_once()
        assert len(cdn_service._metrics_cache) == 1
    
    @pytest.mark.asyncio
    async def test_get_streaming_analytics(self, cdn_service):
        """Test getting streaming analytics"""
        # Add some metrics to the cache
        from server.web.app.services.cdn_service import StreamingMetrics
        
        metrics = [
            StreamingMetrics(
                timestamp=datetime.utcnow() - timedelta(minutes=30),
                video_id='video-123',
                edge_location='us-east-1',
                cache_hit_ratio=0.85,
                bandwidth_mbps=10.5,
                latency_ms=15.0,
                error_rate=0.001,
                concurrent_viewers=50
            ),
            StreamingMetrics(
                timestamp=datetime.utcnow() - timedelta(minutes=15),
                video_id='video-123',
                edge_location='us-west-1',
                cache_hit_ratio=0.82,
                bandwidth_mbps=8.2,
                latency_ms=18.0,
                error_rate=0.002,
                concurrent_viewers=35
            )
        ]
        
        cdn_service._metrics_cache.extend(metrics)
        
        # Execute
        analytics = await cdn_service.get_streaming_analytics(video_id='video-123', hours=1)
        
        # Verify
        assert analytics['total_metrics'] == 2
        assert analytics['average_cache_hit_ratio'] == 0.835  # (0.85 + 0.82) / 2
        assert analytics['peak_concurrent_viewers'] == 50
        assert 'edge_locations' in analytics
    
    @pytest.mark.asyncio
    async def test_optimize_cache_settings(self, cdn_service):
        """Test cache optimization recommendations"""
        # Add some metrics with poor performance
        from server.web.app.services.cdn_service import StreamingMetrics
        
        poor_metrics = [
            StreamingMetrics(
                timestamp=datetime.utcnow() - timedelta(minutes=30),
                video_id='video-123',
                edge_location='us-east-1',
                cache_hit_ratio=0.60,  # Low hit ratio
                bandwidth_mbps=10.5,
                latency_ms=150.0,  # High latency
                error_rate=0.02,  # High error rate
                concurrent_viewers=50
            )
        ]
        
        cdn_service._metrics_cache.extend(poor_metrics)
        
        # Execute
        recommendations = await cdn_service.optimize_cache_settings('video-123')
        
        # Verify
        assert 'recommendations' in recommendations
        assert len(recommendations['recommendations']) > 0
        assert recommendations['optimization_score'] < 70  # Poor performance
    
    def test_calculate_optimization_score(self, cdn_service):
        """Test optimization score calculation"""
        # Test good performance
        good_analytics = {
            'average_cache_hit_ratio': 0.9,
            'average_latency_ms': 25.0,
            'average_error_rate': 0.001
        }
        score = cdn_service._calculate_optimization_score(good_analytics)
        assert score > 80
        
        # Test poor performance
        poor_analytics = {
            'average_cache_hit_ratio': 0.5,
            'average_latency_ms': 200.0,
            'average_error_rate': 0.05
        }
        score = cdn_service._calculate_optimization_score(poor_analytics)
        assert score < 50


if __name__ == '__main__':
    pytest.main([__file__])