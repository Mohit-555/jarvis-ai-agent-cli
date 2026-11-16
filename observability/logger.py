import json
import logging
import os
import sys
import traceback
from datetime import datetime

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "logs")


class JSONFormatter(logging.Formatter):
    def __init__(self, correlation_id: str = ""):
        super().__init__()
        self._correlation_id = correlation_id

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "correlation_id": self._correlation_id,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
        return json.dumps(log_entry)


class JarvisLogger:
    def __init__(self, name: str = "jarvis", log_dir: str = None, correlation_id: str = ""):
        self._name = name
        self._log_dir = log_dir or LOGS_DIR
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        self._correlation_id = correlation_id
        self._setup_handlers()

    def _setup_handlers(self):
        if self._logger.handlers:
            return
        os.makedirs(self._log_dir, exist_ok=True)
        formatter = JSONFormatter(self._correlation_id)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.INFO)
        stdout_handler.setFormatter(formatter)
        self._logger.addHandler(stdout_handler)
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(self._log_dir, f"{self._name}.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)

    def _log(self, level: int, msg: str, **extra):
        if extra:
            self._logger.log(level, msg, extra={"extra_data": extra})
        else:
            self._logger.log(level, msg)

    def debug(self, msg: str, **extra):
        self._log(logging.DEBUG, msg, **extra)

    def info(self, msg: str, **extra):
        self._log(logging.INFO, msg, **extra)

    def warning(self, msg: str, **extra):
        self._log(logging.WARNING, msg, **extra)

    def error(self, msg: str, **extra):
        self._log(logging.ERROR, msg, **extra)

    def critical(self, msg: str, **extra):
        self._log(logging.CRITICAL, msg, **extra)

    def set_correlation_id(self, cid: str):
        self._correlation_id = cid
        for handler in self._logger.handlers:
            if hasattr(handler, "formatter") and isinstance(handler.formatter, JSONFormatter):
                handler.formatter._correlation_id = cid
