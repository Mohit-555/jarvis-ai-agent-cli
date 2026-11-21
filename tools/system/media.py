"""
tools/system/media.py  —  Media Playback Inspection and Control Tool for Jarvis

Detects active media playback on Linux (YouTube on Chrome/Brave/Firefox, Spotify, VLC, etc.)
using standard MPRIS2 DBus interfaces, playerctl, and window title fallback inspection.
"""

import os
import re
import shutil
import subprocess
from typing import Dict, Any, Optional, List


class MediaTool:
    """Tool to inspect and control current media playback on Linux and cross-platform desktop."""

    def __init__(self):
        pass

    def _get_dbus_env(self) -> dict:
        """Ensure session DBus and display environment variables are populated."""
        env = dict(os.environ)
        uid = os.getuid()

        if not env.get("XDG_RUNTIME_DIR"):
            runtime_dir = f"/run/user/{uid}"
            if os.path.exists(runtime_dir):
                env["XDG_RUNTIME_DIR"] = runtime_dir

        if not env.get("DBUS_SESSION_BUS_ADDRESS"):
            bus_path = f"/run/user/{uid}/bus"
            if os.path.exists(bus_path):
                env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus_path}"

        if not env.get("DISPLAY"):
            env["DISPLAY"] = ":0"

        return env

    def _query_playerctl(self, target_player: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Attempt to query media metadata via playerctl CLI if installed."""
        if not shutil.which("playerctl"):
            return None

        cmd = [
            "playerctl",
            "metadata",
            "--format",
            "status:{{status}}||player:{{playerName}}||artist:{{artist}}||title:{{title}}||album:{{album}}||url:{{xesam:url}}"
        ]
        if target_player:
            cmd.extend(["--player", target_player])

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=4,
                env=self._get_dbus_env()
            )
            if res.returncode == 0 and res.stdout.strip():
                lines = res.stdout.strip().split("\n")
                first = lines[0]
                parts = {}
                for item in first.split("||"):
                    if ":" in item:
                        k, v = item.split(":", 1)
                        parts[k.strip()] = v.strip()

                title = parts.get("title", "")
                if title:
                    return {
                        "title": title,
                        "artist": parts.get("artist", ""),
                        "album": parts.get("album", ""),
                        "player": parts.get("player", "Media Player"),
                        "status": parts.get("status", "Playing"),
                        "url": parts.get("url", ""),
                    }
        except Exception:
            pass
        return None

    def _list_mpris_players(self, target_player: Optional[str] = None) -> List[str]:
        """List active DBus MediaPlayer2 names."""
        env = self._get_dbus_env()
        has_gdbus = bool(shutil.which("gdbus"))
        has_dbus_send = bool(shutil.which("dbus-send"))
        player_names = []
        try:
            if has_gdbus:
                cmd = ["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus",
                       "--object-path", "/org/freedesktop/DBus",
                       "--method", "org.freedesktop.DBus.ListNames"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=3, env=env)
                if res.returncode == 0:
                    found = re.findall(r"'([^']*)'", res.stdout)
                    player_names = [n for n in found if n.startswith("org.mpris.MediaPlayer2.")]
            elif has_dbus_send:
                cmd = ["dbus-send", "--session", "--dest=org.freedesktop.DBus", "--type=method_call",
                       "--print-reply", "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=3, env=env)
                if res.returncode == 0:
                    found = re.findall(r'"([^"]*)"', res.stdout)
                    player_names = [n for n in found if n.startswith("org.mpris.MediaPlayer2.")]
        except Exception:
            pass

        if target_player and player_names:
            t_lower = target_player.lower()
            filtered = [p for p in player_names if t_lower in p.lower()]
            if filtered:
                return filtered
        return player_names

    def _query_mpris_dbus(self, target_player: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Query MPRIS2 media players via gdbus or dbus-send."""
        env = self._get_dbus_env()
        has_gdbus = bool(shutil.which("gdbus"))
        has_dbus_send = bool(shutil.which("dbus-send"))

        if not has_gdbus and not has_dbus_send:
            return None

        player_names = self._list_mpris_players(target_player)
        if not player_names:
            return None

        # 2. Inspect players for status and metadata (prioritizing actively Playing tracks)
        playing_candidates = []
        other_candidates = []

        for p_dest in player_names:
            try:
                # Get PlaybackStatus
                status = "Playing"
                if has_gdbus:
                    cmd_status = ["gdbus", "call", "--session", "--dest", p_dest,
                                  "--object-path", "/org/mpris/MediaPlayer2",
                                  "--method", "org.freedesktop.DBus.Properties.Get",
                                  "org.mpris.MediaPlayer2.Player", "PlaybackStatus"]
                    r_st = subprocess.run(cmd_status, capture_output=True, text=True, timeout=3, env=env)
                    if r_st.returncode == 0:
                        m_st = re.search(r"<'([^']*)'>", r_st.stdout)
                        if m_st:
                            status = m_st.group(1)

                    # Get Metadata
                    cmd_meta = ["gdbus", "call", "--session", "--dest", p_dest,
                                "--object-path", "/org/mpris/MediaPlayer2",
                                "--method", "org.freedesktop.DBus.Properties.Get",
                                "org.mpris.MediaPlayer2.Player", "Metadata"]
                    r_meta = subprocess.run(cmd_meta, capture_output=True, text=True, timeout=3, env=env)
                    if r_meta.returncode == 0:
                        raw = r_meta.stdout
                        # Extract title
                        m_title = re.search(r"'xesam:title':\s*<([^>]+)>", raw)
                        title = ""
                        if m_title:
                            val = m_title.group(1).strip()
                            if val.startswith("'") and val.endswith("'"):
                                title = val[1:-1]
                            else:
                                title = val

                        # Extract artist
                        artist = ""
                        m_art = re.search(r"'xesam:artist':\s*<\[([^\]]+)\]>", raw)
                        if m_art:
                            art_val = m_art.group(1).strip()
                            arts = re.findall(r"'([^']*)'", art_val)
                            artist = ", ".join(arts) if arts else art_val.replace("'", "")

                        # Extract player friendly name
                        player_id = p_dest.replace("org.mpris.MediaPlayer2.", "")
                        clean_player = player_id.split(".")[0].capitalize()
                        if "chromium" in player_id.lower():
                            clean_player = "Chrome / YouTube"
                        elif "brave" in player_id.lower():
                            clean_player = "Brave / YouTube"

                        if title:
                            cand = {
                                "title": title,
                                "artist": artist,
                                "status": status,
                                "player": clean_player,
                                "raw_dest": p_dest,
                            }
                            if status.lower() == "playing":
                                playing_candidates.append(cand)
                            else:
                                other_candidates.append(cand)
            except Exception:
                continue

        if playing_candidates:
            return playing_candidates[0]
        if other_candidates:
            return other_candidates[0]

        return None

    def _query_window_titles(self, target_player: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fallback: Scan active window titles for YouTube, Spotify, or Media players."""
        windows = []
        env = self._get_dbus_env()

        # Try wmctrl if available
        if shutil.which("wmctrl"):
            try:
                res = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=3, env=env)
                if res.returncode == 0:
                    for line in res.stdout.strip().split("\n"):
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            windows.append(parts[3])
            except Exception:
                pass

        # Try xwininfo root tree if available
        if not windows and shutil.which("xwininfo"):
            try:
                res = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True, text=True, timeout=4, env=env)
                if res.returncode == 0:
                    found = re.findall(r'"([^"]*)"', res.stdout)
                    windows.extend(found)
            except Exception:
                pass

        if not windows:
            return None

        # Parse YouTube or Spotify titles
        for title in windows:
            t = title.strip()
            # Match YouTube window: "Song Title - YouTube - Google Chrome" or "Song Title - YouTube"
            if " - YouTube" in t:
                # Strip browser suffix
                cleaned = re.sub(r"\s*-\s*(Google Chrome|Brave|Chromium|Mozilla Firefox)$", "", t, flags=re.IGNORECASE)
                song_title = cleaned.replace(" - YouTube", "").strip()
                # Clean leading playback symbols or notification badges like '▶ (171) ' or '🔊 '
                song_title = re.sub(r"^[▶🔊⏸\s]+", "", song_title)
                song_title = re.sub(r"^\(\d+\)\s*", "", song_title).strip()
                if song_title and song_title.lower() != "youtube":
                    return {
                        "title": song_title,
                        "artist": "YouTube",
                        "status": "Playing",
                        "player": "YouTube (Browser)",
                        "source": "window_title",
                    }

            # Match Spotify window
            if " - Spotify" in t or t.startswith("Spotify Free - ") or t.startswith("Spotify Premium - "):
                cleaned = re.sub(r"^(Spotify Free|Spotify Premium|Spotify)\s*-\s*", "", t)
                cleaned = re.sub(r"\s*-\s*Spotify$", "", cleaned)
                if cleaned and cleaned.lower() != "spotify":
                    return {
                        "title": cleaned,
                        "artist": "Spotify",
                        "status": "Playing",
                        "player": "Spotify",
                        "source": "window_title",
                    }

        return None

    def get_current_media(self, player: Optional[str] = None) -> str:
        """
        Inspect the system to find the currently playing song, video, or audio track.
        Checks MPRIS2 players (Chrome, Brave, Spotify, YouTube, Firefox, VLC) and window titles.
        """
        # 1. Try playerctl
        info = self._query_playerctl(player)
        if not info:
            # 2. Try MPRIS DBus directly
            info = self._query_mpris_dbus(player)
        if not info:
            # 3. Try window title inspection
            info = self._query_window_titles(player)

        if not info:
            # Check if browser processes are running to give helpful guidance
            return "No active media playback detected. Make sure YouTube or Spotify is currently playing audio."

        title = info.get("title", "Unknown Title")
        artist = info.get("artist", "")
        status = info.get("status", "Playing")
        player_name = info.get("player", "Media Player")

        if artist and artist.lower() not in ("youtube", "unknown"):
            return f"🎵 Currently {status.lower()}: '{title}' by {artist} on {player_name}"
        else:
            return f"🎵 Currently {status.lower()}: '{title}' on {player_name}"

    def media_control(self, action: str = "play_pause") -> str:
        """
        Control active media playback:
        action: 'play_pause', 'play', 'pause', 'next', 'previous', 'stop'
        """
        act = action.lower().replace("-", "_").strip()
        env = self._get_dbus_env()

        # Try playerctl first (pause/stop with -a to affect all active players)
        if shutil.which("playerctl"):
            if act in ("pause", "stop"):
                try:
                    subprocess.run(["playerctl", "-a", act], capture_output=True, text=True, timeout=3, env=env)
                    return f"Media command '{act}' executed successfully on all players."
                except Exception:
                    pass
            else:
                cmd_map = {
                    "play_pause": ["playerctl", "play-pause"],
                    "play": ["playerctl", "play"],
                    "next": ["playerctl", "next"],
                    "previous": ["playerctl", "previous"],
                }
                if act in cmd_map:
                    try:
                        res = subprocess.run(cmd_map[act], capture_output=True, text=True, timeout=3, env=env)
                        if res.returncode == 0:
                            return f"Media command '{act}' executed successfully."
                    except Exception:
                        pass

        # Try MPRIS via gdbus
        if shutil.which("gdbus"):
            mpris_method = {
                "play_pause": "PlayPause",
                "play": "Play",
                "pause": "Pause",
                "next": "Next",
                "previous": "Previous",
                "stop": "Stop",
            }.get(act, "PlayPause")

            players = self._list_mpris_players()
            if players:
                # If pausing or stopping, send to all players to prevent double playback
                if act in ("pause", "stop"):
                    for dest in players:
                        try:
                            cmd = ["gdbus", "call", "--session", "--dest", dest,
                                   "--object-path", "/org/mpris/MediaPlayer2",
                                   "--method", "org.mpris.MediaPlayer2.Player.Pause"]
                            subprocess.run(cmd, capture_output=True, text=True, timeout=2, env=env)
                        except Exception:
                            pass
                    return f"Media playback '{act}' sent to all players."
                else:
                    dest = players[0]
                    try:
                        cmd = ["gdbus", "call", "--session", "--dest", dest,
                               "--object-path", "/org/mpris/MediaPlayer2",
                               "--method", f"org.mpris.MediaPlayer2.Player.{mpris_method}"]
                        subprocess.run(cmd, capture_output=True, text=True, timeout=3, env=env)
                        return f"Media playback '{act}' sent to {dest}."
                    except Exception as e:
                        return f"Failed to execute media control: {e}"

        return f"Could not execute media action '{action}'. No controllable player active."
