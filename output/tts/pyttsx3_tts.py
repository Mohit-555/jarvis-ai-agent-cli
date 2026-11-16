try:
    import pyttsx3
    _HAS_PYTTSX3 = True
except Exception:
    _HAS_PYTTSX3 = False


class SystemTTS:
    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            if not _HAS_PYTTSX3:
                raise RuntimeError("pyttsx3 not installed")
            self._engine = pyttsx3.init()
        return self._engine

    def speak(self, text):
        engine = self._get_engine()
        engine.say(text)
        engine.runAndWait()
