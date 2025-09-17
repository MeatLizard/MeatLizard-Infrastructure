"""
Streaming Performance Service

Monitors and optimizes video streaming performance including bandwidth detection,
quality adaptation, buffering analysis, and real-time performance metrics.
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import statistics

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from server.web.app.models import ViewSession, Video, TranscodingJob
from server.web.app.services.base_service import BaseService
from server.web.app.services.redis_client import RedisClient, get_redis_client

logger = logging.getLogger(__name__)


class PerformanceLevel(Enum):
    """Performance quality levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class BandwidthMeasurement:
    """Bandwidth measurement data"""
    timestamp: datetime
    session_token: str
    video_id: str
    measured_kbps: float
    quality_used: str
    buffer_health: float  # Seconds of buffer
    dropped_frames: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'session_token': self.session_token,
            'video_id': self.video_id,
            'measured_kbps': self.measured_kbps,
            'quality_used': self.quality_used,
            'buffer_health': self.buffer_health,
            'dropped_frames': self.dropped_frames
        }


@dataclass
class QualityRecommendation:
    """Quality recommendation based on performance"""
    recommended_quality: str
    confidence: float  # 0.0 to 1.0
    reason: str
    estimated_bitrate: float
    buffer_target: float
    adaptive_enabled: bool


@dataclass
class StreamingAlert:
    """Streaming performance alert"""
    timestamp: datetime
    video_id: str
    session_token: str
    alert_type: str
    severity: str
    message: str
    metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'video_id': self.video_id,
            'session_token': self.session_token,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'message': self.message,
            'metrics': self.metrics
        }


class StreamingPerformanceService(BaseService):
    """Service for monitoring and optimizing streaming performance"""
    
    def __init__(self, db: AsyncSession, redis_client: RedisClient = None):
        self.db = db
        self.redis = redis_client
        self._bandwidth_measurements: List[BandwidthMeasurement] = []
        self._performance_alerts: List[StreamingAlert] = []
        self._monitoring_active = False
        
        # Quality presets with estimated bitrates (kbps)
        self.quality_bitrates = {
            '480p_30fps': 1000,
            '720p_30fps': 2500,
            '720p_60fps': 3500,
            '1080p_30fps': 5000,
            '1080p_60fps': 7500,
            '1440p_30fps': 8000,
            '1440p_60fps': 12000,
            '2160p_30fps': 15000,
            '2160p_60fps': 25000
        }
        
        # Performance thresholds
        self.thresholds = {
            'buffer_warning': 5.0,      # Warn if buffer < 5 seconds
            'buffer_critical': 2.0,     # Critical if buffer < 2 seconds
            'dropped_frames_warning': 5, # Warn if > 5 dropped frames per minute
            'dropped_frames_critical': 15, # Critical if > 15 dropped frames per minute
            'bandwidth_variance': 0.3,   # 30% variance threshold
            'quality_switch_limit': 3    # Max quality switches per minute
        }
    
    async def _get_redis(self) -> RedisClient:
        """Get Redis client instance"""
        if self.redis is None:
            self.redis = await get_redis_client()
        return self.redis
    
    async def record_bandwidth_measurement(
        self, 
        session_token: str,
        video_id: str,
        measurement_data: Dict[str, Any]
    ) -> bool:
        """
        Record bandwidth measurement from client
        
        Args:
            session_token: Viewing session token
            video_id: Video identifier
            measurement_data: Bandwidth and performance data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            measurement = BandwidthMeasurement(
                timestamp=datetime.utcnow(),
                session_token=session_token,
                video_id=video_id,
                measured_kbps=measurement_data.get('bandwidth_kbps', 0.0),
                quality_used=measurement_data.get('quality', 'unknown'),
                buffer_health=measurement_data.get('buffer_seconds', 0.0),
                dropped_frames=measurement_data.get('dropped_frames', 0)
            )
            
            # Store in Redis for real-time access
            redis = await self._get_redis()
            measurement_key = f"bandwidth:{session_token}:{int(measurement.timestamp.timestamp())}"
            await redis.set(
                measurement_key,
                measurement.to_dict(),
                expire=3600  # Keep for 1 hour
            )
            
            # Add to in-memory cache
            self._bandwidth_measurements.append(measurement)
            
            # Keep only recent measurements in memory
            cutoff_time = datetime.utcnow() - timedelta(minutes=30)
            self._bandwidth_measurements = [
                m for m in self._bandwidth_measurements
                if m.timestamp > cutoff_time
            ]
            
            # Analyze performance and generate alerts if needed
            await self._analyze_performance(measurement)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record bandwidth measurement: {e}")
            return False
    
    async def _analyze_performance(self, measurement: BandwidthMeasurement):
        """Analyze performance measurement and generate alerts if needed"""
        try:
            # Check buffer health
            if measurement.buffer_health < self.thresholds['buffer_critical']:
                await self._create_alert(
                    measurement.video_id,
                    measurement.session_token,
                    'buffer_underrun',
                    'critical',
                    f'Buffer critically low: {measurement.buffer_health:.1f}s',
                    {'buffer_seconds': measurement.buffer_health}
                )
            elif measurement.buffer_health < self.thresholds['buffer_warning']:
                await self._create_alert(
                    measurement.video_id,
                    measurement.session_token,
                    'buffer_low',
                    'warning',
                    f'Buffer running low: {measurement.buffer_health:.1f}s',
                    {'buffer_seconds': measurement.buffer_health}
                )
            
            # Check dropped frames
            if measurement.dropped_frames > self.thresholds['dropped_frames_critical']:
                await self._create_alert(
                    measurement.video_id,
                    measurement.session_token,
                    'dropped_frames',
                    'critical',
                    f'High frame drops: {measurement.dropped_frames}',
                    {'dropped_frames': measurement.dropped_frames}
                )
            elif measurement.dropped_frames > self.thresholds['dropped_frames_warning']:
                await self._create_alert(
                    measurement.video_id,
                    measurement.session_token,
                    'dropped_frames',
                    'warning',
                    f'Frame drops detected: {measurement.dropped_frames}',
                    {'dropped_frames': measurement.dropped_frames}
                )
            
            # Check bandwidth stability
            recent_measurements = [
                m for m in self._bandwidth_measurements
                if (m.session_token == measurement.session_token and 
                    m.timestamp > datetime.utcnow() - timedelta(minutes=5))
            ]
            
            if len(recent_measurements) >= 3:
                bandwidths = [m.measured_kbps for m in recent_measurements]
                avg_bandwidth = statistics.mean(bandwidths)
                bandwidth_variance = statistics.stdev(bandwidths) / avg_bandwidth if avg_bandwidth > 0 else 0
                
                if bandwidth_variance > self.thresholds['bandwidth_variance']:
                    await self._create_alert(
                        measurement.video_id,
                        measurement.session_token,
                        'bandwidth_unstable',
                        'warning',
                        f'Unstable bandwidth: {bandwidth_variance:.1%} variance',
                        {
                            'bandwidth_variance': bandwidth_variance,
                            'average_kbps': avg_bandwidth,
                            'current_kbps': measurement.measured_kbps
                        }
                    )
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
    
    async def _create_alert(
        self,
        video_id: str,
        session_token: str,
        alert_type: str,
        severity: str,
        message: str,
        metrics: Dict[str, Any]
    ):
        """Create and store a performance alert"""
        try:
            alert = StreamingAlert(
                timestamp=datetime.utcnow(),
                video_id=video_id,
                session_token=session_token,
                alert_type=alert_type,
                severity=severity,
                message=message,
                metrics=metrics
            )
            
            # Store in Redis
            redis = await self._get_redis()
            alert_key = f"streaming:alert:{session_token}:{int(alert.timestamp.timestamp())}"
            await redis.set(
                alert_key,
                alert.to_dict(),
                expire=86400  # Keep for 24 hours
            )
            
            # Add to in-memory cache
            self._performance_alerts.append(alert)
            
            # Keep only recent alerts in memory
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            self._performance_alerts = [
                a for a in self._performance_alerts
                if a.timestamp > cutoff_time
            ]
            
            # Log the alert
            log_level = logging.CRITICAL if severity == 'critical' else logging.WARNING
            logger.log(log_level, f"Streaming Alert [{severity.upper()}]: {message}")
            
        except Exception as e:
            logger.error(f"Failed to create streaming alert: {e}")
    
    async def get_quality_recommendation(
        self,
        session_token: str,
        video_id: str,
        current_quality: str,
        target_buffer: float = 10.0
    ) -> QualityRecommendation:
        """
        Get quality recommendation based on recent performance
        
        Args:
            session_token: Viewing session token
            video_id: Video identifier
            current_quality: Current quality preset
            target_buffer: Target buffer size in seconds
            
        Returns:
            Quality recommendation
        """
        try:
            # Get recent measurements for this session
            recent_measurements = [
                m for m in self._bandwidth_measurements
                if (m.session_token == session_token and 
                    m.timestamp > datetime.utcnow() - timedelta(minutes=2))
            ]
            
            if not recent_measurements:
                # No recent data, maintain current quality
                return QualityRecommendation(
                    recommended_quality=current_quality,
                    confidence=0.5,
                    reason="No recent performance data available",
                    estimated_bitrate=self.quality_bitrates.get(current_quality, 2500),
                    buffer_target=target_buffer,
                    adaptive_enabled=True
                )
            
            # Calculate average bandwidth and buffer health
            avg_bandwidth = statistics.mean([m.measured_kbps for m in recent_measurements])
            avg_buffer = statistics.mean([m.buffer_health for m in recent_measurements])
            total_dropped_frames = sum([m.dropped_frames for m in recent_measurements])
            
            # Determine recommended quality
            recommended_quality = current_quality
            confidence = 0.8
            reason = "Maintaining current quality"
            
            # Check if we should step down
            current_bitrate = self.quality_bitrates.get(current_quality, 2500)
            if (avg_bandwidth < current_bitrate * 1.2 or  # Not enough bandwidth headroom
                avg_buffer < self.thresholds['buffer_warning'] or  # Buffer running low
                total_dropped_frames > self.thresholds['dropped_frames_warning']):
                
                # Find lower quality
                available_qualities = sorted(self.quality_bitrates.items(), key=lambda x: x[1])
                for quality, bitrate in available_qualities:
                    if bitrate < current_bitrate and avg_bandwidth > bitrate * 1.3:
                        recommended_quality = quality
                        confidence = 0.9
                        reason = f"Stepping down due to performance issues (bandwidth: {avg_bandwidth:.0f}kbps, buffer: {avg_buffer:.1f}s)"
                        break
            
            # Check if we can step up
            elif (avg_bandwidth > current_bitrate * 1.8 and  # Plenty of bandwidth
                  avg_buffer > target_buffer and  # Good buffer health
                  total_dropped_frames == 0):  # No dropped frames
                
                # Find higher quality
                available_qualities = sorted(self.quality_bitrates.items(), key=lambda x: x[1], reverse=True)
                for quality, bitrate in available_qualities:
                    if bitrate > current_bitrate and avg_bandwidth > bitrate * 1.5:
                        recommended_quality = quality
                        confidence = 0.85
                        reason = f"Stepping up due to good performance (bandwidth: {avg_bandwidth:.0f}kbps, buffer: {avg_buffer:.1f}s)"
                        break
            
            return QualityRecommendation(
                recommended_quality=recommended_quality,
                confidence=confidence,
                reason=reason,
                estimated_bitrate=self.quality_bitrates.get(recommended_quality, 2500),
                buffer_target=target_buffer,
                adaptive_enabled=True
            )
            
        except Exception as e:
            logger.error(f"Failed to get quality recommendation: {e}")
            return QualityRecommendation(
                recommended_quality=current_quality,
                confidence=0.0,
                reason=f"Error: {str(e)}",
                estimated_bitrate=self.quality_bitrates.get(current_quality, 2500),
                buffer_target=target_buffer,
                adaptive_enabled=False
            )
    
    async def get_session_performance_summary(
        self,
        session_token: str,
        video_id: str
    ) -> Dict[str, Any]:
        """
        Get performance summary for a viewing session
        
        Args:
            session_token: Viewing session token
            video_id: Video identifier
            
        Returns:
            Performance summary
        """
        try:
            # Get measurements for this session
            session_measurements = [
                m for m in self._bandwidth_measurements
                if m.session_token == session_token
            ]
            
            # Get alerts for this session
            session_alerts = [
                a for a in self._performance_alerts
                if a.session_token == session_token
            ]
            
            if not session_measurements:
                return {
                    'session_token': session_token,
                    'video_id': video_id,
                    'measurements_count': 0,
                    'performance_level': PerformanceLevel.POOR.value,
                    'summary': 'No performance data available'
                }
            
            # Calculate performance metrics
            bandwidths = [m.measured_kbps for m in session_measurements]
            buffer_healths = [m.buffer_health for m in session_measurements]
            total_dropped_frames = sum([m.dropped_frames for m in session_measurements])
            
            avg_bandwidth = statistics.mean(bandwidths)
            min_bandwidth = min(bandwidths)
            max_bandwidth = max(bandwidths)
            avg_buffer = statistics.mean(buffer_healths)
            min_buffer = min(buffer_healths)
            
            # Quality switches
            qualities_used = [m.quality_used for m in session_measurements]
            unique_qualities = len(set(qualities_used))
            quality_switches = unique_qualities - 1 if unique_qualities > 1 else 0
            
            # Determine performance level
            performance_level = self._calculate_performance_level(
                avg_bandwidth, min_buffer, total_dropped_frames, quality_switches
            )
            
            # Count alerts by severity
            alert_counts = {
                'critical': len([a for a in session_alerts if a.severity == 'critical']),
                'warning': len([a for a in session_alerts if a.severity == 'warning']),
                'info': len([a for a in session_alerts if a.severity == 'info'])
            }
            
            return {
                'session_token': session_token,
                'video_id': video_id,
                'measurements_count': len(session_measurements),
                'duration_minutes': (session_measurements[-1].timestamp - session_measurements[0].timestamp).total_seconds() / 60,
                'performance_level': performance_level.value,
                'bandwidth': {
                    'average_kbps': round(avg_bandwidth, 1),
                    'min_kbps': round(min_bandwidth, 1),
                    'max_kbps': round(max_bandwidth, 1),
                    'stability': self._calculate_bandwidth_stability(bandwidths)
                },
                'buffer': {
                    'average_seconds': round(avg_buffer, 1),
                    'min_seconds': round(min_buffer, 1),
                    'underruns': len([b for b in buffer_healths if b < self.thresholds['buffer_critical']])
                },
                'quality': {
                    'switches': quality_switches,
                    'qualities_used': list(set(qualities_used)),
                    'most_used': max(set(qualities_used), key=qualities_used.count) if qualities_used else 'unknown'
                },
                'issues': {
                    'dropped_frames': total_dropped_frames,
                    'alerts': alert_counts,
                    'total_alerts': sum(alert_counts.values())
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get session performance summary: {e}")
            return {
                'session_token': session_token,
                'video_id': video_id,
                'error': str(e)
            }
    
    def _calculate_performance_level(
        self,
        avg_bandwidth: float,
        min_buffer: float,
        dropped_frames: int,
        quality_switches: int
    ) -> PerformanceLevel:
        """Calculate overall performance level based on metrics"""
        score = 100
        
        # Penalize low buffer
        if min_buffer < self.thresholds['buffer_critical']:
            score -= 30
        elif min_buffer < self.thresholds['buffer_warning']:
            score -= 15
        
        # Penalize dropped frames
        if dropped_frames > self.thresholds['dropped_frames_critical']:
            score -= 25
        elif dropped_frames > self.thresholds['dropped_frames_warning']:
            score -= 10
        
        # Penalize excessive quality switches
        if quality_switches > self.thresholds['quality_switch_limit']:
            score -= 20
        elif quality_switches > self.thresholds['quality_switch_limit'] / 2:
            score -= 10
        
        # Determine level based on score
        if score >= 85:
            return PerformanceLevel.EXCELLENT
        elif score >= 70:
            return PerformanceLevel.GOOD
        elif score >= 50:
            return PerformanceLevel.FAIR
        else:
            return PerformanceLevel.POOR
    
    def _calculate_bandwidth_stability(self, bandwidths: List[float]) -> str:
        """Calculate bandwidth stability rating"""
        if len(bandwidths) < 2:
            return "unknown"
        
        try:
            avg_bandwidth = statistics.mean(bandwidths)
            variance = statistics.stdev(bandwidths) / avg_bandwidth if avg_bandwidth > 0 else 1
            
            if variance < 0.1:
                return "excellent"
            elif variance < 0.2:
                return "good"
            elif variance < 0.3:
                return "fair"
            else:
                return "poor"
                
        except Exception:
            return "unknown"
    
    async def get_video_performance_analytics(
        self,
        video_id: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get performance analytics for a specific video
        
        Args:
            video_id: Video identifier
            hours: Hours of data to analyze
            
        Returns:
            Performance analytics
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Get measurements for this video
            video_measurements = [
                m for m in self._bandwidth_measurements
                if m.video_id == video_id and m.timestamp > cutoff_time
            ]
            
            # Get alerts for this video
            video_alerts = [
                a for a in self._performance_alerts
                if a.video_id == video_id and a.timestamp > cutoff_time
            ]
            
            if not video_measurements:
                return {
                    'video_id': video_id,
                    'analysis_period_hours': hours,
                    'total_sessions': 0,
                    'performance_summary': 'No data available'
                }
            
            # Group by session
            sessions = {}
            for measurement in video_measurements:
                session_token = measurement.session_token
                if session_token not in sessions:
                    sessions[session_token] = []
                sessions[session_token].append(measurement)
            
            # Analyze each session
            session_summaries = []
            for session_token, measurements in sessions.items():
                bandwidths = [m.measured_kbps for m in measurements]
                buffer_healths = [m.buffer_health for m in measurements]
                dropped_frames = sum([m.dropped_frames for m in measurements])
                
                session_summaries.append({
                    'session_token': session_token,
                    'avg_bandwidth': statistics.mean(bandwidths),
                    'min_buffer': min(buffer_healths),
                    'dropped_frames': dropped_frames,
                    'duration_minutes': (measurements[-1].timestamp - measurements[0].timestamp).total_seconds() / 60
                })
            
            # Calculate overall metrics
            all_bandwidths = [m.measured_kbps for m in video_measurements]
            all_buffers = [m.buffer_health for m in video_measurements]
            total_dropped_frames = sum([m.dropped_frames for m in video_measurements])
            
            # Performance distribution
            performance_levels = []
            for summary in session_summaries:
                level = self._calculate_performance_level(
                    summary['avg_bandwidth'],
                    summary['min_buffer'],
                    summary['dropped_frames'],
                    0  # Quality switches not tracked per session here
                )
                performance_levels.append(level.value)
            
            performance_distribution = {
                level.value: performance_levels.count(level.value)
                for level in PerformanceLevel
            }
            
            # Alert analysis
            alert_counts = {
                'critical': len([a for a in video_alerts if a.severity == 'critical']),
                'warning': len([a for a in video_alerts if a.severity == 'warning']),
                'info': len([a for a in video_alerts if a.severity == 'info'])
            }
            
            return {
                'video_id': video_id,
                'analysis_period_hours': hours,
                'total_sessions': len(sessions),
                'total_measurements': len(video_measurements),
                'performance_distribution': performance_distribution,
                'bandwidth_stats': {
                    'average_kbps': round(statistics.mean(all_bandwidths), 1),
                    'median_kbps': round(statistics.median(all_bandwidths), 1),
                    'min_kbps': round(min(all_bandwidths), 1),
                    'max_kbps': round(max(all_bandwidths), 1),
                    'stability': self._calculate_bandwidth_stability(all_bandwidths)
                },
                'buffer_stats': {
                    'average_seconds': round(statistics.mean(all_buffers), 1),
                    'min_seconds': round(min(all_buffers), 1),
                    'underrun_rate': len([b for b in all_buffers if b < self.thresholds['buffer_critical']]) / len(all_buffers)
                },
                'quality_issues': {
                    'total_dropped_frames': total_dropped_frames,
                    'sessions_with_drops': len([s for s in session_summaries if s['dropped_frames'] > 0]),
                    'avg_drops_per_session': total_dropped_frames / len(sessions) if sessions else 0
                },
                'alerts': alert_counts,
                'recommendations': await self._get_video_recommendations(video_id, session_summaries, alert_counts)
            }
            
        except Exception as e:
            logger.error(f"Failed to get video performance analytics: {e}")
            return {
                'video_id': video_id,
                'error': str(e)
            }
    
    async def _get_video_recommendations(
        self,
        video_id: str,
        session_summaries: List[Dict[str, Any]],
        alert_counts: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on video performance analysis"""
        recommendations = []
        
        try:
            if not session_summaries:
                return recommendations
            
            # Analyze bandwidth patterns
            avg_bandwidths = [s['avg_bandwidth'] for s in session_summaries]
            overall_avg_bandwidth = statistics.mean(avg_bandwidths)
            
            # Check if many sessions have low bandwidth
            low_bandwidth_sessions = len([b for b in avg_bandwidths if b < 1500])  # < 1.5 Mbps
            if low_bandwidth_sessions > len(session_summaries) * 0.3:
                recommendations.append({
                    'type': 'encoding',
                    'priority': 'medium',
                    'title': 'Consider Lower Bitrate Encoding',
                    'description': f'{low_bandwidth_sessions}/{len(session_summaries)} sessions had low bandwidth',
                    'action': 'Add 360p quality preset or optimize existing presets for lower bandwidth'
                })
            
            # Check buffer underruns
            sessions_with_underruns = len([s for s in session_summaries if s['min_buffer'] < self.thresholds['buffer_critical']])
            if sessions_with_underruns > len(session_summaries) * 0.2:
                recommendations.append({
                    'type': 'delivery',
                    'priority': 'high',
                    'title': 'Frequent Buffer Underruns',
                    'description': f'{sessions_with_underruns}/{len(session_summaries)} sessions experienced buffer underruns',
                    'action': 'Optimize CDN configuration or reduce segment size'
                })
            
            # Check dropped frames
            sessions_with_drops = len([s for s in session_summaries if s['dropped_frames'] > 0])
            if sessions_with_drops > len(session_summaries) * 0.15:
                recommendations.append({
                    'type': 'quality',
                    'priority': 'medium',
                    'title': 'Frame Drops Detected',
                    'description': f'{sessions_with_drops}/{len(session_summaries)} sessions had dropped frames',
                    'action': 'Review encoding settings and consider adaptive bitrate improvements'
                })
            
            # Check alert frequency
            total_alerts = sum(alert_counts.values())
            if total_alerts > len(session_summaries) * 2:  # More than 2 alerts per session on average
                recommendations.append({
                    'type': 'monitoring',
                    'priority': 'high',
                    'title': 'High Alert Frequency',
                    'description': f'{total_alerts} alerts generated across {len(session_summaries)} sessions',
                    'action': 'Investigate root causes and optimize streaming infrastructure'
                })
            
        except Exception as e:
            logger.error(f"Error generating video recommendations: {e}")
        
        return recommendations
    
    async def get_performance_alerts(
        self,
        video_id: Optional[str] = None,
        session_token: Optional[str] = None,
        severity: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get performance alerts with optional filtering
        
        Args:
            video_id: Optional video filter
            session_token: Optional session filter
            severity: Optional severity filter
            hours: Hours of history to retrieve
            
        Returns:
            List of alerts
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            filtered_alerts = []
            for alert in self._performance_alerts:
                if alert.timestamp < cutoff_time:
                    continue
                if video_id and alert.video_id != video_id:
                    continue
                if session_token and alert.session_token != session_token:
                    continue
                if severity and alert.severity != severity:
                    continue
                
                filtered_alerts.append(alert.to_dict())
            
            # Sort by timestamp (newest first)
            filtered_alerts.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return filtered_alerts
            
        except Exception as e:
            logger.error(f"Failed to get performance alerts: {e}")
            return []


# Dependency for FastAPI
async def get_streaming_performance_service(db: AsyncSession) -> StreamingPerformanceService:
    """Get streaming performance service instance"""
    return StreamingPerformanceService(db)