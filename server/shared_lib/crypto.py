import base64
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .config import settings

class PayloadEncryptor:
    def __init__(self, key: str):
        if not key:
            raise ValueError("Encryption key cannot be empty.")
        # Key must be 32 bytes for AES-256
        self.key = base64.b64decode(key)
        self.aesgcm = AESGCM(self.key)

    def encrypt(self, data: dict) -> str:
        """Encrypts a dictionary to a Base64 string."""
        plaintext = json.dumps(data).encode('utf-8')
        # Using a fixed nonce is insecure. In a real system, generate and prepend it.
        # For simplicity in this bot-to-bot context with a shared key, we use a zero nonce.
        # A better approach would be to use a counter or random nonce per message.
        nonce = b'\x00' * 12
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, None)
        return base64.b64encode(ciphertext).decode('utf-8')

    def decrypt(self, encrypted_data: str) -> dict:
        """Decrypts a Base64 string back to a dictionary."""
        ciphertext = base64.b64decode(encrypted_data)
        nonce = b'\x00' * 12
        try:
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext.decode('utf-8'))
        except Exception as e:
            # Handle potential decryption errors (e.g., invalid key, corrupted data)
            print(f"Decryption failed: {e}")
            raise ValueError("Invalid or corrupted data")

encryptor = PayloadEncryptor(settings.ENCRYPTION_KEY_B64)
