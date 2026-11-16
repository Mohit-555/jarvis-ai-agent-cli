try:
    import pyperclip
    _HAS_PYPERCLIP = True
except Exception:
    _HAS_PYPERCLIP = False


class ClipboardOutput:
    def copy(self, text):
        if not _HAS_PYPERCLIP:
            return False
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    def paste(self):
        if not _HAS_PYPERCLIP:
            return ""
        try:
            return pyperclip.paste()
        except Exception:
            return ""
