from typing import Optional, Iterable, Generator, TypeVar
from rich.console import Console, RenderableType
from rich.text import Text
from rich.progress import (
    Progress as RichProgress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TaskID,
    ProgressColumn,
)
from rich.table import Table
from rich.style import Style
from rich import box as rich_box
from .theme import theme, color as theme_color
from .components import Pane

T = TypeVar("T")


def ProgressBar(
    total: int = 100,
    description: str = "Processing",
    color: Optional[str] = None,
    transient: bool = True,
) -> RichProgress:
    t = theme()
    c = color or t.color.primary
    return RichProgress(
        SpinnerColumn(style=c),
        TextColumn(f"[bold {c}]{description}"),
        BarColumn(
            bar_width=40,
            style=t.color.subtle,
            complete_style=c,
        ),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        transient=transient,
    )


class Stats:
    """Display system statistics in a formatted table."""

    def __init__(self, title: str = "Stats", color: Optional[str] = None):
        self.title = title
        self.color = color
        self._rows: list = []

    def add(self, label: str, value, style: Optional[str] = None):
        self._rows.append((label, value, style))

    def render(self) -> Table:
        t = theme()
        c = self.color or t.color.primary
        table = Table(box=rich_box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Label", style="dim", width=30)
        table.add_column("Value")
        for label, value, style in self._rows:
            s = style or t.color.foreground
            table.add_row(label, Text(str(value), style=s))
        return table


def MemoryBar(
    used: int,
    total: int,
    label: str = "Memory",
    width: int = 20,
) -> RenderableType:
    pct = used / total if total > 0 else 0
    filled = int(width * pct)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    t = theme()
    color = t.color.success if pct < 0.7 else t.color.warning if pct < 0.9 else t.color.error
    return Text(f"{label}: [{bar}] {used}/{total} ({pct:.0%})", style=color)
