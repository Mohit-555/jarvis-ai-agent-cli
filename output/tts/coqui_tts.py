class CoquiTTS:
    def __init__(self):
        self.available = False

    def speak(self, text):
        return "Coqui TTS requires a GPU. Not available on current hardware."
