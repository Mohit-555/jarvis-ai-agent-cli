import numpy as np

try:
    import torch
    _HAS_TORCH = True
except Exception:
    _HAS_TORCH = False

_SILERO_MODEL = None


def _load_silero():
    global _SILERO_MODEL
    if _SILERO_MODEL is not None:
        return _SILERO_MODEL
    try:
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
        )
        _SILERO_MODEL = (model, utils)
        return _SILERO_MODEL
    except Exception:
        return None


class VoiceActivityDetector:
    def __init__(self, threshold=0.3, use_silero=True):
        self.threshold = threshold
        self._speaking = False
        self._use_silero = use_silero and _HAS_TORCH

        if self._use_silero:
            self._vad_model = _load_silero()
            if self._vad_model is None and _HAS_TORCH:
                self._use_silero = False

    def detect_speech(self, audio_chunk):
        if self._use_silero and self._vad_model is not None:
            return self._silero_detect(audio_chunk)
        return self._energy_detect(audio_chunk)

    def _silero_detect(self, audio_chunk):
        model, (get_speech_timestamps, _, _, _, _) = self._vad_model
        if isinstance(audio_chunk, np.ndarray):
            audio_chunk = torch.from_numpy(audio_chunk).float()
        if audio_chunk.dim() == 1:
            audio_chunk = audio_chunk.unsqueeze(0)
        speech_ts = get_speech_timestamps(audio_chunk, model, threshold=self.threshold)
        is_speech = len(speech_ts) > 0
        self._speaking = is_speech
        return is_speech

    def _energy_detect(self, audio_chunk):
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
        self._speaking = rms > self.threshold
        return self._speaking

    def is_speaking(self):
        return self._speaking
