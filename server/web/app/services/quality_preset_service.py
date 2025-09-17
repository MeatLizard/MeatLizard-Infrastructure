"""
Quality Preset Service

Handles dynamic quality preset generation and management including:
- Quality preset generation based on source video properties
- Preset validation and default selection logic
- Quality preset storage and retrieval
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from pydantic import BaseModel

from server.web.app.models import Video, TranscodingJob, TranscodingStatus
from server.web.app.services.base_service import BaseService


class QualityLevel(str, Enum):
    """Quality level enumeration"""
    P480 = "480p"
    P720 = "720p"
    P1080 = "1080p"
    P1440 = "1440p"
    P2160 = "2160p"


class FrameRate(str, Enum):
    """Frame rate enumeration"""
    FPS30 = "30fps"
    FPS60 = "60fps"


@dataclass
class QualityPreset:
    """Quality preset configuration"""
    name: str
    resolution: QualityLevel
    framerate: FrameRate
    width: int
    height: int
    target_bitrate: int
    max_bitrate: int
    description: str
    is_default: bool = False
    is_recommended: bool = False


class QualityPresetRequest(BaseModel):
    """Request model for quality preset selection"""
    presets: List[str]
    custom_settings: Optional[Dict[str, Any]] = None


class QualityPresetResponse(BaseModel):
    """Response model for quality preset information"""
    name: str
    resolution: str
    framerate: str
    width: int
    height: int
    target_bitrate: int
    description: str
    is_default: bool
    is_recommended: bool
    estimated_file_size_mb: Optional[int] = None
    estimated_processing_time_minutes: Optional[int] = None


class SourceVideoInfo(BaseModel):
    """Source video information for preset generation"""
    width: int
    height: int
    framerate: float
    bitrate: Optional[int] = None
    duration_seconds: Optional[float] = None


class QualityPresetService(BaseService):
    """Service for handling quality preset operations"""
    
    # Quality preset definitions
    QUALITY_PRESETS = {
        "480p_30fps": QualityPreset(
            name="480p_30fps",
            resolution=QualityLevel.P480,
            framerate=FrameRate.FPS30,
            width=854,
            height=480,
            target_bitrate=1000000,  # 1 Mbps
            max_bitrate=1500000,     # 1.5 Mbps
            description="Standard definition, good for mobile devices",
            is_default=False
        ),
        "720p_30fps": QualityPreset(
            name="720p_30fps",
            resolution=QualityLevel.P720,
            framerate=FrameRate.FPS30,
            width=1280,
            height=720,
            target_bitrate=2500000,  # 2.5 Mbps
            max_bitrate=3500000,     # 3.5 Mbps
            description="High definition, recommended for most users",
            is_default=True,
            is_recommended=True
        ),
        "720p_60fps": QualityPreset(
            name="720p_60fps",
            resolution=QualityLevel.P720,
            framerate=FrameRate.FPS60,
            width=1280,
            height=720,
            target_bitrate=4000000,  # 4 Mbps
            max_bitrate=5500000,     # 5.5 Mbps
            description="High definition with smooth motion",
            is_default=False
        ),
        "1080p_30fps": QualityPreset(
            name="1080p_30fps",
            resolution=QualityLevel.P1080,
            framerate=FrameRate.FPS30,
            width=1920,
            height=1080,
            target_bitrate=5000000,  # 5 Mbps
            max_bitrate=7000000,     # 7 Mbps
            description="Full HD, excellent quality",
            is_default=False,
            is_recommended=True
        ),
        "1080p_60fps": QualityPreset(
            name="1080p_60fps",
            resolution=QualityLevel.P1080,
            framerate=FrameRate.FPS60,
            width=1920,
            height=1080,
            target_bitrate=8000000,  # 8 Mbps
            max_bitrate=11000000,    # 11 Mbps
            description="Full HD with smooth motion",
            is_default=False
        ),
        "1440p_30fps": QualityPreset(
            name="1440p_30fps",
            resolution=QualityLevel.P1440,
            framerate=FrameRate.FPS30,
            width=2560,
            height=1440,
            target_bitrate=9000000,  # 9 Mbps
            max_bitrate=13000000,    # 13 Mbps
            description="Quad HD, premium quality",
            is_default=False
        ),
        "1440p_60fps": QualityPreset(
            name="1440p_60fps",
            resolution=QualityLevel.P1440,
            framerate=FrameRate.FPS60,
            width=2560,
            height=1440,
            target_bitrate=16000000, # 16 Mbps
            max_bitrate=22000000,    # 22 Mbps
            description="Quad HD with smooth motion",
            is_default=False
        ),
        "2160p_30fps": QualityPreset(
            name="2160p_30fps",
            resolution=QualityLevel.P2160,
            framerate=FrameRate.FPS30,
            width=3840,
            height=2160,
            target_bitrate=20000000, # 20 Mbps
            max_bitrate=28000000,    # 28 Mbps
            description="4K Ultra HD, maximum quality",
            is_default=False
        ),
        "2160p_60fps": QualityPreset(
            name="2160p_60fps",
            resolution=QualityLevel.P2160,
            framerate=FrameRate.FPS60,
            width=3840,
            height=2160,
            target_bitrate=35000000, # 35 Mbps
            max_bitrate=50000000,    # 50 Mbps
            description="4K Ultra HD with smooth motion",
            is_default=False
        )
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def get_available_presets_for_source(self, source_info: SourceVideoInfo) -> List[QualityPresetResponse]:
        """
        Generate available quality presets based on source video properties.
        
        Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
        """
        available_presets = []
        
        # Determine source resolution category
        source_height = source_info.height
        source_fps = source_info.framerate
        
        # Only offer presets that are equal to or lower than source quality
        for preset_name, preset in self.QUALITY_PRESETS.items():
            # Check if preset resolution is available
            if preset.height <= source_height:
                # Check if preset framerate is available
                preset_fps = 60 if preset.framerate == FrameRate.FPS60 else 30
                
                if preset_fps <= source_fps or (preset_fps == 30 and source_fps >= 25):
                    # Calculate estimated file size and processing time
                    estimated_size = self._estimate_file_size(preset, source_info.duration_seconds)
                    estimated_time = self._estimate_processing_time(preset, source_info.duration_seconds)
                    
                    preset_response = QualityPresetResponse(
                        name=preset.name,
                        resolution=preset.resolution.value,
                        framerate=preset.framerate.value,
                        width=preset.width,
                        height=preset.height,
                        target_bitrate=preset.target_bitrate,
                        description=preset.description,
                        is_default=preset.is_default,
                        is_recommended=preset.is_recommended,
                        estimated_file_size_mb=estimated_size,
                        estimated_processing_time_minutes=estimated_time
                    )
                    
                    available_presets.append(preset_response)
        
        # Sort presets by resolution and framerate
        available_presets.sort(key=lambda p: (p.height, int(p.framerate.replace('fps', ''))))
        
        # Ensure at least one default preset is available
        if not any(p.is_default for p in available_presets) and available_presets:
            # Make the middle-quality preset the default
            middle_index = len(available_presets) // 2
            available_presets[middle_index].is_default = True
        
        return available_presets
    
    def get_preset_by_name(self, preset_name: str) -> Optional[QualityPreset]:
        """Get a quality preset by name"""
        return self.QUALITY_PRESETS.get(preset_name)
    
    def validate_preset_selection(self, preset_names: List[str], source_info: SourceVideoInfo) -> List[str]:
        """
        Validate that selected presets are appropriate for the source video.
        
        Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
        """
        available_presets = self.get_available_presets_for_source(source_info)
        available_names = {p.name for p in available_presets}
        
        valid_presets = []
        for preset_name in preset_names:
            if preset_name in available_names:
                valid_presets.append(preset_name)
        
        # Ensure at least one preset is selected
        if not valid_presets and available_presets:
            # Add default preset
            default_preset = next((p for p in available_presets if p.is_default), available_presets[0])
            valid_presets.append(default_preset.name)
        
        return valid_presets
    
    def get_default_presets_for_source(self, source_info: SourceVideoInfo) -> List[str]:
        """
        Get recommended default presets for a source video.
        
        Requirements: 2.8
        """
        available_presets = self.get_available_presets_for_source(source_info)
        
        # Select default presets based on source quality
        default_presets = []
        
        # Always include 720p_30fps if available (most compatible)
        if any(p.name == "720p_30fps" for p in available_presets):
            default_presets.append("720p_30fps")
        
        # Add 1080p if source is high quality
        if source_info.height >= 1080:
            if any(p.name == "1080p_30fps" for p in available_presets):
                default_presets.append("1080p_30fps")
        
        # Add 60fps version if source has high framerate
        if source_info.framerate >= 50:
            if source_info.height >= 1080 and any(p.name == "1080p_60fps" for p in available_presets):
                default_presets.append("1080p_60fps")
            elif any(p.name == "720p_60fps" for p in available_presets):
                default_presets.append("720p_60fps")
        
        # Fallback to any available preset
        if not default_presets and available_presets:
            default_presets.append(available_presets[0].name)
        
        return default_presets
    
    async def create_transcoding_jobs(self, video_id: str, preset_names: List[str]) -> List[TranscodingJob]:
        """
        Create transcoding jobs for the selected quality presets.
        
        Requirements: 2.8
        """
        # Get video record
        video = await self.db.get(Video, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Create source info from video
        source_info = SourceVideoInfo(
            width=int(video.source_resolution.split('x')[0]) if video.source_resolution else 1920,
            height=int(video.source_resolution.split('x')[1]) if video.source_resolution else 1080,
            framerate=float(video.source_framerate) if video.source_framerate else 30.0,
            bitrate=video.source_bitrate,
            duration_seconds=float(video.duration_seconds) if video.duration_seconds else None
        )
        
        # Validate presets
        valid_presets = self.validate_preset_selection(preset_names, source_info)
        
        # Create transcoding jobs
        transcoding_jobs = []
        for preset_name in valid_presets:
            preset = self.get_preset_by_name(preset_name)
            if preset:
                job = TranscodingJob(
                    video_id=video_id,
                    quality_preset=preset.name,
                    target_resolution=f"{preset.width}x{preset.height}",
                    target_framerate=int(preset.framerate.value.replace('fps', '')),
                    target_bitrate=preset.target_bitrate,
                    status=TranscodingStatus.queued
                )
                
                self.db.add(job)
                transcoding_jobs.append(job)
        
        await self.db.commit()
        
        return transcoding_jobs
    
    async def get_video_transcoding_jobs(self, video_id: str) -> List[TranscodingJob]:
        """Get all transcoding jobs for a video"""
        from sqlalchemy import select
        
        stmt = select(TranscodingJob).where(TranscodingJob.video_id == video_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    def get_preset_recommendations(self, source_info: SourceVideoInfo) -> Dict[str, Any]:
        """
        Get preset recommendations with explanations.
        
        Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
        """
        available_presets = self.get_available_presets_for_source(source_info)
        default_presets = self.get_default_presets_for_source(source_info)
        
        recommendations = {
            "available_presets": available_presets,
            "recommended_presets": default_presets,
            "source_analysis": {
                "resolution": f"{source_info.width}x{source_info.height}",
                "framerate": f"{source_info.framerate} FPS",
                "quality_category": self._get_quality_category(source_info.height),
                "framerate_category": self._get_framerate_category(source_info.framerate)
            },
            "recommendations": {
                "minimum": self._get_minimum_recommendation(available_presets),
                "balanced": self._get_balanced_recommendation(available_presets),
                "maximum": self._get_maximum_recommendation(available_presets)
            }
        }
        
        return recommendations
    
    def _estimate_file_size(self, preset: QualityPreset, duration_seconds: Optional[float]) -> Optional[int]:
        """Estimate output file size in MB"""
        if not duration_seconds:
            return None
        
        # Rough estimation: bitrate * duration / 8 (bits to bytes) / 1024^2 (bytes to MB)
        size_mb = (preset.target_bitrate * duration_seconds) / (8 * 1024 * 1024)
        return int(size_mb)
    
    def _estimate_processing_time(self, preset: QualityPreset, duration_seconds: Optional[float]) -> Optional[int]:
        """Estimate processing time in minutes"""
        if not duration_seconds:
            return None
        
        # Rough estimation based on preset complexity
        # Higher resolution and framerate take longer
        complexity_factor = (preset.height / 720) * (60 if preset.framerate == FrameRate.FPS60 else 30) / 30
        processing_time = (duration_seconds / 60) * complexity_factor * 0.5  # Assume 0.5x realtime for 720p30
        
        return max(1, int(processing_time))
    
    def _get_quality_category(self, height: int) -> str:
        """Get quality category description"""
        if height >= 2160:
            return "4K Ultra HD"
        elif height >= 1440:
            return "Quad HD"
        elif height >= 1080:
            return "Full HD"
        elif height >= 720:
            return "HD"
        else:
            return "Standard Definition"
    
    def _get_framerate_category(self, framerate: float) -> str:
        """Get framerate category description"""
        if framerate >= 50:
            return "High Frame Rate"
        elif framerate >= 25:
            return "Standard Frame Rate"
        else:
            return "Low Frame Rate"
    
    def _get_minimum_recommendation(self, presets: List[QualityPresetResponse]) -> Optional[str]:
        """Get minimum quality recommendation"""
        if not presets:
            return None
        
        # Find lowest resolution preset
        min_preset = min(presets, key=lambda p: p.height)
        return min_preset.name
    
    def _get_balanced_recommendation(self, presets: List[QualityPresetResponse]) -> Optional[str]:
        """Get balanced quality recommendation"""
        if not presets:
            return None
        
        # Prefer 720p or 1080p at 30fps
        for preset in presets:
            if preset.name in ["720p_30fps", "1080p_30fps"]:
                return preset.name
        
        # Fallback to middle preset
        return presets[len(presets) // 2].name
    
    def _get_maximum_recommendation(self, presets: List[QualityPresetResponse]) -> Optional[str]:
        """Get maximum quality recommendation"""
        if not presets:
            return None
        
        # Find highest resolution preset
        max_preset = max(presets, key=lambda p: (p.height, int(p.framerate.replace('fps', ''))))
        return max_preset.name
    
    def get_preset_comparison(self, preset_names: List[str]) -> Dict[str, Any]:
        """Compare multiple presets"""
        presets = [self.get_preset_by_name(name) for name in preset_names if self.get_preset_by_name(name)]
        
        if not presets:
            return {}
        
        comparison = {
            "presets": [],
            "total_estimated_size_mb": 0,
            "total_estimated_time_minutes": 0
        }
        
        for preset in presets:
            preset_info = {
                "name": preset.name,
                "resolution": f"{preset.width}x{preset.height}",
                "framerate": preset.framerate.value,
                "bitrate_mbps": preset.target_bitrate / 1000000,
                "description": preset.description
            }
            comparison["presets"].append(preset_info)
        
        return comparison


# Dependency for FastAPI
def get_quality_preset_service(db: AsyncSession) -> QualityPresetService:
    return QualityPresetService(db)