import subprocess
import platform


class WindowManagerTool:
    def __init__(self):
        self.system = platform.system()

    def list_windows(self):
        try:
            if self.system == "Linux":
                result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=5)
                windows = []
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split(None, 3)
                        windows.append({
                            "id": parts[0],
                            "desktop": parts[1],
                            "pid": parts[2],
                            "title": parts[3] if len(parts) > 3 else "",
                        })
                return windows
            elif self.system == "Windows":
                try:
                    import pywin32
                    return []
                except Exception:
                    return "Window management not available on Windows without pywin32"
            else:
                return f"Window management not supported on {self.system}"
        except FileNotFoundError:
            return "wmctrl not installed (install with: sudo apt install wmctrl)"
        except Exception as e:
            return f"Error: {e}"

    def focus(self, title):
        try:
            if self.system == "Linux":
                windows = self.list_windows()
                if isinstance(windows, str):
                    return windows
                for w in windows:
                    if title.lower() in w["title"].lower():
                        subprocess.run(["wmctrl", "-ia", w["id"]], timeout=5)
                        return f"Focused: {w['title']}"
                return f"Window not found: {title}"
            elif self.system == "Windows":
                return "Window focus not available on Windows"
            else:
                return f"Window management not supported on {self.system}"
        except Exception as e:
            return f"Error: {e}"

    def resize(self, title, w, h):
        try:
            if self.system == "Linux":
                windows = self.list_windows()
                if isinstance(windows, str):
                    return windows
                for win in windows:
                    if title.lower() in win["title"].lower():
                        subprocess.run(["wmctrl", "-ir", win["id"], "-e", f"0,0,0,{w},{h}"], timeout=5)
                        return f"Resized: {win['title']} to {w}x{h}"
                return f"Window not found: {title}"
            else:
                return f"Window management not supported on {self.system}"
        except Exception as e:
            return f"Error: {e}"

    def screenshot(self):
        try:
            path = "/tmp/jarvis_window_screenshot.png"
            if self.system == "Linux":
                subprocess.run(["import", "-window", "root", path], timeout=10)
                return path
            else:
                return "Screenshot not available on this platform"
        except FileNotFoundError:
            return "ImageMagick not installed (install with: sudo apt install imagemagick)"
        except Exception as e:
            return f"Error: {e}"
