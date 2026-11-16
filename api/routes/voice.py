import logging

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

if HAS_FASTAPI:
    router = APIRouter()

    class SpeakRequest(BaseModel):
        text: str
        voice: str = "default"

    @router.post("/voice/transcribe")
    async def transcribe_audio(file: UploadFile = File(...)):
        try:
            contents = await file.read()
            from perception.stt.engine import STTEngine
            engine = STTEngine()
            text = engine.transcribe(contents)
            return {"text": text, "filename": file.filename}
        except ImportError:
            raise HTTPException(status_code=501, detail="STT engine not available")
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/voice/speak")
    async def text_to_speech(req: SpeakRequest):
        try:
            from perception.tts.engine import TTSEngine
            engine = TTSEngine()
            audio_data = engine.synthesize(req.text, voice=req.voice)
            from fastapi.responses import Response
            return Response(content=audio_data, media_type="audio/wav")
        except ImportError:
            raise HTTPException(status_code=501, detail="TTS engine not available")
        except Exception as e:
            logger.error(f"TTS error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
else:
    router = None
