import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path


class EpisodicMemory:
    def __init__(self, db_path: str = None):
        self._db_path = db_path or str(Path.home() / ".jarvis" / "episodic.db")
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS facts ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "key TEXT UNIQUE, value TEXT, category TEXT, "
                    "created_at TEXT, updated_at TEXT"
                    ")"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS episodes ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "session_id TEXT, role TEXT, content TEXT, "
                    "metadata TEXT, timestamp TEXT"
                    ")"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session_id)"
                )
                conn.commit()
            finally:
                conn.close()

    def store_fact(self, key: str, value: str, category: str = "general"):
        now = datetime.now().isoformat()
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "INSERT INTO facts (key, value, category, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                    "category=excluded.category, updated_at=excluded.updated_at",
                    (key, value, category, now, now),
                )
                conn.commit()
            finally:
                conn.close()

    def get_fact(self, key: str) -> dict:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cur = conn.execute(
                    "SELECT key, value, category, created_at, updated_at FROM facts WHERE key = ?",
                    (key,),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "key": row[0],
                        "value": row[1],
                        "category": row[2],
                        "created_at": row[3],
                        "updated_at": row[4],
                    }
                return None
            finally:
                conn.close()

    def search_facts(self, query: str) -> list[dict]:
        pattern = f"%{query}%"
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cur = conn.execute(
                    "SELECT key, value, category, created_at, updated_at FROM facts "
                    "WHERE key LIKE ? OR value LIKE ? OR category LIKE ?",
                    (pattern, pattern, pattern),
                )
                return [
                    {
                        "key": row[0],
                        "value": row[1],
                        "category": row[2],
                        "created_at": row[3],
                        "updated_at": row[4],
                    }
                    for row in cur.fetchall()
                ]
            finally:
                conn.close()

    def get_all_facts(self, category: str = None) -> list[dict]:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                if category:
                    cur = conn.execute(
                        "SELECT key, value, category, created_at, updated_at FROM facts WHERE category = ?",
                        (category,),
                    )
                else:
                    cur = conn.execute(
                        "SELECT key, value, category, created_at, updated_at FROM facts"
                    )
                return [
                    {
                        "key": row[0],
                        "value": row[1],
                        "category": row[2],
                        "created_at": row[3],
                        "updated_at": row[4],
                    }
                    for row in cur.fetchall()
                ]
            finally:
                conn.close()

    def store_episode(self, session_id: str, role: str, content: str, metadata: dict = None):
        now = datetime.now().isoformat()
        meta_json = json.dumps(metadata or {})
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "INSERT INTO episodes (session_id, role, content, metadata, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (session_id, role, content, meta_json, now),
                )
                conn.commit()
            finally:
                conn.close()

    def get_session_episodes(self, session_id: str) -> list[dict]:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cur = conn.execute(
                    "SELECT role, content, metadata, timestamp FROM episodes "
                    "WHERE session_id = ? ORDER BY id",
                    (session_id,),
                )
                return [
                    {
                        "role": row[0],
                        "content": row[1],
                        "metadata": json.loads(row[2]) if row[2] else {},
                        "timestamp": row[3],
                    }
                    for row in cur.fetchall()
                ]
            finally:
                conn.close()

    def delete_fact(self, key: str):
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute("DELETE FROM facts WHERE key = ?", (key,))
                conn.commit()
            finally:
                conn.close()

    def clear(self):
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute("DELETE FROM facts")
                conn.execute("DELETE FROM episodes")
                conn.commit()
            finally:
                conn.close()
