import hashlib
import logging
import os

logger = logging.getLogger('jarvis.security.auth')


class SecurityManager:
    def __init__(self):
        self._api_keys: dict[str, str] = {}
        self._acl: dict[str, list[str]] = {}
        self._require_auth = True
        self._load_from_env()

    def _load_from_env(self):
        key = os.environ.get("JARVIS_API_KEY", "")
        if key:
            self._api_keys[key] = "admin"
        from core.config import load_config
        try:
            cfg = load_config()
            for k, v in cfg.get('api_keys', {}).items():
                self._api_keys[k] = v
        except Exception:
            pass

    def add_api_key(self, key: str, role: str = "user"):
        self._api_keys[key] = role

    def remove_api_key(self, key: str):
        self._api_keys.pop(key, None)

    def verify_api_key(self, key: str) -> bool:
        return key in self._api_keys

    def get_role(self, key: str) -> str:
        return self._api_keys.get(key, "")

    def check_permission(self, tool: str, user: str = None) -> bool:
        if not self._require_auth:
            return True
        if user in self._acl:
            allowed = self._acl[user]
            if "*" in allowed or tool in allowed:
                return True
        role_key = f"role:{self._api_keys.get(user, 'user')}"
        if role_key in self._acl:
            allowed = self._acl[role_key]
            if "*" in allowed or tool in allowed:
                return True
        return False

    def require_auth(self) -> bool:
        return self._require_auth

    def set_require_auth(self, value: bool):
        self._require_auth = value

    def set_acl(self, acl: dict[str, list[str]]):
        self._acl = acl

    def get_acl(self) -> dict[str, list[str]]:
        return dict(self._acl)

    def hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()
