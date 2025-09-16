# shared_lib/encryption.py
import os
from base64 import b64encode, b64decode
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import json

class AESGCMEncryptor:
    """
    A utility for encrypting and decrypting data using AES-256-GCM.

    This class is designed to handle the encryption of JSON payloads
    for secure transmission between the server-bot and client-bot.
    """
    def __init__(self, key: str):
        """
        Initializes the encryptor with a 32-byte key.

        Args:
            key: A 32-byte (64 hex characters) secret key.
        
        Raises:
            ValueError: If the key is not 32 bytes long.
        """
        if len(bytes.fromhex(key)) != 32:
            raise ValueError("Encryption key must be 32 bytes (64 hex characters) long.")
        self.key = bytes.fromhex(key)

    def encrypt(self, plaintext_data: dict) -> str:
        """
        Encrypts a dictionary into a base64-encoded string.

        The format is: base64(nonce + tag + ciphertext)

        Args:
            plaintext_data: The dictionary to encrypt.

        Returns:
            A base64-encoded, encrypted string.
        """
        plaintext_bytes = json.dumps(plaintext_data).encode('utf-8')
        
        cipher = AES.new(self.key, AES.MODE_GCM)
        nonce = cipher.nonce
        
        ciphertext, tag = cipher.encrypt_and_digest(plaintext_bytes)
        
        # Combine nonce, tag, and ciphertext for storage/transmission
        encrypted_payload = nonce + tag + ciphertext
        
        return b64encode(encrypted_payload).decode('utf-8')

    def decrypt(self, encrypted_str: str) -> dict:
        """
        Decrypts a base64-encoded string back into a dictionary.

        Args:
            encrypted_str: The base64-encoded string from the encrypt method.

        Returns:
            The decrypted dictionary.

        Raises:
            ValueError: If the decryption fails due to authentication error (tampering)
                        or incorrect key.
        """
        encrypted_payload = b64decode(encrypted_str)
        
        # Extract the components
        nonce = encrypted_payload[:16]
        tag = encrypted_payload[16:32]
        ciphertext = encrypted_payload[32:]
        
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        
        try:
            decrypted_bytes = cipher.decrypt_and_verify(ciphertext, tag)
            return json.loads(decrypted_bytes.decode('utf-8'))
        except (ValueError, KeyError) as e:
            # This will be raised if the tag does not match, indicating the
            # message was tampered with or the key is incorrect.
            raise ValueError("Decryption failed. Message may be tampered with or key is incorrect.") from e


# --- Example Usage ---
if __name__ == "__main__":
    # Generate a random key for demonstration
    # In the real app, this comes from config/env
    secret_key_hex = get_random_bytes(32).hex()
    print(f"Using secret key: {secret_key_hex}")

    encryptor = AESGCMEncryptor(secret_key_hex)

    # The data to be sent
    original_payload = {
        "session_id": "sess_12345",
        "prompt": "Hello, world!",
        "user_id": "user_abc"
    }
    print(f"\nOriginal data: {original_payload}")

    # Encrypt the data
    encrypted_string = encryptor.encrypt(original_payload)
    print(f"\nEncrypted string: {encrypted_string}")

    # Decrypt the data
    try:
        decrypted_payload = encryptor.decrypt(encrypted_string)
        print(f"\nDecrypted data: {decrypted_payload}")
        
        assert original_payload == decrypted_payload
        print("\n✅ Success: Decrypted data matches original data.")

    except ValueError as e:
        print(f"\n❌ Error during decryption: {e}")

    # --- Tampering Demo ---
    print("\n--- Tampering Demo ---")
    # Modify one character in the encrypted string
    tampered_string = encrypted_string[:-1] + 'A'
    print(f"Tampered string: {tampered_string}")

    try:
        encryptor.decrypt(tampered_string)
    except ValueError as e:
        print(f"Caught expected error: {e}")
        print("✅ Success: Tampering was detected.")
