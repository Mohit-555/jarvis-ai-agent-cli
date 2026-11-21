import os
import re
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextvars import ContextVar
from datetime import datetime

from core.config import LOGS_DIR

# Context variable for tracking request ID across async tasks and threads
_current_request_id: ContextVar[str] = ContextVar("current_request_id", default="")
_req_counter: int = 0

# Maximum log file size: 5MB, keep 5 backups
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5

SENSITIVE_PATTERNS = [
    (re.compile(r'(api[-_]?key["\']?\s*[:=]\s*["\'])([^"\']+)["\']', re.IGNORECASE), r'\1***REDACTED***"'),
    (re.compile(r'(token["\']?\s*[:=]\s*["\'])([^"\']+)["\']', re.IGNORECASE), r'\1***REDACTED***"'),
    (re.compile(r'(password["\']?\s*[:=]\s*["\'])([^"\']+)["\']', re.IGNORECASE), r'\1***REDACTED***"'),
    (re.compile(r'(secret["\']?\s*[:=]\s*["\'])([^"\']+)["\']', re.IGNORECASE), r'\1***REDACTED***"'),
]

def sanitize_message(msg: str) -> str:
    """Redacts sensitive credentials like API keys, tokens, and passwords."""
    if not isinstance(msg, str):
        msg = str(msg)
    for pattern, repl in SENSITIVE_PATTERNS:
        msg = pattern.sub(repl, msg)
    return msg


class SanitizingFormatter(logging.Formatter):
    """Custom formatter that injects [REQ-xxx] and sanitizes sensitive tokens."""
    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "req_id", "") or _current_request_id.get() or "SYSTEM"
        record.req_id_str = f"[{req_id}]" if req_id else ""
        original_msg = record.getMessage()
        sanitized_msg = sanitize_message(original_msg)
        
        # Format with timestamp | LEVEL | [REQ-ID] | logger | message
        formatted = f"{self.formatTime(record, self.datefmt)} | {record.levelname:<7} | {record.req_id_str:<11} | {record.name} | {sanitized_msg}"
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                formatted += f"\n{record.exc_text}"
        return formatted


class RequestSummary:
    def __init__(self, req_id: str, prompt: str):
        self.req_id = req_id
        self.prompt = prompt[:80] + ("..." if len(prompt) > 80 else "")
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration: float = 0.0
        self.status = "in_progress"  # "success", "failed", "timeout", "in_progress"
        self.steps_count = 0
        self.tools_used: List[str] = []
        self.error: Optional[str] = None

    def complete(self, status: str = "success", error: Optional[str] = None):
        self.end_time = time.time()
        self.duration = round(self.end_time - self.start_time, 2)
        self.status = status
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "req_id": self.req_id,
            "prompt": self.prompt,
            "start_time": datetime.fromtimestamp(self.start_time).strftime("%H:%M:%S"),
            "duration": f"{self.duration:.2f}s" if self.duration else f"{round(time.time() - self.start_time, 1)}s",
            "status": self.status,
            "steps": self.steps_count,
            "tools": ", ".join(self.tools_used) or "none",
            "error": self.error or "",
        }


class CentralExecutionLogger:
    """
    Centralized execution logger managing dedicated channels:
      - jarvis.log: Core system events, daemon startup, mode toggles.
      - llm.log: LLM model queries, response durations, token usage.
      - agent.log: Planning requests, execution steps, iteration state.
      - tools.log: Tool invocations, parameters, durations, and outputs.
      - errors.log: Warnings, failures, timeouts, and exception tracebacks.
    """
    _instance = None

    def __init__(self):
        self.log_dir = Path(LOGS_DIR)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Mirror logs to project root logs/ directory if accessible
        self.project_log_dir = Path(__file__).resolve().parent.parent / "logs"
        try:
            self.project_log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.project_log_dir = None

        self._history: List[RequestSummary] = []
        self._max_history = 25
        self._setup_channels()

    @classmethod
    def get(cls) -> "CentralExecutionLogger":
        if cls._instance is None:
            cls._instance = CentralExecutionLogger()
        return cls._instance

    def _setup_channels(self):
        formatter = SanitizingFormatter(datefmt="%Y-%m-%d %H:%M:%S")

        def _make_handler(filename: str, level=logging.DEBUG) -> RotatingFileHandler:
            file_path = self.log_dir / filename
            handler = RotatingFileHandler(
                file_path,
                maxBytes=MAX_LOG_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8"
            )
            handler.setLevel(level)
            handler.setFormatter(formatter)
            return handler

        # Dedicated loggers
        self.jarvis_logger = logging.getLogger("jarvis")
        self.llm_logger = logging.getLogger("jarvis.llm")
        self.agent_logger = logging.getLogger("jarvis.agent")
        self.tools_logger = logging.getLogger("jarvis.tools")
        self.errors_logger = logging.getLogger("jarvis.errors")

        for l in (self.jarvis_logger, self.llm_logger, self.agent_logger, self.tools_logger, self.errors_logger):
            l.setLevel(logging.DEBUG)
            l.propagate = False
            l.handlers.clear()

        # Attach handlers
        h_jarvis = _make_handler("jarvis.log", logging.DEBUG)
        h_llm = _make_handler("llm.log", logging.DEBUG)
        h_agent = _make_handler("agent.log", logging.DEBUG)
        h_tools = _make_handler("tools.log", logging.DEBUG)
        h_errors = _make_handler("errors.log", logging.WARNING)

        self.jarvis_logger.addHandler(h_jarvis)
        self.llm_logger.addHandler(h_llm)
        self.agent_logger.addHandler(h_agent)
        self.tools_logger.addHandler(h_tools)
        self.errors_logger.addHandler(h_errors)

        # Also pipe errors from agent/tools/llm into errors.log
        self.jarvis_logger.addHandler(h_errors)
        self.llm_logger.addHandler(h_errors)
        self.agent_logger.addHandler(h_errors)
        self.tools_logger.addHandler(h_errors)

    def new_request_id(self) -> str:
        global _req_counter
        _req_counter += 1
        req_id = f"REQ-{_req_counter:03d}"
        _current_request_id.set(req_id)
        return req_id

    def set_request_id(self, req_id: str):
        _current_request_id.set(req_id)

    def get_request_id(self) -> str:
        return _current_request_id.get() or "SYSTEM"

    def start_request(self, prompt: str) -> RequestSummary:
        req_id = self.new_request_id()
        summary = RequestSummary(req_id, prompt)
        self._history.append(summary)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        self.agent_logger.info(f"User request received: {summary.prompt}")
        return summary

    def get_current_summary(self) -> Optional[RequestSummary]:
        cid = self.get_request_id()
        for s in reversed(self._history):
            if s.req_id == cid:
                return s
        return None

    def log_llm_start(self, provider: str, model: str, prompt_preview: str = ""):
        self.llm_logger.info(f"LLM request started: provider={provider}, model={model} prompt='{prompt_preview[:60]}'")

    def log_llm_end(self, provider: str, model: str, duration: float, success: bool, error: str = ""):
        if success:
            self.llm_logger.info(f"LLM response received in {duration:.2f}s ({provider}/{model})")
        else:
            self.llm_logger.error(f"LLM request failed after {duration:.2f}s ({provider}/{model}): {error}")

    def log_plan_generated(self, steps_count: int, duration: float):
        self.agent_logger.info(f"Plan generated: {steps_count} steps in {duration:.2f}s")
        curr = self.get_current_summary()
        if curr:
            curr.steps_count = steps_count

    def log_step_start(self, step_id: str, tool: str, desc: str):
        self.agent_logger.info(f"Step {step_id} started: tool={tool} desc='{desc}'")
        curr = self.get_current_summary()
        if curr and tool and tool not in curr.tools_used:
            curr.tools_used.append(tool)

    def log_tool_execution(self, tool: str, args: Any, duration: float, success: bool, error: str = ""):
        safe_args = sanitize_message(str(args))[:120]
        if success:
            self.tools_logger.info(f"Tool '{tool}' completed in {duration:.2f}s | args={safe_args}")
        else:
            self.tools_logger.error(f"Tool '{tool}' failed in {duration:.2f}s | error={error} | args={safe_args}")

    def log_error(self, message: str, exc_info: bool = False):
        self.errors_logger.error(message, exc_info=exc_info)

    def get_recent_requests(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in reversed(self._history)]

    def tail_log(self, channel: str = "jarvis", lines: int = 20) -> List[str]:
        channel = channel.lower()
        mapping = {
            "jarvis": "jarvis.log",
            "llm": "llm.log",
            "agent": "agent.log",
            "tools": "tools.log",
            "errors": "errors.log",
        }
        filename = mapping.get(channel, "jarvis.log")
        path = self.log_dir / filename
        if not path.exists():
            return [f"Log file '{filename}' does not exist yet."]
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.readlines()
                return [line.rstrip() for line in content[-lines:]]
        except Exception as e:
            return [f"Error reading log file: {e}"]


# Global singleton accessors
central_logger = CentralExecutionLogger.get()
