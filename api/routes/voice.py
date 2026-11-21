import asyncio
import logging
import tempfile
import os
from typing import Optional

logger = logging.getLogger('jarvis.api.voice')

try:
    from fastapi import APIRouter, HTTPException, UploadFile, File
    from pydantic import BaseModel
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    APIRouter = object
    BaseModel = object
    UploadFile = object
    File = object

_INTERRUPT_REQUESTED = False

if HAS_FASTAPI:
    router = APIRouter()

    class SpeakRequest(BaseModel):
        text: str
        voice: str = "default"
        rate: Optional[str] = None

    @router.post("/voice/transcribe")
    async def transcribe_audio(file: UploadFile = File(...)):
        try:
            contents = await file.read()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(contents)
                tmp_path = tmp.name

            try:
                from perception.stt.whisper_engine import WhisperEngine
                engine = WhisperEngine()
                text = engine.transcribe(tmp_path)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            return {"text": text, "filename": file.filename}
        except ImportError:
            raise HTTPException(status_code=501, detail="STT engine not available")
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/voice/speak")
    async def text_to_speech(req: SpeakRequest):
        global _INTERRUPT_REQUESTED
        _INTERRUPT_REQUESTED = False
        try:
            try:
                from output.tts.edge_tts import EdgeTTS
                engine = EdgeTTS(voice=req.voice if req.voice != "default" else "en-US-ChristopherNeural")
                audio_data = await engine._synthesize(req.text)
                from fastapi.responses import Response
                return Response(content=audio_data, media_type="audio/wav")
            except Exception:
                from output.tts.pyttsx3_tts import SystemTTS
                sys_tts = SystemTTS()
                sys_tts.speak(req.text)
                return {"status": "spoken_via_system"}
        except ImportError:
            raise HTTPException(status_code=501, detail="TTS engine not available")
        except Exception as e:
            logger.error(f"TTS error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/voice/interrupt")
    async def interrupt_speech():
        global _INTERRUPT_REQUESTED
        _INTERRUPT_REQUESTED = True
        return {"status": "interrupted", "success": True}
else:
    router = None
