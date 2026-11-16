class ClipboardTool:
    def __init__(self):
        self._clipboard = None
        self._has_pyperclip = False
        try:
            import pyperclip
            self._has_pyperclip = True
        except Exception:
            pass

    def read(self):
        if self._has_pyperclip:
            import pyperclip
            try:
                return pyperclip.paste()
            except Exception:
                pass
        return self._clipboard or ""

    def write(self, text):
        if self._has_pyperclip:
            import pyperclip
            try:
                pyperclip.copy(text)
                return f"Copied: {text[:50]}..."
            except Exception:
                pass
        self._clipboard = text
        return f"Copied (fallback): {text[:50]}..."
