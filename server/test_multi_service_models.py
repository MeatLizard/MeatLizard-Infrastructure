#!/usr/bin/env python3
"""
Test the multi-service platform models.
"""

import sys
import os
import uuid
from datetime import datetime

# Add the server directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

def test_model_creation():
    """Test creating instances of the new models."""
    
    try:
        # Import required modules
        from web.app.models import (
            ShortUrl, ShortUrlAccessLog, Paste, PasteAccessLog,
            MediaFile, Playlist, PlaylistItem, MediaComment, MediaLike,
            UserStorageUsage, PastePrivacyLevel, MediaProcessingStatus
        )
        
        print("✓ Successfully imported all multi-service models")
        
        # Test creating model instances
        test_user_id = uuid.uuid4()
        
        # Test ShortUrl
        short_url = ShortUrl(
            user_id=test_user_id,
            slug="test123",
            target_url="https://example.com",
            title="Test URL"
        )
        print("✓ ShortUrl model creation successful")
        
        # Test Paste
        paste = Paste(
            user_id=test_user_id,
            paste_id="abc123",
            content="Test paste content",
            privacy_level=PastePrivacyLevel.public
        )
        print("✓ Paste model creation successful")
        
        # Test MediaFile
        media_file = MediaFile(
            user_id=test_user_id,
            media_id="med123",
            original_filename="test.mp4",
            file_size_bytes=1024000,
            mime_type="video/mp4",
            storage_path="/path/to/file",
            processing_status=MediaProcessingStatus.pending
        )
        print("✓ MediaFile model creation successful")
        
        # Test Playlist
        playlist = Playlist(
            user_id=test_user_id,
            name="Test Playlist",
            description="A test playlist"
        )
        print("✓ Playlist model creation successful")
        
        # Test UserStorageUsage
        storage_usage = UserStorageUsage(
            user_id=test_user_id,
            used_bytes=1024000,
            quota_bytes=4294967296  # 4GB
        )
        print("✓ UserStorageUsage model creation successful")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing model creation: {e}")
        return False

def test_enums():
    """Test the enum values."""
    
    try:
        from web.app.models import PastePrivacyLevel, MediaProcessingStatus
        
        # Test PastePrivacyLevel
        privacy_levels = list(PastePrivacyLevel)
        expected_privacy = ['public', 'private', 'password']
        for level in expected_privacy:
            if level not in [p.value for p in privacy_levels]:
                print(f"✗ Missing privacy level: {level}")
                return False
        print(f"✓ PastePrivacyLevel enum has all expected values: {[p.value for p in privacy_levels]}")
        
        # Test MediaProcessingStatus
        processing_statuses = list(MediaProcessingStatus)
        expected_statuses = ['pending', 'processing', 'completed', 'failed']
        for status in expected_statuses:
            if status not in [s.value for s in processing_statuses]:
                print(f"✗ Missing processing status: {status}")
                return False
        print(f"✓ MediaProcessingStatus enum has all expected values: {[s.value for s in processing_statuses]}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing enums: {e}")
        return False

def test_tier_configuration_updates():
    """Test that TierConfiguration has the new fields."""
    
    try:
        from web.app.models import TierConfiguration
        
        # Check new fields exist
        new_fields = [
            'url_shortener_enabled', 'max_short_urls', 'custom_vanity_slugs',
            'pastebin_enabled', 'max_pastes', 'max_paste_ttl_days', 'private_pastes',
            'media_upload_enabled', 'media_storage_quota_gb'
        ]
        
        for field in new_fields:
            if not hasattr(TierConfiguration, field):
                print(f"✗ TierConfiguration missing field: {field}")
                return False
        
        print(f"✓ TierConfiguration has all new multi-service fields")
        return True
        
    except Exception as e:
        print(f"✗ Error testing TierConfiguration: {e}")
        return False

def main():
    """Run all tests."""
    
    print("Testing multi-service platform models...")
    print("=" * 50)
    
    all_tests_passed = True
    
    print("\n1. Testing model creation...")
    if not test_model_creation():
        all_tests_passed = False
    
    print("\n2. Testing enums...")
    if not test_enums():
        all_tests_passed = False
    
    print("\n3. Testing TierConfiguration updates...")
    if not test_tier_configuration_updates():
        all_tests_passed = False
    
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("✓ All tests passed! Multi-service models are working correctly.")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()