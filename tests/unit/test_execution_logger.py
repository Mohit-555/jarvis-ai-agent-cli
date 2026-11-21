import unittest
import time
from pathlib import Path

from core.logger import central_logger, sanitize_message, CentralExecutionLogger

class TestCentralExecutionLogger(unittest.TestCase):
    def test_singleton_and_channels(self):
        logger = CentralExecutionLogger.get()
        self.assertIsNotNone(logger)
        self.assertTrue(logger.log_dir.exists())
        self.assertIsNotNone(logger.jarvis_logger)
        self.assertIsNotNone(logger.llm_logger)
        self.assertIsNotNone(logger.agent_logger)
        self.assertIsNotNone(logger.tools_logger)
        self.assertIsNotNone(logger.errors_logger)

    def test_request_lifecycle(self):
        summary = central_logger.start_request("Test calculation task")
        self.assertTrue(summary.req_id.startswith("REQ-"))
        self.assertEqual(summary.status, "in_progress")

        central_logger.log_llm_start("gemini", "gemini-3.5-flash-lite", "Test prompt")
        central_logger.log_llm_end("gemini", "gemini-3.5-flash-lite", 0.42, success=True)
        central_logger.log_plan_generated(2, 0.25)
        central_logger.log_step_start("1", "python_interpreter", "Run math code")
        central_logger.log_tool_execution("python_interpreter", {"code": "25*48"}, 0.05, success=True)

        summary.complete("success")
        self.assertEqual(summary.status, "success")
        self.assertGreaterEqual(summary.duration, 0.0)

        recent = central_logger.get_recent_requests()
        self.assertGreaterEqual(len(recent), 1)
        first = recent[0]
        self.assertEqual(first["req_id"], summary.req_id)
        self.assertEqual(first["status"], "success")

    def test_sensitive_sanitization(self):
        raw = "API call with api_key='sk-1234567890abcdef' and password='supersecretpassword'"
        sanitized = sanitize_message(raw)
        self.assertNotIn("sk-1234567890abcdef", sanitized)
        self.assertNotIn("supersecretpassword", sanitized)
        self.assertIn("***REDACTED***", sanitized)

    def test_tail_log(self):
        central_logger.jarvis_logger.info("Verification tail test line")
        lines = central_logger.tail_log("jarvis", lines=5)
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 0)

if __name__ == "__main__":
    unittest.main()
