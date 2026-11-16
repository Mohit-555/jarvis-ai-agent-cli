import sys
import time
import threading
from typing import Optional, Generator, Callable, Any
from rich.console import Console
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner as RichSpinner
from .theme import theme


class SpinnerAnimation:
    """Frame-based animated spinner with shimmer effect."""

    BRAILLE = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    DOTS = ("⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷")
    LINE = ("─", "━", "═")
    ARC = ("◜", "◝", "◞", "◟")
    BOUNCE = ("⢀", "⡀", "⠄", "⠂", "⠁", "⠂", "⠄", "⡀")
    PULSE = ("█", "▓", "▒", "░", "▒", "▓")

    FRAMES = {
        "braille": BRAILLE,
        "dots": DOTS,
        "arc": ARC,
        "bounce": BOUNCE,
        "pulse": PULSE,
    }

    def __init__(
        self,
        style: str = "braille",
        color: Optional[str] = None,
        interval: float = 0.08,
        message: str = "",
    ):
        self.frames = self.FRAMES.get(style, self.BRAILLE)
        self.color = color
        self.interval = interval
        self.message = message
        self._frame = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._console = Console()
        self._on_frame: Optional[Callable[[int], None]] = None

    def __iter__(self) -> Generator[str, None, None]:
        while self._running:
            yield self.current
            self._tick()

    @property
    def current(self) -> str:
        return self.frames[self._frame % len(self.frames)]

    def step(self) -> Text:
        frame = self.current
        c = self.color or theme().color.primary
        t = Text()
        t.append(frame, style=c)
        if self.message:
            t.append(f" {self.message}", style=theme().color.subtle)
        return t

    def _tick(self):
        self._frame += 1

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


def shimmer_text(text: str, position: int, width: int) -> Text:
    """Apply a shimmer/glide highlight effect to text."""
    result = Text()
    for i, ch in enumerate(text):
        if i == position % width:
            result.append(ch, style="bold white")
        elif abs(i - position % width) <= 2:
            result.append(ch, style="bold cyan")
        else:
            result.append(ch, style="dim")
    return result
