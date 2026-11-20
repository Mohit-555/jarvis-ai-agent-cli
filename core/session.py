import uuid
import time
import json
import threading
from typing import Any
from pathlib import Path

from core.event_bus import event_bus, EVENTS
from core.config import SESSIONS_DIR


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
        try:
            session_manager.save_session(self)
        except Exception:
            pass

    def get_context(self, limit: int = 20):
        return self.messages[-limit:] if limit else self.messages

    def update_state(self, key: str, value: Any):
        self.state[key] = value
        self.last_active = time.time()
        try:
            session_manager.save_session(self)
        except Exception:
            pass

    def get_state(self, key: str, default=None):
        return self.state.get(key, default)

    def is_expired(self, ttl_seconds: int = 1800):
        return (time.time() - self.last_active) > ttl_seconds

    def get_title(self) -> str:
        for m in self.messages:
            if m.get('role') == 'user' and m.get('content'):
                text = str(m['content']).strip().replace('\n', ' ')
                return text[:60] if len(text) <= 60 else text[:57] + '...'
        return "New Session"

    def to_dict(self):
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'created_at': self.created_at,
            'last_active': self.last_active,
            'message_count': len(self.messages),
            'turns': len(self.messages) // 2,
            'title': self.get_title(),
            'state_keys': list(self.state.keys()),
            'metadata': self.metadata,
        }

    def to_full_dict(self):
        data = self.to_dict()
        data['messages'] = self.messages
        data['state'] = self.state
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        session = cls(
            session_id=data.get('session_id'),
            user_id=data.get('user_id', 'default'),
        )
        session.created_at = data.get('created_at', time.time())
        session.last_active = data.get('last_active', time.time())
        session.messages = data.get('messages', [])
        session.state = data.get('state', {})
        session.metadata = data.get('metadata', {})
        return session


class SessionManager:
    def __init__(self, ttl_seconds: int = 1800):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._storage_dir: Path = SESSIONS_DIR

    def _ensure_dir(self):
        try:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def save_session(self, session: Session):
        self._ensure_dir()
        file_path = self._storage_dir / f"{session.session_id}.json"
        try:
            tmp_path = self._storage_dir / f"{session.session_id}.tmp"
            tmp_path.write_text(json.dumps(session.to_full_dict(), indent=2))
            tmp_path.replace(file_path)
        except Exception:
            try:
                file_path.write_text(json.dumps(session.to_full_dict(), indent=2))
            except Exception:
                pass

    def create_session(self, user_id: str = 'default') -> Session:
        session = Session(user_id=user_id)
        with self._lock:
            self._sessions[session.session_id] = session
        self.save_session(session)
        event_bus.emit(EVENTS['SESSION_CREATED'], session_id=session.session_id, user_id=user_id)
        return session

    def get_session(self, session_id: str) -> Session | None:
        if not session_id:
            return None
        session_id = session_id.strip()

        with self._lock:
            # 1. Exact match in memory
            if session_id in self._sessions:
                s = self._sessions[session_id]
                s.last_active = time.time()
                return s

            # 2. Prefix match in memory
            for sid, s in self._sessions.items():
                if sid.startswith(session_id):
                    s.last_active = time.time()
                    return s

        # 3. Check disk for exact match
        self._ensure_dir()
        file_path = self._storage_dir / f"{session_id}.json"
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text())
                session = Session.from_dict(data)
                session.last_active = time.time()
                with self._lock:
                    self._sessions[session.session_id] = session
                return session
            except Exception:
                pass

        # 4. Check disk for prefix match
        try:
            for p in self._storage_dir.glob("*.json"):
                stem = p.stem
                if stem.startswith(session_id):
                    data = json.loads(p.read_text())
                    session = Session.from_dict(data)
                    session.last_active = time.time()
                    with self._lock:
                        self._sessions[session.session_id] = session
                    return session
        except Exception:
            pass

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

    def delete_session(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        target_id = session.session_id if session else session_id
        with self._lock:
            self._sessions.pop(target_id, None)

        file_path = self._storage_dir / f"{target_id}.json"
        deleted = False
        if file_path.exists():
            try:
                file_path.unlink()
                deleted = True
            except Exception:
                pass
        return deleted

    def clear_all_sessions(self) -> int:
        count = 0
        with self._lock:
            self._sessions.clear()
        self._ensure_dir()
        try:
            for p in self._storage_dir.glob("*.json"):
                try:
                    p.unlink()
                    count += 1
                except Exception:
                    pass
        except Exception:
            pass
        return count

    def list_sessions(self) -> list[dict]:
        """List all saved sessions from disk and memory, sorted by last_active descending."""
        self._ensure_dir()
        sessions_map: dict[str, dict] = {}

        # Scan disk
        try:
            for p in self._storage_dir.glob("*.json"):
                try:
                    data = json.loads(p.read_text())
                    sid = data.get("session_id", p.stem)
                    messages = data.get("messages", [])
                    title = data.get("title")
                    if not title:
                        for m in messages:
                            if m.get("role") == "user" and m.get("content"):
                                t = str(m["content"]).strip().replace("\n", " ")
                                title = t[:60] if len(t) <= 60 else t[:57] + "..."
                                break
                    sessions_map[sid] = {
                        "session_id": sid,
                        "created_at": data.get("created_at", p.stat().st_ctime),
                        "last_active": data.get("last_active", p.stat().st_mtime),
                        "message_count": len(messages),
                        "turns": len(messages) // 2,
                        "title": title or "New Session",
                    }
                except Exception:
                    continue
        except Exception:
            pass

        # Overlay any active in-memory sessions
        with self._lock:
            for sid, s in self._sessions.items():
                sessions_map[sid] = s.to_dict()

        result = list(sessions_map.values())
        result.sort(key=lambda s: s.get("last_active", 0), reverse=True)
        return result

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
