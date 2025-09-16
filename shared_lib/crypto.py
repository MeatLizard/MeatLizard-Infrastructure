# shared_lib/crypto.py
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

load_dotenv()

class Encryptor:
    def __init__(self, key: str):
        self.key = bytes.fromhex(key)
        self.aesgcm = AESGCM(self.key)

    def encrypt(self, plaintext: str) -> bytes:
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return nonce + ciphertext

    def decrypt(self, ciphertext: bytes) -> str:
        nonce = ciphertext[:12]
        ciphertext = ciphertext[12:]
        plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

def get_encryptor():
    key = os.getenv("PAYLOAD_ENCRYPTION_KEY")
    if not key:
        raise ValueError("PAYLOAD_ENCRYPTION_KEY not set")
    return Encryptor(key)