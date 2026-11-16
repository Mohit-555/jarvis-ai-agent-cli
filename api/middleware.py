import asyncio
import logging
import time

logger = logging.getLogger('jarvis.api.middleware')

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response
    HAS_STARLETTE = True
except ImportError:
    HAS_STARLETTE = False
    BaseHTTPMiddleware = object
    Request = object
    Response = object


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self._requests: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        if not HAS_STARLETTE:
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window
        self._requests.setdefault(client_ip, [])
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > window_start]
        if len(self._requests[client_ip]) >= self.max_requests:
            return Response("Rate limit exceeded", status_code=429)
        self._requests[client_ip].append(now)
        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not HAS_STARLETTE:
            return await call_next(request)
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed:.3f}s)")
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_manager=None):
        super().__init__(app)
        self.auth_manager = auth_manager
        self._excluded_paths = {"/", "/health", "/api/v1/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        if not HAS_STARLETTE:
            return await call_next(request)
        path = request.url.path
        if any(path.startswith(ex) for ex in self._excluded_paths):
            return await call_next(request)
        if self.auth_manager:
            api_key = request.headers.get("X-API-Key", "")
            auth_header = request.headers.get("Authorization", "")
            token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
            if not self.auth_manager.verify_api_key(api_key) and not self.auth_manager.verify_token(token):
                return Response("Unauthorized", status_code=401)
        return await call_next(request)


def cors_middleware(app):
    try:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    except ImportError:
        logger.warning("CORS middleware not available")
    return app


def rate_limit_middleware(app, max_requests: int = 60, window: int = 60):
    if HAS_STARLETTE:
        app.add_middleware(RateLimitMiddleware, max_requests=max_requests, window=window)
    return app


def logging_middleware(app):
    if HAS_STARLETTE:
        app.add_middleware(LoggingMiddleware)
    return app


def auth_middleware(app, auth_manager=None):
    if HAS_STARLETTE:
        app.add_middleware(AuthMiddleware, auth_manager=auth_manager)
    return app
