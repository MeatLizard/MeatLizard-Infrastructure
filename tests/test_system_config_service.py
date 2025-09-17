"""
Tests for system configuration service.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.services.system_config_service import SystemConfigService
from server.web.app.models import SystemConfig


@pytest.fixture
async def config_service():
    return SystemConfigService()


class TestSystemConfigService:
    
    async def test_get_all_config_defaults(
        self, 
        config_service: SystemConfigService, 
        db_session: AsyncSession
    ):
        """Test getting all configuration returns defaults when no config exists."""
        config = await config_service.get_all_config(db_session)
        
        assert 'transcoding' in config
        assert 'upload_limits' in config
        assert 'storage' in config
        assert 'content_moderation' in config
        assert 'analytics' in config
        assert 'notifications' in config
        
        # Check some default values
        assert config['transcoding']['max_concurrent_jobs'] == 3
        assert config['upload_limits']['max_file_size_gb'] == 10
        assert config['storage']['s3_bucket'] == 'meatlizard-video-storage'
    
    async def test_set_and_get_config_value(
        self, 
        config_service: SystemConfigService, 
        db_session: AsyncSession
    ):
        """Test setting and getting a configuration value."""
        key = 'transcoding.max_concurrent_jobs'
        value = 5
        
        # Set the value
        result = await config_service.set_config_value(db_session, key, value)
        
        assert result['success'] is True
        assert result['key'] == key
        assert result['value'] == value
        
        # Get the value
        retrieved_value = await config_service.get_config_value(db_session, key)
        assert retrieved_value == value
    
    async def test_set_config_section(
        self, 
        config_service: SystemConfigService, 
        db_session: AsyncSession
    ):
        """Test setting an entire configuration section."""
        section = 'upload_limits'
        config_data = {
            'max_file_size_gb': 20,
            'max_duration_hours': 8,
            'max_uploads_per_day': 100
        }
        
        result = await config_service.set_config_section(db_session, section, config_data)
        
        assert result['success'] is True
        assert len(result['updated_keys']) == 3
        
        # Verify the values were set
        section_config = await config_service.get_config_section(db_session, section)
        assert section_config['max_file_size_gb'] == 20
        assert section_config['max_duration_hours'] == 8
        assert section_config['max_uploads_per_day'] == 100
    
    async def test_get_config_section(
        self, 
        config_service: SystemConfigService, 
        db_session: AsyncSession
    ):
        """Test getting a specific configuration section."""
        # Set some values first
        await config_service.set_config_value(db_session, 'transcoding.max_concurrent_jobs', 7)
        await config_service.set_config_value(db_session, 'transcoding.job_timeout_minutes', 120)
        
        section_config = await config_service.get_config_section(db_session, 'transcoding')
        
        assert section_config['max_concurrent_jobs'] == 7
        assert section_config['job_timeout_minutes'] == 120
        # Should still have default values for other keys
        assert 'quality_presets' in section_config
    
    async def test_validate_config_value(
        self, 
        config_service: SystemConfigService
    ):
        """Test configuration value validation."""
        # Valid values
        result = config_service._validate_config_value('transcoding.max_concurrent_jobs', 5)
        assert result['valid'] is True
        
        # Invalid type
        result = config_service._validate_config_value('transcoding.max_concurrent_jobs', 'invalid')
        assert result['valid'] is False
        
        # Out of range
        result = config_service._validate_config_value('transcoding.max_concurrent_jobs', 15)
        assert result['valid'] is False
        
        # Valid range
        result = config_service._validate_config_value('upload_limits.max_file_size_gb', 5.5)
        assert result['valid'] is True
    
    async def test_transcoding_presets(
        self, 
        config_service: SystemConfigService, 
        db_session: AsyncSession
    ):
        """Test transcoding preset management."""
        # Get default presets
        presets = await config_service.get_transcoding_presets(db_session)
        
        assert '720p_30fps' in presets
        assert '1080p_30fps' in presets
        
        # Update a preset
        preset_name = 'custom_720p'
        preset_config = {
            'resolution': '1280x720',
            'framerate': 30,
            'bitrate': 3000000,
            'audio_bitrate': 128000,
            'enabled': True
        }
        
        result = await config_service.update_transcoding_preset(
            db_session, 
            preset_name, 
            preset_config
        )
        
        assert result['success'] is True
        
        # Verify the preset was added
        updated_presets = await config_service.get_transcoding_presets(db_session)
        assert preset_name in updated_presets
        assert updated_presets[preset_name]['bitrate'] == 3000000
    
    async def test_delete_transcoding_preset(
        self, 
        config_service: SystemConfigService, 
        db_session: AsyncSession
    ):
        """Test deleting a transcoding preset."""
        # First create a preset
        preset_name = 'test_preset'
        preset_config = {
            'resolution': '640x480',
            'framerate': 30,
            'bitrate': 1000000,
            'audio_bitrate': 128000,
            'enabled': True
        }
        
        await config_service.update_transcoding_preset(
            db_session, 
            preset_name, 
            preset_config
        )
        
        # Verify it exists
        presets = await config_service.get_transcoding_presets(db_session)
        assert preset_name in presets
        
        # Delete it
        result = await config_service.delete_transcoding_preset(db_session, preset_name)
        assert result['success'] is True
        
        # Verify it's gone
        updated_presets = await config_service.get_transcoding_presets(db_session)
        assert preset_name not in updated_presets
    
    async def test_reset_config_to_defaults(
        self, 
        config_service: SystemConfigService, 
        db_session: AsyncSession
    ):
        """Test resetting configuration to defaults."""
        # Set some custom values
        await config_service.set_config_value(db_session, 'transcoding.max_concurrent_jobs', 8)
        await config_service.set_config_value(db_session, 'upload_limits.max_file_size_gb', 25)
        
        # Verify they were set
        value1 = await config_service.get_config_value(db_session, 'transcoding.max_concurrent_jobs')
        value2 = await config_service.get_config_value(db_session, 'upload_limits.max_file_size_gb')
        assert value1 == 8
        assert value2 == 25
        
        # Reset transcoding section
        result = await config_service.reset_config_to_defaults(db_session, 'transcoding')
        assert result['success'] is True
        
        # Verify transcoding was reset but upload_limits wasn't
        value1_after = await config_service.get_config_value(db_session, 'transcoding.max_concurrent_jobs')
        value2_after = await config_service.get_config_value(db_session, 'upload_limits.max_file_size_gb')
        assert value1_after == 3  # Default value
        assert value2_after == 25  # Still custom value
        
        # Reset all configuration
        result = await config_service.reset_config_to_defaults(db_session)
        assert result['success'] is True
        
        # Verify all values are back to defaults
        value2_final = await config_service.get_config_value(db_session, 'upload_limits.max_file_size_gb')
        assert value2_final == 10  # Default value
    
    async def test_backup_and_restore_config(
        self, 
        config_service: SystemConfigService, 
        db_session: AsyncSession
    ):
        """Test configuration backup and restore."""
        # Set some custom values
        await config_service.set_config_value(db_session, 'transcoding.max_concurrent_jobs', 6)
        await config_service.set_config_value(db_session, 'upload_limits.max_file_size_gb', 15)
        
        # Create backup
        backup_result = await config_service.backup_config(db_session)
        assert backup_result['success'] is True
        assert 'backup_data' in backup_result
        
        backup_data = backup_result['backup_data']
        assert 'config' in backup_data
        assert backup_data['config']['transcoding']['max_concurrent_jobs'] == 6
        
        # Reset configuration
        await config_service.reset_config_to_defaults(db_session)
        
        # Verify values are back to defaults
        value = await config_service.get_config_value(db_session, 'transcoding.max_concurrent_jobs')
        assert value == 3
        
        # Restore from backup
        restore_result = await config_service.restore_config(db_session, backup_data)
        assert restore_result['success'] is True
        
        # Verify values are restored
        restored_value = await config_service.get_config_value(db_session, 'transcoding.max_concurrent_jobs')
        assert restored_value == 6
    
    async def test_get_system_health(
        self, 
        config_service: SystemConfigService, 
        db_session: AsyncSession
    ):
        """Test system health check."""
        health = await config_service.get_system_health(db_session)
        
        assert 'overall_status' in health
        assert 'checks' in health
        assert 'warnings' in health
        assert 'errors' in health
        
        # Should have checks for transcoding presets and storage
        assert 'transcoding_presets' in health['checks']
        assert 'storage' in health['checks']
        assert 'upload_limits' in health['checks']
        
        # With default config, should be healthy
        assert health['overall_status'] in ['healthy', 'warning']  # Might be warning if no S3 bucket configured
    
    async def test_invalid_transcoding_preset(
        self, 
        config_service: SystemConfigService, 
        db_session: AsyncSession
    ):
        """Test validation of invalid transcoding preset."""
        preset_name = 'invalid_preset'
        
        # Missing required fields
        invalid_config = {
            'resolution': '1280x720',
            'framerate': 30
            # Missing bitrate, audio_bitrate, enabled
        }
        
        result = await config_service.update_transcoding_preset(
            db_session, 
            preset_name, 
            invalid_config
        )
        
        assert result['success'] is False
        assert 'missing_field' in result['error']
        
        # Invalid resolution format
        invalid_config2 = {
            'resolution': 'invalid',
            'framerate': 30,
            'bitrate': 2000000,
            'audio_bitrate': 128000,
            'enabled': True
        }
        
        result2 = await config_service.update_transcoding_preset(
            db_session, 
            preset_name, 
            invalid_config2
        )
        
        assert result2['success'] is False
        assert 'validation_failed' in result2['error']