"""
Analytics Dashboard Service

Provides dashboard-specific analytics data formatting and aggregation
for content creators and administrators.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Video, ViewSession, VideoLike, VideoComment, User, Channel
from .video_analytics_service import VideoAnalyticsService
from .base_service import BaseService


class AnalyticsDashboardService(BaseService):
    """Service for analytics dashboard data and visualizations"""
    
    def __init__(self):
        super().__init__()
        self.analytics_service = VideoAnalyticsService()
    
    async def get_creator_dashboard_data(
        self, 
        creator_id: UUID, 
        timeframe: str = "30d"
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard data for a creator"""
        async with self.get_db_session() as db:
            # Get basic creator analytics
            creator_analytics = await self.analytics_service.get_creator_analytics(creator_id, timeframe)
            
            # Get additional dashboard-specific data
            dashboard_data = {
                **creator_analytics,
                "charts": await self._get_dashboard_charts(creator_id, timeframe, db),
                "recent_activity": await self._get_recent_activity(creator_id, db),
                "performance_insights": await self._get_performance_insights(creator_id, timeframe, db),
                "audience_demographics": await self._get_audience_demographics(creator_id, timeframe, db)
            }
            
            return dashboard_data
    
    async def get_video_dashboard_data(
        self, 
        video_id: UUID, 
        timeframe: str = "7d"
    ) -> Dict[str, Any]:
        """Get detailed dashboard data for a specific video"""
        async with self.get_db_session() as db:
            # Get basic video analytics
            video_analytics = await self.analytics_service.get_video_analytics(video_id, timeframe)
            
            if not video_analytics:
                return {}
            
            # Add dashboard-specific visualizations
            dashboard_data = {
                **video_analytics,
                "charts": await self._get_video_charts(video_id, timeframe, db),
                "engagement_timeline": await self._get_engagement_timeline(video_id, timeframe, db),
                "quality_performance_chart": await self._get_quality_performance_chart(video_id, timeframe, db),
                "geographic_data": await self._get_geographic_data(video_id, timeframe, db)
            }
            
            return dashboard_data
    
    async def get_platform_overview(self, timeframe: str = "30d") -> Dict[str, Any]:
        """Get platform-wide analytics overview for administrators"""
        async with self.get_db_session() as db:
            end_date = datetime.utcnow()
            if timeframe == "7d":
                start_date = end_date - timedelta(days=7)
            elif timeframe == "30d":
                start_date = end_date - timedelta(days=30)
            elif timeframe == "90d":
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=30)
            
            # Platform-wide metrics
            total_videos_stmt = select(func.count(Video.id)).where(
                Video.created_at >= start_date
            )
            total_videos_result = await db.execute(total_videos_stmt)
            total_videos = total_videos_result.scalar() or 0
            
            total_views_stmt = select(func.count(ViewSession.id)).where(
                ViewSession.started_at >= start_date
            )
            total_views_result = await db.execute(total_views_stmt)
            total_views = total_views_result.scalar() or 0
            
            total_creators_stmt = select(func.count(func.distinct(Video.creator_id))).where(
                Video.created_at >= start_date
            )
            total_creators_result = await db.execute(total_creators_stmt)
            active_creators = total_creators_result.scalar() or 0
            
            return {
                "timeframe": timeframe,
                "platform_metrics": {
                    "total_videos": total_videos,
                    "total_views": total_views,
                    "active_creators": active_creators,
                    "avg_views_per_video": total_views / total_videos if total_videos > 0 else 0
                },
                "growth_charts": await self._get_platform_growth_charts(start_date, timeframe, db),
                "top_content": await self._get_top_platform_content(start_date, db)
            }
    
    async def _get_dashboard_charts(
        self, 
        creator_id: UUID, 
        timeframe: str, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate chart data for creator dashboard"""
        end_date = datetime.utcnow()
        if timeframe == "7d":
            start_date = end_date - timedelta(days=7)
            interval = timedelta(days=1)
        elif timeframe == "30d":
            start_date = end_date - timedelta(days=30)
            interval = timedelta(days=1)
        elif timeframe == "90d":
            start_date = end_date - timedelta(days=90)
            interval = timedelta(days=7)
        else:
            start_date = end_date - timedelta(days=30)
            interval = timedelta(days=1)
        
        # Views over time chart
        views_chart = []
        current_date = start_date
        
        while current_date < end_date:
            next_date = current_date + interval
            
            views_stmt = select(func.count(ViewSession.id)).select_from(
                ViewSession
            ).join(
                Video, ViewSession.video_id == Video.id
            ).where(
                and_(
                    Video.creator_id == creator_id,
                    ViewSession.started_at >= current_date,
                    ViewSession.started_at < next_date
                )
            )
            views_result = await db.execute(views_stmt)
            view_count = views_result.scalar() or 0
            
            views_chart.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "views": view_count
            })
            
            current_date = next_date
        
        # Watch time chart
        watch_time_chart = []
        current_date = start_date
        
        while current_date < end_date:
            next_date = current_date + interval
            
            watch_time_stmt = select(func.sum(ViewSession.total_watch_time_seconds)).select_from(
                ViewSession
            ).join(
                Video, ViewSession.video_id == Video.id
            ).where(
                and_(
                    Video.creator_id == creator_id,
                    ViewSession.started_at >= current_date,
                    ViewSession.started_at < next_date
                )
            )
            watch_time_result = await db.execute(watch_time_stmt)
            watch_time = (watch_time_result.scalar() or 0) / 3600  # Convert to hours
            
            watch_time_chart.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "watch_time_hours": watch_time
            })
            
            current_date = next_date
        
        return {
            "views_over_time": views_chart,
            "watch_time_over_time": watch_time_chart
        }
    
    async def _get_video_charts(
        self, 
        video_id: UUID, 
        timeframe: str, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate chart data for video dashboard"""
        # Audience retention chart (already implemented in analytics service)
        retention_data = await self.analytics_service._calculate_audience_retention(
            video_id, 
            datetime.utcnow() - timedelta(days=7), 
            db
        )
        
        # Quality distribution pie chart
        sessions_stmt = select(ViewSession).where(ViewSession.video_id == video_id)
        sessions_result = await db.execute(sessions_stmt)
        sessions = sessions_result.scalars().all()
        
        quality_distribution = {}
        for session in sessions:
            for quality in session.qualities_used:
                quality_distribution[quality] = quality_distribution.get(quality, 0) + 1
        
        quality_chart = [
            {"quality": quality, "count": count}
            for quality, count in quality_distribution.items()
        ]
        
        return {
            "audience_retention": retention_data,
            "quality_distribution": quality_chart
        }
    
    async def _get_recent_activity(self, creator_id: UUID, db: AsyncSession) -> List[Dict[str, Any]]:
        """Get recent activity for creator dashboard"""
        # Get recent comments on creator's videos
        recent_comments_stmt = select(
            VideoComment.content,
            VideoComment.created_at,
            Video.title,
            User.display_label
        ).select_from(
            VideoComment
        ).join(
            Video, VideoComment.video_id == Video.id
        ).join(
            User, VideoComment.user_id == User.id
        ).where(
            Video.creator_id == creator_id
        ).order_by(
            desc(VideoComment.created_at)
        ).limit(10)
        
        comments_result = await db.execute(recent_comments_stmt)
        recent_comments = comments_result.all()
        
        # Get recent likes
        recent_likes_stmt = select(
            VideoLike.created_at,
            VideoLike.is_like,
            Video.title,
            User.display_label
        ).select_from(
            VideoLike
        ).join(
            Video, VideoLike.video_id == Video.id
        ).join(
            User, VideoLike.user_id == User.id
        ).where(
            Video.creator_id == creator_id
        ).order_by(
            desc(VideoLike.created_at)
        ).limit(10)
        
        likes_result = await db.execute(recent_likes_stmt)
        recent_likes = likes_result.all()
        
        # Combine and format activity
        activity = []
        
        for comment in recent_comments:
            activity.append({
                "type": "comment",
                "timestamp": comment.created_at.isoformat(),
                "user": comment.display_label,
                "video": comment.title,
                "content": comment.content[:100] + "..." if len(comment.content) > 100 else comment.content
            })
        
        for like in recent_likes:
            activity.append({
                "type": "like" if like.is_like else "dislike",
                "timestamp": like.created_at.isoformat(),
                "user": like.display_label,
                "video": like.title
            })
        
        # Sort by timestamp
        activity.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return activity[:20]  # Return top 20 recent activities
    
    async def _get_performance_insights(
        self, 
        creator_id: UUID, 
        timeframe: str, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get performance insights and recommendations"""
        end_date = datetime.utcnow()
        if timeframe == "30d":
            start_date = end_date - timedelta(days=30)
        elif timeframe == "7d":
            start_date = end_date - timedelta(days=7)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Get average completion rate
        completion_stmt = select(
            func.avg(ViewSession.completion_percentage)
        ).select_from(
            ViewSession
        ).join(
            Video, ViewSession.video_id == Video.id
        ).where(
            and_(
                Video.creator_id == creator_id,
                ViewSession.started_at >= start_date
            )
        )
        completion_result = await db.execute(completion_stmt)
        avg_completion = completion_result.scalar() or 0
        
        # Get average engagement rate
        total_views_stmt = select(func.count(ViewSession.id)).select_from(
            ViewSession
        ).join(
            Video, ViewSession.video_id == Video.id
        ).where(
            and_(
                Video.creator_id == creator_id,
                ViewSession.started_at >= start_date
            )
        )
        total_views_result = await db.execute(total_views_stmt)
        total_views = total_views_result.scalar() or 0
        
        total_engagement_stmt = select(
            func.count(VideoLike.id) + func.count(VideoComment.id)
        ).select_from(
            Video
        ).outerjoin(
            VideoLike, VideoLike.video_id == Video.id
        ).outerjoin(
            VideoComment, VideoComment.video_id == Video.id
        ).where(
            and_(
                Video.creator_id == creator_id,
                or_(
                    VideoLike.created_at >= start_date,
                    VideoComment.created_at >= start_date
                )
            )
        )
        total_engagement_result = await db.execute(total_engagement_stmt)
        total_engagement = total_engagement_result.scalar() or 0
        
        engagement_rate = (total_engagement / total_views * 100) if total_views > 0 else 0
        
        # Generate insights
        insights = []
        
        if avg_completion < 50:
            insights.append({
                "type": "warning",
                "title": "Low Completion Rate",
                "message": f"Your average completion rate is {avg_completion:.1f}%. Consider creating more engaging content or shorter videos.",
                "metric": "completion_rate",
                "value": avg_completion
            })
        
        if engagement_rate < 5:
            insights.append({
                "type": "tip",
                "title": "Improve Engagement",
                "message": f"Your engagement rate is {engagement_rate:.1f}%. Try asking questions or encouraging comments.",
                "metric": "engagement_rate",
                "value": engagement_rate
            })
        
        if avg_completion > 80:
            insights.append({
                "type": "success",
                "title": "Great Retention",
                "message": f"Excellent! Your completion rate of {avg_completion:.1f}% shows viewers love your content.",
                "metric": "completion_rate",
                "value": avg_completion
            })
        
        return {
            "completion_rate": avg_completion,
            "engagement_rate": engagement_rate,
            "insights": insights
        }
    
    async def _get_audience_demographics(
        self, 
        creator_id: UUID, 
        timeframe: str, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get audience demographic data (simplified version)"""
        end_date = datetime.utcnow()
        if timeframe == "30d":
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=7)
        
        # Get viewing patterns by hour
        hourly_views = {}
        sessions_stmt = select(ViewSession).select_from(
            ViewSession
        ).join(
            Video, ViewSession.video_id == Video.id
        ).where(
            and_(
                Video.creator_id == creator_id,
                ViewSession.started_at >= start_date
            )
        )
        sessions_result = await db.execute(sessions_stmt)
        sessions = sessions_result.scalars().all()
        
        for session in sessions:
            hour = session.started_at.hour
            hourly_views[hour] = hourly_views.get(hour, 0) + 1
        
        # Convert to chart format
        hourly_chart = [
            {"hour": hour, "views": hourly_views.get(hour, 0)}
            for hour in range(24)
        ]
        
        return {
            "viewing_patterns": {
                "hourly_distribution": hourly_chart
            }
        }
    
    async def _get_engagement_timeline(
        self, 
        video_id: UUID, 
        timeframe: str, 
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get engagement events timeline for a video"""
        end_date = datetime.utcnow()
        if timeframe == "7d":
            start_date = end_date - timedelta(days=7)
        else:
            start_date = end_date - timedelta(days=1)
        
        # Get likes timeline
        likes_stmt = select(
            VideoLike.created_at,
            VideoLike.is_like
        ).where(
            and_(
                VideoLike.video_id == video_id,
                VideoLike.created_at >= start_date
            )
        ).order_by(VideoLike.created_at)
        
        likes_result = await db.execute(likes_stmt)
        likes = likes_result.all()
        
        # Get comments timeline
        comments_stmt = select(
            VideoComment.created_at
        ).where(
            and_(
                VideoComment.video_id == video_id,
                VideoComment.created_at >= start_date
            )
        ).order_by(VideoComment.created_at)
        
        comments_result = await db.execute(comments_stmt)
        comments = comments_result.all()
        
        # Combine into timeline
        timeline = []
        
        for like in likes:
            timeline.append({
                "timestamp": like.created_at.isoformat(),
                "type": "like" if like.is_like else "dislike",
                "count": 1
            })
        
        for comment in comments:
            timeline.append({
                "timestamp": comment.created_at.isoformat(),
                "type": "comment",
                "count": 1
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"])
        
        return timeline
    
    async def _get_quality_performance_chart(
        self, 
        video_id: UUID, 
        timeframe: str, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get quality performance metrics chart"""
        sessions_stmt = select(ViewSession).where(ViewSession.video_id == video_id)
        sessions_result = await db.execute(sessions_stmt)
        sessions = sessions_result.scalars().all()
        
        quality_metrics = {}
        
        for session in sessions:
            for quality in session.qualities_used:
                if quality not in quality_metrics:
                    quality_metrics[quality] = {
                        "total_sessions": 0,
                        "total_buffering": 0,
                        "total_switches": 0
                    }
                
                quality_metrics[quality]["total_sessions"] += 1
                quality_metrics[quality]["total_buffering"] += session.buffering_events
                quality_metrics[quality]["total_switches"] += session.quality_switches
        
        # Calculate averages
        performance_chart = []
        for quality, metrics in quality_metrics.items():
            avg_buffering = metrics["total_buffering"] / metrics["total_sessions"] if metrics["total_sessions"] > 0 else 0
            avg_switches = metrics["total_switches"] / metrics["total_sessions"] if metrics["total_sessions"] > 0 else 0
            
            performance_chart.append({
                "quality": quality,
                "sessions": metrics["total_sessions"],
                "avg_buffering_events": avg_buffering,
                "avg_quality_switches": avg_switches
            })
        
        return {
            "quality_performance": performance_chart
        }
    
    async def _get_geographic_data(
        self, 
        video_id: UUID, 
        timeframe: str, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get geographic viewing data (placeholder - would need IP geolocation)"""
        # This is a placeholder - in a real implementation, you would:
        # 1. Store IP addresses (hashed for privacy)
        # 2. Use a geolocation service to map IPs to countries/regions
        # 3. Aggregate viewing data by geographic location
        
        return {
            "countries": [
                {"country": "United States", "views": 45},
                {"country": "Canada", "views": 23},
                {"country": "United Kingdom", "views": 18},
                {"country": "Australia", "views": 12},
                {"country": "Germany", "views": 8}
            ]
        }
    
    async def _get_platform_growth_charts(
        self, 
        start_date: datetime, 
        timeframe: str, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get platform-wide growth charts"""
        # This would implement platform-wide growth metrics
        # Similar to creator charts but aggregated across all creators
        return {
            "user_growth": [],
            "content_growth": [],
            "engagement_growth": []
        }
    
    async def _get_top_platform_content(
        self, 
        start_date: datetime, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get top performing content across the platform"""
        # Get top videos by views
        top_videos_stmt = select(
            Video.id,
            Video.title,
            User.display_label,
            func.count(ViewSession.id).label('view_count')
        ).select_from(
            Video
        ).join(
            User, Video.creator_id == User.id
        ).outerjoin(
            ViewSession, 
            and_(
                ViewSession.video_id == Video.id,
                ViewSession.started_at >= start_date
            )
        ).group_by(
            Video.id, Video.title, User.display_label
        ).order_by(
            desc('view_count')
        ).limit(10)
        
        top_videos_result = await db.execute(top_videos_stmt)
        top_videos = top_videos_result.all()
        
        return {
            "top_videos": [
                {
                    "video_id": str(video.id),
                    "title": video.title,
                    "creator": video.display_label,
                    "views": video.view_count or 0
                }
                for video in top_videos
            ]
        }