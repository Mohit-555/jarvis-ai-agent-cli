import base64
import logging
import os

logger = logging.getLogger('jarvis.security.encryption')

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


class EncryptionEngine:
    def __init__(self):
        self._default_key = os.environ.get("JARVIS_ENCRYPTION_KEY", "").encode()

    def _derive_key(self, key: bytes) -> bytes:
        if isinstance(key, str):
            key = key.encode('utf-8')
        key = key.ljust(32, b'\0')[:32]
        return key

    def encrypt(self, key: bytes, data: bytes) -> bytes:
        if HAS_CRYPTOGRAPHY:
            return self._encrypt_aesgcm(key, data)
        return self._encrypt_xor(key, data)

    def decrypt(self, key: bytes, data: bytes) -> bytes:
        if HAS_CRYPTOGRAPHY:
            return self._decrypt_aesgcm(key, data)
        return self._decrypt_xor(key, data)

    def encrypt_text(self, key: bytes, text: str) -> str:
        encrypted = self.encrypt(key, text.encode("utf-8"))
        return base64.b64encode(encrypted).decode("ascii")

    def decrypt_text(self, key: bytes, ciphertext: str) -> str:
        decoded = base64.b64decode(ciphertext)
        return self.decrypt(key, decoded).decode("utf-8")

    def _encrypt_aesgcm(self, key: bytes, data: bytes) -> bytes:
        derived = self._derive_key(key)
        aesgcm = AESGCM(derived)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, data, None)
        return nonce + ct

    def _decrypt_aesgcm(self, key: bytes, data: bytes) -> bytes:
        derived = self._derive_key(key)
        aesgcm = AESGCM(derived)
        nonce, ct = data[:12], data[12:]
        return aesgcm.decrypt(nonce, ct, None)

    def _encrypt_xor(self, key: bytes, data: bytes) -> bytes:
        derived = self._derive_key(key)
        result = bytearray()
        for i, b in enumerate(data):
            result.append(b ^ derived[i % len(derived)])
        return bytes(result)

    def _decrypt_xor(self, key: bytes, data: bytes) -> bytes:
        return self._encrypt_xor(key, data)
