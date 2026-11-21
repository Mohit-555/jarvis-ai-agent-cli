"""
ui/status_indicator.py  —  Modern execution state indicator inspired by OpenCode CLI

Renders subtle visual badges for:
  • READY
  • THINKING
  • WAITING FOR USER
  • EXECUTING
  • COMPLETED
  • ERROR
"""

from typing import Optional
from rich.text import Text

class StatusState:
    READY = "READY"
    THINKING = "THINKING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class StatusIndicator:
    """Renders sleek terminal state badges."""

    @staticmethod
    def render(state: str, detail: str = "", duration: Optional[float] = None) -> Text:
        t = Text()
        state = state.upper()

        if state == StatusState.READY:
            t.append("● ", style="bold #25C5DD")
            t.append("Ready", style="dim")

        elif state == StatusState.THINKING:
            t.append("◐ ", style="bold #38bdf8")
            t.append("Thinking…", style="#38bdf8")
            if detail:
                t.append(f" {detail}", style="dim")

        elif state == StatusState.WAITING_FOR_USER:
            t.append("▲ ", style="bold #f59e0b")
            t.append("Waiting for input…", style="bold #f59e0b")
            if detail:
                t.append(f" {detail}", style="dim")

        elif state == StatusState.EXECUTING:
            t.append("⚙ ", style="bold #a855f7")
            t.append("Executing: ", style="#a855f7")
            t.append(detail or "tool", style="bold cyan")

        elif state == StatusState.COMPLETED:
            t.append("✓ ", style="bold #10b981")
            t.append("Completed", style="dim")
            if duration is not None:
                t.append(f" ({duration:.2f}s)", style="dim")
            elif detail:
                t.append(f" ({detail})", style="dim")

        elif state == StatusState.ERROR:
            t.append("✗ ", style="bold #ef4444")
            t.append("Error: ", style="bold red")
            t.append(detail or "Operation failed", style="red")

        else:
            t.append("• ", style="dim")
            t.append(detail or state, style="dim")

        return t
