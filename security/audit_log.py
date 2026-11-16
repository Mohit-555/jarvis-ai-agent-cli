import json
import logging
import os
from datetime import datetime

logger = logging.getLogger('jarvis.security.audit')

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "audit")


class AuditLogger:
    def __init__(self, log_dir: str = None):
        self._log_dir = log_dir or LOGS_DIR
        os.makedirs(self._log_dir, exist_ok=True)

    def _get_log_file(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self._log_dir, f"audit-{today}.log")

    def log(self, action: str, tool: str = "", args: dict = None, user: str = "", success: bool = True):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "tool": tool,
            "args": args or {},
            "user": user or "system",
            "success": success,
        }
        try:
            log_file = self._get_log_file()
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def query(self, limit: int = 100, action: str = None, tool: str = None) -> list[dict]:
        results = []
        if not os.path.exists(self._log_dir):
            return results
        log_files = sorted(os.listdir(self._log_dir), reverse=True)
        for fname in log_files:
            fpath = os.path.join(self._log_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath) as f:
                    for line in f:
                        entry = json.loads(line.strip())
                        if action and entry.get("action") != action:
                            continue
                        if tool and entry.get("tool") != tool:
                            continue
                        results.append(entry)
                        if len(results) >= limit:
                            return results
            except Exception:
                continue
        return results[:limit]
