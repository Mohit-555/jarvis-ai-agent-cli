try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except Exception:
    _HAS_PYAUTOGUI = False

try:
    import mss
    import numpy as np
    _HAS_MSS = True
except Exception:
    _HAS_MSS = False


class ScreenshotTool:
    def __init__(self):
        self._use_mss = _HAS_MSS

    def capture(self, full_screen=True, region=None):
        if not _HAS_PYAUTOGUI and not _HAS_MSS:
            raise RuntimeError("No screenshot library available (install pyautogui or mss)")

        if self._use_mss and _HAS_MSS:
            return self._capture_mss(full_screen, region)
        return self._capture_pyautogui(full_screen, region)

    def _capture_mss(self, full_screen, region):
        with mss.mss() as sct:
            if region:
                monitor = {"left": region[0], "top": region[1], "width": region[2], "height": region[3]}
            else:
                monitor = sct.monitors[1] if full_screen else sct.monitors[1]
            img = sct.grab(monitor)
            return np.array(img)

    def _capture_pyautogui(self, full_screen, region):
        if region:
            img = pyautogui.screenshot(region=region)
        else:
            img = pyautogui.screenshot()
        return img
