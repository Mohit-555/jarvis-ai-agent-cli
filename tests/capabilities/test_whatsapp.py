import unittest
from tools.messaging.whatsapp import WhatsAppTool
from agent.planner import Planner


class TestWhatsAppCapabilities(unittest.TestCase):
    """
    Verification of Tasks 151–160: WhatsApp & Communication.
    """

    def setUp(self):
        self.wa = WhatsAppTool()
        self.planner = Planner()

    def test_task_151_160_planner_whatsapp_routing(self):
        """Tasks 151-160: Planner correctly routes WhatsApp message and document sending."""
        prompt = self.planner.get_prompt("send report.pdf to Mohit on whatsapp")
        self.assertIn("whatsapp_send", prompt)
        self.assertIn("whatsapp_send_file", prompt)
        self.assertIn("whatsapp_read_unread", prompt)
        self.assertIn("whatsapp_check_unread", prompt)

    def test_task_157_158_send_file_signature(self):
        """Tasks 157 & 158: Document and project file sharing method verification."""
        self.assertTrue(hasattr(self.wa, "send_file"))
        import inspect
        sig = inspect.signature(self.wa.send_file)
        params = list(sig.parameters.keys())
        self.assertIn("phone", params)
        self.assertIn("file_path", params)


if __name__ == "__main__":
    unittest.main()
