try:
    import edge_tts
    import asyncio
    _HAS_EDGE_TTS = True
except Exception:
    _HAS_EDGE_TTS = False


class EdgeTTS:
    def __init__(self, voice="en-US-ChristopherNeural"):
        self.voice = voice

    async def _synthesize(self, text):
        communicate = edge_tts.Communicate(text, self.voice)
        audio = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        return audio

    def speak(self, text):
        if not _HAS_EDGE_TTS:
            raise RuntimeError("edge-tts not installed")
        audio = self.synthesize(text)
        try:
            import sounddevice as sd
            import numpy as np
            import soundfile as sf
            import tempfile, os
            path = os.path.join(tempfile.gettempdir(), "jarvis_edge.wav")
            with open(path, "wb") as f:
                f.write(audio)
            data, sr = sf.read(path)
            sd.play(data, sr)
            sd.wait()
        except Exception as e:
            raise RuntimeError(f"Failed to play audio: {e}")

    def synthesize(self, text):
        if not _HAS_EDGE_TTS:
            raise RuntimeError("edge-tts not installed")
        return asyncio.run(self._synthesize(text))
