import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime

logger = logging.getLogger('jarvis.scheduler.reminders')

try:
    import sqlite3
    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False


class ReminderSystem:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "output", "reminders.db"
            )
        self._db_path = db_path
        self._reminders: dict[str, dict] = {}
        self._running = False
        self._thread = None
        self._next_id = 1
        self._load()

    def _load(self):
        if not HAS_SQLITE:
            return
        try:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path)
            conn.execute("CREATE TABLE IF NOT EXISTS reminders (id TEXT PRIMARY KEY, time REAL, message TEXT, created REAL)")
            for row in conn.execute("SELECT id, time, message, created FROM reminders"):
                self._reminders[row[0]] = {
                    "time": row[1], "message": row[2], "created": row[3],
                }
            conn.close()
        except Exception as e:
            logger.error(f"Failed to load reminders from DB: {e}")

    def _save(self, reminder: dict):
        if not HAS_SQLITE:
            return
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO reminders (id, time, message, created) VALUES (?, ?, ?, ?)",
                (reminder["id"], reminder["time"], reminder["message"], reminder["created"]),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save reminder: {e}")

    def _delete_from_db(self, reminder_id: str):
        if not HAS_SQLITE:
            return
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to delete reminder: {e}")

    def set_reminder(self, time_str: str, message: str) -> str:
        reminder_time = self._parse_time(time_str)
        reminder_id = f"rem_{self._next_id}_{int(time.time())}"
        self._next_id += 1
        reminder = {
            "id": reminder_id,
            "time": reminder_time,
            "message": message,
            "created": time.time(),
        }
        self._reminders[reminder_id] = reminder
        self._save(reminder)
        logger.info(f"Reminder set: '{message}' at {datetime.fromtimestamp(reminder_time).isoformat()}")
        return reminder_id

    def _parse_time(self, time_str: str) -> float:
        try:
            dt = datetime.fromisoformat(time_str)
            return dt.timestamp()
        except ValueError:
            pass
        try:
            timestamp = float(time_str)
            if timestamp > 1e9:
                return timestamp
        except ValueError:
            pass
        parsed = time.mktime(time.strptime(time_str, "%Y-%m-%d %H:%M:%S"))
        if parsed > time.time():
            return parsed
        from datetime import timedelta
        import re
        match = re.match(r"(\d+)\s*(s|sec|m|min|h|hr|d|day)(s?)$", time_str.strip().lower())
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            multipliers = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hr": 3600, "d": 86400, "day": 86400}
            return time.time() + value * multipliers.get(unit, 60)
        return time.time() + 3600

    def list_reminders(self) -> list[dict]:
        now = time.time()
        return [
            r for r in self._reminders.values()
            if r["time"] > now
        ]

    def cancel(self, reminder_id: str) -> bool:
        if reminder_id in self._reminders:
            del self._reminders[reminder_id]
            self._delete_from_db(reminder_id)
            logger.info(f"Reminder cancelled: {reminder_id}")
            return True
        return False

    def _run_loop(self):
        while self._running:
            now = time.time()
            triggered = []
            for rid, reminder in list(self._reminders.items()):
                if reminder["time"] <= now and reminder["time"] > 0:
                    triggered.append(reminder)
                    del self._reminders[rid]
                    self._delete_from_db(rid)
            for reminder in triggered:
                try:
                    logger.info(f"REMINDER: {reminder['message']}")
                    if self._callback:
                        self._callback(reminder)
                except Exception as e:
                    logger.error(f"Reminder callback error: {e}")
            time.sleep(5)

    def start(self, callback=None):
        self._callback = callback
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="reminder-loop")
        self._thread.start()
        logger.info("Reminder system started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Reminder system stopped")
