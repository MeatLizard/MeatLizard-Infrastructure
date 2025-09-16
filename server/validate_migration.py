#!/usr/bin/env python3
"""
Validate the database migration script and model definitions.
"""

import sys
import os

# Add the server directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

def validate_migration_file():
    """Validate the migration file syntax and structure."""
    
    migration_file = "web/alembic/versions/001_enhance_database_models_for_discord_integration.py"
    
    try:
        # Try to import the migration file
        spec = __import__(migration_file.replace('/', '.').replace('.py', ''), fromlist=[''])
        
        # Check required attributes
        required_attrs = ['revision', 'down_revision', 'upgrade', 'downgrade']
        for attr in required_attrs:
            if not hasattr(spec, attr):
                print(f"✗ Migration missing required attribute: {attr}")
                return False
            
        print(f"✓ Migration file structure is valid")
        print(f"  - Revision: {spec.revision}")
        print(f"  - Down revision: {spec.down_revision}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error validating migration file: {e}")
        return False


def validate_model_definitions():
    """Validate the SQLAlchemy model definitions."""
    
    try:
        from web.app.models import (
            Base, User, Session, Message, Transcript, 
            Metrics, SystemConfig, BackupLog,
            SessionOrigin, MessageRole, TranscriptFormat, BackupStatus
        )
        
        # Check that all models inherit from Base
        models = [User, Session, Message, Transcript, Metrics, SystemConfig, BackupLog]
        
        for model in models:
            if not issubclass(model, Base):
                print(f"✗ Model {model.__name__} does not inherit from Base")
                return False
            
            if not hasattr(model, '__tablename__'):
                print(f"✗ Model {model.__name__} missing __tablename__")
                return False
                
            print(f"✓ Model {model.__name__} is valid (table: {model.__tablename__})")
        
        # Check enums
        enums = [SessionOrigin, MessageRole, TranscriptFormat, BackupStatus]
        for enum_class in enums:
            print(f"✓ Enum {enum_class.__name__} is valid with values: {list(enum_class)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error validating model definitions: {e}")
        return False


def validate_shared_models():
    """Validate the shared Pydantic models."""
    
    try:
        from shared_lib.models import (
            UserData, SessionData, MessageData, TranscriptData,
            MetricsData, SystemConfigData, BackupLogData,
            MessageRole, SessionOrigin, TranscriptFormat, BackupStatus
        )
        
        # Test model instantiation
        models_to_test = [
            (UserData, {"display_label": "Test User"}),
            (SessionData, {"owner_user_id": "123e4567-e89b-12d3-a456-426614174000", "origin": SessionOrigin.DISCORD}),
            (MessageData, {"session_id": "123e4567-e89b-12d3-a456-426614174000", "role": MessageRole.USER, "content": "test"}),
            (TranscriptData, {"session_id": "123e4567-e89b-12d3-a456-426614174000", "format": TranscriptFormat.JSON}),
            (MetricsData, {"client_bot_id": "test", "metric_type": "performance", "metric_data": {}}),
            (SystemConfigData, {"key": "test", "value": {}}),
            (BackupLogData, {"backup_type": "database", "status": BackupStatus.COMPLETED})
        ]
        
        for model_class, test_data in models_to_test:
            try:
                instance = model_class(**test_data)
                print(f"✓ Pydantic model {model_class.__name__} is valid")
            except Exception as e:
                print(f"✗ Error creating {model_class.__name__}: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error validating shared models: {e}")
        return False


def main():
    """Run all validation checks."""
    
    print("Validating database models and migration...")
    print("=" * 50)
    
    all_valid = True
    
    print("\n1. Validating migration file...")
    if not validate_migration_file():
        all_valid = False
    
    print("\n2. Validating SQLAlchemy models...")
    if not validate_model_definitions():
        all_valid = False
    
    print("\n3. Validating shared Pydantic models...")
    if not validate_shared_models():
        all_valid = False
    
    print("\n" + "=" * 50)
    if all_valid:
        print("✓ All validations passed! Database models are ready.")
    else:
        print("✗ Some validations failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()