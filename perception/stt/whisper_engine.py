import os
import tempfile

try:
    import numpy as np
    import soundfile as sf
    _HAS_SOUNDFILE = True
except Exception:
    _HAS_SOUNDFILE = False

_WHISPER_MODEL = {}


class WhisperEngine:
    def __init__(self, model_name=None):
        self.model_name = model_name or "tiny"
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            import whisper
            model = whisper.load_model(self.model_name)
            self._model = model
            return model
        except Exception as e:
            raise RuntimeError(f"Failed to load whisper model: {e}")

    def transcribe(self, audio_path):
        model = self._load_model()
        import whisper
        result = model.transcribe(audio_path)
        return result["text"].strip()

    def transcribe_array(self, audio_array):
        model = self._load_model()
        if not _HAS_SOUNDFILE:
            import numpy as np
            audio_array = np.array(audio_array, dtype=np.float32)
        path = os.path.join(tempfile.gettempdir(), "jarvis_transcribe.wav")
        sf.write(path, audio_array, 16000)
        return self.transcribe(path)
