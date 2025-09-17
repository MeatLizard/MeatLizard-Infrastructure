"""
Media Import API endpoints for yt-dlp integration.
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db, get_current_user
from ..models import User, ImportJob, ImportPreset, ImportStatus
from ..services.media_import_service import (
    MediaImportService, ImportConfig, MediaInfo, MediaExtractionError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["media_import"])

# Request/Response Models

class ImportJobRequest(BaseModel):
    """Request model for creating import job"""
    url: HttpUrl
    config: ImportConfig
    discord_channel_id: Optional[str] = None
    discord_message_id: Optional[str] = None

class ImportJobResponse(BaseModel):
    """Response model for import job"""
    id: str
    source_url: str
    platform: str
    status: ImportStatus
    progress_percent: int
    error_message: Optional[str] = None
    original_title: Optional[str] = None
    original_uploader: Optional[str] = None
    video_id: Optional[str] = None
    created_at: str
    
    class Config:
        from_attributes = True

class MediaInfoResponse(BaseModel):
    """Response model for media info extraction"""
    title: str
    description: Optional[str] = None
    uploader: str
    upload_date: Optional[str] = None
    duration: Optional[float] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    thumbnail_url: Optional[str] = None
    platform: str
    available_formats: List[dict] = Field(default_factory=list)

class ImportPresetRequest(BaseModel):
    """Request model for creating import preset"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    config: ImportConfig

class ImportPresetResponse(BaseModel):
    """Response model for import preset"""
    id: str
    name: str
    description: Optional[str] = None
    config: ImportConfig
    is_default: bool
    created_at: str
    
    class Config:
        from_attributes = True

# API Endpoints

@router.post("/extract-info", response_model=MediaInfoResponse)
async def extract_media_info(
    url: HttpUrl,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Extract media information from URL"""
    try:
        service = MediaImportService(db)
        
        # Check if URL is supported
        if not service.is_supported_url(str(url)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL from unsupported platform"
            )
        
        # Extract media info
        media_info = await service.extract_media_info(str(url))
        
        return MediaInfoResponse(
            title=media_info.title,
            description=media_info.description,
            uploader=media_info.uploader,
            upload_date=media_info.upload_date.isoformat() if media_info.upload_date else None,
            duration=media_info.duration,
            view_count=media_info.view_count,
            like_count=media_info.like_count,
            thumbnail_url=media_info.thumbnail_url,
            platform=media_info.platform,
            available_formats=media_info.available_formats[:10]  # Limit to first 10 formats
        )
        
    except MediaExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to extract media info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extract media information"
        )

@router.post("/jobs", response_model=ImportJobResponse)
async def create_import_job(
    request: ImportJobRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new import job"""
    try:
        service = MediaImportService(db)
        
        # Check if URL is supported
        if not service.is_supported_url(str(request.url)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL from unsupported platform"
            )
        
        # Create import job
        job = await service.create_import_job(
            url=str(request.url),
            config=request.config,
            user_id=str(current_user.id),
            discord_channel_id=request.discord_channel_id,
            discord_message_id=request.discord_message_id
        )
        
        # TODO: Queue job for processing
        # This would be handled by the job queue service
        
        return ImportJobResponse(
            id=str(job.id),
            source_url=job.source_url,
            platform=job.platform,
            status=job.status,
            progress_percent=job.progress_percent,
            error_message=job.error_message,
            original_title=job.original_title,
            original_uploader=job.original_uploader,
            video_id=str(job.video_id) if job.video_id else None,
            created_at=job.created_at.isoformat()
        )
        
    except MediaExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create import job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create import job"
        )

@router.get("/jobs", response_model=List[ImportJobResponse])
async def get_import_jobs(
    status: Optional[ImportStatus] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get import jobs for current user"""
    try:
        service = MediaImportService(db)
        
        jobs = await service.get_import_jobs(
            user_id=str(current_user.id),
            status=status,
            limit=limit,
            offset=offset
        )
        
        return [
            ImportJobResponse(
                id=str(job.id),
                source_url=job.source_url,
                platform=job.platform,
                status=job.status,
                progress_percent=job.progress_percent,
                error_message=job.error_message,
                original_title=job.original_title,
                original_uploader=job.original_uploader,
                video_id=str(job.video_id) if job.video_id else None,
                created_at=job.created_at.isoformat()
            )
            for job in jobs
        ]
        
    except Exception as e:
        logger.error(f"Failed to get import jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get import jobs"
        )

@router.get("/jobs/{job_id}", response_model=ImportJobResponse)
async def get_import_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific import job"""
    try:
        service = MediaImportService(db)
        
        jobs = await service.get_import_jobs(
            user_id=str(current_user.id),
            limit=1,
            offset=0
        )
        
        job = next((j for j in jobs if j.id == job_id), None)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Import job not found"
            )
        
        return ImportJobResponse(
            id=str(job.id),
            source_url=job.source_url,
            platform=job.platform,
            status=job.status,
            progress_percent=job.progress_percent,
            error_message=job.error_message,
            original_title=job.original_title,
            original_uploader=job.original_uploader,
            video_id=str(job.video_id) if job.video_id else None,
            created_at=job.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get import job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get import job"
        )

@router.post("/presets", response_model=ImportPresetResponse)
async def create_import_preset(
    request: ImportPresetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new import preset"""
    try:
        service = MediaImportService(db)
        
        preset = await service.create_import_preset(
            name=request.name,
            description=request.description,
            config=request.config,
            user_id=str(current_user.id)
        )
        
        return ImportPresetResponse(
            id=str(preset.id),
            name=preset.name,
            description=preset.description,
            config=ImportConfig(**preset.config),
            is_default=preset.is_default,
            created_at=preset.created_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to create import preset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create import preset"
        )

@router.get("/presets", response_model=List[ImportPresetResponse])
async def get_import_presets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get import presets for current user"""
    try:
        service = MediaImportService(db)
        
        presets = await service.get_import_presets(user_id=str(current_user.id))
        
        return [
            ImportPresetResponse(
                id=str(preset.id),
                name=preset.name,
                description=preset.description,
                config=ImportConfig(**preset.config),
                is_default=preset.is_default,
                created_at=preset.created_at.isoformat()
            )
            for preset in presets
        ]
        
    except Exception as e:
        logger.error(f"Failed to get import presets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get import presets"
        )

@router.put("/presets/{preset_id}", response_model=ImportPresetResponse)
async def update_import_preset(
    preset_id: UUID,
    request: ImportPresetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an existing import preset"""
    try:
        from ..services.import_config_service import ImportConfigService
        
        service = ImportConfigService(db)
        
        preset = await service.update_preset(
            preset_id=str(preset_id),
            name=request.name,
            description=request.description,
            config=request.config,
            user_id=str(current_user.id)
        )
        
        return ImportPresetResponse(
            id=str(preset.id),
            name=preset.name,
            description=preset.description,
            config=ImportConfig(**preset.config),
            is_default=preset.is_default,
            created_at=preset.created_at.isoformat()
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update import preset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update import preset"
        )

@router.delete("/presets/{preset_id}")
async def delete_import_preset(
    preset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an import preset"""
    try:
        from ..services.import_config_service import ImportConfigService
        
        service = ImportConfigService(db)
        
        success = await service.delete_preset(
            preset_id=str(preset_id),
            user_id=str(current_user.id)
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preset not found"
            )
        
        return {"message": "Preset deleted successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete import preset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete import preset"
        )

@router.post("/presets/{preset_id}/set-default")
async def set_default_preset(
    preset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set a preset as default for the current user"""
    try:
        from ..services.import_config_service import ImportConfigService
        
        service = ImportConfigService(db)
        
        success = await service.set_default_preset(
            preset_id=str(preset_id),
            user_id=str(current_user.id)
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preset not found"
            )
        
        return {"message": "Default preset updated successfully"}
        
    except Exception as e:
        logger.error(f"Failed to set default preset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set default preset"
        )

@router.get("/presets/{preset_id}/stats")
async def get_preset_stats(
    preset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get usage statistics for a preset"""
    try:
        from ..services.import_config_service import ImportConfigService
        
        service = ImportConfigService(db)
        
        stats = await service.get_preset_usage_stats(str(preset_id))
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get preset stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get preset statistics"
        )

@router.get("/platform-config/{platform}")
async def get_platform_config(
    platform: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get platform-specific optimization configuration"""
    try:
        from ..services.import_config_service import ImportConfigService
        
        service = ImportConfigService(db)
        
        config = await service.get_platform_optimization_config(platform)
        
        return {"platform": platform, "config": config}
        
    except Exception as e:
        logger.error(f"Failed to get platform config: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get platform configuration"
        )

@router.get("/storage-quota")
async def get_storage_quota(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get storage quota information for current user"""
    try:
        from ..services.import_config_service import ImportConfigService
        
        service = ImportConfigService(db)
        
        quota_info = await service.validate_storage_quota(str(current_user.id))
        
        return quota_info
        
    except Exception as e:
        logger.error(f"Failed to get storage quota: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get storage quota information"
        )

@router.get("/supported-platforms")
async def get_supported_platforms():
    """Get list of supported platforms"""
    return {
        "platforms": [
            {"name": "YouTube", "domains": ["youtube.com", "youtu.be"]},
            {"name": "TikTok", "domains": ["tiktok.com"]},
            {"name": "Instagram", "domains": ["instagram.com"]},
            {"name": "Twitter/X", "domains": ["twitter.com", "x.com"]},
            {"name": "Vimeo", "domains": ["vimeo.com"]},
            {"name": "Dailymotion", "domains": ["dailymotion.com"]},
            {"name": "Twitch", "domains": ["twitch.tv"]},
            {"name": "Reddit", "domains": ["reddit.com"]},
            {"name": "Facebook", "domains": ["facebook.com"]}
        ]
    }