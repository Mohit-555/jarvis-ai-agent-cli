import shutil
from typing import Optional, List, Callable
from rich.console import Console, RenderableType
from rich.text import Text
from rich.table import Table
from rich.style import Style
from rich.layout import Layout
from .theme import theme, color as theme_color


class StatusLine:
    """Bottom status bar showing model, mode, session info, and stats."""

    def __init__(self):
        self._segments: List[dict] = []
        self._left: List[Callable] = []
        self._right: List[Callable] = []
        self._console = Console()

    def add_left(self, label: str, value: Callable, color: Optional[str] = None):
        self._left.append({"label": label, "value": value, "color": color})

    def add_right(self, label: str, value: Callable, color: Optional[str] = None):
        self._right.append({"label": label, "value": value, "color": color})

    def set_model(self, model_name: str):
        self._model = model_name

    def set_mode(self, mode: str):
        self._mode = mode

    def render(self) -> Text:
        tw = shutil.get_terminal_size().columns
        t = theme()
        result = Text()
        result.append(theme().divider_char * tw, style=t.color.subtle)
        result.append("\n")
        left_parts = Text()
        for seg in self._left:
            label = seg["label"]
            value = seg["value"]() if callable(seg["value"]) else seg["value"]
            color = seg.get("color") or t.color.primary
            if left_parts:
                left_parts.append(" | ", style=t.color.subtle)
            left_parts.append(f"{label} ", style="dim")
            left_parts.append(str(value), style=color)
        right_parts = Text()
        for seg in self._right:
            label = seg["label"]
            value = seg["value"]() if callable(seg["value"]) else seg["value"]
            color = seg.get("color") or t.color.subtle
            if right_parts:
                right_parts.append(" | ", style=t.color.subtle)
            right_parts.append(f"{label} ", style="dim")
            right_parts.append(str(value), style=color)
        left_str = left_parts.plain if left_parts else ""
        right_str = right_parts.plain if right_parts else ""
        pad = max(0, tw - len(left_str) - len(right_str) - 4)
        if pad > 0:
            left_parts.append(" " * pad)
        result.append(left_parts)
        if right_str:
            result.append(right_parts)
        return result

    def show(self):
        self._console.print(self.render())

    def __rich__(self) -> RenderableType:
        return self.render()
