#!/usr/bin/env python3
"""
Validate the multi-service platform migration and model definitions.
"""

import sys
import os

# Add the server directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

def validate_migration_file():
    """Validate the migration file syntax and structure."""
    
    migration_file = "web/alembic/versions/005_add_multi_service_platform_models.py"
    
    try:
        # Try to import the migration file
        import importlib.util
        spec = importlib.util.spec_from_file_location("migration", migration_file)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)
        
        # Check required attributes
        required_attrs = ['revision', 'down_revision', 'upgrade', 'downgrade']
        for attr in required_attrs:
            if not hasattr(migration_module, attr):
                print(f"✗ Migration missing required attribute: {attr}")
                return False
            
        print(f"✓ Migration file structure is valid")
        print(f"  - Revision: {migration_module.revision}")
        print(f"  - Down revision: {migration_module.down_revision}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error validating migration file: {e}")
        return False


def validate_model_definitions():
    """Validate the SQLAlchemy model definitions."""
    
    try:
        from web.app.models import (
            Base, User, TierConfiguration,
            ShortUrl, ShortUrlAccessLog, Paste, PasteAccessLog,
            MediaFile, Playlist, PlaylistItem, MediaComment, MediaLike,
            UserStorageUsage, PastePrivacyLevel, MediaProcessingStatus
        )
        
        # Check that all new models inherit from Base
        new_models = [
            ShortUrl, ShortUrlAccessLog, Paste, PasteAccessLog,
            MediaFile, Playlist, PlaylistItem, MediaComment, MediaLike,
            UserStorageUsage
        ]
        
        for model in new_models:
            if not issubclass(model, Base):
                print(f"✗ Model {model.__name__} does not inherit from Base")
                return False
            
            if not hasattr(model, '__tablename__'):
                print(f"✗ Model {model.__name__} missing __tablename__")
                return False
                
            print(f"✓ Model {model.__name__} is valid (table: {model.__tablename__})")
        
        # Check enums
        enums = [PastePrivacyLevel, MediaProcessingStatus]
        for enum_class in enums:
            print(f"✓ Enum {enum_class.__name__} is valid with values: {list(enum_class)}")
        
        # Check TierConfiguration has new fields
        tier_config = TierConfiguration()
        new_fields = [
            'url_shortener_enabled', 'max_short_urls', 'custom_vanity_slugs',
            'pastebin_enabled', 'max_pastes', 'max_paste_ttl_days', 'private_pastes',
            'media_upload_enabled', 'media_storage_quota_gb'
        ]
        
        for field in new_fields:
            if not hasattr(TierConfiguration, field):
                print(f"✗ TierConfiguration missing field: {field}")
                return False
            print(f"✓ TierConfiguration has field: {field}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error validating model definitions: {e}")
        return False


def validate_relationships():
    """Validate model relationships."""
    
    try:
        from web.app.models import User, ShortUrl, Paste, MediaFile
        
        # Check User relationships
        user = User()
        relationships = ['short_urls', 'pastes', 'media_files', 'playlists', 'media_comments', 'media_likes', 'storage_usage']
        
        for rel in relationships:
            if not hasattr(User, rel):
                print(f"✗ User missing relationship: {rel}")
                return False
            print(f"✓ User has relationship: {rel}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error validating relationships: {e}")
        return False


def main():
    """Run all validation checks."""
    
    print("Validating multi-service platform models and migration...")
    print("=" * 60)
    
    all_valid = True
    
    print("\n1. Validating migration file...")
    if not validate_migration_file():
        all_valid = False
    
    print("\n2. Validating SQLAlchemy models...")
    if not validate_model_definitions():
        all_valid = False
    
    print("\n3. Validating model relationships...")
    if not validate_relationships():
        all_valid = False
    
    print("\n" + "=" * 60)
    if all_valid:
        print("✓ All validations passed! Multi-service platform models are ready.")
    else:
        print("✗ Some validations failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()