import logging

logger = logging.getLogger('jarvis.api.system')

try:
    from fastapi import APIRouter, HTTPException
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    APIRouter = object

if HAS_FASTAPI:
    router = APIRouter()

    @router.get("/system/status")
    async def system_status():
        import time
        import os
        import psutil
        try:
            return {
                "status": "ok",
                "uptime": time.time(),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage("/").percent,
                "pid": os.getpid(),
            }
        except Exception as e:
            logger.error(f"Status check error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/sessions")
    async def list_sessions():
        try:
            from core.session_manager import SessionManager
            mgr = SessionManager()
            sessions = mgr.list_active()
            return {"sessions": sessions, "count": len(sessions)}
        except ImportError:
            raise HTTPException(status_code=501, detail="Session manager not available")
        except Exception as e:
            logger.error(f"Sessions error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/system/shutdown")
    async def shutdown():
        import os
        import signal
        logger.warning("API shutdown requested")
        os.kill(os.getpid(), signal.SIGTERM)
        return {"status": "shutting_down"}
else:
    router = None
