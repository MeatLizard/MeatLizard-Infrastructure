"""
Import Configuration Service for managing import presets and settings.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from ..models import ImportPreset, User, ImportJob, ImportStatus
from .base_service import BaseService
from .media_import_service import ImportConfig

logger = logging.getLogger(__name__)

class ImportConfigService(BaseService):
    """Service for managing import configurations and presets"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        
        # Default presets that are always available
        self.default_presets = {
            "standard_quality": {
                "name": "Standard Quality",
                "description": "720p 30fps - Good balance of quality and file size",
                "config": {
                    "max_height": 720,
                    "max_fps": 30,
                    "quality_presets": ["720p_30fps"],
                    "preserve_metadata": True,
                    "auto_publish": False
                }
            },
            "high_quality": {
                "name": "High Quality",
                "description": "1080p 30fps - Best video quality",
                "config": {
                    "max_height": 1080,
                    "max_fps": 30,
                    "quality_presets": ["1080p_30fps", "720p_30fps"],
                    "preserve_metadata": True,
                    "auto_publish": False
                }
            },
            "low_quality": {
                "name": "Low Quality",
                "description": "480p 30fps - Smaller file size",
                "config": {
                    "max_height": 480,
                    "max_fps": 30,
                    "max_filesize": "500M",
                    "quality_presets": ["480p_30fps"],
                    "preserve_metadata": True,
                    "auto_publish": False
                }
            },
            "audio_only": {
                "name": "Audio Only",
                "description": "Extract audio only in MP3 format",
                "config": {
                    "audio_only": True,
                    "audio_format": "mp3",
                    "preserve_metadata": True,
                    "auto_publish": False
                }
            },
            "high_quality_60fps": {
                "name": "High Quality 60fps",
                "description": "1080p 60fps - Best quality with smooth motion",
                "config": {
                    "max_height": 1080,
                    "max_fps": 60,
                    "quality_presets": ["1080p_60fps", "720p_60fps", "720p_30fps"],
                    "preserve_metadata": True,
                    "auto_publish": False
                }
            }
        }
    
    async def create_preset(self, name: str, description: str, config: ImportConfig, 
                          user_id: str, is_default: bool = False) -> ImportPreset:
        """Create a new import preset"""
        try:
            # Validate config
            self._validate_import_config(config)
            
            # Check if preset name already exists for this user
            existing = await self.get_preset_by_name(name, user_id)
            if existing:
                raise ValueError(f"Preset with name '{name}' already exists")
            
            preset = ImportPreset(
                name=name,
                description=description,
                config=config.dict(),
                created_by=user_id,
                is_default=is_default
            )
            
            self.db.add(preset)
            await self.db.commit()
            await self.db.refresh(preset)
            
            logger.info(f"Created import preset '{name}' for user {user_id}")
            return preset
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create preset: {str(e)}")
            raise
    
    async def update_preset(self, preset_id: str, name: Optional[str] = None,
                          description: Optional[str] = None, config: Optional[ImportConfig] = None,
                          user_id: Optional[str] = None) -> ImportPreset:
        """Update an existing import preset"""
        try:
            # Get preset
            preset = await self.get_preset_by_id(preset_id)
            if not preset:
                raise ValueError("Preset not found")
            
            # Check ownership if user_id provided
            if user_id and preset.created_by != user_id:
                raise ValueError("Not authorized to update this preset")
            
            # Update fields
            update_data = {}
            if name is not None:
                # Check for name conflicts
                if name != preset.name:
                    existing = await self.get_preset_by_name(name, preset.created_by)
                    if existing and existing.id != preset.id:
                        raise ValueError(f"Preset with name '{name}' already exists")
                update_data["name"] = name
            
            if description is not None:
                update_data["description"] = description
            
            if config is not None:
                self._validate_import_config(config)
                update_data["config"] = config.dict()
            
            if update_data:
                await self.db.execute(
                    update(ImportPreset)
                    .where(ImportPreset.id == preset_id)
                    .values(**update_data)
                )
                await self.db.commit()
                
                # Refresh preset
                await self.db.refresh(preset)
            
            logger.info(f"Updated import preset {preset_id}")
            return preset
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update preset: {str(e)}")
            raise
    
    async def delete_preset(self, preset_id: str, user_id: Optional[str] = None) -> bool:
        """Delete an import preset"""
        try:
            # Get preset
            preset = await self.get_preset_by_id(preset_id)
            if not preset:
                return False
            
            # Check ownership if user_id provided
            if user_id and preset.created_by != user_id:
                raise ValueError("Not authorized to delete this preset")
            
            await self.db.execute(
                delete(ImportPreset).where(ImportPreset.id == preset_id)
            )
            await self.db.commit()
            
            logger.info(f"Deleted import preset {preset_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete preset: {str(e)}")
            raise
    
    async def get_preset_by_id(self, preset_id: str) -> Optional[ImportPreset]:
        """Get preset by ID"""
        result = await self.db.execute(
            select(ImportPreset)
            .options(selectinload(ImportPreset.creator))
            .where(ImportPreset.id == preset_id)
        )
        return result.scalar_one_or_none()
    
    async def get_preset_by_name(self, name: str, user_id: str) -> Optional[ImportPreset]:
        """Get preset by name for a specific user"""
        result = await self.db.execute(
            select(ImportPreset)
            .where(ImportPreset.name == name)
            .where(ImportPreset.created_by == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_presets(self, user_id: str, include_defaults: bool = True) -> List[ImportPreset]:
        """Get all presets for a user"""
        # Get user's custom presets
        result = await self.db.execute(
            select(ImportPreset)
            .where(ImportPreset.created_by == user_id)
            .order_by(ImportPreset.is_default.desc(), ImportPreset.name)
        )
        presets = list(result.scalars().all())
        
        # Add default presets if requested
        if include_defaults:
            default_presets = self._get_default_presets()
            presets.extend(default_presets)
        
        return presets
    
    async def get_all_presets(self, limit: int = 100, offset: int = 0) -> List[ImportPreset]:
        """Get all presets (admin function)"""
        result = await self.db.execute(
            select(ImportPreset)
            .options(selectinload(ImportPreset.creator))
            .order_by(ImportPreset.is_default.desc(), ImportPreset.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def set_default_preset(self, preset_id: str, user_id: str) -> bool:
        """Set a preset as default for a user"""
        try:
            # First, unset any existing default for this user
            await self.db.execute(
                update(ImportPreset)
                .where(ImportPreset.created_by == user_id)
                .where(ImportPreset.is_default == True)
                .values(is_default=False)
            )
            
            # Set the new default
            result = await self.db.execute(
                update(ImportPreset)
                .where(ImportPreset.id == preset_id)
                .where(ImportPreset.created_by == user_id)
                .values(is_default=True)
            )
            
            await self.db.commit()
            
            if result.rowcount > 0:
                logger.info(f"Set preset {preset_id} as default for user {user_id}")
                return True
            else:
                return False
                
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to set default preset: {str(e)}")
            raise
    
    async def get_default_preset(self, user_id: str) -> Optional[ImportPreset]:
        """Get the default preset for a user"""
        result = await self.db.execute(
            select(ImportPreset)
            .where(ImportPreset.created_by == user_id)
            .where(ImportPreset.is_default == True)
        )
        preset = result.scalar_one_or_none()
        
        # If no custom default, return the first default preset
        if not preset:
            defaults = self._get_default_presets()
            return defaults[0] if defaults else None
        
        return preset
    
    async def get_preset_usage_stats(self, preset_id: str) -> Dict[str, Any]:
        """Get usage statistics for a preset"""
        # Count jobs that used this preset
        result = await self.db.execute(
            select(ImportJob)
            .where(ImportJob.import_config.contains({"preset_id": preset_id}))
        )
        jobs = list(result.scalars().all())
        
        # Calculate statistics
        total_jobs = len(jobs)
        successful_jobs = len([j for j in jobs if j.status == ImportStatus.completed])
        failed_jobs = len([j for j in jobs if j.status == ImportStatus.failed])
        
        return {
            "total_jobs": total_jobs,
            "successful_jobs": successful_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0,
            "last_used": max([j.created_at for j in jobs]) if jobs else None
        }
    
    async def get_platform_optimization_config(self, platform: str) -> Dict[str, Any]:
        """Get platform-specific optimization settings"""
        platform_configs = {
            "YouTube": {
                "preferred_codec": "h264",
                "max_filesize": "2G",
                "audio_format": "aac"
            },
            "TikTok": {
                "max_height": 1080,
                "max_fps": 30,
                "preferred_codec": "h264"
            },
            "Instagram": {
                "max_height": 1080,
                "max_fps": 30,
                "max_filesize": "1G"
            },
            "Twitter": {
                "max_height": 720,
                "max_fps": 30,
                "max_filesize": "500M"
            },
            "Twitch": {
                "preferred_codec": "h264",
                "audio_format": "aac"
            }
        }
        
        return platform_configs.get(platform, {})
    
    async def create_optimized_config(self, platform: str, base_config: ImportConfig) -> ImportConfig:
        """Create optimized config for a specific platform"""
        platform_opts = await self.get_platform_optimization_config(platform)
        
        # Merge base config with platform optimizations
        config_dict = base_config.dict()
        
        for key, value in platform_opts.items():
            if key not in config_dict or config_dict[key] is None:
                config_dict[key] = value
        
        return ImportConfig(**config_dict)
    
    async def validate_storage_quota(self, user_id: str, estimated_size: Optional[int] = None) -> Dict[str, Any]:
        """Validate storage quota for import"""
        # Get user's import jobs
        result = await self.db.execute(
            select(ImportJob)
            .where(ImportJob.requested_by == user_id)
            .where(ImportJob.status == ImportStatus.completed)
        )
        completed_jobs = list(result.scalars().all())
        
        # Calculate used storage (this would need to be implemented based on actual file sizes)
        used_storage = sum([job.downloaded_file_path and 0 or 0 for job in completed_jobs])  # Placeholder
        
        # Get user's storage quota (this would come from user tier/subscription)
        storage_quota = 10 * 1024 * 1024 * 1024  # 10GB default
        
        available_storage = storage_quota - used_storage
        
        result = {
            "used_storage": used_storage,
            "total_quota": storage_quota,
            "available_storage": available_storage,
            "usage_percentage": (used_storage / storage_quota * 100) if storage_quota > 0 else 0,
            "can_import": True
        }
        
        if estimated_size and estimated_size > available_storage:
            result["can_import"] = False
            result["error"] = "Insufficient storage quota"
        
        return result
    
    def _get_default_presets(self) -> List[ImportPreset]:
        """Get default system presets"""
        presets = []
        for preset_id, preset_data in self.default_presets.items():
            preset = ImportPreset(
                id=preset_id,
                name=preset_data["name"],
                description=preset_data["description"],
                config=preset_data["config"],
                created_by="system",
                is_default=True,
                created_at=datetime.utcnow()
            )
            presets.append(preset)
        return presets
    
    def _validate_import_config(self, config: ImportConfig):
        """Validate import configuration"""
        # Check for conflicting settings
        if config.audio_only and (config.max_height or config.max_fps):
            raise ValueError("Audio-only imports cannot have video quality settings")
        
        # Validate quality presets
        valid_presets = [
            "480p_30fps", "720p_30fps", "1080p_30fps", "1440p_30fps",
            "480p_60fps", "720p_60fps", "1080p_60fps", "1440p_60fps"
        ]
        
        for preset in config.quality_presets:
            if preset not in valid_presets:
                raise ValueError(f"Invalid quality preset: {preset}")
        
        # Validate file size format
        if config.max_filesize:
            valid_suffixes = ['K', 'M', 'G']
            if not any(config.max_filesize.endswith(suffix) for suffix in valid_suffixes):
                raise ValueError("Invalid file size format. Use K, M, or G suffix (e.g., '500M')")
        
        # Validate audio format
        if config.audio_only:
            valid_formats = ['mp3', 'flac', 'aac', 'ogg']
            if config.audio_format not in valid_formats:
                raise ValueError(f"Invalid audio format: {config.audio_format}")
        
        logger.debug("Import config validation passed")