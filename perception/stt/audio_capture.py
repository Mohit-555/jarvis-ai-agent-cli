import numpy as np

try:
    import sounddevice as sd
    _HAS_SOUNDDEVICE = True
except Exception:
    _HAS_SOUNDDEVICE = False


class AudioCapture:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self._stream = None

    def record(self, duration=5, sample_rate=None):
        if not _HAS_SOUNDDEVICE:
            raise RuntimeError("sounddevice not installed")
        sr = sample_rate or self.sample_rate
        audio = sd.rec(
            int(duration * sr),
            samplerate=sr,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        return audio.flatten()

    def start_stream(self, callback, sample_rate=None, blocksize=1024):
        if not _HAS_SOUNDDEVICE:
            raise RuntimeError("sounddevice not installed")
        sr = sample_rate or self.sample_rate
        self._stream = sd.InputStream(
            samplerate=sr,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
            callback=lambda indata, frames, time, status: callback(indata.copy()),
        )
        self._stream.start()

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
