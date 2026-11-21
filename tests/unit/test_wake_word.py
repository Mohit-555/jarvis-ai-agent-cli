import unittest
from unittest.mock import patch, MagicMock
import numpy as np

from voice.wake_word import WakeWordListener
from cli import JarvisCLI


class TestWakeWord(unittest.TestCase):
    def setUp(self):
        self.listener = WakeWordListener(
            config={"user_name": "Mohit", "enable_wake_word": True},
            energy_threshold=300.0
        )

    def test_wake_phrase_matching(self):
        # Valid wake phrases
        self.assertTrue(self.listener.is_wake_phrase("Hello Jarvis"))
        self.assertTrue(self.listener.is_wake_phrase("hey jarvis, what's up?"))
        self.assertTrue(self.listener.is_wake_phrase("OK Jarvis"))
        self.assertTrue(self.listener.is_wake_phrase("Sun jarvis ek gana chalao"))
        self.assertTrue(self.listener.is_wake_phrase("Jarvis"))

        # Non-wake phrases
        self.assertFalse(self.listener.is_wake_phrase("hello world"))
        self.assertFalse(self.listener.is_wake_phrase("what is the weather today"))
        self.assertFalse(self.listener.is_wake_phrase("testing microphone"))
        self.assertFalse(self.listener.is_wake_phrase(""))
        self.assertFalse(self.listener.is_wake_phrase(None))

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch.object(WakeWordListener, "speak_greeting")
    def test_trigger_wake_focuses_existing_window(self, mock_speak, mock_run, mock_which):
        # wmctrl available and finds open jarvis window
        mock_which.side_effect = lambda cmd: "/usr/bin/wmctrl" if cmd == "wmctrl" else None

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "0x03800003  0 1234  jarvis\n0x04000004 0 5678 Brave"
        mock_run.return_value = mock_res

        self.listener.trigger_wake()
        mock_speak.assert_called_once()
        # Verify wmctrl focused the window
        mock_run.assert_any_call(["wmctrl", "-ia", "0x03800003"], timeout=2, env=self.listener._get_desktop_env())

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("subprocess.Popen")
    @patch.object(WakeWordListener, "speak_greeting")
    def test_trigger_wake_spawns_terminal_if_not_running(self, mock_speak, mock_popen, mock_run, mock_which):
        # wmctrl available but no jarvis window exists; gnome-terminal available
        def which_mock(cmd):
            if cmd in ("wmctrl", "gnome-terminal"):
                return f"/usr/bin/{cmd}"
            return None
        mock_which.side_effect = which_mock

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "0x04000004 0 5678 Brave"
        mock_run.return_value = mock_res

        self.listener.trigger_wake()
        mock_speak.assert_called_once()
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        self.assertEqual(args[0][0], "gnome-terminal")
        self.assertIn("--title=jarvis", args[0])

    def test_audio_recorder_selection(self):
        with patch("shutil.which", side_effect=lambda c: "/usr/bin/pw-record" if c == "pw-record" else None):
            cmd = self.listener._find_audio_recorder()
            self.assertEqual(cmd[0], "pw-record")

        with patch("shutil.which", side_effect=lambda c: "/usr/bin/arecord" if c == "arecord" else None):
            cmd = self.listener._find_audio_recorder()
            self.assertEqual(cmd[0], "arecord")

    @patch("voice.wake_word.WakeWordListener.start")
    @patch("voice.wake_word.WakeWordListener.stop")
    def test_cli_slash_wake_toggle(self, mock_stop, mock_start):
        cli = JarvisCLI()
        # Test /wake status
        res = cli.handle_slash("/wake status")
        self.assertIsNone(res)

        # Test /wake on
        cli.handle_slash("/wake on")
        self.assertTrue(cli.config.get("enable_wake_word"))

        # Test /wake off
        cli.handle_slash("/wake off")
        self.assertFalse(cli.config.get("enable_wake_word"))


if __name__ == "__main__":
    unittest.main()
