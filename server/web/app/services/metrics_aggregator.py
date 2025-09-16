"""
Metrics aggregation system for processing and summarizing analytics data.
Provides comprehensive metrics calculation and reporting capabilities.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc, text
from collections import defaultdict

from ..models import (
    User, UserTier, UserUsageStats, AuditLog, ShortUrl, Paste, MediaFile,
    UserStorageUsage, RateLimit
)
from .analytics_collector import EventType
from .tier_manager import TierManager

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics."""
    COUNT = "count"
    SUM = "sum"
    AVERAGE = "average"
    PERCENTAGE = "percentage"
    RATE = "rate"
    DISTRIBUTION = "distribution"


class TimeGranularity(str, Enum):
    """Time granularity for metrics."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


@dataclass
class MetricResult:
    """Result of a metric calculation."""
    metric_name: str
    metric_type: MetricType
    value: Any
    timestamp: datetime
    granularity: TimeGranularity
    filters: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = {}
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MetricSeries:
    """Time series of metric values."""
    metric_name: str
    metric_type: MetricType
    granularity: TimeGranularity
    data_points: List[Tuple[datetime, Any]]
    filters: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = {}
        if self.metadata is None:
            self.metadata = {}


class MetricsAggregator:
    """
    Aggregates and processes analytics data into meaningful metrics.
    Provides various metric calculations and reporting capabilities.
    """
    
    def __init__(self, db: Session, tier_manager: Optional[TierManager] = None):
        """
        Initialize metrics aggregator.
        
        Args:
            db: Database session
            tier_manager: TierManager instance for tier-related metrics
        """
        self.db = db
        self.tier_manager = tier_manager or TierManager(db)
    
    def calculate_user_metrics(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive metrics for a specific user.
        
        Args:
            user_id: User ID to calculate metrics for
            start_date: Start date for metrics calculation
            end_date: End date for metrics calculation
            
        Returns:
            Dictionary containing user metrics
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        try:
            metrics = {}
            
            # Basic user info
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"error": "User not found"}
            
            user_tier = self.tier_manager.get_user_tier(user_id)
            metrics["user_tier"] = user_tier.value
            metrics["account_age_days"] = (datetime.utcnow() - user.created_at).days
            
            # Resource creation metrics
            metrics["resources"] = {
                "short_urls": self._count_user_resources(user_id, ShortUrl, start_date, end_date),
                "pastes": self._count_user_resources(user_id, Paste, start_date, end_date),
                "media_files": self._count_user_resources(user_id, MediaFile, start_date, end_date)
            }
            
            # Storage usage
            storage_usage = self.db.query(UserStorageUsage).filter(
                UserStorageUsage.user_id == user_id
            ).first()
            
            if storage_usage:
                metrics["storage"] = {
                    "used_bytes": storage_usage.used_bytes,
                    "quota_bytes": storage_usage.quota_bytes,
                    "usage_percentage": (storage_usage.used_bytes / storage_usage.quota_bytes * 100) 
                                     if storage_usage.quota_bytes > 0 else 0
                }
            else:
                metrics["storage"] = {"used_bytes": 0, "quota_bytes": 0, "usage_percentage": 0}
            
            # Activity metrics from analytics events
            metrics["activity"] = self._calculate_user_activity_metrics(user_id, start_date, end_date)
            
            # Usage statistics
            metrics["usage_stats"] = self._get_user_usage_stats(user_id, start_date, end_date)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating user metrics for {user_id}: {e}")
            return {"error": str(e)}
    
    def calculate_system_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate system-wide metrics.
        
        Args:
            start_date: Start date for metrics calculation
            end_date: End date for metrics calculation
            
        Returns:
            Dictionary containing system metrics
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=7)
        if not end_date:
            end_date = datetime.utcnow()
        
        try:
            metrics = {}
            
            # User metrics
            metrics["users"] = self._calculate_user_system_metrics(start_date, end_date)
            
            # Resource metrics
            metrics["resources"] = self._calculate_resource_system_metrics(start_date, end_date)
            
            # Performance metrics
            metrics["performance"] = self._calculate_performance_metrics(start_date, end_date)
            
            # Tier distribution
            metrics["tier_distribution"] = self._calculate_tier_distribution()
            
            # Growth metrics
            metrics["growth"] = self._calculate_growth_metrics(start_date, end_date)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating system metrics: {e}")
            return {"error": str(e)}
    
    def calculate_tier_metrics(
        self,
        tier: UserTier,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate metrics for a specific user tier.
        
        Args:
            tier: User tier to calculate metrics for
            start_date: Start date for metrics calculation
            end_date: End date for metrics calculation
            
        Returns:
            Dictionary containing tier metrics
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        try:
            # Get users in this tier
            tier_users = self._get_users_by_tier(tier)
            user_ids = [str(user.id) for user in tier_users]
            
            if not user_ids:
                return {"tier": tier.value, "user_count": 0}
            
            metrics = {
                "tier": tier.value,
                "user_count": len(user_ids),
                "resources": {},
                "activity": {},
                "usage_patterns": {}
            }
            
            # Resource usage by tier
            for resource_type, model in [("short_urls", ShortUrl), ("pastes", Paste), ("media_files", MediaFile)]:
                total_count = self.db.query(func.count(model.id)).filter(
                    and_(
                        model.user_id.in_(user_ids),
                        model.created_at >= start_date,
                        model.created_at <= end_date
                    )
                ).scalar() or 0
                
                avg_per_user = total_count / len(user_ids) if user_ids else 0
                
                metrics["resources"][resource_type] = {
                    "total": total_count,
                    "average_per_user": round(avg_per_user, 2)
                }
            
            # Activity metrics
            metrics["activity"] = self._calculate_tier_activity_metrics(user_ids, start_date, end_date)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating tier metrics for {tier}: {e}")
            return {"error": str(e)}
    
    def generate_time_series(
        self,
        metric_name: str,
        granularity: TimeGranularity,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> MetricSeries:
        """
        Generate time series data for a specific metric.
        
        Args:
            metric_name: Name of the metric to generate series for
            granularity: Time granularity for the series
            start_date: Start date for the series
            end_date: End date for the series
            filters: Optional filters to apply
            
        Returns:
            MetricSeries with time series data
        """
        try:
            data_points = []
            
            # Generate time intervals
            intervals = self._generate_time_intervals(start_date, end_date, granularity)
            
            for interval_start, interval_end in intervals:
                value = self._calculate_metric_for_interval(
                    metric_name, interval_start, interval_end, filters
                )
                data_points.append((interval_start, value))
            
            return MetricSeries(
                metric_name=metric_name,
                metric_type=MetricType.COUNT,  # Default, could be determined dynamically
                granularity=granularity,
                data_points=data_points,
                filters=filters or {}
            )
            
        except Exception as e:
            logger.error(f"Error generating time series for {metric_name}: {e}")
            return MetricSeries(
                metric_name=metric_name,
                metric_type=MetricType.COUNT,
                granularity=granularity,
                data_points=[],
                filters=filters or {},
                metadata={"error": str(e)}
            )
    
    def calculate_conversion_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate conversion metrics (e.g., guest to free, free to paid).
        
        Args:
            start_date: Start date for calculation
            end_date: End date for calculation
            
        Returns:
            Dictionary containing conversion metrics
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        try:
            # Get tier change events
            tier_changes = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.action.in_(["tier_upgrade", "tier_downgrade"]),
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date
                )
            ).all()
            
            conversions = defaultdict(int)
            
            for change in tier_changes:
                if change.new_values and "old_tier" in change.new_values and "new_tier" in change.new_values:
                    old_tier = change.new_values["old_tier"]
                    new_tier = change.new_values["new_tier"]
                    conversion_key = f"{old_tier}_to_{new_tier}"
                    conversions[conversion_key] += 1
            
            # Calculate conversion rates
            total_users_by_tier = self._get_user_count_by_tier()
            
            conversion_rates = {}
            for conversion, count in conversions.items():
                old_tier = conversion.split("_to_")[0]
                if old_tier in total_users_by_tier and total_users_by_tier[old_tier] > 0:
                    rate = (count / total_users_by_tier[old_tier]) * 100
                    conversion_rates[conversion] = {
                        "count": count,
                        "rate_percentage": round(rate, 2)
                    }
            
            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "conversions": dict(conversions),
                "conversion_rates": conversion_rates,
                "total_users_by_tier": total_users_by_tier
            }
            
        except Exception as e:
            logger.error(f"Error calculating conversion metrics: {e}")
            return {"error": str(e)}
    
    def generate_usage_report(
        self,
        user_id: Optional[str] = None,
        tier: Optional[UserTier] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive usage report.
        
        Args:
            user_id: Optional user ID to filter by
            tier: Optional tier to filter by
            start_date: Start date for report
            end_date: End date for report
            
        Returns:
            Dictionary containing usage report
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        try:
            report = {
                "report_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "filters": {
                    "user_id": user_id,
                    "tier": tier.value if tier else None
                }
            }
            
            if user_id:
                # User-specific report
                report["user_metrics"] = self.calculate_user_metrics(user_id, start_date, end_date)
            elif tier:
                # Tier-specific report
                report["tier_metrics"] = self.calculate_tier_metrics(tier, start_date, end_date)
            else:
                # System-wide report
                report["system_metrics"] = self.calculate_system_metrics(start_date, end_date)
                report["conversion_metrics"] = self.calculate_conversion_metrics(start_date, end_date)
            
            # Add summary statistics
            report["summary"] = self._generate_report_summary(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating usage report: {e}")
            return {"error": str(e)}
    
    # Helper methods
    
    def _count_user_resources(
        self, 
        user_id: str, 
        model_class, 
        start_date: datetime, 
        end_date: datetime
    ) -> int:
        """Count user resources within date range."""
        return self.db.query(func.count(model_class.id)).filter(
            and_(
                model_class.user_id == user_id,
                model_class.created_at >= start_date,
                model_class.created_at <= end_date
            )
        ).scalar() or 0
    
    def _calculate_user_activity_metrics(
        self, 
        user_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate user activity metrics from analytics events."""
        try:
            # Get analytics events for user
            events = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.resource_type == "analytics_event",
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date
                )
            ).all()
            
            activity_counts = defaultdict(int)
            for event in events:
                activity_counts[event.action] += 1
            
            # Calculate activity score (weighted by event importance)
            event_weights = {
                "user_login": 1,
                "short_url_created": 2,
                "paste_created": 2,
                "media_uploaded": 3,
                "feature_used": 1
            }
            
            activity_score = sum(
                activity_counts[event_type] * event_weights.get(event_type, 1)
                for event_type in activity_counts
            )
            
            return {
                "total_events": len(events),
                "event_breakdown": dict(activity_counts),
                "activity_score": activity_score,
                "avg_events_per_day": len(events) / max((end_date - start_date).days, 1)
            }
            
        except Exception as e:
            logger.error(f"Error calculating user activity metrics: {e}")
            return {}
    
    def _get_user_usage_stats(
        self, 
        user_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get user usage statistics from UserUsageStats table."""
        try:
            stats = self.db.query(UserUsageStats).filter(
                and_(
                    UserUsageStats.user_id == user_id,
                    UserUsageStats.date >= start_date.date(),
                    UserUsageStats.date <= end_date.date()
                )
            ).all()
            
            if not stats:
                return {}
            
            total_stats = {
                "messages_sent": sum(s.messages_sent for s in stats),
                "ai_responses_received": sum(s.ai_responses_received for s in stats),
                "sessions_created": sum(s.sessions_created for s in stats),
                "total_tokens_used": sum(s.total_tokens_used for s in stats),
                "premium_features_used": sum(s.premium_features_used for s in stats),
                "api_calls_made": sum(s.api_calls_made for s in stats)
            }
            
            return total_stats
            
        except Exception as e:
            logger.error(f"Error getting user usage stats: {e}")
            return {}
    
    def _calculate_user_system_metrics(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate system-wide user metrics."""
        try:
            total_users = self.db.query(func.count(User.id)).scalar() or 0
            
            new_users = self.db.query(func.count(User.id)).filter(
                and_(
                    User.created_at >= start_date,
                    User.created_at <= end_date
                )
            ).scalar() or 0
            
            active_users = self.db.query(func.count(func.distinct(AuditLog.user_id))).filter(
                and_(
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date,
                    AuditLog.user_id.isnot(None)
                )
            ).scalar() or 0
            
            return {
                "total_users": total_users,
                "new_users": new_users,
                "active_users": active_users,
                "activation_rate": (active_users / new_users * 100) if new_users > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating user system metrics: {e}")
            return {}
    
    def _calculate_resource_system_metrics(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate system-wide resource metrics."""
        try:
            metrics = {}
            
            for resource_name, model_class in [
                ("short_urls", ShortUrl), 
                ("pastes", Paste), 
                ("media_files", MediaFile)
            ]:
                total = self.db.query(func.count(model_class.id)).scalar() or 0
                
                new_resources = self.db.query(func.count(model_class.id)).filter(
                    and_(
                        model_class.created_at >= start_date,
                        model_class.created_at <= end_date
                    )
                ).scalar() or 0
                
                metrics[resource_name] = {
                    "total": total,
                    "new": new_resources
                }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating resource system metrics: {e}")
            return {}
    
    def _calculate_performance_metrics(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate system performance metrics."""
        try:
            # Get API request events
            api_events = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.action == "api_request",
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date
                )
            ).all()
            
            if not api_events:
                return {}
            
            response_times = []
            status_codes = defaultdict(int)
            
            for event in api_events:
                if event.new_values and "response_time_ms" in event.new_values:
                    response_times.append(event.new_values["response_time_ms"])
                
                if event.new_values and "status_code" in event.new_values:
                    status_codes[event.new_values["status_code"]] += 1
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            return {
                "total_requests": len(api_events),
                "average_response_time_ms": round(avg_response_time, 2),
                "status_code_distribution": dict(status_codes),
                "error_rate": (status_codes.get(500, 0) / len(api_events) * 100) if api_events else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def _calculate_tier_distribution(self) -> Dict[str, Any]:
        """Calculate distribution of users across tiers."""
        try:
            tier_counts = {}
            
            for tier in UserTier:
                users = self._get_users_by_tier(tier)
                tier_counts[tier.value] = len(users)
            
            total_users = sum(tier_counts.values())
            
            tier_percentages = {}
            for tier, count in tier_counts.items():
                tier_percentages[tier] = (count / total_users * 100) if total_users > 0 else 0
            
            return {
                "counts": tier_counts,
                "percentages": tier_percentages,
                "total_users": total_users
            }
            
        except Exception as e:
            logger.error(f"Error calculating tier distribution: {e}")
            return {}
    
    def _calculate_growth_metrics(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate growth metrics."""
        try:
            # Compare with previous period
            period_length = end_date - start_date
            prev_start = start_date - period_length
            prev_end = start_date
            
            current_new_users = self.db.query(func.count(User.id)).filter(
                and_(
                    User.created_at >= start_date,
                    User.created_at <= end_date
                )
            ).scalar() or 0
            
            previous_new_users = self.db.query(func.count(User.id)).filter(
                and_(
                    User.created_at >= prev_start,
                    User.created_at <= prev_end
                )
            ).scalar() or 0
            
            growth_rate = 0
            if previous_new_users > 0:
                growth_rate = ((current_new_users - previous_new_users) / previous_new_users) * 100
            
            return {
                "current_period_new_users": current_new_users,
                "previous_period_new_users": previous_new_users,
                "growth_rate_percentage": round(growth_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating growth metrics: {e}")
            return {}
    
    def _get_users_by_tier(self, tier: UserTier) -> List[User]:
        """Get users by tier."""
        # This is a simplified implementation
        # In practice, you'd query the UserTierModel table for active tiers
        return []
    
    def _get_user_count_by_tier(self) -> Dict[str, int]:
        """Get user count by tier."""
        counts = {}
        for tier in UserTier:
            counts[tier.value] = len(self._get_users_by_tier(tier))
        return counts
    
    def _calculate_tier_activity_metrics(
        self, 
        user_ids: List[str], 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate activity metrics for a tier."""
        try:
            if not user_ids:
                return {}
            
            events = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.user_id.in_(user_ids),
                    AuditLog.resource_type == "analytics_event",
                    AuditLog.timestamp >= start_date,
                    AuditLog.timestamp <= end_date
                )
            ).all()
            
            activity_counts = defaultdict(int)
            for event in events:
                activity_counts[event.action] += 1
            
            return {
                "total_events": len(events),
                "events_per_user": len(events) / len(user_ids) if user_ids else 0,
                "event_breakdown": dict(activity_counts)
            }
            
        except Exception as e:
            logger.error(f"Error calculating tier activity metrics: {e}")
            return {}
    
    def _generate_time_intervals(
        self, 
        start_date: datetime, 
        end_date: datetime, 
        granularity: TimeGranularity
    ) -> List[Tuple[datetime, datetime]]:
        """Generate time intervals for time series."""
        intervals = []
        current = start_date
        
        if granularity == TimeGranularity.HOUR:
            delta = timedelta(hours=1)
        elif granularity == TimeGranularity.DAY:
            delta = timedelta(days=1)
        elif granularity == TimeGranularity.WEEK:
            delta = timedelta(weeks=1)
        elif granularity == TimeGranularity.MONTH:
            delta = timedelta(days=30)  # Approximate
        else:
            delta = timedelta(days=365)  # Year
        
        while current < end_date:
            interval_end = min(current + delta, end_date)
            intervals.append((current, interval_end))
            current = interval_end
        
        return intervals
    
    def _calculate_metric_for_interval(
        self, 
        metric_name: str, 
        start: datetime, 
        end: datetime, 
        filters: Optional[Dict[str, Any]]
    ) -> Any:
        """Calculate metric value for a specific time interval."""
        # This is a simplified implementation
        # In practice, you'd have specific calculations for each metric type
        try:
            if metric_name == "user_registrations":
                return self.db.query(func.count(User.id)).filter(
                    and_(
                        User.created_at >= start,
                        User.created_at < end
                    )
                ).scalar() or 0
            
            elif metric_name == "api_requests":
                return self.db.query(func.count(AuditLog.id)).filter(
                    and_(
                        AuditLog.action == "api_request",
                        AuditLog.timestamp >= start,
                        AuditLog.timestamp < end
                    )
                ).scalar() or 0
            
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Error calculating metric {metric_name} for interval: {e}")
            return 0
    
    def _generate_report_summary(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary statistics for a report."""
        summary = {
            "generated_at": datetime.utcnow().isoformat(),
            "report_type": "usage_report"
        }
        
        # Add key highlights based on report content
        if "system_metrics" in report:
            system_metrics = report["system_metrics"]
            if "users" in system_metrics:
                summary["total_users"] = system_metrics["users"].get("total_users", 0)
                summary["new_users"] = system_metrics["users"].get("new_users", 0)
        
        return summary