import unittest
from agent.planner import Planner

try:
    from core.config import load_config
except ImportError:
    load_config = lambda: {"llm_provider": "gemini"}


class TestMediaCapabilities(unittest.TestCase):
    def setUp(self):
        try:
            from core.config import load_config
            cfg = load_config()
        except Exception:
            cfg = {"llm_provider": "gemini"}
        self.planner = Planner(cfg)

    def test_planner_prompt_contains_media_tools_and_rules(self):
        prompt = self.planner.get_prompt("mai kaun sa gana sun rha hu")
        self.assertIn("get_current_media", prompt)
        self.assertIn("media_control", prompt)
        self.assertIn("mai kaun sa gana sun rha hu", prompt)
        self.assertIn("youtube per", prompt)
        self.assertIn("CRITICAL GUARD", prompt)

    def test_step_parsing_media_tool(self):
        raw_response = "1 | Check current song | get_current_media | {}\n"
        steps = self.planner._parse_steps(raw_response)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].tool, "get_current_media")
        self.assertEqual(steps[0].description, "Check current song")

    def test_step_parsing_media_control(self):
        raw_response = '1 | Pause music playback | media_control | {"action": "play_pause"}\n'
        steps = self.planner._parse_steps(raw_response)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].tool, "media_control")
        self.assertEqual(steps[0].args.get("action"), "play_pause")


if __name__ == "__main__":
    unittest.main()
