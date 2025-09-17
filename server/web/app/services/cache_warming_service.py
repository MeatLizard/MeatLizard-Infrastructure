"""
Cache Warming Service

Implements intelligent cache warming strategies for video metadata,
including scheduled warming of popular content and predictive caching.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from server.web.app.models import Video, ViewSession, VideoLike, VideoComment
from server.web.app.services.video_cache_service import VideoCacheService
from server.web.app.services.base_service import BaseService

logger = logging.getLogger(__name__)


@dataclass
class WarmingStrategy:
    """Configuration for cache warming strategy"""
    name: str
    enabled: bool = True
    interval_minutes: int = 60
    video_limit: int = 100
    priority: int = 1  # Lower number = higher priority


class CacheWarmingService(BaseService):
    """Service for intelligent cache warming"""
    
    def __init__(self, db: AsyncSession, cache_service: VideoCacheService):
        self.db = db
        self.cache_service = cache_service
        self._warming_tasks: Dict[str, asyncio.Task] = {}
        self._is_running = False
        
        # Define warming strategies
        self.strategies = {
            'popular_videos': WarmingStrategy(
                name='popular_videos',
                enabled=True,
                interval_minutes=30,
                video_limit=50,
                priority=1
            ),
            'trending_videos': WarmingStrategy(
                name='trending_videos',
                enabled=True,
                interval_minutes=15,
                video_limit=25,
                priority=2
            ),
            'recent_uploads': WarmingStrategy(
                name='recent_uploads',
                enabled=True,
                interval_minutes=60,
                video_limit=20,
                priority=3
            ),
            'user_favorites': WarmingStrategy(
                name='user_favorites',
                enabled=True,
                interval_minutes=120,
                video_limit=30,
                priority=4
            )
        }
    
    async def start_warming_scheduler(self):
        """Start the cache warming scheduler"""
        if self._is_running:
            logger.warning("Cache warming scheduler is already running")
            return
        
        self._is_running = True
        logger.info("Starting cache warming scheduler")
        
        # Start warming tasks for each enabled strategy
        for strategy_name, strategy in self.strategies.items():
            if strategy.enabled:
                task = asyncio.create_task(
                    self._run_warming_strategy(strategy_name, strategy)
                )
                self._warming_tasks[strategy_name] = task
        
        logger.info(f"Started {len(self._warming_tasks)} cache warming strategies")
    
    async def stop_warming_scheduler(self):
        """Stop the cache warming scheduler"""
        if not self._is_running:
            return
        
        self._is_running = False
        logger.info("Stopping cache warming scheduler")
        
        # Cancel all warming tasks
        for task_name, task in self._warming_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"Cancelled warming task: {task_name}")
        
        self._warming_tasks.clear()
        logger.info("Cache warming scheduler stopped")
    
    async def _run_warming_strategy(self, strategy_name: str, strategy: WarmingStrategy):
        """Run a specific warming strategy in a loop"""
        logger.info(f"Starting warming strategy: {strategy_name}")
        
        while self._is_running:
            try:
                start_time = datetime.utcnow()
                
                # Execute the warming strategy
                warmed_count = await self._execute_strategy(strategy_name, strategy)
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                logger.info(
                    f"Strategy '{strategy_name}' warmed {warmed_count} videos "
                    f"in {execution_time:.2f} seconds"
                )
                
                # Wait for the next interval
                await asyncio.sleep(strategy.interval_minutes * 60)
                
            except asyncio.CancelledError:
                logger.info(f"Warming strategy '{strategy_name}' cancelled")
                break
            except Exception as e:
                logger.error(f"Error in warming strategy '{strategy_name}': {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)
    
    async def _execute_strategy(self, strategy_name: str, strategy: WarmingStrategy) -> int:
        """Execute a specific warming strategy"""
        if strategy_name == 'popular_videos':
            return await self._warm_popular_videos(strategy.video_limit)
        elif strategy_name == 'trending_videos':
            return await self._warm_trending_videos(strategy.video_limit)
        elif strategy_name == 'recent_uploads':
            return await self._warm_recent_uploads(strategy.video_limit)
        elif strategy_name == 'user_favorites':
            return await self._warm_user_favorites(strategy.video_limit)
        else:
            logger.warning(f"Unknown warming strategy: {strategy_name}")
            return 0
    
    async def _warm_popular_videos(self, limit: int) -> int:
        """Warm cache for popular videos based on view count"""
        try:
            # Get videos with highest view counts in the last 30 days
            since_time = datetime.utcnow() - timedelta(days=30)
            
            stmt = (
                select(Video.id, func.count(ViewSession.id).label('view_count'))
                .outerjoin(ViewSession, and_(
                    ViewSession.video_id == Video.id,
                    ViewSession.started_at >= since_time
                ))
                .where(Video.visibility == 'public')
                .group_by(Video.id)
                .order_by(func.count(ViewSession.id).desc())
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            video_ids = [str(video_id) for video_id, _ in result]
            
            # Warm cache for each video
            warmed_count = 0
            for video_id in video_ids:
                if await self.cache_service.warm_cache_for_video(video_id):
                    warmed_count += 1
            
            return warmed_count
            
        except Exception as e:
            logger.error(f"Error warming popular videos: {e}")
            return 0
    
    async def _warm_trending_videos(self, limit: int) -> int:
        """Warm cache for trending videos based on recent engagement"""
        try:
            # Get videos with highest engagement in the last 24 hours
            since_time = datetime.utcnow() - timedelta(hours=24)
            
            stmt = (
                select(
                    Video.id,
                    (func.count(ViewSession.id) * 1.0 + 
                     func.count(VideoLike.id) * 2.0 + 
                     func.count(VideoComment.id) * 3.0).label('engagement_score')
                )
                .outerjoin(ViewSession, and_(
                    ViewSession.video_id == Video.id,
                    ViewSession.started_at >= since_time
                ))
                .outerjoin(VideoLike, and_(
                    VideoLike.video_id == Video.id,
                    VideoLike.created_at >= since_time
                ))
                .outerjoin(VideoComment, and_(
                    VideoComment.video_id == Video.id,
                    VideoComment.created_at >= since_time
                ))
                .where(Video.visibility == 'public')
                .group_by(Video.id)
                .order_by(desc('engagement_score'))
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            video_ids = [str(video_id) for video_id, _ in result]
            
            # Warm cache for each video
            warmed_count = 0
            for video_id in video_ids:
                if await self.cache_service.warm_cache_for_video(video_id):
                    warmed_count += 1
            
            return warmed_count
            
        except Exception as e:
            logger.error(f"Error warming trending videos: {e}")
            return 0
    
    async def _warm_recent_uploads(self, limit: int) -> int:
        """Warm cache for recently uploaded videos"""
        try:
            # Get most recent public videos
            stmt = (
                select(Video.id)
                .where(Video.visibility == 'public')
                .order_by(Video.created_at.desc())
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            video_ids = [str(video_id) for (video_id,) in result]
            
            # Warm cache for each video
            warmed_count = 0
            for video_id in video_ids:
                if await self.cache_service.warm_cache_for_video(video_id):
                    warmed_count += 1
            
            return warmed_count
            
        except Exception as e:
            logger.error(f"Error warming recent uploads: {e}")
            return 0
    
    async def _warm_user_favorites(self, limit: int) -> int:
        """Warm cache for videos that users frequently interact with"""
        try:
            # Get videos with highest like-to-view ratio
            since_time = datetime.utcnow() - timedelta(days=7)
            
            stmt = (
                select(
                    Video.id,
                    func.count(VideoLike.id).label('like_count'),
                    func.count(ViewSession.id).label('view_count')
                )
                .outerjoin(VideoLike, VideoLike.video_id == Video.id)
                .outerjoin(ViewSession, and_(
                    ViewSession.video_id == Video.id,
                    ViewSession.started_at >= since_time
                ))
                .where(Video.visibility == 'public')
                .group_by(Video.id)
                .having(func.count(ViewSession.id) > 5)  # Minimum view threshold
                .order_by(
                    (func.count(VideoLike.id).cast(float) / 
                     func.greatest(func.count(ViewSession.id), 1)).desc()
                )
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            video_ids = [str(video_id) for video_id, _, _ in result]
            
            # Warm cache for each video
            warmed_count = 0
            for video_id in video_ids:
                if await self.cache_service.warm_cache_for_video(video_id):
                    warmed_count += 1
            
            return warmed_count
            
        except Exception as e:
            logger.error(f"Error warming user favorites: {e}")
            return 0
    
    async def warm_video_on_demand(self, video_id: str) -> bool:
        """
        Warm cache for a specific video immediately
        
        Args:
            video_id: Video ID to warm
            
        Returns:
            True if successful, False otherwise
        """
        return await self.cache_service.warm_cache_for_video(video_id)
    
    async def warm_user_videos(self, user_id: str, limit: int = 20) -> int:
        """
        Warm cache for a user's videos
        
        Args:
            user_id: User ID
            limit: Maximum number of videos to warm
            
        Returns:
            Number of videos successfully warmed
        """
        try:
            # Get user's most recent videos
            stmt = (
                select(Video.id)
                .where(Video.creator_id == user_id)
                .order_by(Video.created_at.desc())
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            video_ids = [str(video_id) for (video_id,) in result]
            
            # Warm cache for each video
            warmed_count = 0
            for video_id in video_ids:
                if await self.cache_service.warm_cache_for_video(video_id):
                    warmed_count += 1
            
            return warmed_count
            
        except Exception as e:
            logger.error(f"Error warming user videos for {user_id}: {e}")
            return 0
    
    async def get_warming_status(self) -> Dict[str, Any]:
        """
        Get status of cache warming operations
        
        Returns:
            Dictionary with warming status information
        """
        status = {
            'is_running': self._is_running,
            'active_strategies': len(self._warming_tasks),
            'strategies': {}
        }
        
        for strategy_name, strategy in self.strategies.items():
            task = self._warming_tasks.get(strategy_name)
            status['strategies'][strategy_name] = {
                'enabled': strategy.enabled,
                'interval_minutes': strategy.interval_minutes,
                'video_limit': strategy.video_limit,
                'priority': strategy.priority,
                'task_running': task is not None and not task.done() if task else False
            }
        
        return status
    
    async def update_strategy_config(
        self, 
        strategy_name: str, 
        config: Dict[str, Any]
    ) -> bool:
        """
        Update configuration for a warming strategy
        
        Args:
            strategy_name: Name of the strategy to update
            config: New configuration parameters
            
        Returns:
            True if successful, False otherwise
        """
        if strategy_name not in self.strategies:
            logger.error(f"Unknown warming strategy: {strategy_name}")
            return False
        
        try:
            strategy = self.strategies[strategy_name]
            
            # Update configuration
            if 'enabled' in config:
                strategy.enabled = config['enabled']
            if 'interval_minutes' in config:
                strategy.interval_minutes = max(1, config['interval_minutes'])
            if 'video_limit' in config:
                strategy.video_limit = max(1, config['video_limit'])
            if 'priority' in config:
                strategy.priority = max(1, config['priority'])
            
            # Restart the strategy if it's currently running
            if strategy_name in self._warming_tasks:
                old_task = self._warming_tasks[strategy_name]
                if not old_task.done():
                    old_task.cancel()
                
                if strategy.enabled and self._is_running:
                    new_task = asyncio.create_task(
                        self._run_warming_strategy(strategy_name, strategy)
                    )
                    self._warming_tasks[strategy_name] = new_task
                else:
                    del self._warming_tasks[strategy_name]
            
            logger.info(f"Updated warming strategy '{strategy_name}' configuration")
            return True
            
        except Exception as e:
            logger.error(f"Error updating strategy config for '{strategy_name}': {e}")
            return False
    
    async def force_warm_all_strategies(self) -> Dict[str, int]:
        """
        Force execution of all enabled warming strategies immediately
        
        Returns:
            Dictionary with strategy names and number of videos warmed
        """
        results = {}
        
        for strategy_name, strategy in self.strategies.items():
            if strategy.enabled:
                try:
                    warmed_count = await self._execute_strategy(strategy_name, strategy)
                    results[strategy_name] = warmed_count
                    logger.info(f"Force warmed {warmed_count} videos for strategy '{strategy_name}'")
                except Exception as e:
                    logger.error(f"Error force warming strategy '{strategy_name}': {e}")
                    results[strategy_name] = 0
        
        return results


# Dependency for FastAPI
async def get_cache_warming_service(
    db: AsyncSession,
    cache_service: VideoCacheService
) -> CacheWarmingService:
    """Get cache warming service instance"""
    return CacheWarmingService(db, cache_service)