import os
import tempfile
import unittest
from pathlib import Path
import sys

jarvis_agent_dir = str(Path(__file__).resolve().parent.parent.parent)
if jarvis_agent_dir not in sys.path:
    sys.path.insert(0, jarvis_agent_dir)

from tools.messaging.whatsapp import WhatsAppTool
from tools.registry import ToolRegistry
from daemon import Daemon
from agent.executor import AgentExecutor


class TestWhatsAppFile(unittest.TestCase):
    def setUp(self):
        self.tool = WhatsAppTool()

    def test_nonexistent_file_rejection(self):
        res = self.tool.send_file(phone="9315878702", file_path="/tmp/non_existent_file_12345.pdf")
        self.assertIn("File does not exist", res)

    def test_directory_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            res = self.tool.send_file(phone="9315878702", file_path=td)
            self.assertIn("Path is not a regular file", res)

    def test_invalid_phone_rejection(self):
        with tempfile.NamedTemporaryFile() as tf:
            # An invalid number like "+" or empty
            res = self.tool.send_file(phone="+", file_path=tf.name)
            self.assertIn("Invalid phone number", res)

    def test_daemon_registration(self):
        d = Daemon()
        reg = ToolRegistry()
        d._register_all_tools(reg)
        tool = reg.get("whatsapp_send_file")
        self.assertIsNotNone(tool, "whatsapp_send_file should be registered in daemon")
        self.assertIn("phone", tool["parameters"]["required"])
        self.assertIn("file_path", tool["parameters"]["required"])

    def test_executor_direct_chat_routing(self):
        executor = AgentExecutor()
        # Direct chat should NOT bypass file sending or WhatsApp commands
        self.assertFalse(executor._is_direct_chat("send /tmp/doc.pdf to 9315878702 on whatsapp"))
        self.assertFalse(executor._is_direct_chat("whatsapp pe photo bhej do"))
        self.assertFalse(executor._is_direct_chat("send document to Mohit on whatsapp"))


if __name__ == "__main__":
    unittest.main()
