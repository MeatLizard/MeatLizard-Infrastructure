"""
CDN Service

Provides CDN integration for global content delivery, edge caching,
bandwidth optimization, and streaming performance monitoring.
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import time

from server.web.app.config import settings
from server.web.app.services.base_service import BaseService
from server.web.app.services.redis_client import RedisClient, get_redis_client

logger = logging.getLogger(__name__)


class CDNProvider(Enum):
    """Supported CDN providers"""
    CLOUDFRONT = "cloudfront"
    CLOUDFLARE = "cloudflare"
    FASTLY = "fastly"
    GENERIC = "generic"


@dataclass
class CDNConfig:
    """CDN configuration settings"""
    provider: CDNProvider
    distribution_domain: str
    origin_domain: str
    cache_behaviors: Dict[str, Any]
    signed_urls_enabled: bool = True
    compression_enabled: bool = True
    http2_enabled: bool = True
    
    # Performance settings
    default_ttl: int = 86400  # 24 hours
    max_ttl: int = 31536000   # 1 year
    min_ttl: int = 0
    
    # Geographic settings
    price_class: str = "PriceClass_All"
    geo_restrictions: Optional[Dict[str, List[str]]] = None


@dataclass
class CachePolicy:
    """Cache policy for different content types"""
    path_pattern: str
    ttl_seconds: int
    cache_key_parameters: List[str]
    compress: bool = True
    forward_headers: List[str] = None
    
    def __post_init__(self):
        if self.forward_headers is None:
            self.forward_headers = []


@dataclass
class StreamingMetrics:
    """Streaming performance metrics"""
    timestamp: datetime
    video_id: str
    edge_location: str
    cache_hit_ratio: float
    bandwidth_mbps: float
    latency_ms: float
    error_rate: float
    concurrent_viewers: int


class CDNService(BaseService):
    """Service for CDN integration and streaming optimization"""
    
    def __init__(self, config: CDNConfig = None, redis_client: RedisClient = None):
        self.config = config or self._get_default_config()
        self.redis = redis_client
        self._metrics_cache: List[StreamingMetrics] = []
        
        # Define cache policies for different content types
        self.cache_policies = {
            'hls_manifests': CachePolicy(
                path_pattern="*.m3u8",
                ttl_seconds=30,  # Short TTL for manifests
                cache_key_parameters=['video_id', 'quality'],
                compress=True,
                forward_headers=['Range', 'If-Modified-Since']
            ),
            'hls_segments': CachePolicy(
                path_pattern="*.ts",
                ttl_seconds=86400,  # Long TTL for segments (immutable)
                cache_key_parameters=['video_id', 'quality', 'segment'],
                compress=False,  # Video segments are already compressed
                forward_headers=['Range']
            ),
            'thumbnails': CachePolicy(
                path_pattern="thumbnails/*",
                ttl_seconds=604800,  # 1 week TTL for thumbnails
                cache_key_parameters=['video_id', 'timestamp'],
                compress=True,
                forward_headers=['If-Modified-Since']
            ),
            'metadata': CachePolicy(
                path_pattern="api/video/*/metadata",
                ttl_seconds=300,  # 5 minutes TTL for metadata
                cache_key_parameters=['video_id'],
                compress=True,
                forward_headers=['Authorization']
            )
        }
    
    def _get_default_config(self) -> CDNConfig:
        """Get default CDN configuration"""
        return CDNConfig(
            provider=CDNProvider.GENERIC,
            distribution_domain="cdn.example.com",
            origin_domain="origin.example.com",
            cache_behaviors={
                "default": {
                    "ttl": 86400,
                    "compress": True,
                    "forward_query_string": True
                }
            }
        )
    
    async def _get_redis(self) -> RedisClient:
        """Get Redis client instance"""
        if self.redis is None:
            self.redis = await get_redis_client()
        return self.redis
    
    def get_cdn_url(self, s3_key: str, content_type: str = "hls_segments") -> str:
        """
        Generate CDN URL for S3 content
        
        Args:
            s3_key: S3 object key
            content_type: Type of content for cache policy selection
            
        Returns:
            CDN URL
        """
        # Remove leading slash if present
        s3_key = s3_key.lstrip('/')
        
        # Build CDN URL
        cdn_url = f"https://{self.config.distribution_domain}/{s3_key}"
        
        return cdn_url
    
    def generate_signed_cdn_url(
        self, 
        s3_key: str, 
        expires_in: int = 7200,
        ip_address: Optional[str] = None,
        content_type: str = "hls_segments"
    ) -> str:
        """
        Generate signed CDN URL with expiration and optional IP restriction
        
        Args:
            s3_key: S3 object key
            expires_in: URL expiration time in seconds
            ip_address: Optional IP address restriction
            content_type: Type of content for cache policy selection
            
        Returns:
            Signed CDN URL
        """
        if not self.config.signed_urls_enabled:
            return self.get_cdn_url(s3_key, content_type)
        
        base_url = self.get_cdn_url(s3_key, content_type)
        expires = int(time.time()) + expires_in
        
        # Create policy for CloudFront-style signed URLs
        policy = {
            "Statement": [{
                "Resource": base_url,
                "Condition": {
                    "DateLessThan": {
                        "AWS:EpochTime": expires
                    }
                }
            }]
        }
        
        # Add IP restriction if specified
        if ip_address:
            policy["Statement"][0]["Condition"]["IpAddress"] = {
                "AWS:SourceIp": f"{ip_address}/32"
            }
        
        # Generate signature (simplified - in production use proper CDN signing)
        policy_str = json.dumps(policy, separators=(',', ':'))
        signature = hmac.new(
            settings.SECRET_KEY.encode(),
            policy_str.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        
        # Add signature parameters
        separator = "&" if "?" in base_url else "?"
        signed_url = f"{base_url}{separator}Expires={expires}&Signature={signature}"
        
        return signed_url
    
    async def get_hls_manifest_url(
        self, 
        video_id: str, 
        quality: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        Get CDN URL for HLS manifest with caching optimization
        
        Args:
            video_id: Video identifier
            quality: Quality preset (None for master playlist)
            user_id: User identifier for access control
            ip_address: Client IP address
            
        Returns:
            CDN URL for HLS manifest
        """
        # Build S3 key for manifest
        if quality:
            s3_key = f"transcoded/{video_id}/{quality}/playlist.m3u8"
        else:
            s3_key = f"transcoded/{video_id}/master.m3u8"
        
        # Generate signed URL with short expiration for manifests
        signed_url = self.generate_signed_cdn_url(
            s3_key,
            expires_in=1800,  # 30 minutes for manifests
            ip_address=ip_address,
            content_type="hls_manifests"
        )
        
        return signed_url
    
    async def get_hls_segment_url(
        self, 
        video_id: str, 
        quality: str, 
        segment_name: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        Get CDN URL for HLS segment with long-term caching
        
        Args:
            video_id: Video identifier
            quality: Quality preset
            segment_name: Segment file name
            user_id: User identifier for access control
            ip_address: Client IP address
            
        Returns:
            CDN URL for HLS segment
        """
        # Build S3 key for segment
        s3_key = f"transcoded/{video_id}/{quality}/segments/{segment_name}"
        
        # Generate signed URL with long expiration for segments (immutable)
        signed_url = self.generate_signed_cdn_url(
            s3_key,
            expires_in=86400,  # 24 hours for segments
            ip_address=ip_address,
            content_type="hls_segments"
        )
        
        return signed_url
    
    async def get_thumbnail_url(
        self, 
        video_id: str, 
        timestamp: str,
        size: Optional[str] = None
    ) -> str:
        """
        Get CDN URL for video thumbnail
        
        Args:
            video_id: Video identifier
            timestamp: Thumbnail timestamp
            size: Optional size variant
            
        Returns:
            CDN URL for thumbnail
        """
        # Build S3 key for thumbnail
        if size:
            s3_key = f"thumbnails/{video_id}/thumb_{timestamp}_{size}.jpg"
        else:
            s3_key = f"thumbnails/{video_id}/thumb_{timestamp}.jpg"
        
        # Thumbnails can use longer expiration and no IP restriction
        signed_url = self.generate_signed_cdn_url(
            s3_key,
            expires_in=604800,  # 1 week for thumbnails
            content_type="thumbnails"
        )
        
        return signed_url
    
    async def invalidate_cache(self, paths: List[str]) -> bool:
        """
        Invalidate CDN cache for specified paths
        
        Args:
            paths: List of paths to invalidate
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # In a real implementation, this would call the CDN provider's API
            # For now, we'll simulate the operation and cache the invalidation request
            
            redis = await self._get_redis()
            
            invalidation_id = hashlib.md5(
                f"{time.time()}:{','.join(paths)}".encode()
            ).hexdigest()[:16]
            
            invalidation_data = {
                'id': invalidation_id,
                'paths': paths,
                'status': 'in_progress',
                'created_at': datetime.utcnow().isoformat(),
                'provider': self.config.provider.value
            }
            
            # Cache invalidation request
            await redis.set(
                f"cdn:invalidation:{invalidation_id}",
                invalidation_data,
                expire=3600
            )
            
            logger.info(f"CDN cache invalidation requested for {len(paths)} paths")
            
            # Simulate async processing
            asyncio.create_task(self._process_invalidation(invalidation_id, paths))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate CDN cache: {e}")
            return False
    
    async def _process_invalidation(self, invalidation_id: str, paths: List[str]):
        """Process CDN cache invalidation (simulated)"""
        try:
            # Simulate processing time
            await asyncio.sleep(30)
            
            redis = await self._get_redis()
            
            # Update invalidation status
            invalidation_data = await redis.get(f"cdn:invalidation:{invalidation_id}")
            if invalidation_data:
                invalidation_data['status'] = 'completed'
                invalidation_data['completed_at'] = datetime.utcnow().isoformat()
                
                await redis.set(
                    f"cdn:invalidation:{invalidation_id}",
                    invalidation_data,
                    expire=3600
                )
            
            logger.info(f"CDN cache invalidation {invalidation_id} completed")
            
        except Exception as e:
            logger.error(f"Failed to process CDN invalidation {invalidation_id}: {e}")
    
    async def invalidate_video_cache(self, video_id: str) -> bool:
        """
        Invalidate all CDN cache entries for a video
        
        Args:
            video_id: Video identifier
            
        Returns:
            True if successful, False otherwise
        """
        paths_to_invalidate = [
            f"transcoded/{video_id}/*",
            f"thumbnails/{video_id}/*",
            f"api/video/{video_id}/metadata"
        ]
        
        return await self.invalidate_cache(paths_to_invalidate)
    
    async def get_edge_locations(self) -> List[Dict[str, Any]]:
        """
        Get list of CDN edge locations and their status
        
        Returns:
            List of edge location information
        """
        # In a real implementation, this would query the CDN provider's API
        # For now, return simulated data
        
        edge_locations = [
            {
                'location': 'us-east-1',
                'city': 'Virginia',
                'country': 'US',
                'status': 'active',
                'cache_hit_ratio': 0.85,
                'bandwidth_gbps': 10.5,
                'latency_ms': 15
            },
            {
                'location': 'us-west-1',
                'city': 'California',
                'country': 'US',
                'status': 'active',
                'cache_hit_ratio': 0.82,
                'bandwidth_gbps': 8.2,
                'latency_ms': 18
            },
            {
                'location': 'eu-west-1',
                'city': 'Ireland',
                'country': 'IE',
                'status': 'active',
                'cache_hit_ratio': 0.78,
                'bandwidth_gbps': 6.8,
                'latency_ms': 22
            },
            {
                'location': 'ap-southeast-1',
                'city': 'Singapore',
                'country': 'SG',
                'status': 'active',
                'cache_hit_ratio': 0.75,
                'bandwidth_gbps': 5.5,
                'latency_ms': 28
            }
        ]
        
        return edge_locations
    
    async def record_streaming_metrics(
        self, 
        video_id: str, 
        metrics: Dict[str, Any]
    ) -> bool:
        """
        Record streaming performance metrics
        
        Args:
            video_id: Video identifier
            metrics: Performance metrics data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            redis = await self._get_redis()
            
            # Create metrics record
            streaming_metrics = StreamingMetrics(
                timestamp=datetime.utcnow(),
                video_id=video_id,
                edge_location=metrics.get('edge_location', 'unknown'),
                cache_hit_ratio=metrics.get('cache_hit_ratio', 0.0),
                bandwidth_mbps=metrics.get('bandwidth_mbps', 0.0),
                latency_ms=metrics.get('latency_ms', 0.0),
                error_rate=metrics.get('error_rate', 0.0),
                concurrent_viewers=metrics.get('concurrent_viewers', 0)
            )
            
            # Store in Redis with TTL
            metrics_key = f"streaming:metrics:{video_id}:{int(time.time())}"
            await redis.set(
                metrics_key,
                {
                    'timestamp': streaming_metrics.timestamp.isoformat(),
                    'video_id': streaming_metrics.video_id,
                    'edge_location': streaming_metrics.edge_location,
                    'cache_hit_ratio': streaming_metrics.cache_hit_ratio,
                    'bandwidth_mbps': streaming_metrics.bandwidth_mbps,
                    'latency_ms': streaming_metrics.latency_ms,
                    'error_rate': streaming_metrics.error_rate,
                    'concurrent_viewers': streaming_metrics.concurrent_viewers
                },
                expire=86400  # Keep for 24 hours
            )
            
            # Add to in-memory cache for quick access
            self._metrics_cache.append(streaming_metrics)
            
            # Keep only recent metrics in memory
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            self._metrics_cache = [
                m for m in self._metrics_cache 
                if m.timestamp > cutoff_time
            ]
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record streaming metrics: {e}")
            return False
    
    async def get_streaming_analytics(
        self, 
        video_id: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get streaming performance analytics
        
        Args:
            video_id: Optional video identifier filter
            hours: Hours of data to retrieve
            
        Returns:
            Analytics data
        """
        try:
            redis = await self._get_redis()
            
            # Get metrics from Redis
            cutoff_timestamp = int((datetime.utcnow() - timedelta(hours=hours)).timestamp())
            
            # Build pattern for metrics keys
            if video_id:
                pattern = f"streaming:metrics:{video_id}:*"
            else:
                pattern = "streaming:metrics:*"
            
            # In a real implementation, you'd use SCAN to get keys
            # For now, we'll use the in-memory cache and simulate
            
            relevant_metrics = []
            for metric in self._metrics_cache:
                if metric.timestamp > datetime.utcnow() - timedelta(hours=hours):
                    if not video_id or metric.video_id == video_id:
                        relevant_metrics.append(metric)
            
            if not relevant_metrics:
                return {
                    'total_metrics': 0,
                    'average_cache_hit_ratio': 0.0,
                    'average_bandwidth_mbps': 0.0,
                    'average_latency_ms': 0.0,
                    'average_error_rate': 0.0,
                    'peak_concurrent_viewers': 0,
                    'edge_locations': []
                }
            
            # Calculate aggregated metrics
            total_metrics = len(relevant_metrics)
            avg_cache_hit_ratio = sum(m.cache_hit_ratio for m in relevant_metrics) / total_metrics
            avg_bandwidth = sum(m.bandwidth_mbps for m in relevant_metrics) / total_metrics
            avg_latency = sum(m.latency_ms for m in relevant_metrics) / total_metrics
            avg_error_rate = sum(m.error_rate for m in relevant_metrics) / total_metrics
            peak_viewers = max(m.concurrent_viewers for m in relevant_metrics)
            
            # Group by edge location
            edge_stats = {}
            for metric in relevant_metrics:
                location = metric.edge_location
                if location not in edge_stats:
                    edge_stats[location] = {
                        'metrics_count': 0,
                        'cache_hit_ratio': 0.0,
                        'bandwidth_mbps': 0.0,
                        'latency_ms': 0.0,
                        'error_rate': 0.0
                    }
                
                edge_stats[location]['metrics_count'] += 1
                edge_stats[location]['cache_hit_ratio'] += metric.cache_hit_ratio
                edge_stats[location]['bandwidth_mbps'] += metric.bandwidth_mbps
                edge_stats[location]['latency_ms'] += metric.latency_ms
                edge_stats[location]['error_rate'] += metric.error_rate
            
            # Calculate averages for each edge location
            for location, stats in edge_stats.items():
                count = stats['metrics_count']
                stats['cache_hit_ratio'] /= count
                stats['bandwidth_mbps'] /= count
                stats['latency_ms'] /= count
                stats['error_rate'] /= count
            
            return {
                'total_metrics': total_metrics,
                'time_range_hours': hours,
                'average_cache_hit_ratio': round(avg_cache_hit_ratio, 3),
                'average_bandwidth_mbps': round(avg_bandwidth, 2),
                'average_latency_ms': round(avg_latency, 1),
                'average_error_rate': round(avg_error_rate, 4),
                'peak_concurrent_viewers': peak_viewers,
                'edge_locations': edge_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get streaming analytics: {e}")
            return {'error': str(e)}
    
    async def optimize_cache_settings(self, video_id: str) -> Dict[str, Any]:
        """
        Analyze performance and suggest cache optimization settings
        
        Args:
            video_id: Video identifier
            
        Returns:
            Optimization recommendations
        """
        try:
            # Get recent analytics for the video
            analytics = await self.get_streaming_analytics(video_id, hours=24)
            
            recommendations = []
            
            # Analyze cache hit ratio
            cache_hit_ratio = analytics.get('average_cache_hit_ratio', 0.0)
            if cache_hit_ratio < 0.7:
                recommendations.append({
                    'type': 'cache_policy',
                    'priority': 'high',
                    'title': 'Low Cache Hit Ratio',
                    'description': f'Cache hit ratio is {cache_hit_ratio:.1%}. Consider increasing TTL for segments.',
                    'suggested_action': 'Increase segment cache TTL to 7 days',
                    'current_ttl': self.cache_policies['hls_segments'].ttl_seconds,
                    'suggested_ttl': 604800
                })
            
            # Analyze latency
            avg_latency = analytics.get('average_latency_ms', 0.0)
            if avg_latency > 100:
                recommendations.append({
                    'type': 'performance',
                    'priority': 'medium',
                    'title': 'High Latency',
                    'description': f'Average latency is {avg_latency:.1f}ms. Consider edge optimization.',
                    'suggested_action': 'Enable additional edge locations or optimize routing',
                    'current_latency_ms': avg_latency,
                    'target_latency_ms': 50
                })
            
            # Analyze error rate
            error_rate = analytics.get('average_error_rate', 0.0)
            if error_rate > 0.01:  # 1%
                recommendations.append({
                    'type': 'reliability',
                    'priority': 'high',
                    'title': 'High Error Rate',
                    'description': f'Error rate is {error_rate:.2%}. Check origin server health.',
                    'suggested_action': 'Investigate origin server performance and implement retry logic',
                    'current_error_rate': error_rate,
                    'target_error_rate': 0.005
                })
            
            # Analyze bandwidth usage
            bandwidth = analytics.get('average_bandwidth_mbps', 0.0)
            peak_viewers = analytics.get('peak_concurrent_viewers', 0)
            
            if peak_viewers > 100 and bandwidth > 50:
                recommendations.append({
                    'type': 'capacity',
                    'priority': 'medium',
                    'title': 'High Bandwidth Usage',
                    'description': f'Peak bandwidth usage is {bandwidth:.1f} Mbps with {peak_viewers} viewers.',
                    'suggested_action': 'Consider implementing adaptive bitrate optimization',
                    'current_bandwidth_mbps': bandwidth,
                    'peak_viewers': peak_viewers
                })
            
            return {
                'video_id': video_id,
                'analysis_period_hours': 24,
                'current_performance': {
                    'cache_hit_ratio': cache_hit_ratio,
                    'average_latency_ms': avg_latency,
                    'error_rate': error_rate,
                    'bandwidth_mbps': bandwidth
                },
                'recommendations': recommendations,
                'optimization_score': self._calculate_optimization_score(analytics)
            }
            
        except Exception as e:
            logger.error(f"Failed to optimize cache settings for video {video_id}: {e}")
            return {'error': str(e)}
    
    def _calculate_optimization_score(self, analytics: Dict[str, Any]) -> float:
        """Calculate optimization score based on performance metrics"""
        try:
            cache_hit_ratio = analytics.get('average_cache_hit_ratio', 0.0)
            latency = analytics.get('average_latency_ms', 100.0)
            error_rate = analytics.get('average_error_rate', 0.01)
            
            # Score components (0-100 each)
            cache_score = min(cache_hit_ratio * 100, 100)
            latency_score = max(0, 100 - (latency - 20) * 2)  # Penalty after 20ms
            error_score = max(0, 100 - error_rate * 10000)  # Heavy penalty for errors
            
            # Weighted average
            total_score = (cache_score * 0.4 + latency_score * 0.4 + error_score * 0.2)
            
            return round(total_score, 1)
            
        except Exception:
            return 0.0
    
    async def get_cdn_status(self) -> Dict[str, Any]:
        """
        Get overall CDN status and health
        
        Returns:
            CDN status information
        """
        try:
            edge_locations = await self.get_edge_locations()
            analytics = await self.get_streaming_analytics(hours=1)
            
            # Calculate overall health
            active_edges = len([loc for loc in edge_locations if loc['status'] == 'active'])
            total_edges = len(edge_locations)
            
            avg_cache_hit_ratio = sum(loc['cache_hit_ratio'] for loc in edge_locations) / total_edges
            avg_latency = sum(loc['latency_ms'] for loc in edge_locations) / total_edges
            
            # Determine overall status
            if active_edges == total_edges and avg_cache_hit_ratio > 0.8 and avg_latency < 50:
                overall_status = "healthy"
            elif active_edges >= total_edges * 0.8 and avg_cache_hit_ratio > 0.6:
                overall_status = "degraded"
            else:
                overall_status = "unhealthy"
            
            return {
                'overall_status': overall_status,
                'provider': self.config.provider.value,
                'distribution_domain': self.config.distribution_domain,
                'edge_locations': {
                    'total': total_edges,
                    'active': active_edges,
                    'inactive': total_edges - active_edges
                },
                'performance': {
                    'average_cache_hit_ratio': round(avg_cache_hit_ratio, 3),
                    'average_latency_ms': round(avg_latency, 1),
                    'compression_enabled': self.config.compression_enabled,
                    'http2_enabled': self.config.http2_enabled
                },
                'recent_metrics': analytics,
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get CDN status: {e}")
            return {
                'overall_status': 'error',
                'error': str(e),
                'last_updated': datetime.utcnow().isoformat()
            }


# Dependency for FastAPI
async def get_cdn_service() -> CDNService:
    """Get CDN service instance"""
    return CDNService()