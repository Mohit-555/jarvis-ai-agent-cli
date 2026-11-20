"""
banner.py  —  Jarvis startup banner
Drop this file in your project root and call print_banner() from main.py / cli.py.
"""
import shutil
import time
from rich.console import Console
from rich.text import Text

console = Console()

# ── ASCII art ─────────────────────────────────────────────────────────────────
# Each string is exactly the same length — do NOT reformat.

JARVIS_ART = [
    "     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗",
    "     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝",
    "     ██║███████║██████╔╝██║   ██║██║███████╗",
    "██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║",
    "╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║",
    " ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝",
]

ART_W = max(len(line) for line in JARVIS_ART)  # 44

# Gradient: top rows brighter, bottom rows slightly dimmer for depth
_ROW_STYLES = [
    "bold bright_cyan",
    "bold bright_cyan",
    "bold cyan",
    "bold cyan",
    "cyan",
    "cyan",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tw() -> int:
    return shutil.get_terminal_size((80, 24)).columns


def _center(text: str, width: int, style: str = "") -> Text:
    pad = max(0, (width - len(text)) // 2)
    t = Text(" " * pad + text, style=style)
    return t


def _rule(width: int, char: str = "─", style: str = "bright_black") -> Text:
    return Text(char * width, style=style)


def _sep(style: str = "bright_black") -> Text:
    return Text(" · ", style=style)


# ── Banner ────────────────────────────────────────────────────────────────────

def print_banner(
    version: str = "2.1",
    provider: str = "ollama",
    model: str = "",
    device: str = "cpu",
    animate: bool = True,
):
    """
    Print the full Jarvis startup banner.

    Args:
        version:  Version string shown under the logo.
        provider: LLM provider name (ollama / openai / gemini / …).
        model:    Model name.
        device:   cpu / cuda / mps.
        animate:  If True, fade-in the art row by row (looks great in real terminal).
    """
    tw = _tw()

    # Centre offset: how far to push the art block left/right
    offset = max(0, (tw - ART_W) // 2)
    pad = " " * offset

    console.print()  # breathing room at top

    # ── ASCII art (animated or instant) ──────────────────────────────────────
    for i, (line, style) in enumerate(zip(JARVIS_ART, _ROW_STYLES)):
        console.print(Text(pad + line, style=style))
        if animate:
            time.sleep(0.04)   # 40 ms per row → ~240 ms total, snappy

    console.print()

    # ── Subtitle & Credit ────────────────────────────────────────────────────
    console.print(_center("Personal AI Assistant System", tw, style="dim"))
    dev = Text()
    dev.append("Developed by ", style="dim")
    dev.append("Mohit Patel", style="bold cyan")
    dev_pad = max(0, (tw - len(dev.plain)) // 2)
    console.print(Text(" " * dev_pad) + dev)
    console.print()

    # ── Meta row: version · provider · model · device ────────────────────────
    meta = Text(justify="center")
    meta.append(f"v{version}", style="bright_cyan")
    meta.append_text(_sep())
    meta.append(provider, style="cyan")
    if model:
        meta.append_text(_sep())
        meta.append(model, style="cyan")
    meta.append_text(_sep())
    meta.append(device.upper(), style="dim")

    meta_pad = max(0, (tw - len(meta.plain)) // 2)
    console.print(Text(" " * meta_pad) + meta)

    console.print()

    # ── Keyboard hints ────────────────────────────────────────────────────────
    hints = Text(justify="center")
    def _hint(key: str, desc: str):
        hints.append(f"[{key}]", style="bold cyan")
        hints.append(f" {desc}", style="dim")

    _hint("Ctrl+T", "theme")
    hints.append("   ")
    _hint("Ctrl+L", "clear")
    hints.append("   ")
    _hint("/help", "commands")
    hints.append("   ")
    _hint("↑↓", "history")

    hint_pad = max(0, (tw - len(hints.plain)) // 2)
    console.print(Text(" " * hint_pad) + hints)

    # ── Ready rule ────────────────────────────────────────────────────────────
    console.print()
    side = max(0, (tw - 9)) // 2
    ready_line = Text()
    ready_line.append("─" * side, style="bright_black")
    ready_line.append("  ready  ", style="dim")
    ready_line.append("─" * side, style="bright_black")
    console.print(ready_line)
    console.print()


# ── Compact one-liner for re-prints (e.g. after /reset) ──────────────────────

def print_mini_banner(provider: str = "", model: str = ""):
    """Small one-line header — used after /reset or screen clear."""
    t = Text()
    t.append("⬡  JARVIS", style="bold cyan")
    if provider:
        t.append("  ·  ", style="bright_black")
        t.append(provider, style="cyan")
    if model:
        t.append("/", style="bright_black")
        t.append(model, style="cyan")
    console.print(t)
    console.print()


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print_banner(
        version="2.1.1",
        provider="ollama",
        model="llama3.2:3b",
        device="cpu",
        animate=True,
    )