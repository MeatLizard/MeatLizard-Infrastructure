"""
Video Analytics Service

Handles collection and aggregation of video analytics data including:
- View tracking and engagement metrics
- Performance metrics (buffering, quality switches)
- User behavior analytics and retention
- Real-time analytics data collection
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    Video, ViewSession, VideoLike, VideoComment, User, 
    AnalyticsEvent, TranscodingJob, VideoPlaylist
)
from .base_service import BaseService


class VideoAnalyticsService(BaseService):
    """Service for collecting and managing video analytics data"""
    
    async def record_view_event(
        self, 
        video_id: UUID, 
        user_id: Optional[UUID], 
        event_data: Dict[str, Any]
    ) -> None:
        """Record a video viewing event for analytics"""
        async with self.get_db_session() as db:
            # Create analytics event
            event = AnalyticsEvent(
                event_type="video_view",
                user_id=user_id,
                content_id=video_id,
                data=event_data
            )
            db.add(event)
            await db.commit()
    
    async def record_engagement_event(
        self,
        video_id: UUID,
        user_id: Optional[UUID],
        event_type: str,
        event_data: Dict[str, Any]
    ) -> None:
        """Record user engagement events (like, comment, share, etc.)"""
        async with self.get_db_session() as db:
            event = AnalyticsEvent(
                event_type=f"video_{event_type}",
                user_id=user_id,
                content_id=video_id,
                data=event_data
            )
            db.add(event)
            await db.commit()
    
    async def record_performance_event(
        self,
        video_id: UUID,
        session_id: UUID,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> None:
        """Record video performance events (buffering, quality switches, errors)"""
        async with self.get_db_session() as db:
            event = AnalyticsEvent(
                event_type=f"video_performance_{event_type}",
                content_id=video_id,
                data={
                    **event_data,
                    "session_id": str(session_id)
                }
            )
            db.add(event)
            await db.commit()
    
    async def record_playback_progress(
        self,
        session_id: UUID,
        current_position: int,
        quality: str,
        buffering_events: int = 0,
        quality_switches: int = 0
    ) -> None:
        """Update viewing session with current playback progress"""
        async with self.get_db_session() as db:
            # Update view session
            stmt = select(ViewSession).where(ViewSession.id == session_id)
            result = await db.execute(stmt)
            session = result.scalar_one_or_none()
            
            if session:
                session.current_position_seconds = current_position
                session.last_heartbeat = datetime.utcnow()
                session.buffering_events = buffering_events
                session.quality_switches = quality_switches
                
                # Update qualities used
                if quality not in session.qualities_used:
                    session.qualities_used = session.qualities_used + [quality]
                
                # Calculate completion percentage
                if session.video.duration_seconds > 0:
                    session.completion_percentage = min(
                        100, 
                        int((current_position / session.video.duration_seconds) * 100)
                    )
                
                await db.commit()
    
    async def get_video_analytics(
        self, 
        video_id: UUID, 
        timeframe: str = "7d"
    ) -> Dict[str, Any]:
        """Get comprehensive analytics for a specific video"""
        async with self.get_db_session() as db:
            # Calculate timeframe
            end_date = datetime.utcnow()
            if timeframe == "1h":
                start_date = end_date - timedelta(hours=1)
            elif timeframe == "24h":
                start_date = end_date - timedelta(days=1)
            elif timeframe == "7d":
                start_date = end_date - timedelta(days=7)
            elif timeframe == "30d":
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=7)
            
            # Get video info
            video_stmt = select(Video).where(Video.id == video_id)
            video_result = await db.execute(video_stmt)
            video = video_result.scalar_one_or_none()
            
            if not video:
                return {}
            
            # Get view sessions in timeframe
            sessions_stmt = select(ViewSession).where(
                and_(
                    ViewSession.video_id == video_id,
                    ViewSession.started_at >= start_date
                )
            )
            sessions_result = await db.execute(sessions_stmt)
            sessions = sessions_result.scalars().all()
            
            # Calculate basic metrics
            total_views = len(sessions)
            total_watch_time = sum(s.total_watch_time_seconds for s in sessions)
            avg_watch_time = total_watch_time / total_views if total_views > 0 else 0
            
            # Calculate completion rates
            completed_views = len([s for s in sessions if s.completion_percentage >= 90])
            completion_rate = (completed_views / total_views * 100) if total_views > 0 else 0
            
            # Get engagement metrics
            likes_stmt = select(func.count(VideoLike.id)).where(
                and_(
                    VideoLike.video_id == video_id,
                    VideoLike.is_like == True,
                    VideoLike.created_at >= start_date
                )
            )
            likes_result = await db.execute(likes_stmt)
            likes_count = likes_result.scalar() or 0
            
            dislikes_stmt = select(func.count(VideoLike.id)).where(
                and_(
                    VideoLike.video_id == video_id,
                    VideoLike.is_like == False,
                    VideoLike.created_at >= start_date
                )
            )
            dislikes_result = await db.execute(dislikes_stmt)
            dislikes_count = dislikes_result.scalar() or 0
            
            comments_stmt = select(func.count(VideoComment.id)).where(
                and_(
                    VideoComment.video_id == video_id,
                    VideoComment.created_at >= start_date
                )
            )
            comments_result = await db.execute(comments_stmt)
            comments_count = comments_result.scalar() or 0
            
            # Calculate quality performance
            quality_distribution = {}
            buffering_events = sum(s.buffering_events for s in sessions)
            quality_switches = sum(s.quality_switches for s in sessions)
            
            for session in sessions:
                for quality in session.qualities_used:
                    quality_distribution[quality] = quality_distribution.get(quality, 0) + 1
            
            # Get audience retention data (by percentage of video)
            retention_data = await self._calculate_audience_retention(video_id, start_date, db)
            
            # Get views over time
            views_over_time = await self._get_views_over_time(video_id, start_date, timeframe, db)
            
            return {
                "video_id": str(video_id),
                "timeframe": timeframe,
                "basic_metrics": {
                    "total_views": total_views,
                    "total_watch_time_seconds": total_watch_time,
                    "average_watch_time_seconds": avg_watch_time,
                    "completion_rate_percent": completion_rate,
                    "video_duration_seconds": video.duration_seconds
                },
                "engagement_metrics": {
                    "likes": likes_count,
                    "dislikes": dislikes_count,
                    "comments": comments_count,
                    "engagement_rate": ((likes_count + dislikes_count + comments_count) / total_views * 100) if total_views > 0 else 0
                },
                "quality_metrics": {
                    "quality_distribution": quality_distribution,
                    "total_buffering_events": buffering_events,
                    "total_quality_switches": quality_switches,
                    "avg_buffering_per_view": buffering_events / total_views if total_views > 0 else 0,
                    "avg_quality_switches_per_view": quality_switches / total_views if total_views > 0 else 0
                },
                "audience_retention": retention_data,
                "views_over_time": views_over_time
            }
    
    async def get_creator_analytics(
        self, 
        creator_id: UUID, 
        timeframe: str = "30d"
    ) -> Dict[str, Any]:
        """Get comprehensive analytics for a content creator"""
        async with self.get_db_session() as db:
            # Calculate timeframe
            end_date = datetime.utcnow()
            if timeframe == "7d":
                start_date = end_date - timedelta(days=7)
            elif timeframe == "30d":
                start_date = end_date - timedelta(days=30)
            elif timeframe == "90d":
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=30)
            
            # Get creator's videos
            videos_stmt = select(Video).where(Video.creator_id == creator_id)
            videos_result = await db.execute(videos_stmt)
            videos = videos_result.scalars().all()
            video_ids = [v.id for v in videos]
            
            if not video_ids:
                return {"error": "No videos found for creator"}
            
            # Get aggregate metrics across all videos
            total_views_stmt = select(func.count(ViewSession.id)).where(
                and_(
                    ViewSession.video_id.in_(video_ids),
                    ViewSession.started_at >= start_date
                )
            )
            total_views_result = await db.execute(total_views_stmt)
            total_views = total_views_result.scalar() or 0
            
            # Get total watch time
            watch_time_stmt = select(func.sum(ViewSession.total_watch_time_seconds)).where(
                and_(
                    ViewSession.video_id.in_(video_ids),
                    ViewSession.started_at >= start_date
                )
            )
            watch_time_result = await db.execute(watch_time_stmt)
            total_watch_time = watch_time_result.scalar() or 0
            
            # Get engagement metrics
            total_likes_stmt = select(func.count(VideoLike.id)).where(
                and_(
                    VideoLike.video_id.in_(video_ids),
                    VideoLike.is_like == True,
                    VideoLike.created_at >= start_date
                )
            )
            total_likes_result = await db.execute(total_likes_stmt)
            total_likes = total_likes_result.scalar() or 0
            
            # Get top performing videos
            top_videos = await self._get_top_videos_for_creator(creator_id, start_date, db)
            
            # Get subscriber growth (using view sessions as proxy)
            subscriber_growth = await self._get_subscriber_growth(creator_id, start_date, timeframe, db)
            
            return {
                "creator_id": str(creator_id),
                "timeframe": timeframe,
                "overview": {
                    "total_videos": len(videos),
                    "total_views": total_views,
                    "total_watch_time_hours": total_watch_time / 3600,
                    "total_likes": total_likes,
                    "average_views_per_video": total_views / len(videos) if videos else 0
                },
                "top_videos": top_videos,
                "growth_metrics": subscriber_growth
            }
    
    async def get_real_time_metrics(self, video_id: UUID) -> Dict[str, Any]:
        """Get real-time metrics for a video (last 5 minutes)"""
        async with self.get_db_session() as db:
            five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
            
            # Current active viewers
            active_viewers_stmt = select(func.count(ViewSession.id)).where(
                and_(
                    ViewSession.video_id == video_id,
                    ViewSession.last_heartbeat >= five_minutes_ago,
                    ViewSession.ended_at.is_(None)
                )
            )
            active_viewers_result = await db.execute(active_viewers_stmt)
            active_viewers = active_viewers_result.scalar() or 0
            
            # Recent events
            recent_events_stmt = select(AnalyticsEvent).where(
                and_(
                    AnalyticsEvent.content_id == video_id,
                    AnalyticsEvent.timestamp >= five_minutes_ago
                )
            ).order_by(desc(AnalyticsEvent.timestamp)).limit(50)
            recent_events_result = await db.execute(recent_events_stmt)
            recent_events = recent_events_result.scalars().all()
            
            # Group events by type
            event_counts = {}
            for event in recent_events:
                event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
            
            return {
                "video_id": str(video_id),
                "timestamp": datetime.utcnow().isoformat(),
                "active_viewers": active_viewers,
                "recent_activity": event_counts,
                "events_last_5min": len(recent_events)
            }
    
    async def _calculate_audience_retention(
        self, 
        video_id: UUID, 
        start_date: datetime, 
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Calculate audience retention by video percentage"""
        # Get all view sessions for the video
        sessions_stmt = select(ViewSession).where(
            and_(
                ViewSession.video_id == video_id,
                ViewSession.started_at >= start_date
            )
        )
        sessions_result = await db.execute(sessions_stmt)
        sessions = sessions_result.scalars().all()
        
        if not sessions:
            return []
        
        # Calculate retention at 10% intervals
        retention_points = []
        total_sessions = len(sessions)
        
        for percentage in range(0, 101, 10):
            viewers_at_point = len([
                s for s in sessions 
                if s.completion_percentage >= percentage
            ])
            retention_rate = (viewers_at_point / total_sessions * 100) if total_sessions > 0 else 0
            
            retention_points.append({
                "percentage": percentage,
                "viewers": viewers_at_point,
                "retention_rate": retention_rate
            })
        
        return retention_points
    
    async def _get_views_over_time(
        self, 
        video_id: UUID, 
        start_date: datetime, 
        timeframe: str, 
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get views over time for charting"""
        # Determine interval based on timeframe
        if timeframe == "1h":
            interval = timedelta(minutes=5)
        elif timeframe == "24h":
            interval = timedelta(hours=1)
        elif timeframe == "7d":
            interval = timedelta(hours=6)
        else:
            interval = timedelta(days=1)
        
        views_over_time = []
        current_time = start_date
        end_time = datetime.utcnow()
        
        while current_time < end_time:
            next_time = current_time + interval
            
            # Count views in this interval
            views_stmt = select(func.count(ViewSession.id)).where(
                and_(
                    ViewSession.video_id == video_id,
                    ViewSession.started_at >= current_time,
                    ViewSession.started_at < next_time
                )
            )
            views_result = await db.execute(views_stmt)
            view_count = views_result.scalar() or 0
            
            views_over_time.append({
                "timestamp": current_time.isoformat(),
                "views": view_count
            })
            
            current_time = next_time
        
        return views_over_time
    
    async def _get_top_videos_for_creator(
        self, 
        creator_id: UUID, 
        start_date: datetime, 
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get top performing videos for a creator"""
        # Get videos with view counts
        stmt = select(
            Video.id,
            Video.title,
            func.count(ViewSession.id).label('view_count'),
            func.sum(ViewSession.total_watch_time_seconds).label('total_watch_time')
        ).select_from(
            Video
        ).outerjoin(
            ViewSession, 
            and_(
                ViewSession.video_id == Video.id,
                ViewSession.started_at >= start_date
            )
        ).where(
            Video.creator_id == creator_id
        ).group_by(
            Video.id, Video.title
        ).order_by(
            desc('view_count')
        ).limit(10)
        
        result = await db.execute(stmt)
        rows = result.all()
        
        return [
            {
                "video_id": str(row.id),
                "title": row.title,
                "views": row.view_count or 0,
                "watch_time_hours": (row.total_watch_time or 0) / 3600
            }
            for row in rows
        ]
    
    async def _get_subscriber_growth(
        self, 
        creator_id: UUID, 
        start_date: datetime, 
        timeframe: str, 
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Get subscriber growth metrics (using unique viewers as proxy)"""
        # Get unique viewers over time
        unique_viewers_stmt = select(func.count(func.distinct(ViewSession.user_id))).where(
            and_(
                ViewSession.video_id.in_(
                    select(Video.id).where(Video.creator_id == creator_id)
                ),
                ViewSession.started_at >= start_date,
                ViewSession.user_id.is_not(None)
            )
        )
        unique_viewers_result = await db.execute(unique_viewers_stmt)
        unique_viewers = unique_viewers_result.scalar() or 0
        
        return {
            "unique_viewers": unique_viewers,
            "timeframe": timeframe
        }
    
    async def export_analytics_data(
        self, 
        video_id: UUID, 
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export comprehensive analytics data for a video"""
        analytics_data = await self.get_video_analytics(video_id, "30d")
        
        if format == "json":
            return analytics_data
        elif format == "csv":
            # Convert to CSV-friendly format
            return self._convert_to_csv_format(analytics_data)
        else:
            return analytics_data
    
    def _convert_to_csv_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert analytics data to CSV-friendly format"""
        # Flatten nested dictionaries for CSV export
        flattened = {}
        
        def flatten_dict(d: Dict, prefix: str = ""):
            for key, value in d.items():
                new_key = f"{prefix}_{key}" if prefix else key
                if isinstance(value, dict):
                    flatten_dict(value, new_key)
                elif isinstance(value, list):
                    flattened[f"{new_key}_count"] = len(value)
                else:
                    flattened[new_key] = value
        
        flatten_dict(data)
        return flattened