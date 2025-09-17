"""
System Configuration Management API Endpoints.
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..dependencies import get_db, get_current_user
from ..models import User
from ..services.system_config_service import SystemConfigService


router = APIRouter(prefix="/admin/system", tags=["admin-system"])


class ConfigValueRequest(BaseModel):
    value: Any


class ConfigSectionRequest(BaseModel):
    config: Dict[str, Any]


class TranscodingPresetRequest(BaseModel):
    resolution: str
    framerate: int
    bitrate: int
    audio_bitrate: int
    enabled: bool = True


class BackupRestoreRequest(BaseModel):
    backup_data: Dict[str, Any]


# Dependency to check admin permissions
async def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the current user has admin permissions."""
    # TODO: Implement proper admin role checking
    # For now, we'll assume all authenticated users are admins
    # In production, this should check for admin role/permissions
    return current_user


@router.get("/config")
async def get_all_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get all system configuration."""
    service = SystemConfigService()
    config = await service.get_all_config(db)
    return config


@router.get("/config/{section}")
async def get_config_section(
    section: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get a specific configuration section."""
    service = SystemConfigService()
    config = await service.get_config_section(db, section)
    
    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration section '{section}' not found")
    
    return {section: config}


@router.get("/config/{section}/{key}")
async def get_config_value(
    section: str,
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get a specific configuration value."""
    service = SystemConfigService()
    full_key = f"{section}.{key}"
    value = await service.get_config_value(db, full_key)
    
    return {
        "key": full_key,
        "value": value
    }


@router.put("/config/{section}/{key}")
async def set_config_value(
    section: str,
    key: str,
    request: ConfigValueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Set a specific configuration value."""
    service = SystemConfigService()
    full_key = f"{section}.{key}"
    
    result = await service.set_config_value(db, full_key, request.value)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])
    
    return result


@router.put("/config/{section}")
async def set_config_section(
    section: str,
    request: ConfigSectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Set an entire configuration section."""
    service = SystemConfigService()
    
    result = await service.set_config_section(db, section, request.config)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])
    
    return result


@router.post("/config/reset")
async def reset_config_to_defaults(
    section: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Reset configuration to defaults."""
    service = SystemConfigService()
    
    result = await service.reset_config_to_defaults(db, section)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])
    
    return result


@router.post("/config/backup")
async def backup_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Create a backup of current configuration."""
    service = SystemConfigService()
    
    result = await service.backup_config(db)
    
    if not result['success']:
        raise HTTPException(status_code=500, detail=result['message'])
    
    return result


@router.post("/config/restore")
async def restore_config(
    request: BackupRestoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Restore configuration from backup."""
    service = SystemConfigService()
    
    result = await service.restore_config(db, request.backup_data)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])
    
    return result


@router.get("/transcoding/presets")
async def get_transcoding_presets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get transcoding quality presets."""
    service = SystemConfigService()
    presets = await service.get_transcoding_presets(db)
    return {"presets": presets}


@router.put("/transcoding/presets/{preset_name}")
async def update_transcoding_preset(
    preset_name: str,
    request: TranscodingPresetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Update or create a transcoding preset."""
    service = SystemConfigService()
    
    preset_config = {
        'resolution': request.resolution,
        'framerate': request.framerate,
        'bitrate': request.bitrate,
        'audio_bitrate': request.audio_bitrate,
        'enabled': request.enabled
    }
    
    result = await service.update_transcoding_preset(db, preset_name, preset_config)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])
    
    return result


@router.delete("/transcoding/presets/{preset_name}")
async def delete_transcoding_preset(
    preset_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Delete a transcoding preset."""
    service = SystemConfigService()
    
    result = await service.delete_transcoding_preset(db, preset_name)
    
    if not result['success']:
        raise HTTPException(status_code=404, detail=result['message'])
    
    return result


@router.get("/health")
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_user)
):
    """Get system health status based on configuration."""
    service = SystemConfigService()
    health = await service.get_system_health(db)
    return health


@router.get("/defaults")
async def get_default_config():
    """Get default configuration values."""
    service = SystemConfigService()
    return {"defaults": service.DEFAULT_CONFIG}


@router.post("/validate-config")
async def validate_config(
    config_data: Dict[str, Any],
    current_user: User = Depends(require_admin_user)
):
    """Validate configuration data without saving."""
    service = SystemConfigService()
    
    validation_results = {}
    errors = []
    
    for key, value in config_data.items():
        validation_result = service._validate_config_value(key, value)
        validation_results[key] = validation_result
        
        if not validation_result['valid']:
            errors.append(f"{key}: {validation_result['message']}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "validation_results": validation_results
    }