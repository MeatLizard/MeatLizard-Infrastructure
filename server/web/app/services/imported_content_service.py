"""
Imported Content Management Service for handling attribution, organization, and policies.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.orm import selectinload

from ..models import Video, ImportJob, User, VideoStatus, VideoVisibility, ImportStatus
from .base_service import BaseService

logger = logging.getLogger(__name__)

class ImportedContentService(BaseService):
    """Service for managing imported content attribution and organization"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db)
    
    async def get_imported_videos(self, user_id: Optional[str] = None, 
                                platform: Optional[str] = None,
                                status: Optional[VideoStatus] = None,
                                limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get imported videos with attribution information"""
        try:
            # Build query for videos that have associated import jobs
            query = (
                select(Video, ImportJob)
                .join(ImportJob, Video.id == ImportJob.video_id)
                .options(
                    selectinload(Video.creator),
                    selectinload(ImportJob.requested_by_user)
                )
            )
            
            # Apply filters
            if user_id:
                query = query.where(Video.creator_id == user_id)
            
            if platform:
                query = query.where(ImportJob.platform == platform)
            
            if status:
                query = query.where(Video.status == status)
            
            # Order by creation date (newest first)
            query = query.order_by(Video.created_at.desc()).limit(limit).offset(offset)
            
            result = await self.db.execute(query)
            rows = result.all()
            
            # Format results with attribution
            imported_videos = []
            for video, import_job in rows:
                video_data = {
                    "id": str(video.id),
                    "title": video.title,
                    "description": video.description,
                    "status": video.status,
                    "visibility": video.visibility,
                    "created_at": video.created_at.isoformat(),
                    "duration_seconds": video.duration_seconds,
                    "file_size": video.file_size,
                    "thumbnail_s3_key": video.thumbnail_s3_key,
                    
                    # Attribution information
                    "attribution": {
                        "source_url": import_job.source_url,
                        "platform": import_job.platform,
                        "original_title": import_job.original_title,
                        "original_uploader": import_job.original_uploader,
                        "original_upload_date": import_job.original_upload_date.isoformat() if import_job.original_upload_date else None,
                        "original_duration": import_job.original_duration,
                        "original_view_count": import_job.original_view_count,
                        "original_like_count": import_job.original_like_count,
                        "import_date": import_job.created_at.isoformat(),
                        "imported_by": import_job.requested_by_user.display_label if import_job.requested_by_user else None
                    },
                    
                    # Import job information
                    "import_job": {
                        "id": str(import_job.id),
                        "status": import_job.status,
                        "progress_percent": import_job.progress_percent,
                        "error_message": import_job.error_message
                    }
                }
                
                imported_videos.append(video_data)
            
            return imported_videos
            
        except Exception as e:
            logger.error(f"Failed to get imported videos: {str(e)}")
            raise
    
    async def get_imported_video_by_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get specific imported video with full attribution"""
        try:
            result = await self.db.execute(
                select(Video, ImportJob)
                .join(ImportJob, Video.id == ImportJob.video_id)
                .options(
                    selectinload(Video.creator),
                    selectinload(ImportJob.requested_by_user)
                )
                .where(Video.id == video_id)
            )
            
            row = result.first()
            if not row:
                return None
            
            video, import_job = row
            
            return {
                "id": str(video.id),
                "title": video.title,
                "description": video.description,
                "tags": video.tags,
                "category": video.category,
                "status": video.status,
                "visibility": video.visibility,
                "created_at": video.created_at.isoformat(),
                "updated_at": video.updated_at.isoformat(),
                "duration_seconds": video.duration_seconds,
                "file_size": video.file_size,
                "source_resolution": video.source_resolution,
                "source_framerate": video.source_framerate,
                "source_codec": video.source_codec,
                "thumbnail_s3_key": video.thumbnail_s3_key,
                
                # Full attribution information
                "attribution": {
                    "source_url": import_job.source_url,
                    "platform": import_job.platform,
                    "original_title": import_job.original_title,
                    "original_description": import_job.original_description,
                    "original_uploader": import_job.original_uploader,
                    "original_upload_date": import_job.original_upload_date.isoformat() if import_job.original_upload_date else None,
                    "original_duration": import_job.original_duration,
                    "original_view_count": import_job.original_view_count,
                    "original_like_count": import_job.original_like_count,
                    "import_date": import_job.created_at.isoformat(),
                    "imported_by": import_job.requested_by_user.display_label if import_job.requested_by_user else None,
                    "import_config": import_job.import_config
                },
                
                # Creator information
                "creator": {
                    "id": str(video.creator.id),
                    "display_label": video.creator.display_label
                } if video.creator else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get imported video {video_id}: {str(e)}")
            raise
    
    async def update_imported_video_metadata(self, video_id: str, 
                                           title: Optional[str] = None,
                                           description: Optional[str] = None,
                                           tags: Optional[List[str]] = None,
                                           category: Optional[str] = None,
                                           visibility: Optional[VideoVisibility] = None,
                                           user_id: Optional[str] = None) -> bool:
        """Update metadata for imported video"""
        try:
            # Build update data
            update_data = {}
            if title is not None:
                update_data["title"] = title
            if description is not None:
                update_data["description"] = description
            if tags is not None:
                update_data["tags"] = tags
            if category is not None:
                update_data["category"] = category
            if visibility is not None:
                update_data["visibility"] = visibility
            
            if not update_data:
                return False
            
            update_data["updated_at"] = datetime.utcnow()
            
            # Build query
            query = update(Video).where(Video.id == video_id)
            
            # Add user authorization if provided
            if user_id:
                query = query.where(Video.creator_id == user_id)
            
            result = await self.db.execute(query.values(**update_data))
            await self.db.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update imported video metadata: {str(e)}")
            raise
    
    async def bulk_update_imported_videos(self, video_ids: List[str],
                                        visibility: Optional[VideoVisibility] = None,
                                        category: Optional[str] = None,
                                        user_id: Optional[str] = None) -> int:
        """Bulk update multiple imported videos"""
        try:
            update_data = {}
            if visibility is not None:
                update_data["visibility"] = visibility
            if category is not None:
                update_data["category"] = category
            
            if not update_data:
                return 0
            
            update_data["updated_at"] = datetime.utcnow()
            
            # Build query
            query = update(Video).where(Video.id.in_(video_ids))
            
            # Add user authorization if provided
            if user_id:
                query = query.where(Video.creator_id == user_id)
            
            result = await self.db.execute(query.values(**update_data))
            await self.db.commit()
            
            logger.info(f"Bulk updated {result.rowcount} imported videos")
            return result.rowcount
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to bulk update imported videos: {str(e)}")
            raise
    
    async def delete_imported_video(self, video_id: str, user_id: Optional[str] = None) -> bool:
        """Delete imported video and associated import job"""
        try:
            # Get video to check ownership
            video_query = select(Video).where(Video.id == video_id)
            if user_id:
                video_query = video_query.where(Video.creator_id == user_id)
            
            result = await self.db.execute(video_query)
            video = result.scalar_one_or_none()
            
            if not video:
                return False
            
            # Delete associated import job first (due to foreign key)
            await self.db.execute(
                delete(ImportJob).where(ImportJob.video_id == video_id)
            )
            
            # Delete video
            await self.db.execute(
                delete(Video).where(Video.id == video_id)
            )
            
            await self.db.commit()
            
            logger.info(f"Deleted imported video {video_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete imported video: {str(e)}")
            raise
    
    async def get_import_statistics(self, user_id: Optional[str] = None,
                                  days: int = 30) -> Dict[str, Any]:
        """Get import statistics for dashboard"""
        try:
            # Date range
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Base query for import jobs
            base_query = select(ImportJob).where(ImportJob.created_at >= start_date)
            if user_id:
                base_query = base_query.where(ImportJob.requested_by == user_id)
            
            # Get all import jobs in date range
            result = await self.db.execute(base_query)
            import_jobs = list(result.scalars().all())
            
            # Calculate statistics
            total_imports = len(import_jobs)
            successful_imports = len([j for j in import_jobs if j.status == ImportStatus.completed])
            failed_imports = len([j for j in import_jobs if j.status == ImportStatus.failed])
            pending_imports = len([j for j in import_jobs if j.status in [ImportStatus.queued, ImportStatus.downloading, ImportStatus.processing]])
            
            # Platform breakdown
            platform_stats = {}
            for job in import_jobs:
                platform = job.platform
                if platform not in platform_stats:
                    platform_stats[platform] = {"total": 0, "successful": 0, "failed": 0}
                
                platform_stats[platform]["total"] += 1
                if job.status == ImportStatus.completed:
                    platform_stats[platform]["successful"] += 1
                elif job.status == ImportStatus.failed:
                    platform_stats[platform]["failed"] += 1
            
            # Success rate by platform
            for platform, stats in platform_stats.items():
                if stats["total"] > 0:
                    stats["success_rate"] = (stats["successful"] / stats["total"]) * 100
                else:
                    stats["success_rate"] = 0
            
            return {
                "period_days": days,
                "total_imports": total_imports,
                "successful_imports": successful_imports,
                "failed_imports": failed_imports,
                "pending_imports": pending_imports,
                "success_rate": (successful_imports / total_imports * 100) if total_imports > 0 else 0,
                "platform_breakdown": platform_stats,
                "recent_imports": [
                    {
                        "id": str(job.id),
                        "platform": job.platform,
                        "original_title": job.original_title,
                        "status": job.status,
                        "created_at": job.created_at.isoformat()
                    }
                    for job in sorted(import_jobs, key=lambda x: x.created_at, reverse=True)[:10]
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get import statistics: {str(e)}")
            raise
    
    async def check_copyright_compliance(self, video_id: str) -> Dict[str, Any]:
        """Check copyright compliance for imported video"""
        try:
            # Get imported video with attribution
            video_data = await self.get_imported_video_by_id(video_id)
            if not video_data:
                raise ValueError("Video not found")
            
            attribution = video_data["attribution"]
            
            # Basic compliance checks
            compliance_issues = []
            
            # Check if source URL is still accessible
            # (This would require actual HTTP requests in a real implementation)
            
            # Check for required attribution fields
            if not attribution.get("original_uploader"):
                compliance_issues.append("Missing original uploader information")
            
            if not attribution.get("source_url"):
                compliance_issues.append("Missing source URL")
            
            # Check for platform-specific requirements
            platform = attribution.get("platform", "").lower()
            
            if platform == "youtube":
                # YouTube requires attribution to original creator
                if not attribution.get("original_title"):
                    compliance_issues.append("Missing original video title for YouTube content")
            
            elif platform == "tiktok":
                # TikTok content may have additional restrictions
                if not attribution.get("original_uploader"):
                    compliance_issues.append("Missing original creator for TikTok content")
            
            # Check video age (some platforms have time-based restrictions)
            if attribution.get("original_upload_date"):
                original_date = datetime.fromisoformat(attribution["original_upload_date"].replace('Z', '+00:00'))
                days_old = (datetime.utcnow() - original_date.replace(tzinfo=None)).days
                
                if days_old < 7:
                    compliance_issues.append("Content is very recent - consider additional review")
            
            return {
                "video_id": video_id,
                "compliant": len(compliance_issues) == 0,
                "issues": compliance_issues,
                "attribution_complete": all([
                    attribution.get("source_url"),
                    attribution.get("original_uploader"),
                    attribution.get("platform")
                ]),
                "recommendations": self._get_compliance_recommendations(platform, compliance_issues)
            }
            
        except Exception as e:
            logger.error(f"Failed to check copyright compliance: {str(e)}")
            raise
    
    async def generate_attribution_text(self, video_id: str, format_type: str = "standard") -> str:
        """Generate attribution text for imported video"""
        try:
            video_data = await self.get_imported_video_by_id(video_id)
            if not video_data:
                raise ValueError("Video not found")
            
            attribution = video_data["attribution"]
            
            if format_type == "standard":
                return self._format_standard_attribution(attribution)
            elif format_type == "youtube":
                return self._format_youtube_attribution(attribution)
            elif format_type == "academic":
                return self._format_academic_attribution(attribution)
            else:
                return self._format_standard_attribution(attribution)
                
        except Exception as e:
            logger.error(f"Failed to generate attribution text: {str(e)}")
            raise
    
    async def organize_imported_content(self, organization_type: str = "platform",
                                      user_id: Optional[str] = None) -> Dict[str, Any]:
        """Organize imported content by various criteria"""
        try:
            imported_videos = await self.get_imported_videos(user_id=user_id, limit=1000)
            
            if organization_type == "platform":
                return self._organize_by_platform(imported_videos)
            elif organization_type == "date":
                return self._organize_by_date(imported_videos)
            elif organization_type == "uploader":
                return self._organize_by_uploader(imported_videos)
            elif organization_type == "status":
                return self._organize_by_status(imported_videos)
            else:
                raise ValueError(f"Unknown organization type: {organization_type}")
                
        except Exception as e:
            logger.error(f"Failed to organize imported content: {str(e)}")
            raise
    
    def _get_compliance_recommendations(self, platform: str, issues: List[str]) -> List[str]:
        """Get compliance recommendations based on platform and issues"""
        recommendations = []
        
        if "Missing original uploader information" in issues:
            recommendations.append("Add original creator attribution in video description")
        
        if "Missing source URL" in issues:
            recommendations.append("Include link to original content")
        
        if platform.lower() == "youtube":
            recommendations.append("Consider reaching out to original creator for permission")
            recommendations.append("Ensure compliance with YouTube's Terms of Service")
        
        elif platform.lower() == "tiktok":
            recommendations.append("Verify TikTok creator consent for reposting")
            recommendations.append("Consider fair use implications")
        
        if not recommendations:
            recommendations.append("Content appears compliant - monitor for any changes")
        
        return recommendations
    
    def _format_standard_attribution(self, attribution: Dict[str, Any]) -> str:
        """Format standard attribution text"""
        parts = []
        
        if attribution.get("original_title"):
            parts.append(f'"{attribution["original_title"]}"')
        
        if attribution.get("original_uploader"):
            parts.append(f"by {attribution['original_uploader']}")
        
        if attribution.get("platform"):
            parts.append(f"on {attribution['platform']}")
        
        if attribution.get("source_url"):
            parts.append(f"({attribution['source_url']})")
        
        return " ".join(parts)
    
    def _format_youtube_attribution(self, attribution: Dict[str, Any]) -> str:
        """Format YouTube-style attribution"""
        return f"Original video: {attribution.get('source_url', 'Unknown')} by {attribution.get('original_uploader', 'Unknown Creator')}"
    
    def _format_academic_attribution(self, attribution: Dict[str, Any]) -> str:
        """Format academic-style attribution"""
        uploader = attribution.get("original_uploader", "Unknown")
        title = attribution.get("original_title", "Untitled")
        platform = attribution.get("platform", "Unknown Platform")
        url = attribution.get("source_url", "")
        
        upload_date = "n.d."
        if attribution.get("original_upload_date"):
            try:
                date_obj = datetime.fromisoformat(attribution["original_upload_date"].replace('Z', '+00:00'))
                upload_date = date_obj.strftime("%Y, %B %d")
            except:
                pass
        
        return f'{uploader}. ({upload_date}). {title} [{platform} video]. {url}'
    
    def _organize_by_platform(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Organize videos by platform"""
        organized = {}
        
        for video in videos:
            platform = video["attribution"]["platform"]
            if platform not in organized:
                organized[platform] = []
            organized[platform].append(video)
        
        return {
            "organization_type": "platform",
            "groups": organized,
            "summary": {platform: len(videos) for platform, videos in organized.items()}
        }
    
    def _organize_by_date(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Organize videos by import date"""
        organized = {}
        
        for video in videos:
            import_date = datetime.fromisoformat(video["attribution"]["import_date"])
            date_key = import_date.strftime("%Y-%m")
            
            if date_key not in organized:
                organized[date_key] = []
            organized[date_key].append(video)
        
        return {
            "organization_type": "date",
            "groups": organized,
            "summary": {date: len(videos) for date, videos in organized.items()}
        }
    
    def _organize_by_uploader(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Organize videos by original uploader"""
        organized = {}
        
        for video in videos:
            uploader = video["attribution"]["original_uploader"] or "Unknown"
            if uploader not in organized:
                organized[uploader] = []
            organized[uploader].append(video)
        
        return {
            "organization_type": "uploader",
            "groups": organized,
            "summary": {uploader: len(videos) for uploader, videos in organized.items()}
        }
    
    def _organize_by_status(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Organize videos by status"""
        organized = {}
        
        for video in videos:
            status = video["status"]
            if status not in organized:
                organized[status] = []
            organized[status].append(video)
        
        return {
            "organization_type": "status",
            "groups": organized,
            "summary": {status: len(videos) for status, videos in organized.items()}
        }