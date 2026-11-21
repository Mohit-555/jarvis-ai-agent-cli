import unittest
from unittest.mock import patch, MagicMock
import subprocess

from tools.system.media import MediaTool


class TestMediaTool(unittest.TestCase):
    def setUp(self):
        self.tool = MediaTool()

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_playerctl_metadata_parsing(self, mock_run, mock_which):
        # Mock playerctl available
        mock_which.side_effect = lambda cmd: "/usr/bin/playerctl" if cmd == "playerctl" else None
        
        # Mock playerctl output
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "status:Playing||player:brave||artist:Arijit Singh||title:Kesariya Audio||album:Brahmastra||url:https://www.youtube.com/watch?v=123"
        mock_run.return_value = mock_res

        media = self.tool._query_playerctl()
        self.assertIsNotNone(media)
        self.assertEqual(media["title"], "Kesariya Audio")
        self.assertEqual(media["artist"], "Arijit Singh")
        self.assertEqual(media["player"], "brave")
        self.assertEqual(media["status"], "Playing")

        formatted = self.tool.get_current_media()
        self.assertIn("Kesariya Audio", formatted)
        self.assertIn("Arijit Singh", formatted)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_mpris_gdbus_parsing(self, mock_run, mock_which):
        # Mock playerctl NOT available, gdbus available
        mock_which.side_effect = lambda cmd: "/usr/bin/gdbus" if cmd == "gdbus" else None

        def run_side_effect(cmd, **kwargs):
            res = MagicMock()
            res.returncode = 0
            # 1. ListNames call
            if "ListNames" in cmd[-1]:
                res.stdout = "(['org.freedesktop.DBus', 'org.mpris.MediaPlayer2.chromium.instance1234'],)"
            # 2. PlaybackStatus call
            elif "PlaybackStatus" in cmd[-1]:
                res.stdout = "(<'Playing'>,)"
            # 3. Metadata call
            elif "Metadata" in cmd[-1]:
                res.stdout = "({'xesam:title': <'Coldplay - Viva La Vida'>, 'xesam:artist': <['Coldplay']>},)"
            return res

        mock_run.side_effect = run_side_effect

        media = self.tool._query_mpris_dbus()
        self.assertIsNotNone(media)
        self.assertEqual(media["title"], "Coldplay - Viva La Vida")
        self.assertEqual(media["artist"], "Coldplay")
        self.assertEqual(media["status"], "Playing")
        self.assertEqual(media["player"], "Chrome / YouTube")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_mpris_prioritizes_playing_over_paused(self, mock_run, mock_which):
        # Two players: Player 1 is Paused (Old track), Player 2 is Playing (Active song)
        mock_which.side_effect = lambda cmd: "/usr/bin/gdbus" if cmd == "gdbus" else None

        def run_side_effect(cmd, **kwargs):
            res = MagicMock()
            res.returncode = 0
            if "ListNames" in cmd[-1]:
                res.stdout = "(['org.mpris.MediaPlayer2.brave.instance1', 'org.mpris.MediaPlayer2.brave.instance2'],)"
            elif "PlaybackStatus" in cmd[-1]:
                if "instance1" in cmd:
                    res.stdout = "(<'Paused'>,)"
                else:
                    res.stdout = "(<'Playing'>,)"
            elif "Metadata" in cmd[-1]:
                if "instance1" in cmd:
                    res.stdout = "({'xesam:title': <'Old Paused Song'>, 'xesam:artist': <['Old Artist']>},)"
                else:
                    res.stdout = "({'xesam:title': <'Hum Unse Mohabbat Karke'>, 'xesam:artist': <['Kumar Sanu']>},)"
            return res

        mock_run.side_effect = run_side_effect

        media = self.tool._query_mpris_dbus()
        self.assertIsNotNone(media)
        self.assertEqual(media["title"], "Hum Unse Mohabbat Karke")
        self.assertEqual(media["artist"], "Kumar Sanu")
        self.assertEqual(media["status"], "Playing")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_window_title_youtube_fallback(self, mock_run, mock_which):
        # Mock playerctl and gdbus not returning, but wmctrl available
        mock_which.side_effect = lambda cmd: "/usr/bin/wmctrl" if cmd == "wmctrl" else None

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "0x01  0 1234  Hozier - Take Me To Church - YouTube - Brave\n0x02 0 5678 Terminal"
        mock_run.return_value = mock_res

        media = self.tool._query_window_titles()
        self.assertIsNotNone(media)
        self.assertEqual(media["title"], "Hozier - Take Me To Church")
        self.assertEqual(media["player"], "YouTube (Browser)")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_window_title_spotify_fallback(self, mock_run, mock_which):
        mock_which.side_effect = lambda cmd: "/usr/bin/wmctrl" if cmd == "wmctrl" else None

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "0x01  0 1234  The Weeknd - Blinding Lights - Spotify\n"
        mock_run.return_value = mock_res

        media = self.tool._query_window_titles()
        self.assertIsNotNone(media)
        self.assertEqual(media["title"], "The Weeknd - Blinding Lights")
        self.assertEqual(media["player"], "Spotify")

    @patch.object(MediaTool, "_query_playerctl", return_value=None)
    @patch.object(MediaTool, "_query_mpris_dbus", return_value=None)
    @patch.object(MediaTool, "_query_window_titles", return_value=None)
    def test_no_media_detected_guidance(self, m1, m2, m3):
        res = self.tool.get_current_media()
        self.assertIn("No active media playback detected", res)

    @patch("shutil.which", return_value="/usr/bin/playerctl")
    @patch("subprocess.run")
    def test_media_control(self, mock_run, mock_which):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res

        res = self.tool.media_control("play_pause")
        self.assertIn("play_pause", res)
        self.assertIn("successfully", res)

    @patch("shutil.which", return_value="/usr/bin/playerctl")
    @patch("subprocess.run")
    def test_media_control_pause_all_players(self, mock_run, mock_which):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res

        res = self.tool.media_control("pause")
        self.assertIn("pause", res)
        self.assertIn("all players", res)
        mock_run.assert_called_with(
            ["playerctl", "-a", "pause"],
            capture_output=True,
            text=True,
            timeout=3,
            env=self.tool._get_dbus_env()
        )


if __name__ == "__main__":
    unittest.main()
