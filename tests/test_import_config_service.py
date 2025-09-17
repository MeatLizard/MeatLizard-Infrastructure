"""
Tests for Import Configuration Service.
"""
import pytest
from datetime import datetime

from server.web.app.services.import_config_service import ImportConfigService
from server.web.app.services.media_import_service import ImportConfig
from server.web.app.models import ImportPreset, User, ImportJob, ImportStatus


class TestImportConfigService:
    """Test cases for ImportConfigService"""
    
    @pytest.fixture
    async def service(self, db_session):
        """Create ImportConfigService instance"""
        return ImportConfigService(db_session)
    
    @pytest.fixture
    async def test_user(self, db_session):
        """Create test user"""
        user = User(
            display_label="Test User",
            email="test@example.com"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user
    
    @pytest.fixture
    def sample_config(self):
        """Sample import configuration"""
        return ImportConfig(
            max_height=720,
            max_fps=30,
            quality_presets=["720p_30fps"],
            preserve_metadata=True,
            auto_publish=False
        )
    
    async def test_create_preset(self, service, test_user, sample_config):
        """Test creating a new import preset"""
        preset = await service.create_preset(
            name="Test Preset",
            description="Test description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        assert preset.name == "Test Preset"
        assert preset.description == "Test description"
        assert preset.created_by == test_user.id
        assert preset.config == sample_config.dict()
        assert preset.is_default is False
    
    async def test_create_preset_duplicate_name(self, service, test_user, sample_config):
        """Test creating preset with duplicate name fails"""
        # Create first preset
        await service.create_preset(
            name="Test Preset",
            description="First preset",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Try to create second preset with same name
        with pytest.raises(ValueError, match="already exists"):
            await service.create_preset(
                name="Test Preset",
                description="Second preset",
                config=sample_config,
                user_id=str(test_user.id)
            )
    
    async def test_update_preset(self, service, test_user, sample_config):
        """Test updating an existing preset"""
        # Create preset
        preset = await service.create_preset(
            name="Test Preset",
            description="Original description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Update preset
        new_config = ImportConfig(
            max_height=1080,
            max_fps=60,
            quality_presets=["1080p_60fps"],
            preserve_metadata=True,
            auto_publish=True
        )
        
        updated_preset = await service.update_preset(
            preset_id=str(preset.id),
            name="Updated Preset",
            description="Updated description",
            config=new_config,
            user_id=str(test_user.id)
        )
        
        assert updated_preset.name == "Updated Preset"
        assert updated_preset.description == "Updated description"
        assert updated_preset.config == new_config.dict()
    
    async def test_update_preset_unauthorized(self, service, test_user, sample_config, db_session):
        """Test updating preset by unauthorized user fails"""
        # Create another user
        other_user = User(
            display_label="Other User",
            email="other@example.com"
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        # Create preset
        preset = await service.create_preset(
            name="Test Preset",
            description="Original description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Try to update with different user
        with pytest.raises(ValueError, match="Not authorized"):
            await service.update_preset(
                preset_id=str(preset.id),
                name="Hacked Preset",
                user_id=str(other_user.id)
            )
    
    async def test_delete_preset(self, service, test_user, sample_config):
        """Test deleting a preset"""
        # Create preset
        preset = await service.create_preset(
            name="Test Preset",
            description="Test description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Delete preset
        success = await service.delete_preset(
            preset_id=str(preset.id),
            user_id=str(test_user.id)
        )
        
        assert success is True
        
        # Verify preset is deleted
        deleted_preset = await service.get_preset_by_id(str(preset.id))
        assert deleted_preset is None
    
    async def test_delete_preset_unauthorized(self, service, test_user, sample_config, db_session):
        """Test deleting preset by unauthorized user fails"""
        # Create another user
        other_user = User(
            display_label="Other User",
            email="other@example.com"
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)
        
        # Create preset
        preset = await service.create_preset(
            name="Test Preset",
            description="Test description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Try to delete with different user
        with pytest.raises(ValueError, match="Not authorized"):
            await service.delete_preset(
                preset_id=str(preset.id),
                user_id=str(other_user.id)
            )
    
    async def test_get_preset_by_id(self, service, test_user, sample_config):
        """Test getting preset by ID"""
        # Create preset
        preset = await service.create_preset(
            name="Test Preset",
            description="Test description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Get preset by ID
        retrieved_preset = await service.get_preset_by_id(str(preset.id))
        
        assert retrieved_preset is not None
        assert retrieved_preset.id == preset.id
        assert retrieved_preset.name == "Test Preset"
    
    async def test_get_preset_by_name(self, service, test_user, sample_config):
        """Test getting preset by name"""
        # Create preset
        await service.create_preset(
            name="Test Preset",
            description="Test description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Get preset by name
        retrieved_preset = await service.get_preset_by_name("Test Preset", str(test_user.id))
        
        assert retrieved_preset is not None
        assert retrieved_preset.name == "Test Preset"
        assert retrieved_preset.created_by == test_user.id
    
    async def test_get_user_presets(self, service, test_user, sample_config):
        """Test getting all presets for a user"""
        # Create custom preset
        await service.create_preset(
            name="Custom Preset",
            description="Custom description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Get user presets (including defaults)
        presets = await service.get_user_presets(str(test_user.id), include_defaults=True)
        
        # Should have custom preset plus default presets
        assert len(presets) > 1
        
        custom_presets = [p for p in presets if p.name == "Custom Preset"]
        assert len(custom_presets) == 1
        
        default_presets = [p for p in presets if p.created_by == "system"]
        assert len(default_presets) > 0
    
    async def test_get_user_presets_no_defaults(self, service, test_user, sample_config):
        """Test getting user presets without defaults"""
        # Create custom preset
        await service.create_preset(
            name="Custom Preset",
            description="Custom description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Get user presets (excluding defaults)
        presets = await service.get_user_presets(str(test_user.id), include_defaults=False)
        
        # Should only have custom preset
        assert len(presets) == 1
        assert presets[0].name == "Custom Preset"
    
    async def test_set_default_preset(self, service, test_user, sample_config):
        """Test setting a preset as default"""
        # Create preset
        preset = await service.create_preset(
            name="Test Preset",
            description="Test description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Set as default
        success = await service.set_default_preset(
            preset_id=str(preset.id),
            user_id=str(test_user.id)
        )
        
        assert success is True
        
        # Verify it's set as default
        default_preset = await service.get_default_preset(str(test_user.id))
        assert default_preset is not None
        assert default_preset.id == preset.id
    
    async def test_get_default_preset_fallback(self, service, test_user):
        """Test getting default preset when user has no custom default"""
        # Get default preset (should return system default)
        default_preset = await service.get_default_preset(str(test_user.id))
        
        assert default_preset is not None
        assert default_preset.created_by == "system"
    
    async def test_get_platform_optimization_config(self, service):
        """Test getting platform-specific optimization config"""
        # Test YouTube config
        youtube_config = await service.get_platform_optimization_config("YouTube")
        assert "preferred_codec" in youtube_config
        assert youtube_config["preferred_codec"] == "h264"
        
        # Test unknown platform
        unknown_config = await service.get_platform_optimization_config("UnknownPlatform")
        assert unknown_config == {}
    
    async def test_create_optimized_config(self, service, sample_config):
        """Test creating optimized config for platform"""
        # Create optimized config for YouTube
        optimized_config = await service.create_optimized_config("YouTube", sample_config)
        
        # Should have original settings plus YouTube optimizations
        assert optimized_config.max_height == 720  # From original
        assert optimized_config.preferred_codec == "h264"  # From YouTube optimization
        assert optimized_config.audio_format == "aac"  # From YouTube optimization
    
    async def test_validate_storage_quota(self, service, test_user):
        """Test storage quota validation"""
        quota_info = await service.validate_storage_quota(str(test_user.id))
        
        assert "used_storage" in quota_info
        assert "total_quota" in quota_info
        assert "available_storage" in quota_info
        assert "usage_percentage" in quota_info
        assert "can_import" in quota_info
        assert quota_info["can_import"] is True
    
    def test_validate_import_config_valid(self, service):
        """Test validation of valid import config"""
        config = ImportConfig(
            max_height=720,
            max_fps=30,
            quality_presets=["720p_30fps"],
            preserve_metadata=True
        )
        
        # Should not raise exception
        service._validate_import_config(config)
    
    def test_validate_import_config_audio_only_conflict(self, service):
        """Test validation fails for audio-only with video settings"""
        config = ImportConfig(
            audio_only=True,
            max_height=720,  # Conflicting setting
            quality_presets=["720p_30fps"]
        )
        
        with pytest.raises(ValueError, match="Audio-only imports cannot have video quality settings"):
            service._validate_import_config(config)
    
    def test_validate_import_config_invalid_preset(self, service):
        """Test validation fails for invalid quality preset"""
        config = ImportConfig(
            quality_presets=["invalid_preset"]
        )
        
        with pytest.raises(ValueError, match="Invalid quality preset"):
            service._validate_import_config(config)
    
    def test_validate_import_config_invalid_filesize(self, service):
        """Test validation fails for invalid file size format"""
        config = ImportConfig(
            max_filesize="500MB"  # Should be "500M"
        )
        
        with pytest.raises(ValueError, match="Invalid file size format"):
            service._validate_import_config(config)
    
    def test_validate_import_config_invalid_audio_format(self, service):
        """Test validation fails for invalid audio format"""
        config = ImportConfig(
            audio_only=True,
            audio_format="invalid_format"
        )
        
        with pytest.raises(ValueError, match="Invalid audio format"):
            service._validate_import_config(config)
    
    def test_get_default_presets(self, service):
        """Test getting default system presets"""
        default_presets = service._get_default_presets()
        
        assert len(default_presets) > 0
        
        # Check that all default presets are properly configured
        for preset in default_presets:
            assert preset.name is not None
            assert preset.description is not None
            assert preset.config is not None
            assert preset.created_by == "system"
            assert preset.is_default is True
    
    async def test_get_preset_usage_stats(self, service, test_user, sample_config, db_session):
        """Test getting preset usage statistics"""
        # Create preset
        preset = await service.create_preset(
            name="Test Preset",
            description="Test description",
            config=sample_config,
            user_id=str(test_user.id)
        )
        
        # Create import job that uses this preset
        job = ImportJob(
            source_url="https://youtube.com/watch?v=test",
            platform="YouTube",
            import_config={"preset_id": str(preset.id)},
            requested_by=test_user.id,
            status=ImportStatus.completed
        )
        db_session.add(job)
        await db_session.commit()
        
        # Get usage stats
        stats = await service.get_preset_usage_stats(str(preset.id))
        
        assert stats["total_jobs"] == 1
        assert stats["successful_jobs"] == 1
        assert stats["failed_jobs"] == 0
        assert stats["success_rate"] == 100.0
        assert stats["last_used"] is not None