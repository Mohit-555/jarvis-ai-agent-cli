import unittest
from unittest.mock import patch, MagicMock
import urllib.parse

from tools.system import SystemTool
from agent.planner import Planner


class TestPlayYouTube(unittest.TestCase):
    def setUp(self):
        self.tool = SystemTool()
        self.planner = Planner({"llm_provider": "gemini"})

    @patch.object(SystemTool, "_get_youtube_watch_url")
    @patch.object(SystemTool, "browse_url")
    def test_play_youtube_query_cleaning_and_url_formatting(self, mock_browse, mock_watch):
        mock_watch.side_effect = lambda q: f"https://www.youtube.com/watch?v=TESTID&autoplay=1"
        mock_browse.return_value = "Navigated"

        # Case 1: Plain song name
        self.tool.play_youtube("Tum Hi Ho")
        mock_watch.assert_called_with("Tum Hi Ho")
        mock_browse.assert_called_with("https://www.youtube.com/watch?v=TESTID&autoplay=1", target_domain="youtube.com")

        # Case 2: Hindi command "Tum Hi Ho isko chalao"
        self.tool.play_youtube("Tum Hi Ho isko chalao")
        mock_watch.assert_called_with("Tum Hi Ho isko")

        # Case 3: "play Kesariya song"
        self.tool.play_youtube("play Kesariya song")
        mock_watch.assert_called_with("Kesariya")

        # Case 4: "gana chalao Raabta"
        self.tool.play_youtube("gana chalao Raabta")
        mock_watch.assert_called_with("Raabta")

    @patch("shutil.which")
    @patch("subprocess.Popen")
    @patch.object(SystemTool, "_focus_browser_window")
    def test_browse_url_uses_session_env_and_gio(self, mock_focus, mock_popen, mock_which):
        # When gio is available on Linux desktop
        mock_which.side_effect = lambda cmd: "/usr/bin/gio" if cmd == "gio" else None

        res = self.tool.browse_url("https://www.youtube.com/results?search_query=Tum+Hi+Ho")
        self.assertIn("current browser session", res)
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        self.assertEqual(args[0], ["gio", "open", "https://www.youtube.com/results?search_query=Tum+Hi+Ho"])
        self.assertIn("env", kwargs)
        self.assertIn("DBUS_SESSION_BUS_ADDRESS", kwargs["env"])

    def test_planner_prompt_has_play_youtube_and_guard(self):
        prompt = self.planner.get_prompt("Tum Hi Ho isko chalao")
        self.assertIn("play_youtube", prompt)
        self.assertIn("CRITICAL MUSIC GUARD", prompt)
        self.assertIn("Tum Hi Ho isko chalao", prompt)

    def test_planner_parses_play_youtube_step(self):
        raw_response = '1 | Play song on YouTube | play_youtube | {"query": "Tum Hi Ho"}\n'
        steps = self.planner._parse_steps(raw_response)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].tool, "play_youtube")
        self.assertEqual(steps[0].args.get("query"), "Tum Hi Ho")

    def test_planner_fastpath_music_intent(self):
        import asyncio
        context = '''JARVIS:
1 "Tum Hi Ho" - Aashiqui 2
2 "Raataan Lambiyan" - Shershaah
3 "Channa Mereya" - Ae Dil'''

        # Fast path 1: "Tum Hi Ho isko play karo"
        steps = asyncio.run(self.planner.plan("Tum Hi Ho isko play karo", context))
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].tool, "play_youtube")
        self.assertEqual(steps[0].args.get("query"), "Tum Hi Ho")

        # Fast path 2: "ynhi chala" (retry resolves previous song)
        steps_retry = asyncio.run(self.planner.plan("ynhi chala", context))
        self.assertEqual(len(steps_retry), 1)
        self.assertEqual(steps_retry[0].tool, "play_youtube")
        self.assertEqual(steps_retry[0].args.get("query"), "Tum Hi Ho")

        # Fast path 3: "1 song chalao"
        steps_num = asyncio.run(self.planner.plan("1 song chalao", context))
        self.assertEqual(len(steps_num), 1)
        self.assertEqual(steps_num[0].tool, "play_youtube")
        self.assertEqual(steps_num[0].args.get("query"), "Tum Hi Ho")


if __name__ == "__main__":
    unittest.main()
