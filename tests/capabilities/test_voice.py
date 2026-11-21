import unittest
from perception.stt.whisper_engine import WhisperEngine
from output.tts.edge_tts import EdgeTTS
from perception.stt.engine import STTEngine
from perception.tts.engine import TTSEngine


class TestVoiceCapabilities(unittest.TestCase):
    """
    Verification of Tasks 141–150: Voice Assistant Capabilities.
    """

    def test_task_141_142_stt_engine_instantiation(self):
        """Tasks 141 & 142: STT engine availability and model configuration."""
        engine = WhisperEngine(model_name="tiny")
        self.assertEqual(engine.model_name, "tiny")
        self.assertIs(STTEngine, WhisperEngine)

    def test_task_143_149_tts_engine_instantiation(self):
        """Tasks 143 & 149: TTS engine availability and voice settings."""
        tts = EdgeTTS(voice="en-US-ChristopherNeural")
        self.assertEqual(tts.voice, "en-US-ChristopherNeural")
        self.assertIs(TTSEngine, EdgeTTS)

    def test_task_148_interruption_support(self):
        """Task 148: Interruption support flag verification."""
        import api.routes.voice as voice_route
        self.assertIsNotNone(voice_route)
        self.assertTrue(hasattr(voice_route, "_INTERRUPT_REQUESTED"))


if __name__ == "__main__":
    unittest.main()
