"""
AES-256-GCM encryption and decryption for message payloads.
"""
import os
from base64 import b64encode, b64decode
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

class AESCipher:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("AES key must be 32 bytes long")
        self.key = key

    def encrypt(self, plaintext: str) -> dict:
        """
        Encrypts plaintext using AES-256-GCM.
        Returns a dictionary with ciphertext, iv, and auth_tag, all base64-encoded.
        """
        data = plaintext.encode('utf-8')
        cipher = AES.new(self.key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return {
            'encrypted_payload': b64encode(ciphertext).decode('utf-8'),
            'iv': b64encode(cipher.nonce).decode('utf-8'),
            'auth_tag': b64encode(tag).decode('utf-8')
        }

    def decrypt(self, encrypted_data: dict) -> str:
        """
        Decrypts a payload encrypted with AES-256-GCM.
        Expects a dictionary with base64-encoded ciphertext, iv, and auth_tag.
        """
        iv = b64decode(encrypted_data['iv'])
        tag = b64decode(encrypted_data['auth_tag'])
        ciphertext = b64decode(encrypted_data['encrypted_payload'])
        
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=iv)
        decrypted_data = cipher.decrypt_and_verify(ciphertext, tag)
        return decrypted_data.decode('utf-8')

# Example usage:
# key = get_random_bytes(32) # Store this securely!
# cipher = AESCipher(key)
# encrypted = cipher.encrypt("Hello, secure world!")
# print(encrypted)
# decrypted = cipher.decrypt(encrypted)
# print(decrypted)
