import os
import re
import subprocess
import shutil
from typing import Optional
try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyautogui
    import pyperclip
    _HAS_GUI_TOOLS = True
except Exception:
    _HAS_GUI_TOOLS = False


from .media import MediaTool

class SystemTool:
    def run_command(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            output = result.stdout or result.stderr
            return output.strip() or f"Command completed (exit code: {result.returncode})"
        except subprocess.TimeoutExpired:
            return "Command timed out"
        except Exception as e:
            return f"Error: {e}"

    def get_system_info(self):
        if not psutil:
            return {"cpu_percent": 0.0, "memory": {}, "disk": {}, "processes": 0}
        info = {
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "memory": psutil.virtual_memory()._asdict(),
            "disk": psutil.disk_usage("/")._asdict(),
            "processes": len(psutil.pids()),
        }
        return info

    def open_app(self, app_name):
        # Maps user-friendly names to ordered lists of binary candidates to try
        APP_MAP = {
            # Browsers
            "browser":        ["brave-browser", "brave", "google-chrome", "chromium-browser", "chromium", "firefox", "xdg-open"],
            "brave":          ["brave-browser", "brave"],
            "brave browser":  ["brave-browser", "brave"],
            "chrome":         ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium", "brave-browser"],
            "google chrome":  ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium", "brave-browser"],
            "chromium":       ["chromium-browser", "chromium"],
            "firefox":        ["firefox"],
            "edge":           ["microsoft-edge", "microsoft-edge-stable"],
            # System apps
            "calculator":     ["gnome-calculator", "kcalc", "xcalc"],
            "calc":           ["gnome-calculator", "kcalc", "xcalc"],
            "clock":          ["gnome-clocks", "kclock"],
            "calendar":       ["gnome-calendar", "korganizer"],
            "terminal":       ["gnome-terminal", "konsole", "xterm", "xfce4-terminal"],
            "console":        ["gnome-terminal", "konsole", "xterm"],
            "settings":       ["gnome-control-center", "systemsettings5"],
            "files":          ["nautilus", "dolphin", "thunar", "nemo"],
            "file manager":   ["nautilus", "dolphin", "thunar", "nemo"],
            "nautilus":       ["nautilus"],
            # Text/code editors
            "text editor":    ["gedit", "kate", "mousepad", "xed"],
            "editor":         ["gedit", "kate", "mousepad", "xed"],
            "notepad":        ["gedit", "mousepad", "xed"],
            "code":           ["code", "code-insiders", "vscodium"],
            "vscode":         ["code", "code-insiders", "vscodium"],
            # Media
            "vlc":            ["vlc"],
            "music":          ["rhythmbox", "amarok", "audacious", "vlc"],
            "video":          ["vlc", "totem", "mpv"],
            "photos":         ["eog", "shotwell", "gwenview"],
            # Communication
            "telegram":       ["telegram-desktop", "telegram"],
            "discord":        ["discord"],
            "slack":          ["slack"],
            "zoom":           ["zoom"],
        }

        key = app_name.strip().lower()

        # Auto-detect URLs and open them in the browser
        if key.startswith("http://") or key.startswith("https://") or key.startswith("www."):
            return self.browse_url(app_name)

        candidates = APP_MAP.get(key, [app_name])

        # Try each candidate — use the first one found on PATH
        for binary in candidates:
            exe = binary.split()[0]
            if shutil.which(exe):
                try:
                    subprocess.Popen(binary, shell=True,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return f"Opened {app_name} (using '{binary}')"
                except Exception as e:
                    return f"Found '{binary}' but failed to launch: {e}"

        # Nothing worked — give a helpful message
        tried = ', '.join(candidates)
        return (
            f"Could not open '{app_name}'. "
            f"Tried: {tried}. "
            f"Make sure the app is installed (e.g. 'sudo apt install brave-browser')."
        )

    def _get_session_env(self) -> dict:
        """Ensure GUI, DBus, and session variables are populated for desktop IPC."""
        env = dict(os.environ)
        uid = os.getuid()

        if not env.get("XDG_RUNTIME_DIR"):
            env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"

        if not env.get("DBUS_SESSION_BUS_ADDRESS"):
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"

        if not env.get("DISPLAY"):
            env["DISPLAY"] = ":0"

        if not env.get("XDG_CURRENT_DESKTOP"):
            env["XDG_CURRENT_DESKTOP"] = "GNOME"

        return env

    def _focus_browser_window(self):
        """Bring the active browser window to the foreground."""
        env = self._get_session_env()
        if shutil.which("wmctrl"):
            try:
                for target in ("Brave-browser", "brave", "Google-chrome", "chrome"):
                    res = subprocess.run(["wmctrl", "-xa", target], capture_output=True, timeout=2, env=env)
                    if res.returncode == 0:
                        return
                subprocess.run(["wmctrl", "-a", "Brave"], capture_output=True, timeout=2, env=env)
            except Exception:
                pass

    def browse_url(self, url: str, target_domain: Optional[str] = None) -> str:
        """Open any URL in the existing browser window/tab if possible, or best available browser."""
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        # Strategy 1: CDP (Remote Debugging port 9222) to reuse existing window and tabs
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            cdp_open = (sock.connect_ex(('127.0.0.1', 9222)) == 0)
            sock.close()
            if cdp_open:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                    if browser.contexts:
                        ctx = browser.contexts[0]
                        matched_page = None
                        if target_domain:
                            for pg in ctx.pages:
                                if target_domain.lower() in pg.url.lower():
                                    matched_page = pg
                                    break
                        if matched_page:
                            matched_page.bring_to_front()
                            matched_page.goto(url)
                            self._focus_browser_window()
                            return f"Navigated existing {target_domain} tab to: {url}"
                        else:
                            new_page = ctx.new_page()
                            new_page.goto(url)
                            self._focus_browser_window()
                            return f"Opened tab in current browser window: {url}"
        except Exception:
            pass

        # Strategy 2: gio open uses DBus portal, reliably reusing the existing browser window
        env = self._get_session_env()
        if shutil.which("gio"):
            try:
                subprocess.Popen(["gio", "open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
                self._focus_browser_window()
                return f"Opened in current browser session: {url}"
            except Exception:
                pass

        # Strategy 3: Direct browser binary with full session environment
        BROWSERS = ["brave-browser", "brave", "google-chrome", "google-chrome-stable",
                    "chromium-browser", "chromium", "firefox", "xdg-open"]
        for browser in BROWSERS:
            if shutil.which(browser):
                try:
                    subprocess.Popen([browser, url],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL,
                                     env=env)
                    self._focus_browser_window()
                    return f"Opened in {browser}: {url}"
                except Exception as e:
                    return f"Found '{browser}' but failed to open URL: {e}"
        return "No browser found. Install brave: sudo apt install brave-browser"

    def search_in_browser(self, query: str) -> str:
        """Google-search for `query` and open result in browser."""
        import urllib.parse
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        return self.browse_url(url)

    def play_youtube(self, query: str) -> str:
        """Search and play a song/video directly on YouTube in the current browser window."""
        import urllib.parse
        clean_q = query.strip()
        for prefix in ("play ", "song ", "gana ", "chalao "):
            if clean_q.lower().startswith(prefix):
                clean_q = clean_q[len(prefix):].strip()
        for suffix in (" chalao", " play", " chala do", " laga do", " song", " gana"):
            if clean_q.lower().endswith(suffix):
                clean_q = clean_q[:-len(suffix)].strip()
        if not clean_q:
            clean_q = query.strip()

        encoded = urllib.parse.quote(clean_q)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        return self.browse_url(url, target_domain="youtube.com")

    def screenshot(self):
        img_path = "/tmp/jarvis_screenshot.png"
        import subprocess
        import os

        if os.path.exists(img_path):
            try:
                os.remove(img_path)
            except Exception:
                pass

        # Strategy 1: GNOME Shell DBus (extremely reliable on Ubuntu GNOME Wayland/X11)
        try:
            cmd = [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Shell.Screenshot",
                "--object-path", "/org/gnome/Shell/Screenshot",
                "--method", "org.gnome.Shell.Screenshot.Screenshot",
                "true", "false", img_path
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0 and os.path.exists(img_path):
                return img_path
        except Exception:
            pass

        # Strategy 2: scrot (classic X11)
        try:
            res = subprocess.run(["scrot", "-z", img_path], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and os.path.exists(img_path):
                return img_path
        except Exception:
            pass

        # Strategy 3: gnome-screenshot (GNOME utility fallback)
        try:
            res = subprocess.run(["gnome-screenshot", "-f", img_path], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and os.path.exists(img_path):
                return img_path
        except Exception:
            pass

        # Strategy 4: PyAutoGUI (original fallback)
        if not _HAS_GUI_TOOLS:
            return "Screenshot not available (no display)"
        try:
            img = pyautogui.screenshot()
            img.save(img_path)
            return img_path
        except Exception as e:
            return f"Screenshot failed. Error: {e}"

    def type_text(self, text):
        if not _HAS_GUI_TOOLS:
            return "Type not available (no display)"
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        return f"Pasted: {text[:50]}..."

    def get_clipboard(self):
        if not _HAS_GUI_TOOLS:
            return "Clipboard not available (no display)"
        return pyperclip.paste()

    def list_browser_tabs(self):
        import threading
        result = []
        def _run():
            try:
                from playwright.sync_api import sync_playwright
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if sock.connect_ex(('127.0.0.1', 9222)) != 0:
                    sock.close()
                    result.append("Brave is not running with remote debugging enabled.")
                    return
                sock.close()
                with sync_playwright() as p:
                    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                    context = browser.contexts[0]
                    lines = []
                    for i, pg in enumerate(context.pages, 1):
                        title = pg.title() or "(no title)"
                        url = pg.url
                        lines.append(f"  {i}. {title}")
                        if len(url) < 100:
                            lines.append(f"     {url}")
                    result.append("\n".join(lines) if lines else "No tabs found.")
            except ImportError:
                result.append("Playwright not available.")
            except Exception as e:
                result.append(f"Error listing tabs: {e}")
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=15)
        return result[0] if result else "Timed out listing tabs."

    def list_processes(self, filter_str=None):
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                name = proc.info["name"] or ""
                if filter_str and filter_str.lower() not in name.lower():
                    continue
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return sorted(processes, key=lambda p: p["cpu_percent"] or 0, reverse=True)[:20]

    def get_current_media(self, player=None):
        return MediaTool().get_current_media(player)

    def media_control(self, action="play_pause"):
        return MediaTool().media_control(action)
