import time
import threading
from typing import Callable, Optional


class AnimationFrame:
    """Frame-based animation controller using a background thread."""

    def __init__(self, interval_ms: int = 80):
        self.interval = interval_ms / 1000
        self._frame: int = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._listeners: list[Callable[[int], None]] = []
        self._start_time: float = 0.0

    @property
    def frame(self) -> int:
        return self._frame

    @property
    def elapsed(self) -> float:
        return time.time() - self._start_time if self._start_time else 0.0

    def on_frame(self, callback: Callable[[int], None]):
        self._listeners.append(callback)

    def start(self):
        if self._running:
            return
        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None

    def _run(self):
        while self._running:
            time.sleep(self.interval)
            self._frame += 1
            for cb in self._listeners:
                try:
                    cb(self._frame)
                except Exception:
                    pass

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
