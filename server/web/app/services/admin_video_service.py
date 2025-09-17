"""
Admin video management service for video platform administration.
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from .base_service import BaseService
from ..models import (
    Video, TranscodingJob, User, Channel, ViewSession, VideoComment, VideoLike,
    VideoStatus, TranscodingStatus, VideoVisibility, ContentReport, ModerationRecord
)


class AdminVideoService(BaseService):
    """Service for administrative video management operations."""
    
    async def get_video_dashboard_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get comprehensive video platform statistics for admin dashboard."""
        
        # Total videos by status
        video_stats_query = select(
            Video.status,
            func.count(Video.id).label('count')
        ).group_by(Video.status)
        video_stats_result = await db.execute(video_stats_query)
        video_stats = {row.status.value: row.count for row in video_stats_result}
        
        # Total transcoding jobs by status
        transcoding_stats_query = select(
            TranscodingJob.status,
            func.count(TranscodingJob.id).label('count')
        ).group_by(TranscodingJob.status)
        transcoding_stats_result = await db.execute(transcoding_stats_query)
        transcoding_stats = {row.status.value: row.count for row in transcoding_stats_result}
        
        # Storage usage
        storage_query = select(
            func.sum(Video.file_size).label('total_original_size'),
            func.sum(TranscodingJob.output_file_size).label('total_transcoded_size'),
            func.count(Video.id).label('total_videos')
        )
        storage_result = await db.execute(storage_query)
        storage_data = storage_result.first()
        
        # Recent activity (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_uploads_query = select(func.count(Video.id)).where(
            Video.created_at >= yesterday
        )
        recent_uploads = await db.scalar(recent_uploads_query)
        
        recent_views_query = select(func.count(ViewSession.id)).where(
            ViewSession.started_at >= yesterday
        )
        recent_views = await db.scalar(recent_views_query)
        
        # Failed jobs needing attention
        failed_jobs_query = select(func.count(TranscodingJob.id)).where(
            TranscodingJob.status == TranscodingStatus.failed
        )
        failed_jobs = await db.scalar(failed_jobs_query)
        
        return {
            'video_stats': video_stats,
            'transcoding_stats': transcoding_stats,
            'storage': {
                'total_original_gb': round((storage_data.total_original_size or 0) / (1024**3), 2),
                'total_transcoded_gb': round((storage_data.total_transcoded_size or 0) / (1024**3), 2),
                'total_videos': storage_data.total_videos or 0
            },
            'recent_activity': {
                'uploads_24h': recent_uploads or 0,
                'views_24h': recent_views or 0,
                'failed_jobs': failed_jobs or 0
            }
        }
    
    async def get_videos_list(
        self,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 50,
        status_filter: Optional[VideoStatus] = None,
        visibility_filter: Optional[VideoVisibility] = None,
        creator_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        sort_by: str = 'created_at',
        sort_order: str = 'desc'
    ) -> Dict[str, Any]:
        """Get paginated list of videos with filtering and sorting."""
        
        # Build base query
        query = select(Video).options(
            joinedload(Video.creator),
            joinedload(Video.channel),
            selectinload(Video.transcoding_jobs)
        )
        
        # Apply filters
        if status_filter:
            query = query.where(Video.status == status_filter)
        
        if visibility_filter:
            query = query.where(Video.visibility == visibility_filter)
        
        if creator_filter:
            query = query.join(User).where(
                or_(
                    User.display_label.ilike(f'%{creator_filter}%'),
                    User.email.ilike(f'%{creator_filter}%')
                )
            )
        
        if search_query:
            query = query.where(
                or_(
                    Video.title.ilike(f'%{search_query}%'),
                    Video.description.ilike(f'%{search_query}%')
                )
            )
        
        # Apply sorting
        sort_column = getattr(Video, sort_by, Video.created_at)
        if sort_order == 'desc':
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_count = await db.scalar(count_query)
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        result = await db.execute(query)
        videos = result.scalars().all()
        
        # Format video data
        video_data = []
        for video in videos:
            # Get transcoding job summary
            transcoding_summary = {
                'total_jobs': len(video.transcoding_jobs),
                'completed_jobs': len([j for j in video.transcoding_jobs if j.status == TranscodingStatus.completed]),
                'failed_jobs': len([j for j in video.transcoding_jobs if j.status == TranscodingStatus.failed]),
                'processing_jobs': len([j for j in video.transcoding_jobs if j.status == TranscodingStatus.processing])
            }
            
            video_data.append({
                'id': str(video.id),
                'title': video.title,
                'creator': {
                    'id': str(video.creator.id),
                    'display_label': video.creator.display_label,
                    'email': video.creator.email
                },
                'channel': {
                    'id': str(video.channel.id) if video.channel else None,
                    'name': video.channel.name if video.channel else None
                } if video.channel else None,
                'status': video.status.value,
                'visibility': video.visibility.value,
                'file_size_mb': round(video.file_size / (1024**2), 2),
                'duration_seconds': video.duration_seconds,
                'source_resolution': video.source_resolution,
                'created_at': video.created_at.isoformat(),
                'transcoding_summary': transcoding_summary
            })
        
        return {
            'videos': video_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        }
    
    async def get_video_details(self, db: AsyncSession, video_id: uuid.UUID) -> Dict[str, Any]:
        """Get detailed information about a specific video."""
        
        query = select(Video).options(
            joinedload(Video.creator),
            joinedload(Video.channel),
            selectinload(Video.transcoding_jobs),
            selectinload(Video.view_sessions),
            selectinload(Video.comments).selectinload(VideoComment.user),
            selectinload(Video.likes).selectinload(VideoLike.user)
        ).where(Video.id == video_id)
        
        result = await db.execute(query)
        video = result.scalar_one_or_none()
        
        if not video:
            return None
        
        # Calculate view statistics
        total_views = len(video.view_sessions)
        total_watch_time = sum(session.total_watch_time_seconds for session in video.view_sessions)
        avg_completion = sum(session.completion_percentage for session in video.view_sessions) / len(video.view_sessions) if video.view_sessions else 0
        
        # Calculate engagement statistics
        likes = len([like for like in video.likes if like.is_like])
        dislikes = len([like for like in video.likes if not like.is_like])
        comments_count = len([comment for comment in video.comments if not comment.is_deleted])
        
        # Format transcoding jobs
        transcoding_jobs = []
        for job in video.transcoding_jobs:
            transcoding_jobs.append({
                'id': str(job.id),
                'quality_preset': job.quality_preset,
                'target_resolution': job.target_resolution,
                'target_framerate': job.target_framerate,
                'status': job.status.value,
                'progress_percent': job.progress_percent,
                'error_message': job.error_message,
                'output_file_size_mb': round(job.output_file_size / (1024**2), 2) if job.output_file_size else None,
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None
            })
        
        return {
            'id': str(video.id),
            'title': video.title,
            'description': video.description,
            'tags': video.tags,
            'category': video.category,
            'creator': {
                'id': str(video.creator.id),
                'display_label': video.creator.display_label,
                'email': video.creator.email
            },
            'channel': {
                'id': str(video.channel.id) if video.channel else None,
                'name': video.channel.name if video.channel else None,
                'slug': video.channel.slug if video.channel else None
            } if video.channel else None,
            'file_info': {
                'original_filename': video.original_filename,
                'file_size_mb': round(video.file_size / (1024**2), 2),
                'duration_seconds': video.duration_seconds,
                'source_resolution': video.source_resolution,
                'source_framerate': video.source_framerate,
                'source_codec': video.source_codec,
                'source_bitrate': video.source_bitrate
            },
            'status': video.status.value,
            'visibility': video.visibility.value,
            'created_at': video.created_at.isoformat(),
            'updated_at': video.updated_at.isoformat(),
            'statistics': {
                'total_views': total_views,
                'total_watch_time_hours': round(total_watch_time / 3600, 2),
                'average_completion_percent': round(avg_completion, 2),
                'likes': likes,
                'dislikes': dislikes,
                'comments': comments_count
            },
            'transcoding_jobs': transcoding_jobs
        }
    
    async def retry_failed_transcoding_job(self, db: AsyncSession, job_id: uuid.UUID) -> bool:
        """Retry a failed transcoding job."""
        
        query = select(TranscodingJob).where(TranscodingJob.id == job_id)
        result = await db.execute(query)
        job = result.scalar_one_or_none()
        
        if not job or job.status != TranscodingStatus.failed:
            return False
        
        # Reset job status for retry
        job.status = TranscodingStatus.queued
        job.progress_percent = 0
        job.error_message = None
        job.started_at = None
        job.completed_at = None
        
        await db.commit()
        
        # TODO: Trigger transcoding queue processing
        # This would typically involve sending a message to a job queue
        
        return True
    
    async def bulk_update_video_visibility(
        self,
        db: AsyncSession,
        video_ids: List[uuid.UUID],
        visibility: VideoVisibility
    ) -> int:
        """Update visibility for multiple videos."""
        
        from sqlalchemy import update
        
        stmt = update(Video).where(
            Video.id.in_(video_ids)
        ).values(
            visibility=visibility,
            updated_at=datetime.utcnow()
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        return result.rowcount
    
    async def bulk_delete_videos(self, db: AsyncSession, video_ids: List[uuid.UUID]) -> int:
        """Mark multiple videos as deleted."""
        
        from sqlalchemy import update
        
        stmt = update(Video).where(
            Video.id.in_(video_ids)
        ).values(
            status=VideoStatus.deleted,
            updated_at=datetime.utcnow()
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        # TODO: Trigger cleanup of S3 files
        # This would typically involve sending messages to a cleanup queue
        
        return result.rowcount
    
    async def get_storage_usage_report(self, db: AsyncSession) -> Dict[str, Any]:
        """Generate detailed storage usage report."""
        
        # Storage by video status
        status_storage_query = select(
            Video.status,
            func.count(Video.id).label('video_count'),
            func.sum(Video.file_size).label('total_size')
        ).group_by(Video.status)
        
        status_storage_result = await db.execute(status_storage_query)
        status_storage = []
        for row in status_storage_result:
            status_storage.append({
                'status': row.status.value,
                'video_count': row.video_count,
                'size_gb': round((row.total_size or 0) / (1024**3), 2)
            })
        
        # Storage by creator (top 10)
        creator_storage_query = select(
            User.display_label,
            User.email,
            func.count(Video.id).label('video_count'),
            func.sum(Video.file_size).label('total_size')
        ).join(Video).group_by(
            User.id, User.display_label, User.email
        ).order_by(
            desc(func.sum(Video.file_size))
        ).limit(10)
        
        creator_storage_result = await db.execute(creator_storage_query)
        creator_storage = []
        for row in creator_storage_result:
            creator_storage.append({
                'creator': row.display_label,
                'email': row.email,
                'video_count': row.video_count,
                'size_gb': round((row.total_size or 0) / (1024**3), 2)
            })
        
        # Transcoded storage by quality
        quality_storage_query = select(
            TranscodingJob.quality_preset,
            func.count(TranscodingJob.id).label('job_count'),
            func.sum(TranscodingJob.output_file_size).label('total_size')
        ).where(
            TranscodingJob.status == TranscodingStatus.completed
        ).group_by(TranscodingJob.quality_preset)
        
        quality_storage_result = await db.execute(quality_storage_query)
        quality_storage = []
        for row in quality_storage_result:
            quality_storage.append({
                'quality_preset': row.quality_preset,
                'job_count': row.job_count,
                'size_gb': round((row.total_size or 0) / (1024**3), 2)
            })
        
        return {
            'storage_by_status': status_storage,
            'storage_by_creator': creator_storage,
            'storage_by_quality': quality_storage
        }
    
    async def get_user_management_data(self, db: AsyncSession) -> Dict[str, Any]:
        """Get user management data for admin dashboard."""
        
        # Total users and creators
        total_users_query = select(func.count(User.id))
        total_users = await db.scalar(total_users_query)
        
        # Users with videos (content creators)
        creators_query = select(func.count(func.distinct(Video.creator_id)))
        total_creators = await db.scalar(creators_query)
        
        # Top content creators by video count
        top_creators_query = select(
            User.display_label,
            User.email,
            func.count(Video.id).label('video_count'),
            func.sum(Video.file_size).label('total_storage')
        ).join(Video).group_by(
            User.id, User.display_label, User.email
        ).order_by(
            func.count(Video.id).desc()
        ).limit(10)
        
        top_creators_result = await db.execute(top_creators_query)
        top_creators = []
        for row in top_creators_result:
            top_creators.append({
                'name': row.display_label,
                'email': row.email,
                'video_count': row.video_count,
                'storage_gb': round((row.total_storage or 0) / (1024**3), 2)
            })
        
        # Recent user registrations (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_users_query = select(func.count(User.id)).where(
            User.created_at >= thirty_days_ago
        )
        recent_users = await db.scalar(recent_users_query)
        
        return {
            'total_users': total_users,
            'total_creators': total_creators,
            'top_creators': top_creators,
            'recent_registrations_30d': recent_users
        }
    
    async def manage_user_access(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        action: str,
        reason: Optional[str] = None,
        duration_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """Manage user access (suspend, ban, etc.)."""
        
        # Get user
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return {
                'success': False,
                'error': 'user_not_found',
                'message': 'User not found'
            }
        
        # Apply action based on type
        if action == 'suspend':
            user.is_active = False
            # TODO: Add suspension expiry logic
        elif action == 'ban':
            user.is_active = False
            # TODO: Add permanent ban flag
        elif action == 'activate':
            user.is_active = True
        else:
            return {
                'success': False,
                'error': 'invalid_action',
                'message': f'Invalid action: {action}'
            }
        
        await db.commit()
        
        # TODO: Log the admin action for audit trail
        
        return {
            'success': True,
            'message': f'User {action} applied successfully',
            'user_id': str(user_id),
            'action': action
        }
    
    async def get_content_reports_summary(self, db: AsyncSession) -> Dict[str, Any]:
        """Get summary of content reports for admin dashboard."""
        
        # Import here to avoid circular imports
        from ..models import ContentReport, ModerationRecord
        
        # Total reports by status
        reports_by_status_query = select(
            ContentReport.status,
            func.count(ContentReport.id).label('count')
        ).group_by(ContentReport.status)
        
        reports_by_status_result = await db.execute(reports_by_status_query)
        reports_by_status = {row.status: row.count for row in reports_by_status_result}
        
        # Reports by content type
        reports_by_type_query = select(
            ContentReport.content_type,
            func.count(ContentReport.id).label('count')
        ).group_by(ContentReport.content_type)
        
        reports_by_type_result = await db.execute(reports_by_type_query)
        reports_by_type = {row.content_type: row.count for row in reports_by_type_result}
        
        # Recent moderation actions (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_actions_query = select(func.count(ModerationRecord.id)).where(
            ModerationRecord.created_at >= week_ago
        )
        recent_actions = await db.scalar(recent_actions_query)
        
        # Pending reports needing attention
        pending_reports_query = select(func.count(ContentReport.id)).where(
            ContentReport.status == 'pending'
        )
        pending_reports = await db.scalar(pending_reports_query)
        
        return {
            'reports_by_status': reports_by_status,
            'reports_by_type': reports_by_type,
            'recent_actions_7d': recent_actions or 0,
            'pending_reports': pending_reports or 0
        }
    
    async def get_transcoding_queue_status(self, db: AsyncSession) -> Dict[str, Any]:
        """Get current transcoding queue status and performance metrics."""
        
        # Queue status
        queue_status_query = select(
            TranscodingJob.status,
            func.count(TranscodingJob.id).label('count')
        ).group_by(TranscodingJob.status)
        
        queue_status_result = await db.execute(queue_status_query)
        queue_status = {row.status.value: row.count for row in queue_status_result}
        
        # Recent performance (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        recent_completed_query = select(
            func.count(TranscodingJob.id).label('completed_count'),
            func.avg(
                func.extract('epoch', TranscodingJob.completed_at - TranscodingJob.started_at)
            ).label('avg_duration_seconds')
        ).where(
            and_(
                TranscodingJob.status == TranscodingStatus.completed,
                TranscodingJob.completed_at >= yesterday
            )
        )
        
        recent_completed_result = await db.execute(recent_completed_query)
        recent_completed = recent_completed_result.first()
        
        # Failed jobs with errors
        failed_jobs_query = select(
            TranscodingJob.error_message,
            func.count(TranscodingJob.id).label('count')
        ).where(
            TranscodingJob.status == TranscodingStatus.failed
        ).group_by(TranscodingJob.error_message).limit(10)
        
        failed_jobs_result = await db.execute(failed_jobs_query)
        failed_jobs_errors = []
        for row in failed_jobs_result:
            failed_jobs_errors.append({
                'error_message': row.error_message,
                'count': row.count
            })
        
        return {
            'queue_status': queue_status,
            'recent_performance': {
                'completed_24h': recent_completed.completed_count or 0,
                'avg_duration_minutes': round((recent_completed.avg_duration_seconds or 0) / 60, 2)
            },
            'common_errors': failed_jobs_errors
        }