import asyncio
import logging
import threading
import time

logger = logging.getLogger('jarvis.scheduler.cron')

try:
    from croniter import croniter
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False


class CronManager:
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def add_job(self, name: str, cron_expr: str, callback):
        if not HAS_CRONITER:
            logger.warning("croniter not installed, job will run on simple interval")
        with self._lock:
            self._jobs[name] = {
                "cron": cron_expr,
                "callback": callback,
                "last_run": 0,
                "next_run": self._get_next(cron_expr) if HAS_CRONITER else time.time(),
            }
        logger.info(f"Cron job added: {name} [{cron_expr}]")

    def remove_job(self, name: str):
        with self._lock:
            self._jobs.pop(name, None)
        logger.info(f"Cron job removed: {name}")

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [
                {"name": n, "cron": j["cron"], "last_run": j["last_run"], "next_run": j["next_run"]}
                for n, j in self._jobs.items()
            ]

    def _get_next(self, cron_expr: str, base: float = None) -> float:
        if not HAS_CRONITER:
            return (base or time.time()) + 60
        try:
            cron = croniter(cron_expr, time.gmtime(base or time.time()))
            return cron.get_next(float)
        except Exception:
            return (base or time.time()) + 60

    def _run_loop(self):
        while self._running:
            now = time.time()
            with self._lock:
                for name, job in list(self._jobs.items()):
                    if job["next_run"] <= now:
                        try:
                            job["callback"]()
                        except Exception as e:
                            logger.error(f"Cron job '{name}' error: {e}")
                        job["last_run"] = now
                        job["next_run"] = self._get_next(job["cron"], now)
            time.sleep(1)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="cron-manager")
        self._thread.start()
        logger.info("Cron manager started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Cron manager stopped")
