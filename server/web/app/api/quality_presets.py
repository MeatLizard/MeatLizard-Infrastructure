"""
Quality Presets API Endpoints

Provides REST API endpoints for quality preset management including:
- Dynamic preset generation based on source video
- Preset validation and recommendations
- Transcoding job creation
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.quality_preset_service import (
    QualityPresetService,
    QualityPresetRequest,
    QualityPresetResponse,
    SourceVideoInfo,
    get_quality_preset_service
)
from server.web.app.models import User
from server.web.app.middleware.permissions import get_current_user

router = APIRouter(prefix="/api/video/presets", tags=["quality-presets"])


# Request/Response Models
class SourceVideoRequest(BaseModel):
    width: int
    height: int
    framerate: float
    bitrate: int = None
    duration_seconds: float = None


class PresetRecommendationsResponse(BaseModel):
    available_presets: List[QualityPresetResponse]
    recommended_presets: List[str]
    source_analysis: Dict[str, Any]
    recommendations: Dict[str, Any]


class CreateTranscodingJobsRequest(BaseModel):
    preset_names: List[str]


class TranscodingJobResponse(BaseModel):
    job_id: str
    preset_name: str
    status: str
    target_resolution: str
    target_framerate: int
    target_bitrate: int


@router.post("/analyze-source", response_model=PresetRecommendationsResponse)
async def analyze_source_video(
    request: SourceVideoRequest,
    user: User = Depends(get_current_user),
    service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Analyze source video and get available quality presets.
    
    This endpoint analyzes the source video properties and returns
    available quality presets with recommendations.
    
    Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
    """
    try:
        source_info = SourceVideoInfo(
            width=request.width,
            height=request.height,
            framerate=request.framerate,
            bitrate=request.bitrate,
            duration_seconds=request.duration_seconds
        )
        
        recommendations = service.get_preset_recommendations(source_info)
        
        return PresetRecommendationsResponse(**recommendations)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze source video: {str(e)}")


@router.get("/available/{width}x{height}/{framerate}", response_model=List[QualityPresetResponse])
async def get_available_presets(
    width: int,
    height: int,
    framerate: float,
    duration_seconds: float = Query(None),
    bitrate: int = Query(None),
    user: User = Depends(get_current_user),
    service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Get available quality presets for given source video dimensions.
    
    This endpoint returns quality presets that can be generated based on
    the source video resolution and framerate.
    
    Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
    """
    try:
        source_info = SourceVideoInfo(
            width=width,
            height=height,
            framerate=framerate,
            bitrate=bitrate,
            duration_seconds=duration_seconds
        )
        
        presets = service.get_available_presets_for_source(source_info)
        return presets
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available presets: {str(e)}")


@router.get("/defaults/{width}x{height}/{framerate}", response_model=List[str])
async def get_default_presets(
    width: int,
    height: int,
    framerate: float,
    user: User = Depends(get_current_user),
    service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Get recommended default presets for source video dimensions.
    
    This endpoint returns the recommended default quality presets
    that should be pre-selected for the user.
    
    Requirements: 2.8
    """
    try:
        source_info = SourceVideoInfo(
            width=width,
            height=height,
            framerate=framerate
        )
        
        defaults = service.get_default_presets_for_source(source_info)
        return defaults
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get default presets: {str(e)}")


@router.post("/validate")
async def validate_preset_selection(
    request: Dict[str, Any],
    user: User = Depends(get_current_user),
    service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Validate selected quality presets against source video properties.
    
    This endpoint validates that the selected presets are appropriate
    for the source video and returns any necessary corrections.
    
    Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
    """
    try:
        # Extract source info and preset names from request
        source_info = SourceVideoInfo(
            width=request.get('width'),
            height=request.get('height'),
            framerate=request.get('framerate'),
            bitrate=request.get('bitrate'),
            duration_seconds=request.get('duration_seconds')
        )
        
        preset_names = request.get('preset_names', [])
        
        # Validate presets
        valid_presets = service.validate_preset_selection(preset_names, source_info)
        
        return {
            "valid": len(valid_presets) > 0,
            "original_presets": preset_names,
            "valid_presets": valid_presets,
            "invalid_presets": [p for p in preset_names if p not in valid_presets],
            "message": "Preset validation complete"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/videos/{video_id}/transcoding-jobs", response_model=List[TranscodingJobResponse])
async def create_transcoding_jobs(
    video_id: str,
    request: CreateTranscodingJobsRequest,
    user: User = Depends(get_current_user),
    service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Create transcoding jobs for selected quality presets.
    
    This endpoint creates transcoding jobs for the specified video
    using the selected quality presets.
    
    Requirements: 2.8
    """
    try:
        jobs = await service.create_transcoding_jobs(video_id, request.preset_names)
        
        job_responses = []
        for job in jobs:
            job_response = TranscodingJobResponse(
                job_id=str(job.id),
                preset_name=job.quality_preset,
                status=job.status.value,
                target_resolution=job.target_resolution,
                target_framerate=job.target_framerate,
                target_bitrate=job.target_bitrate
            )
            job_responses.append(job_response)
        
        return job_responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create transcoding jobs: {str(e)}")


@router.get("/videos/{video_id}/transcoding-jobs", response_model=List[TranscodingJobResponse])
async def get_video_transcoding_jobs(
    video_id: str,
    user: User = Depends(get_current_user),
    service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Get transcoding jobs for a video.
    
    This endpoint returns all transcoding jobs associated with
    the specified video.
    
    Requirements: 2.8
    """
    try:
        jobs = await service.get_video_transcoding_jobs(video_id)
        
        job_responses = []
        for job in jobs:
            job_response = TranscodingJobResponse(
                job_id=str(job.id),
                preset_name=job.quality_preset,
                status=job.status.value,
                target_resolution=job.target_resolution,
                target_framerate=job.target_framerate,
                target_bitrate=job.target_bitrate
            )
            job_responses.append(job_response)
        
        return job_responses
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transcoding jobs: {str(e)}")


@router.post("/compare")
async def compare_presets(
    preset_names: List[str],
    user: User = Depends(get_current_user),
    service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Compare multiple quality presets.
    
    This endpoint provides a comparison of multiple quality presets
    including file sizes, processing times, and quality differences.
    
    Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
    """
    try:
        comparison = service.get_preset_comparison(preset_names)
        return comparison
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare presets: {str(e)}")


@router.get("/all", response_model=List[QualityPresetResponse])
async def get_all_presets(
    user: User = Depends(get_current_user),
    service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Get all available quality presets.
    
    This endpoint returns information about all quality presets
    supported by the system.
    
    Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
    """
    try:
        # Create a high-quality source to get all presets
        source_info = SourceVideoInfo(
            width=3840,
            height=2160,
            framerate=60.0
        )
        
        presets = service.get_available_presets_for_source(source_info)
        return presets
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get all presets: {str(e)}")


@router.get("/preset/{preset_name}")
async def get_preset_details(
    preset_name: str,
    user: User = Depends(get_current_user),
    service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Get detailed information about a specific preset.
    
    This endpoint returns detailed configuration and specifications
    for a specific quality preset.
    
    Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
    """
    try:
        preset = service.get_preset_by_name(preset_name)
        
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        return {
            "name": preset.name,
            "resolution": preset.resolution.value,
            "framerate": preset.framerate.value,
            "width": preset.width,
            "height": preset.height,
            "target_bitrate": preset.target_bitrate,
            "max_bitrate": preset.max_bitrate,
            "description": preset.description,
            "is_default": preset.is_default,
            "is_recommended": preset.is_recommended,
            "bitrate_mbps": preset.target_bitrate / 1000000,
            "max_bitrate_mbps": preset.max_bitrate / 1000000
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get preset details: {str(e)}")


@router.get("/recommendations/quick/{height}/{framerate}")
async def get_quick_recommendations(
    height: int,
    framerate: float,
    user: User = Depends(get_current_user),
    service: QualityPresetService = Depends(get_quality_preset_service)
):
    """
    Get quick preset recommendations based on height and framerate.
    
    This endpoint provides quick recommendations without requiring
    full source video analysis.
    
    Requirements: 2.8
    """
    try:
        # Estimate width based on common aspect ratios
        width = int(height * 16 / 9)  # Assume 16:9 aspect ratio
        
        source_info = SourceVideoInfo(
            width=width,
            height=height,
            framerate=framerate
        )
        
        recommendations = service.get_preset_recommendations(source_info)
        
        return {
            "recommended_presets": recommendations["recommended_presets"],
            "quality_category": recommendations["source_analysis"]["quality_category"],
            "framerate_category": recommendations["source_analysis"]["framerate_category"],
            "minimum": recommendations["recommendations"]["minimum"],
            "balanced": recommendations["recommendations"]["balanced"],
            "maximum": recommendations["recommendations"]["maximum"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get quick recommendations: {str(e)}")