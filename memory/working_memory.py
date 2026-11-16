import time
import threading

try:
    import redis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False


class WorkingMemory:
    def __init__(self, redis_url: str = None, default_ttl: int = 3600):
        self._default_ttl = default_ttl
        self._local: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._redis = None
        if _HAS_REDIS and redis_url:
            try:
                self._redis = redis.from_url(redis_url, decode_responses=True)
            except Exception:
                self._redis = None

    def set(self, key: str, value: str, ttl: int = None):
        ttl = ttl or self._default_ttl
        if self._redis:
            try:
                self._redis.setex(key, ttl, value)
                return
            except Exception:
                pass
        with self._lock:
            self._local[key] = (value, time.time() + ttl)

    def get(self, key: str) -> str:
        if self._redis:
            try:
                val = self._redis.get(key)
                if val is not None:
                    return val
            except Exception:
                pass
        with self._lock:
            entry = self._local.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if time.time() > expiry:
                del self._local[key]
                return None
            return value

    def delete(self, key: str):
        if self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        with self._lock:
            self._local.pop(key, None)

    def clear(self):
        if self._redis:
            try:
                self._redis.flushdb()
            except Exception:
                pass
        with self._lock:
            self._local.clear()

    def keys(self, pattern: str = "*") -> list[str]:
        if self._redis:
            try:
                return self._redis.keys(pattern)
            except Exception:
                pass
        with self._lock:
            now = time.time()
            return [k for k, (_, e) in self._local.items() if now <= e]

    def cleanup_expired(self):
        if not self._redis:
            with self._lock:
                now = time.time()
                expired = [k for k, (_, e) in self._local.items() if now > e]
                for k in expired:
                    del self._local[k]
