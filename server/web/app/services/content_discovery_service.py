"""
Content discovery and browsing service for video platform.
"""
import uuid
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_, desc, asc, text
from sqlalchemy.orm import selectinload
from enum import Enum

from .base_service import BaseService
from ..models import Video, Channel, VideoPlaylist, User, VideoVisibility, ViewSession, VideoLike


class SortOrder(str, Enum):
    newest = "newest"
    oldest = "oldest"
    most_viewed = "most_viewed"
    most_liked = "most_liked"
    duration_asc = "duration_asc"
    duration_desc = "duration_desc"
    alphabetical = "alphabetical"


class ContentDiscoveryService(BaseService):
    """Service for content discovery, browsing, and filtering."""
    
    async def browse_videos(
        self,
        viewer_user_id: Optional[uuid.UUID] = None,
        channel_id: Optional[uuid.UUID] = None,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        sort_order: SortOrder = SortOrder.newest,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Video], int]:
        """Browse videos with comprehensive filtering and sorting."""
        async with self.get_db_session() as db:
            # Base query with visibility filtering
            query = select(Video).options(
                selectinload(Video.creator),
                selectinload(Video.channel)
            )
            
            # Apply visibility filtering
            if viewer_user_id:
                # User can see their own private videos and public/unlisted videos
                query = query.where(
                    or_(
                        Video.visibility.in_([VideoVisibility.public, VideoVisibility.unlisted]),
                        Video.creator_id == viewer_user_id
                    )
                )
            else:
                # Anonymous users can only see public videos
                query = query.where(Video.visibility == VideoVisibility.public)
            
            # Only show ready videos
            from ..models import VideoStatus
            query = query.where(Video.status == VideoStatus.ready)
            
            # Apply filters
            if channel_id:
                query = query.where(Video.channel_id == channel_id)
            
            if category:
                query = query.where(Video.category == category)
            
            if search_query:
                search_terms = search_query.strip().split()
                for term in search_terms:
                    query = query.where(
                        or_(
                            Video.title.ilike(f"%{term}%"),
                            Video.description.ilike(f"%{term}%"),
                            Video.tags.op('@>')([term])  # PostgreSQL array contains
                        )
                    )
            
            if min_duration:
                query = query.where(Video.duration_seconds >= min_duration)
            
            if max_duration:
                query = query.where(Video.duration_seconds <= max_duration)
            
            if date_from:
                query = query.where(Video.created_at >= date_from)
            
            if date_to:
                query = query.where(Video.created_at <= date_to)
            
            # Get total count before applying limit/offset
            count_query = select(func.count()).select_from(query.subquery())
            count_result = await db.execute(count_query)
            total_count = count_result.scalar()
            
            # Apply sorting
            query = self._apply_video_sorting(query, sort_order)
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            # Execute query
            result = await db.execute(query)
            videos = result.scalars().all()
            
            return videos, total_count
    
    async def search_content(
        self,
        search_query: str,
        content_types: List[str] = None,  # ['videos', 'channels', 'playlists']
        viewer_user_id: Optional[uuid.UUID] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search across videos, channels, and playlists."""
        if not content_types:
            content_types = ['videos', 'channels', 'playlists']
        
        results = {}
        
        async with self.get_db_session() as db:
            # Search videos
            if 'videos' in content_types:
                videos, video_count = await self.browse_videos(
                    viewer_user_id=viewer_user_id,
                    search_query=search_query,
                    limit=limit,
                    offset=offset
                )
                results['videos'] = {
                    'items': videos,
                    'total': video_count
                }
            
            # Search channels
            if 'channels' in content_types:
                channel_query = (
                    select(Channel)
                    .options(selectinload(Channel.creator))
                    .where(Channel.visibility == VideoVisibility.public)
                )
                
                search_terms = search_query.strip().split()
                for term in search_terms:
                    channel_query = channel_query.where(
                        or_(
                            Channel.name.ilike(f"%{term}%"),
                            Channel.description.ilike(f"%{term}%")
                        )
                    )
                
                # Get count
                channel_count_query = select(func.count()).select_from(channel_query.subquery())
                channel_count_result = await db.execute(channel_count_query)
                channel_total = channel_count_result.scalar()
                
                # Get results
                channel_query = (
                    channel_query
                    .order_by(Channel.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                
                channel_result = await db.execute(channel_query)
                channels = channel_result.scalars().all()
                
                results['channels'] = {
                    'items': channels,
                    'total': channel_total
                }
            
            # Search playlists
            if 'playlists' in content_types:
                playlist_query = (
                    select(VideoPlaylist)
                    .options(
                        selectinload(VideoPlaylist.creator),
                        selectinload(VideoPlaylist.channel)
                    )
                    .where(VideoPlaylist.visibility == VideoVisibility.public)
                )
                
                search_terms = search_query.strip().split()
                for term in search_terms:
                    playlist_query = playlist_query.where(
                        or_(
                            VideoPlaylist.name.ilike(f"%{term}%"),
                            VideoPlaylist.description.ilike(f"%{term}%")
                        )
                    )
                
                # Get count
                playlist_count_query = select(func.count()).select_from(playlist_query.subquery())
                playlist_count_result = await db.execute(playlist_count_query)
                playlist_total = playlist_count_result.scalar()
                
                # Get results
                playlist_query = (
                    playlist_query
                    .order_by(VideoPlaylist.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                
                playlist_result = await db.execute(playlist_query)
                playlists = playlist_result.scalars().all()
                
                results['playlists'] = {
                    'items': playlists,
                    'total': playlist_total
                }
        
        return results
    
    async def get_trending_videos(
        self,
        timeframe: str = "week",  # "day", "week", "month", "all"
        viewer_user_id: Optional[uuid.UUID] = None,
        limit: int = 20
    ) -> List[Video]:
        """Get trending videos based on view count in timeframe."""
        async with self.get_db_session() as db:
            # Calculate date threshold
            now = datetime.utcnow()
            if timeframe == "day":
                date_threshold = now - timedelta(days=1)
            elif timeframe == "week":
                date_threshold = now - timedelta(weeks=1)
            elif timeframe == "month":
                date_threshold = now - timedelta(days=30)
            else:  # "all"
                date_threshold = datetime.min
            
            # Query for videos with view counts
            query = (
                select(Video, func.count(ViewSession.id).label('view_count'))
                .outerjoin(ViewSession, Video.id == ViewSession.video_id)
                .options(
                    selectinload(Video.creator),
                    selectinload(Video.channel)
                )
            )
            
            # Apply visibility filtering
            if viewer_user_id:
                query = query.where(
                    or_(
                        Video.visibility.in_([VideoVisibility.public, VideoVisibility.unlisted]),
                        Video.creator_id == viewer_user_id
                    )
                )
            else:
                query = query.where(Video.visibility == VideoVisibility.public)
            
            # Only ready videos
            from ..models import VideoStatus
            query = query.where(Video.status == VideoStatus.ready)
            
            # Apply timeframe filter
            if date_threshold != datetime.min:
                query = query.where(ViewSession.started_at >= date_threshold)
            
            # Group and order by view count
            query = (
                query
                .group_by(Video.id)
                .order_by(desc('view_count'))
                .limit(limit)
            )
            
            result = await db.execute(query)
            # Extract just the Video objects from the tuples
            videos = [row[0] for row in result.all()]
            
            return videos
    
    async def get_popular_videos(
        self,
        timeframe: str = "week",
        viewer_user_id: Optional[uuid.UUID] = None,
        limit: int = 20
    ) -> List[Video]:
        """Get popular videos based on likes in timeframe."""
        async with self.get_db_session() as db:
            # Calculate date threshold
            now = datetime.utcnow()
            if timeframe == "day":
                date_threshold = now - timedelta(days=1)
            elif timeframe == "week":
                date_threshold = now - timedelta(weeks=1)
            elif timeframe == "month":
                date_threshold = now - timedelta(days=30)
            else:  # "all"
                date_threshold = datetime.min
            
            # Query for videos with like counts
            query = (
                select(Video, func.count(VideoLike.id).label('like_count'))
                .outerjoin(VideoLike, and_(
                    Video.id == VideoLike.video_id,
                    VideoLike.is_like == True
                ))
                .options(
                    selectinload(Video.creator),
                    selectinload(Video.channel)
                )
            )
            
            # Apply visibility filtering
            if viewer_user_id:
                query = query.where(
                    or_(
                        Video.visibility.in_([VideoVisibility.public, VideoVisibility.unlisted]),
                        Video.creator_id == viewer_user_id
                    )
                )
            else:
                query = query.where(Video.visibility == VideoVisibility.public)
            
            # Only ready videos
            from ..models import VideoStatus
            query = query.where(Video.status == VideoStatus.ready)
            
            # Apply timeframe filter
            if date_threshold != datetime.min:
                query = query.where(VideoLike.created_at >= date_threshold)
            
            # Group and order by like count
            query = (
                query
                .group_by(Video.id)
                .order_by(desc('like_count'))
                .limit(limit)
            )
            
            result = await db.execute(query)
            # Extract just the Video objects from the tuples
            videos = [row[0] for row in result.all()]
            
            return videos
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all available categories with video counts."""
        async with self.get_db_session() as db:
            # Get video categories
            video_categories_query = (
                select(Video.category, func.count(Video.id).label('video_count'))
                .where(
                    and_(
                        Video.category.isnot(None),
                        Video.visibility == VideoVisibility.public,
                        Video.status == 'ready'
                    )
                )
                .group_by(Video.category)
                .order_by(desc('video_count'))
            )
            
            video_result = await db.execute(video_categories_query)
            video_categories = video_result.all()
            
            # Get channel categories
            channel_categories_query = (
                select(Channel.category, func.count(Channel.id).label('channel_count'))
                .where(
                    and_(
                        Channel.category.isnot(None),
                        Channel.visibility == VideoVisibility.public
                    )
                )
                .group_by(Channel.category)
                .order_by(desc('channel_count'))
            )
            
            channel_result = await db.execute(channel_categories_query)
            channel_categories = channel_result.all()
            
            # Combine and format results
            categories = {}
            
            for category, video_count in video_categories:
                categories[category] = {
                    'name': category,
                    'video_count': video_count,
                    'channel_count': 0
                }
            
            for category, channel_count in channel_categories:
                if category in categories:
                    categories[category]['channel_count'] = channel_count
                else:
                    categories[category] = {
                        'name': category,
                        'video_count': 0,
                        'channel_count': channel_count
                    }
            
            return list(categories.values())
    
    async def get_related_videos(
        self,
        video_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None,
        limit: int = 10
    ) -> List[Video]:
        """Get videos related to the given video based on tags, category, and creator."""
        async with self.get_db_session() as db:
            # Get the source video
            source_video_result = await db.execute(
                select(Video).where(Video.id == video_id)
            )
            source_video = source_video_result.scalar_one_or_none()
            
            if not source_video:
                return []
            
            # Build related videos query
            query = (
                select(Video)
                .options(
                    selectinload(Video.creator),
                    selectinload(Video.channel)
                )
                .where(
                    and_(
                        Video.id != video_id,  # Exclude the source video
                        Video.status == 'ready'
                    )
                )
            )
            
            # Apply visibility filtering
            if viewer_user_id:
                query = query.where(
                    or_(
                        Video.visibility.in_([VideoVisibility.public, VideoVisibility.unlisted]),
                        Video.creator_id == viewer_user_id
                    )
                )
            else:
                query = query.where(Video.visibility == VideoVisibility.public)
            
            # Build relevance conditions (ordered by priority)
            relevance_conditions = []
            
            # Same creator (highest priority)
            if source_video.creator_id:
                relevance_conditions.append((
                    Video.creator_id == source_video.creator_id,
                    3  # Priority weight
                ))
            
            # Same category
            if source_video.category:
                relevance_conditions.append((
                    Video.category == source_video.category,
                    2
                ))
            
            # Shared tags
            if source_video.tags:
                for tag in source_video.tags[:5]:  # Limit to top 5 tags
                    relevance_conditions.append((
                        Video.tags.op('@>')([tag]),
                        1
                    ))
            
            # Same channel
            if source_video.channel_id:
                relevance_conditions.append((
                    Video.channel_id == source_video.channel_id,
                    2
                ))
            
            # Apply relevance filtering (at least one condition must match)
            if relevance_conditions:
                relevance_filters = [condition for condition, _ in relevance_conditions]
                query = query.where(or_(*relevance_filters))
            
            # Order by creation date and limit
            query = query.order_by(Video.created_at.desc()).limit(limit * 2)  # Get more to filter
            
            result = await db.execute(query)
            related_videos = result.scalars().all()
            
            # Sort by relevance score
            scored_videos = []
            for video in related_videos:
                score = 0
                for condition, weight in relevance_conditions:
                    # This is a simplified scoring - in practice you'd evaluate conditions
                    if video.creator_id == source_video.creator_id:
                        score += 3
                    if video.category == source_video.category:
                        score += 2
                    if video.channel_id == source_video.channel_id:
                        score += 2
                    if source_video.tags and video.tags:
                        shared_tags = set(source_video.tags) & set(video.tags)
                        score += len(shared_tags)
                
                scored_videos.append((video, score))
            
            # Sort by score and return top results
            scored_videos.sort(key=lambda x: x[1], reverse=True)
            return [video for video, _ in scored_videos[:limit]]

    async def get_recommended_videos(
        self,
        user_id: uuid.UUID,
        limit: int = 20
    ) -> List[Video]:
        """Get personalized video recommendations based on viewing history."""
        async with self.get_db_session() as db:
            # Get user's viewing history to understand preferences
            viewed_videos_query = (
                select(Video.category, Video.tags, func.count().label('view_count'))
                .join(ViewSession, Video.id == ViewSession.video_id)
                .where(ViewSession.user_id == user_id)
                .group_by(Video.category, Video.tags)
                .order_by(desc('view_count'))
                .limit(10)
            )
            
            viewed_result = await db.execute(viewed_videos_query)
            user_preferences = viewed_result.all()
            
            if not user_preferences:
                # No viewing history, return trending videos
                return await self.get_trending_videos(viewer_user_id=user_id, limit=limit)
            
            # Get videos the user hasn't watched in preferred categories/tags
            preferred_categories = [pref[0] for pref in user_preferences if pref[0]]
            preferred_tags = []
            for pref in user_preferences:
                if pref[1]:  # tags array
                    preferred_tags.extend(pref[1])
            
            # Remove duplicates
            preferred_tags = list(set(preferred_tags))
            
            # Build recommendation query
            query = (
                select(Video)
                .options(
                    selectinload(Video.creator),
                    selectinload(Video.channel)
                )
                .where(
                    and_(
                        Video.visibility.in_([VideoVisibility.public, VideoVisibility.unlisted]),
                        Video.status == 'ready',
                        # Exclude videos user has already watched
                        ~Video.id.in_(
                            select(ViewSession.video_id)
                            .where(ViewSession.user_id == user_id)
                        )
                    )
                )
            )
            
            # Add preference-based filtering
            preference_conditions = []
            if preferred_categories:
                preference_conditions.append(Video.category.in_(preferred_categories))
            
            if preferred_tags:
                for tag in preferred_tags[:5]:  # Limit to top 5 tags
                    preference_conditions.append(Video.tags.op('@>')([tag]))
            
            if preference_conditions:
                query = query.where(or_(*preference_conditions))
            
            # Order by creation date (newest first) and limit
            query = query.order_by(Video.created_at.desc()).limit(limit)
            
            result = await db.execute(query)
            recommended_videos = result.scalars().all()
            
            # If we don't have enough recommendations, fill with trending
            if len(recommended_videos) < limit:
                trending = await self.get_trending_videos(
                    viewer_user_id=user_id,
                    limit=limit - len(recommended_videos)
                )
                # Filter out videos already in recommendations
                recommended_ids = {v.id for v in recommended_videos}
                trending_filtered = [v for v in trending if v.id not in recommended_ids]
                recommended_videos.extend(trending_filtered)
            
            return recommended_videos
    
    def _apply_video_sorting(self, query, sort_order: SortOrder):
        """Apply sorting to video query."""
        if sort_order == SortOrder.newest:
            return query.order_by(Video.created_at.desc())
        elif sort_order == SortOrder.oldest:
            return query.order_by(Video.created_at.asc())
        elif sort_order == SortOrder.duration_asc:
            return query.order_by(Video.duration_seconds.asc())
        elif sort_order == SortOrder.duration_desc:
            return query.order_by(Video.duration_seconds.desc())
        elif sort_order == SortOrder.alphabetical:
            return query.order_by(Video.title.asc())
        elif sort_order == SortOrder.most_viewed:
            # This requires a subquery to count views
            view_count_subquery = (
                select(ViewSession.video_id, func.count().label('view_count'))
                .group_by(ViewSession.video_id)
                .subquery()
            )
            return (
                query
                .outerjoin(view_count_subquery, Video.id == view_count_subquery.c.video_id)
                .order_by(desc(view_count_subquery.c.view_count))
            )
        elif sort_order == SortOrder.most_liked:
            # This requires a subquery to count likes
            like_count_subquery = (
                select(VideoLike.video_id, func.count().label('like_count'))
                .where(VideoLike.is_like == True)
                .group_by(VideoLike.video_id)
                .subquery()
            )
            return (
                query
                .outerjoin(like_count_subquery, Video.id == like_count_subquery.c.video_id)
                .order_by(desc(like_count_subquery.c.like_count))
            )
        else:
            return query.order_by(Video.created_at.desc())
    
    async def get_videos_by_category(
        self,
        category: str,
        viewer_user_id: Optional[uuid.UUID] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Video], int]:
        """Get videos in a specific category."""
        return await self.browse_videos(
            viewer_user_id=viewer_user_id,
            category=category,
            limit=limit,
            offset=offset
        )
    
    async def get_latest_videos(
        self,
        viewer_user_id: Optional[uuid.UUID] = None,
        limit: int = 20
    ) -> List[Video]:
        """Get the latest uploaded videos."""
        videos, _ = await self.browse_videos(
            viewer_user_id=viewer_user_id,
            sort_order=SortOrder.newest,
            limit=limit,
            offset=0
        )
        return videos
    
    async def get_videos_by_creator(
        self,
        creator_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Video]:
        """Get videos by a specific creator."""
        async with self.get_db_session() as db:
            query = (
                select(Video)
                .options(
                    selectinload(Video.creator),
                    selectinload(Video.channel)
                )
                .where(
                    and_(
                        Video.creator_id == creator_id,
                        Video.status == 'ready'
                    )
                )
            )
            
            # Apply visibility filtering
            if viewer_user_id:
                query = query.where(
                    or_(
                        Video.visibility.in_([VideoVisibility.public, VideoVisibility.unlisted]),
                        Video.creator_id == viewer_user_id
                    )
                )
            else:
                query = query.where(Video.visibility == VideoVisibility.public)
            
            query = (
                query
                .order_by(Video.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            result = await db.execute(query)
            return result.scalars().all()
    
    async def get_discovery_sections(
        self,
        viewer_user_id: Optional[uuid.UUID] = None
    ) -> Dict[str, List[Video]]:
        """Get multiple discovery sections for the home page."""
        sections = {}
        
        # Trending videos
        sections['trending'] = await self.get_trending_videos(
            timeframe="week",
            viewer_user_id=viewer_user_id,
            limit=10
        )
        
        # Popular videos
        sections['popular'] = await self.get_popular_videos(
            timeframe="month",
            viewer_user_id=viewer_user_id,
            limit=10
        )
        
        # Latest videos
        sections['latest'] = await self.get_latest_videos(
            viewer_user_id=viewer_user_id,
            limit=10
        )
        
        # Personalized recommendations (if user is logged in)
        if viewer_user_id:
            sections['recommended'] = await self.get_recommended_videos(
                user_id=viewer_user_id,
                limit=10
            )
        
        # Category-based sections
        categories = await self.get_categories()
        for category in categories[:3]:  # Top 3 categories
            category_videos, _ = await self.get_videos_by_category(
                category=category['name'],
                viewer_user_id=viewer_user_id,
                limit=8
            )
            if category_videos:
                sections[f"category_{category['name']}"] = category_videos
        
        return sections
    
    async def get_video_analytics_for_discovery(
        self,
        video_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Get analytics data for a video to help with discovery algorithms."""
        async with self.get_db_session() as db:
            # View count
            view_count_result = await db.execute(
                select(func.count(ViewSession.id))
                .where(ViewSession.video_id == video_id)
            )
            view_count = view_count_result.scalar() or 0
            
            # Like count
            like_count_result = await db.execute(
                select(func.count(VideoLike.id))
                .where(
                    and_(
                        VideoLike.video_id == video_id,
                        VideoLike.is_like == True
                    )
                )
            )
            like_count = like_count_result.scalar() or 0
            
            # Dislike count
            dislike_count_result = await db.execute(
                select(func.count(VideoLike.id))
                .where(
                    and_(
                        VideoLike.video_id == video_id,
                        VideoLike.is_like == False
                    )
                )
            )
            dislike_count = dislike_count_result.scalar() or 0
            
            # Average watch time
            avg_watch_time_result = await db.execute(
                select(func.avg(ViewSession.total_watch_time_seconds))
                .where(ViewSession.video_id == video_id)
            )
            avg_watch_time = avg_watch_time_result.scalar() or 0
            
            # Completion rate
            completion_rate_result = await db.execute(
                select(func.avg(ViewSession.completion_percentage))
                .where(ViewSession.video_id == video_id)
            )
            completion_rate = completion_rate_result.scalar() or 0
            
            return {
                'view_count': view_count,
                'like_count': like_count,
                'dislike_count': dislike_count,
                'engagement_rate': (like_count + dislike_count) / max(view_count, 1) * 100,
                'like_ratio': like_count / max(like_count + dislike_count, 1) * 100,
                'avg_watch_time_seconds': float(avg_watch_time),
                'completion_rate': float(completion_rate)
            }