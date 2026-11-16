import threading
import queue
import os
import tempfile

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    _HAS_AUDIO = True
except Exception:
    _HAS_AUDIO = False


class VoiceTool:
    def __init__(self):
        self.sample_rate = 16000
        self.recording = False
        self.audio_queue = queue.Queue()

    def list_devices(self):
        if not _HAS_AUDIO:
            return "Audio not available"
        return sd.query_devices()

    def record_audio(self, duration=5, device=None):
        if not _HAS_AUDIO:
            return None
        recording = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            device=device,
            dtype="float32",
        )
        sd.wait()
        return recording.flatten()

    def record_until_silence(self, silence_duration=1.5, threshold=0.01, max_duration=30):
        if not _HAS_AUDIO:
            return None
        recording = []
        silent_chunks = 0
        chunk_size = int(self.sample_rate * 0.1)

        self.recording = True
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
        )

        with stream:
            for _ in range(int(max_duration / 0.1)):
                chunk, _ = stream.read(chunk_size)
                recording.append(chunk)
                rms = np.sqrt(np.mean(chunk**2))
                if rms < threshold:
                    silent_chunks += 1
                else:
                    silent_chunks = 0
                if silent_chunks >= int(silence_duration / 0.1):
                    break

        self.recording = False
        return np.concatenate(recording).flatten()

    def save_audio(self, audio, path=None):
        if not _HAS_AUDIO or audio is None:
            return None
        if path is None:
            path = os.path.join(tempfile.gettempdir(), "jarvis_input.wav")
        sf.write(path, audio, self.sample_rate)
        return path

    def transcribe(self, audio_path):
        if audio_path is None:
            return None
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_path)
            return result["text"].strip()
        except Exception:
            return None

    def speak(self, text):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            pass
