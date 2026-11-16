import time
import threading
import uuid


class SchedulerTool:
    def __init__(self):
        self._jobs = {}
        self._running = False
        self._thread = None

    def _match_field(self, pattern, value):
        if pattern == "*":
            return True
        for part in pattern.split(","):
            if "-" in part:
                lo, hi = part.split("-")
                if int(lo) <= value <= int(hi):
                    return True
            elif part == str(value):
                return True
        return False

    def _match_cron(self, expr, t):
        parts = expr.strip().split()
        if len(parts) != 5:
            return False
        fields = [t.tm_min, t.tm_hour, t.tm_mday, t.tm_mon, t.tm_wday]
        for i, part in enumerate(parts):
            if not self._match_field(part, fields[i]):
                return False
        return True

    def schedule(self, cron_expr, task):
        job_id = str(uuid.uuid4())[:8]
        self._jobs[job_id] = {"cron": cron_expr, "task": task, "active": True}
        if not self._running:
            self._start_loop()
        return f"Scheduled job {job_id}: {cron_expr}"

    def _start_loop(self):
        def loop():
            self._running = True
            last_run = {}
            while self._running:
                now = time.localtime()
                minute_key = f"{now.tm_min}:{now.tm_hour}:{now.tm_mday}:{now.tm_mon}:{now.tm_wday}"
                for jid, job in list(self._jobs.items()):
                    if not job["active"]:
                        continue
                    if last_run.get(jid) == minute_key:
                        continue
                    try:
                        if self._match_cron(job["cron"], now):
                            job["task"]()
                            last_run[jid] = minute_key
                    except Exception:
                        pass
                time.sleep(30)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def list_jobs(self):
        return [
            {"id": jid, "cron": job["cron"], "active": job["active"]}
            for jid, job in self._jobs.items()
        ]

    def cancel(self, job_id):
        if job_id in self._jobs:
            self._jobs[job_id]["active"] = False
            return f"Cancelled job {job_id}"
        return f"Job not found: {job_id}"
