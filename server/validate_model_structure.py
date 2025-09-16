#!/usr/bin/env python3
"""
Validate the structure of multi-service platform models without importing.
"""

import ast
import sys

def extract_class_info(file_path):
    """Extract class and enum information from a Python file."""
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        classes = []
        enums = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's an enum
                for base in node.bases:
                    if isinstance(base, ast.Attribute) and base.attr == 'Enum':
                        enums.append(node.name)
                        break
                    elif isinstance(base, ast.Name) and 'enum' in base.id.lower():
                        enums.append(node.name)
                        break
                else:
                    classes.append(node.name)
        
        return classes, enums
        
    except Exception as e:
        print(f"✗ Error parsing {file_path}: {e}")
        return [], []

def validate_model_structure():
    """Validate that all expected models and enums are defined."""
    
    classes, enums = extract_class_info("web/app/models.py")
    
    # Expected new models
    expected_models = [
        'ShortUrl', 'ShortUrlAccessLog', 'Paste', 'PasteAccessLog',
        'MediaFile', 'Playlist', 'PlaylistItem', 'MediaComment', 
        'MediaLike', 'UserStorageUsage'
    ]
    
    # Expected new enums
    expected_enums = [
        'PastePrivacyLevel', 'MediaProcessingStatus'
    ]
    
    print("Checking for new models...")
    all_models_found = True
    for model in expected_models:
        if model in classes:
            print(f"✓ Found model: {model}")
        else:
            print(f"✗ Missing model: {model}")
            all_models_found = False
    
    print("\nChecking for new enums...")
    all_enums_found = True
    for enum in expected_enums:
        if enum in enums:
            print(f"✓ Found enum: {enum}")
        else:
            print(f"✗ Missing enum: {enum}")
            all_enums_found = False
    
    return all_models_found and all_enums_found

def validate_migration_structure():
    """Validate the migration file structure."""
    
    try:
        with open("web/alembic/versions/005_add_multi_service_platform_models.py", 'r') as f:
            content = f.read()
        
        # Check for key migration elements
        required_elements = [
            'revision = \'005\'',
            'down_revision = \'004\'',
            'def upgrade()',
            'def downgrade()',
            'op.create_table(\'short_urls\'',
            'op.create_table(\'pastes\'',
            'op.create_table(\'media_files\'',
            'CREATE TYPE pasteprivacylevel',
            'CREATE TYPE mediaprocessingstatus'
        ]
        
        print("Checking migration file structure...")
        all_elements_found = True
        for element in required_elements:
            if element in content:
                print(f"✓ Found: {element}")
            else:
                print(f"✗ Missing: {element}")
                all_elements_found = False
        
        return all_elements_found
        
    except Exception as e:
        print(f"✗ Error reading migration file: {e}")
        return False

def validate_tier_configuration_updates():
    """Check that TierConfiguration has new fields."""
    
    try:
        with open("web/app/models.py", 'r') as f:
            content = f.read()
        
        # Look for TierConfiguration class and new fields
        new_fields = [
            'url_shortener_enabled', 'max_short_urls', 'custom_vanity_slugs',
            'pastebin_enabled', 'max_pastes', 'max_paste_ttl_days', 'private_pastes',
            'media_upload_enabled', 'media_storage_quota_gb'
        ]
        
        print("Checking TierConfiguration updates...")
        all_fields_found = True
        
        # Find TierConfiguration class
        if 'class TierConfiguration(Base):' in content:
            print("✓ Found TierConfiguration class")
            
            for field in new_fields:
                if f'{field} = Column(' in content:
                    print(f"✓ Found field: {field}")
                else:
                    print(f"✗ Missing field: {field}")
                    all_fields_found = False
        else:
            print("✗ TierConfiguration class not found")
            all_fields_found = False
        
        return all_fields_found
        
    except Exception as e:
        print(f"✗ Error checking TierConfiguration: {e}")
        return False

def main():
    """Run all validation checks."""
    
    print("Validating multi-service platform model structure...")
    print("=" * 60)
    
    all_valid = True
    
    print("\n1. Validating model definitions...")
    if not validate_model_structure():
        all_valid = False
    
    print("\n2. Validating migration structure...")
    if not validate_migration_structure():
        all_valid = False
    
    print("\n3. Validating TierConfiguration updates...")
    if not validate_tier_configuration_updates():
        all_valid = False
    
    print("\n" + "=" * 60)
    if all_valid:
        print("✓ All structure validations passed!")
        print("✓ Database models and migration are properly defined.")
    else:
        print("✗ Some validations failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()