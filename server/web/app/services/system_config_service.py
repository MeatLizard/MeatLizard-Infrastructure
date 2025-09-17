"""
System Configuration Management Service

Handles system-wide settings, transcoding presets, S3 configuration, and other admin settings.
"""
import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from .base_service import BaseService
from ..models import SystemConfig


class SystemConfigService(BaseService):
    """Service for managing system configuration."""
    
    # Default configuration values
    DEFAULT_CONFIG = {
        'transcoding': {
            'quality_presets': {
                '480p_30fps': {
                    'resolution': '854x480',
                    'framerate': 30,
                    'bitrate': 1000000,
                    'audio_bitrate': 128000,
                    'enabled': True
                },
                '720p_30fps': {
                    'resolution': '1280x720',
                    'framerate': 30,
                    'bitrate': 2500000,
                    'audio_bitrate': 128000,
                    'enabled': True
                },
                '720p_60fps': {
                    'resolution': '1280x720',
                    'framerate': 60,
                    'bitrate': 3500000,
                    'audio_bitrate': 128000,
                    'enabled': True
                },
                '1080p_30fps': {
                    'resolution': '1920x1080',
                    'framerate': 30,
                    'bitrate': 4000000,
                    'audio_bitrate': 192000,
                    'enabled': True
                },
                '1080p_60fps': {
                    'resolution': '1920x1080',
                    'framerate': 60,
                    'bitrate': 6000000,
                    'audio_bitrate': 192000,
                    'enabled': True
                },
                '1440p_30fps': {
                    'resolution': '2560x1440',
                    'framerate': 30,
                    'bitrate': 8000000,
                    'audio_bitrate': 192000,
                    'enabled': False
                },
                '1440p_60fps': {
                    'resolution': '2560x1440',
                    'framerate': 60,
                    'bitrate': 12000000,
                    'audio_bitrate': 192000,
                    'enabled': False
                }
            },
            'hls_segment_duration': 6,
            'hls_playlist_type': 'vod',
            'max_concurrent_jobs': 3,
            'job_timeout_minutes': 60,
            'retry_attempts': 3
        },
        'upload_limits': {
            'max_file_size_gb': 10,
            'max_duration_hours': 4,
            'allowed_formats': ['mp4', 'mov', 'avi', 'mkv', 'webm'],
            'max_uploads_per_day': 50,
            'max_uploads_per_hour': 10
        },
        'storage': {
            's3_bucket': 'meatlizard-video-storage',
            's3_region': 'us-east-1',
            'cdn_domain': '',
            'cleanup_deleted_after_days': 7,
            'storage_quota_warning_gb': 1000,
            'storage_quota_limit_gb': 2000
        },
        'content_moderation': {
            'auto_scan_enabled': True,
            'auto_scan_metadata': True,
            'auto_scan_visual': False,
            'auto_scan_audio': False,
            'auto_moderate_threshold': 'high',
            'report_threshold_auto_escalate': 3,
            'profanity_filter_enabled': True
        },
        'analytics': {
            'retention_days': 365,
            'aggregate_daily': True,
            'track_ip_addresses': False,
            'track_user_agents': True,
            'export_enabled': True
        },
        'notifications': {
            'email_enabled': False,
            'webhook_enabled': False,
            'webhook_url': '',
            'notify_on_upload': False,
            'notify_on_transcoding_complete': False,
            'notify_on_transcoding_failed': True,
            'notify_on_moderation_needed': True
        }
    }
    
    async def get_all_config(self, db: AsyncSession) -> Dict[str, Any]:
        """Get all system configuration."""
        
        # Get all config from database
        query = select(SystemConfig)
        result = await db.execute(query)
        config_records = result.scalars().all()
        
        # Start with default config
        config = self.DEFAULT_CONFIG.copy()
        
        # Override with database values
        for record in config_records:
            self._set_nested_value(config, record.key, record.value)
        
        return config
    
    async def get_config_section(self, db: AsyncSession, section: str) -> Dict[str, Any]:
        """Get a specific configuration section."""
        
        config = await self.get_all_config(db)
        return config.get(section, {})
    
    async def get_config_value(self, db: AsyncSession, key: str) -> Any:
        """Get a specific configuration value."""
        
        query = select(SystemConfig).where(SystemConfig.key == key)
        result = await db.execute(query)
        config_record = result.scalar_one_or_none()
        
        if config_record:
            return config_record.value
        
        # Return default value if exists
        return self._get_nested_value(self.DEFAULT_CONFIG, key)
    
    async def set_config_value(self, db: AsyncSession, key: str, value: Any) -> Dict[str, Any]:
        """Set a specific configuration value."""
        
        # Validate the configuration key and value
        validation_result = self._validate_config_value(key, value)
        if not validation_result['valid']:
            return {
                'success': False,
                'error': 'validation_failed',
                'message': validation_result['message']
            }
        
        # Check if config already exists
        query = select(SystemConfig).where(SystemConfig.key == key)
        result = await db.execute(query)
        config_record = result.scalar_one_or_none()
        
        if config_record:
            # Update existing config
            config_record.value = value
            config_record.updated_at = datetime.utcnow()
        else:
            # Create new config
            config_record = SystemConfig(
                key=key,
                value=value,
                updated_at=datetime.utcnow()
            )
            db.add(config_record)
        
        await db.commit()
        
        return {
            'success': True,
            'message': f'Configuration {key} updated successfully',
            'key': key,
            'value': value
        }
    
    async def set_config_section(self, db: AsyncSession, section: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set an entire configuration section."""
        
        # Validate the section
        if section not in self.DEFAULT_CONFIG:
            return {
                'success': False,
                'error': 'invalid_section',
                'message': f'Invalid configuration section: {section}'
            }
        
        # Validate each value in the section
        for key, value in config_data.items():
            full_key = f"{section}.{key}"
            validation_result = self._validate_config_value(full_key, value)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': 'validation_failed',
                    'message': f'Validation failed for {full_key}: {validation_result["message"]}'
                }
        
        # Update all values in the section
        updated_keys = []
        for key, value in config_data.items():
            full_key = f"{section}.{key}"
            result = await self.set_config_value(db, full_key, value)
            if result['success']:
                updated_keys.append(full_key)
        
        return {
            'success': True,
            'message': f'Configuration section {section} updated successfully',
            'updated_keys': updated_keys
        }
    
    async def reset_config_to_defaults(self, db: AsyncSession, section: Optional[str] = None) -> Dict[str, Any]:
        """Reset configuration to defaults."""
        
        if section:
            # Reset specific section
            if section not in self.DEFAULT_CONFIG:
                return {
                    'success': False,
                    'error': 'invalid_section',
                    'message': f'Invalid configuration section: {section}'
                }
            
            # Delete all keys in the section
            section_prefix = f"{section}."
            delete_query = delete(SystemConfig).where(
                SystemConfig.key.like(f"{section_prefix}%")
            )
            await db.execute(delete_query)
            await db.commit()
            
            return {
                'success': True,
                'message': f'Configuration section {section} reset to defaults'
            }
        else:
            # Reset all configuration
            delete_query = delete(SystemConfig)
            await db.execute(delete_query)
            await db.commit()
            
            return {
                'success': True,
                'message': 'All configuration reset to defaults'
            }
    
    async def backup_config(self, db: AsyncSession) -> Dict[str, Any]:
        """Create a backup of current configuration."""
        
        config = await self.get_all_config(db)
        
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'config': config
        }
        
        # In a real implementation, this would save to S3 or another backup location
        # For now, we'll return the backup data
        
        return {
            'success': True,
            'message': 'Configuration backup created',
            'backup_data': backup_data
        }
    
    async def restore_config(self, db: AsyncSession, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restore configuration from backup."""
        
        if 'config' not in backup_data:
            return {
                'success': False,
                'error': 'invalid_backup',
                'message': 'Invalid backup data format'
            }
        
        # Clear existing configuration
        delete_query = delete(SystemConfig)
        await db.execute(delete_query)
        
        # Restore configuration
        config = backup_data['config']
        restored_keys = []
        
        for section_name, section_data in config.items():
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    full_key = f"{section_name}.{key}"
                    
                    # Skip nested dictionaries for now (would need recursive handling)
                    if not isinstance(value, dict):
                        config_record = SystemConfig(
                            key=full_key,
                            value=value,
                            updated_at=datetime.utcnow()
                        )
                        db.add(config_record)
                        restored_keys.append(full_key)
        
        await db.commit()
        
        return {
            'success': True,
            'message': f'Configuration restored from backup',
            'restored_keys': restored_keys
        }
    
    async def get_transcoding_presets(self, db: AsyncSession) -> Dict[str, Any]:
        """Get transcoding quality presets."""
        
        presets_config = await self.get_config_section(db, 'transcoding')
        return presets_config.get('quality_presets', {})
    
    async def update_transcoding_preset(
        self, 
        db: AsyncSession, 
        preset_name: str, 
        preset_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update or create a transcoding preset."""
        
        # Validate preset configuration
        required_fields = ['resolution', 'framerate', 'bitrate', 'audio_bitrate', 'enabled']
        for field in required_fields:
            if field not in preset_config:
                return {
                    'success': False,
                    'error': 'missing_field',
                    'message': f'Missing required field: {field}'
                }
        
        # Validate values
        try:
            # Validate resolution format
            if not isinstance(preset_config['resolution'], str) or 'x' not in preset_config['resolution']:
                raise ValueError('Resolution must be in format "WIDTHxHEIGHT"')
            
            # Validate numeric values
            if not isinstance(preset_config['framerate'], (int, float)) or preset_config['framerate'] <= 0:
                raise ValueError('Framerate must be a positive number')
            
            if not isinstance(preset_config['bitrate'], int) or preset_config['bitrate'] <= 0:
                raise ValueError('Bitrate must be a positive integer')
            
            if not isinstance(preset_config['audio_bitrate'], int) or preset_config['audio_bitrate'] <= 0:
                raise ValueError('Audio bitrate must be a positive integer')
            
            if not isinstance(preset_config['enabled'], bool):
                raise ValueError('Enabled must be a boolean')
                
        except ValueError as e:
            return {
                'success': False,
                'error': 'validation_failed',
                'message': str(e)
            }
        
        # Update the preset
        key = f"transcoding.quality_presets.{preset_name}"
        result = await self.set_config_value(db, key, preset_config)
        
        return result
    
    async def delete_transcoding_preset(self, db: AsyncSession, preset_name: str) -> Dict[str, Any]:
        """Delete a transcoding preset."""
        
        key = f"transcoding.quality_presets.{preset_name}"
        
        # Check if preset exists
        query = select(SystemConfig).where(SystemConfig.key == key)
        result = await db.execute(query)
        config_record = result.scalar_one_or_none()
        
        if not config_record:
            return {
                'success': False,
                'error': 'preset_not_found',
                'message': f'Transcoding preset {preset_name} not found'
            }
        
        # Delete the preset
        delete_query = delete(SystemConfig).where(SystemConfig.key == key)
        await db.execute(delete_query)
        await db.commit()
        
        return {
            'success': True,
            'message': f'Transcoding preset {preset_name} deleted successfully'
        }
    
    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """Get a nested value using dot notation."""
        keys = key.split('.')
        value = data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    def _set_nested_value(self, data: Dict[str, Any], key: str, value: Any) -> None:
        """Set a nested value using dot notation."""
        keys = key.split('.')
        current = data
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Set the final value
        current[keys[-1]] = value
    
    def _validate_config_value(self, key: str, value: Any) -> Dict[str, Any]:
        """Validate a configuration value."""
        
        # Define validation rules for specific keys
        validation_rules = {
            'transcoding.max_concurrent_jobs': {
                'type': int,
                'min': 1,
                'max': 10
            },
            'transcoding.job_timeout_minutes': {
                'type': int,
                'min': 5,
                'max': 240
            },
            'upload_limits.max_file_size_gb': {
                'type': (int, float),
                'min': 0.1,
                'max': 100
            },
            'upload_limits.max_duration_hours': {
                'type': (int, float),
                'min': 0.1,
                'max': 24
            },
            'storage.cleanup_deleted_after_days': {
                'type': int,
                'min': 1,
                'max': 365
            }
        }
        
        # Check if we have specific validation rules for this key
        if key in validation_rules:
            rules = validation_rules[key]
            
            # Check type
            if 'type' in rules:
                expected_type = rules['type']
                if not isinstance(value, expected_type):
                    return {
                        'valid': False,
                        'message': f'Value must be of type {expected_type.__name__}'
                    }
            
            # Check numeric ranges
            if isinstance(value, (int, float)):
                if 'min' in rules and value < rules['min']:
                    return {
                        'valid': False,
                        'message': f'Value must be at least {rules["min"]}'
                    }
                
                if 'max' in rules and value > rules['max']:
                    return {
                        'valid': False,
                        'message': f'Value must be at most {rules["max"]}'
                    }
        
        # Additional validation for specific key patterns
        if key.startswith('transcoding.quality_presets.'):
            # Validate quality preset structure
            if not isinstance(value, dict):
                return {
                    'valid': False,
                    'message': 'Quality preset must be a dictionary'
                }
        
        return {'valid': True, 'message': 'Valid'}
    
    async def get_system_health(self, db: AsyncSession) -> Dict[str, Any]:
        """Get system health status based on configuration."""
        
        config = await self.get_all_config(db)
        health_status = {
            'overall_status': 'healthy',
            'checks': {},
            'warnings': [],
            'errors': []
        }
        
        # Check transcoding configuration
        transcoding_config = config.get('transcoding', {})
        enabled_presets = sum(
            1 for preset in transcoding_config.get('quality_presets', {}).values()
            if preset.get('enabled', False)
        )
        
        if enabled_presets == 0:
            health_status['errors'].append('No transcoding presets enabled')
            health_status['overall_status'] = 'error'
        elif enabled_presets < 2:
            health_status['warnings'].append('Only one transcoding preset enabled')
            if health_status['overall_status'] == 'healthy':
                health_status['overall_status'] = 'warning'
        
        health_status['checks']['transcoding_presets'] = {
            'status': 'ok' if enabled_presets >= 2 else 'warning' if enabled_presets == 1 else 'error',
            'enabled_presets': enabled_presets
        }
        
        # Check storage configuration
        storage_config = config.get('storage', {})
        if not storage_config.get('s3_bucket'):
            health_status['errors'].append('S3 bucket not configured')
            health_status['overall_status'] = 'error'
        
        health_status['checks']['storage'] = {
            'status': 'ok' if storage_config.get('s3_bucket') else 'error',
            'bucket_configured': bool(storage_config.get('s3_bucket'))
        }
        
        # Check upload limits
        upload_limits = config.get('upload_limits', {})
        max_size = upload_limits.get('max_file_size_gb', 0)
        if max_size > 50:
            health_status['warnings'].append('Very high file size limit may impact performance')
            if health_status['overall_status'] == 'healthy':
                health_status['overall_status'] = 'warning'
        
        health_status['checks']['upload_limits'] = {
            'status': 'ok' if max_size <= 50 else 'warning',
            'max_file_size_gb': max_size
        }
        
        return health_status