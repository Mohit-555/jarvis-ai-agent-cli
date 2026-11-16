import logging

logger = logging.getLogger('jarvis.api.gateway')

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    FastAPI = object


class APIGateway:
    def __init__(self, config: dict = None, daemon=None):
        self._app = None
        self._running = False
        self.config = config or {}
        self.daemon = daemon

    def get_app(self):
        if not HAS_FASTAPI:
            raise RuntimeError("FastAPI is not installed")
        if self._app is None:
            self._app = FastAPI(title="Jarvis API", version="1.0.0")
            self._app.state.daemon = self.daemon
            origins = [
                "http://localhost:3000",
                "http://localhost:8000",
                "http://localhost:7777",
                "http://localhost:7778",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
                "http://127.0.0.1:7777",
                "http://127.0.0.1:7778",
            ]
            self._app.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            self._register_routes()
        return self._app

    def _register_routes(self):
        from fastapi import APIRouter
        router = APIRouter(prefix="/api/v1")

        @router.get("/health")
        async def health():
            return {"status": "ok", "service": "jarvis"}

        self._app.include_router(router)
        from api.routes import chat, voice, memory, tools, system
        self._app.include_router(chat.router, prefix="/api/v1")
        self._app.include_router(voice.router, prefix="/api/v1")
        self._app.include_router(memory.router, prefix="/api/v1")
        self._app.include_router(tools.router, prefix="/api/v1")
        self._app.include_router(system.router, prefix="/api/v1")
        
        from api.websocket import chat_ws, event_ws
        self._app.add_api_websocket_route("/ws/chat", chat_ws.handle)
        self._app.add_api_websocket_route("/ws/events", event_ws.handle)

    async def start(self, host=None, port=None):
        if not HAS_FASTAPI:
            logger.error("Cannot start API gateway: FastAPI not installed")
            return
        host = host or self.config.get('api_host', '127.0.0.1')
        port = port or self.config.get('api_port', 8000)
        import uvicorn
        cfg = uvicorn.Config(self.get_app(), host=host, port=port, log_level="info")
        server = uvicorn.Server(cfg)
        self._running = True
        await server.serve()

    async def stop(self):
        self._running = False
        logger.info("API gateway stopped")

