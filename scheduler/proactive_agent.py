import asyncio
import logging
import os
import threading
import time

logger = logging.getLogger('jarvis.scheduler.proactive')

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


class ProactiveAgent:
    def __init__(self):
        self._conditions: list[dict] = []
        self._running = False
        self._thread = None
        self._observer = None
        self._file_handlers: dict[str, object] = {}

    def start_monitoring(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="proactive-agent")
        self._thread.start()
        logger.info("Proactive agent monitoring started")

    def stop(self):
        self._running = False
        if HAS_WATCHDOG and self._observer:
            self._observer.stop()
            self._observer.join()
        if self._thread:
            self._thread.join(timeout=5)
        self._file_handlers.clear()
        logger.info("Proactive agent stopped")

    def on_condition(self, condition: dict, callback):
        self._conditions.append({"condition": condition, "callback": callback})
        ctype = condition.get("type", "")
        if ctype == "file_change" and HAS_WATCHDOG:
            self._watch_file(condition.get("path", ""), callback)
        logger.info(f"Proactive condition registered: {condition}")

    def _monitor_loop(self):
        while self._running:
            now = time.time()
            for entry in list(self._conditions):
                condition = entry["condition"]
                ctype = condition.get("type", "")
                if ctype == "time":
                    self._check_time_condition(condition, entry["callback"], now)
                elif ctype == "interval":
                    self._check_interval_condition(condition, entry["callback"], now)
            time.sleep(1)

    def _check_time_condition(self, condition: dict, callback, now: float):
        target = condition.get("target", 0)
        if isinstance(target, str):
            from datetime import datetime
            try:
                target = datetime.fromisoformat(target).timestamp()
            except ValueError:
                return
        if condition.get("_triggered"):
            return
        if abs(now - target) < 2:
            try:
                callback()
            except Exception as e:
                logger.error(f"Time condition callback error: {e}")
            condition["_triggered"] = True

    def _check_interval_condition(self, condition: dict, callback, now: float):
        seconds = condition.get("seconds", 300)
        last = condition.get("_last_run", 0)
        if now - last >= seconds:
            try:
                callback()
            except Exception as e:
                logger.error(f"Interval condition callback error: {e}")
            condition["_last_run"] = now

    def _watch_file(self, filepath: str, callback):
        if not os.path.exists(filepath):
            logger.warning(f"File not found for watching: {filepath}")
            return
        if not HAS_WATCHDOG:
            logger.warning("watchdog not installed, file watching disabled")
            return
        try:
            class ChangeHandler(FileSystemEventHandler):
                def __init__(self, cb):
                    self.cb = cb

                def on_modified(self, event):
                    if not event.is_directory:
                        try:
                            self.cb()
                        except Exception as e:
                            logger.error(f"File watch callback error: {e}")

            self._observer = Observer()
            watch_dir = os.path.dirname(filepath) or "."
            self._observer.schedule(ChangeHandler(callback), watch_dir, recursive=False)
            self._observer.start()
        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
