import functools
import logging
import time
import uuid
from contextlib import contextmanager

logger = logging.getLogger('jarvis.observability.tracer')

try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False


class Tracer:
    def __init__(self):
        self._spans: dict[str, dict] = {}
        self._stack: list[str] = []

    def start_span(self, name: str, attributes: dict = None) -> str:
        span_id = str(uuid.uuid4())[:8]
        parent_id = self._stack[-1] if self._stack else None
        self._spans[span_id] = {
            "name": name,
            "start": time.time(),
            "end": None,
            "attributes": attributes or {},
            "parent_id": parent_id,
        }
        self._stack.append(span_id)
        logger.debug(f"Span started: {name} [{span_id}]")
        return span_id

    def end_span(self, span_id: str = None):
        if not span_id and self._stack:
            span_id = self._stack.pop()
        if span_id and span_id in self._spans:
            self._spans[span_id]["end"] = time.time()
            duration = self._spans[span_id]["end"] - self._spans[span_id]["start"]
            logger.debug(f"Span ended: {self._spans[span_id]['name']} [{span_id}] ({duration:.3f}s)")

    def get_span(self, span_id: str) -> dict | None:
        return self._spans.get(span_id)

    def get_trace(self) -> list[dict]:
        return [s for s in self._spans.values() if s["end"] is not None]

    def clear(self):
        self._spans.clear()
        self._stack.clear()

    @contextmanager
    def span(self, name: str, attributes: dict = None):
        span_id = self.start_span(name, attributes)
        try:
            yield span_id
        finally:
            self.end_span(span_id)

    def trace(self, name: str = None, attributes: dict = None):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                span_name = name or func.__name__
                with self.span(span_name, attributes):
                    return func(*args, **kwargs)

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                span_name = name or func.__name__
                with self.span(span_name, attributes):
                    return await func(*args, **kwargs)

            import inspect
            if inspect.iscoroutinefunction(func):
                return async_wrapper
            return wrapper
        return decorator
