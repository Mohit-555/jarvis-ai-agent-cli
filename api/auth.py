import hashlib
import hmac
import logging
import os
import time

logger = logging.getLogger('jarvis.api.auth')

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False


class AuthManager:
    def __init__(self, secret_key: str = None):
        secret = secret_key or os.environ.get("JARVIS_SECRET_KEY", "")
        if not secret:
            from core.config import KEYS_DIR
            key_file = KEYS_DIR / "jwt_secret"
            if key_file.exists():
                secret = key_file.read_text().strip()
            else:
                import secrets
                secret = secrets.token_hex(32)
                try:
                    key_file.write_text(secret)
                    os.chmod(key_file, 0o600)
                except Exception:
                    pass
        if secret == "change-me-in-production":
            raise ValueError("Insecure JARVIS_SECRET_KEY set to 'change-me-in-production'. Please change it.")
        self.secret_key = secret
        self._api_keys: dict[str, str] = {}

    def add_api_key(self, key: str, label: str = "default"):
        self._api_keys[key] = label

    def verify_api_key(self, key: str) -> bool:
        if not key:
            return False
        if key in self._api_keys:
            return True
        try:
            from core.config import load_config
            cfg = load_config()
            configured_key = cfg.get("api_key", "")
            if configured_key and hmac.compare_digest(configured_key, key):
                return True
        except Exception:
            pass
        return False

    def create_token(self, user: str, expires_in: int = 3600) -> str:
        if not HAS_JWT:
            logger.warning("JWT not installed, using unsigned token")
            return f"tok_{user}_{int(time.time())}"
        payload = {
            "sub": user,
            "iat": int(time.time()),
            "exp": int(time.time()) + expires_in,
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> dict:
        if not token:
            return {}
        if not HAS_JWT:
            parts = token.split("_")
            if len(parts) >= 2:
                return {"sub": parts[1], "verified": False}
            return {}
        try:
            return jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return {}
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return {}
