"""
Tests for encryption utilities.
"""

import pytest
import base64
from shared_lib.encryption import MessageEncryption, EncryptionError, generate_encryption_key


class TestMessageEncryption:
    """Test cases for MessageEncryption class."""
    
    def test_initialization_with_key(self):
        """Test encryption initialization with provided key."""
        key = base64.b64decode(generate_encryption_key())
        encryption = MessageEncryption(key)
        assert encryption._key == key
    
    def test_initialization_without_key(self):
        """Test encryption initialization with generated key."""
        encryption = MessageEncryption()
        assert len(encryption._key) == 32
    
    def test_invalid_key_length(self):
        """Test initialization with invalid key length."""
        with pytest.raises(ValueError, match="Encryption key must be exactly 32 bytes"):
            MessageEncryption(b"short_key")
    
    def test_from_base64_key(self):
        """Test creating encryption from base64 key."""
        key_b64 = generate_encryption_key()
        encryption = MessageEncryption.from_base64_key(key_b64)
        assert encryption.key_base64 == key_b64
    
    def test_invalid_base64_key(self):
        """Test creating encryption from invalid base64 key."""
        with pytest.raises(EncryptionError, match="Invalid base64 key"):
            MessageEncryption.from_base64_key("invalid_base64!")
    
    def test_encrypt_decrypt_message(self):
        """Test basic message encryption and decryption."""
        encryption = MessageEncryption()
        message = "Hello, World!"
        
        encrypted = encryption.encrypt_message(message)
        decrypted = encryption.decrypt_message(encrypted)
        
        assert decrypted == message
        assert encrypted != message
    
    def test_encrypt_decrypt_with_aad(self):
        """Test encryption/decryption with additional authenticated data."""
        encryption = MessageEncryption()
        message = "Secret message"
        aad = "session_123"
        
        encrypted = encryption.encrypt_message(message, aad)
        decrypted = encryption.decrypt_message(encrypted, aad)
        
        assert decrypted == message
    
    def test_decrypt_with_wrong_aad(self):
        """Test decryption fails with wrong AAD."""
        encryption = MessageEncryption()
        message = "Secret message"
        aad = "session_123"
        wrong_aad = "session_456"
        
        encrypted = encryption.encrypt_message(message, aad)
        
        with pytest.raises(EncryptionError, match="Authentication failed"):
            encryption.decrypt_message(encrypted, wrong_aad)
    
    def test_encrypt_decrypt_json(self):
        """Test JSON encryption and decryption."""
        encryption = MessageEncryption()
        data = {
            "user_id": "123",
            "message": "Hello",
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        encrypted = encryption.encrypt_json(data)
        decrypted = encryption.decrypt_json(encrypted)
        
        assert decrypted == data
    
    def test_encrypt_invalid_json(self):
        """Test encryption of non-serializable data."""
        encryption = MessageEncryption()
        
        # Object with non-serializable content
        class NonSerializable:
            pass
        
        data = {"obj": NonSerializable()}
        
        with pytest.raises(EncryptionError, match="JSON serialization failed"):
            encryption.encrypt_json(data)
    
    def test_decrypt_invalid_json(self):
        """Test decryption of invalid JSON."""
        encryption = MessageEncryption()
        
        # Encrypt non-JSON string
        encrypted = encryption.encrypt_message("not json")
        
        with pytest.raises(EncryptionError, match="JSON parsing failed"):
            encryption.decrypt_json(encrypted)
    
    def test_decrypt_tampered_message(self):
        """Test decryption of tampered message."""
        encryption = MessageEncryption()
        message = "Original message"
        
        encrypted = encryption.encrypt_message(message)
        
        # Tamper with the encrypted data
        encrypted_bytes = base64.b64decode(encrypted)
        tampered_bytes = encrypted_bytes[:-1] + b'\x00'  # Change last byte
        tampered_encrypted = base64.b64encode(tampered_bytes).decode()
        
        with pytest.raises(EncryptionError, match="Authentication failed"):
            encryption.decrypt_message(tampered_encrypted)
    
    def test_decrypt_invalid_format(self):
        """Test decryption of invalid format."""
        encryption = MessageEncryption()
        
        with pytest.raises(EncryptionError, match="Decryption failed"):
            encryption.decrypt_message("invalid_base64!")
    
    def test_decrypt_short_data(self):
        """Test decryption of data too short to contain nonce."""
        encryption = MessageEncryption()
        
        # Create data shorter than nonce length (12 bytes)
        short_data = base64.b64encode(b"short").decode()
        
        with pytest.raises(EncryptionError, match="Decryption failed"):
            encryption.decrypt_message(short_data)
    
    def test_different_keys_cant_decrypt(self):
        """Test that different keys cannot decrypt each other's messages."""
        encryption1 = MessageEncryption()
        encryption2 = MessageEncryption()
        
        message = "Secret message"
        encrypted = encryption1.encrypt_message(message)
        
        with pytest.raises(EncryptionError, match="Authentication failed"):
            encryption2.decrypt_message(encrypted)
    
    def test_empty_message(self):
        """Test encryption of empty message."""
        encryption = MessageEncryption()
        message = ""
        
        encrypted = encryption.encrypt_message(message)
        decrypted = encryption.decrypt_message(encrypted)
        
        assert decrypted == message
    
    def test_unicode_message(self):
        """Test encryption of unicode message."""
        encryption = MessageEncryption()
        message = "Hello 世界! 🌍 émojis and ñoñó"
        
        encrypted = encryption.encrypt_message(message)
        decrypted = encryption.decrypt_message(encrypted)
        
        assert decrypted == message


def test_generate_encryption_key():
    """Test encryption key generation."""
    key1 = generate_encryption_key()
    key2 = generate_encryption_key()
    
    # Keys should be different
    assert key1 != key2
    
    # Keys should be valid base64
    decoded1 = base64.b64decode(key1)
    decoded2 = base64.b64decode(key2)
    
    # Keys should be 32 bytes
    assert len(decoded1) == 32
    assert len(decoded2) == 32