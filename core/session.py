import uuid
import time
import threading
from typing import Any

from core.event_bus import event_bus, EVENTS


class Session:
    def __init__(self, session_id: str = None, user_id: str = 'default'):
        self.session_id = session_id or str(uuid.uuid4())
        self.user_id = user_id
        self.created_at = time.time()
        self.last_active = time.time()
        self.messages: list[dict] = []
        self.state: dict[str, Any] = {}
        self.metadata: dict[str, Any] = {}

    def add_message(self, role: str, content: str, **kwargs):
        msg = {'role': role, 'content': content, 'timestamp': time.time(), **kwargs}
        self.messages.append(msg)
        self.last_active = time.time()

    def get_context(self, limit: int = 20):
        return self.messages[-limit:] if limit else self.messages

    def update_state(self, key: str, value: Any):
        self.state[key] = value
        self.last_active = time.time()

    def get_state(self, key: str, default=None):
        return self.state.get(key, default)

    def is_expired(self, ttl_seconds: int = 1800):
        return (time.time() - self.last_active) > ttl_seconds

    def to_dict(self):
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'created_at': self.created_at,
            'last_active': self.last_active,
            'message_count': len(self.messages),
            'state_keys': list(self.state.keys()),
            'metadata': self.metadata,
        }


class SessionManager:
    def __init__(self, ttl_seconds: int = 1800):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def create_session(self, user_id: str = 'default') -> Session:
        session = Session(user_id=user_id)
        with self._lock:
            self._sessions[session.session_id] = session
        event_bus.emit(EVENTS['SESSION_CREATED'], session_id=session.session_id, user_id=user_id)
        return session

    def get_session(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_active = time.time()
                return session
        return None

    def get_or_create(self, session_id: str = None, user_id: str = 'default') -> Session:
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        return self.create_session(user_id)

    def destroy_session(self, session_id: str):
        with self._lock:
            self._sessions.pop(session_id, None)
        event_bus.emit(EVENTS['SESSION_DESTROYED'], session_id=session_id)

    def list_sessions(self) -> list[dict]:
        with self._lock:
            return [s.to_dict() for s in self._sessions.values() if not s.is_expired(self._ttl)]

    def cleanup_expired(self):
        with self._lock:
            expired = [sid for sid, s in self._sessions.items() if s.is_expired(self._ttl)]
            for sid in expired:
                self._sessions.pop(sid, None)

    def get_message_history(self, session_id: str, limit: int = 20) -> list[dict]:
        session = self.get_session(session_id)
        if session:
            return session.get_context(limit)
        return []


session_manager = SessionManager()
