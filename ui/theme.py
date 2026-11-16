import os
import shutil
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Color:
    foreground: str = "text"
    background: str = "bg"
    primary: str = "cyan"
    secondary: str = "blue"
    success: str = "green"
    warning: str = "yellow"
    error: str = "red"
    subtle: str = "bright_black"
    accent: str = "magenta"
    link: str = "bright_blue"
    border: str = "cyan"


@dataclass(frozen=True)
class Theme:
    name: str
    color: Color = field(default_factory=Color)
    spinner_frames: tuple = (
        "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"
    )
    shimmer_chars: str = "█▇▆▅▄▃▂▁"
    border_style: str = "cyan"
    panel_style: str = "cyan"
    input_style: str = "bold cyan"
    prompt_prefix: str = ">"
    clock_prefix: str = "─"
    divider_char: str = "─"


def detect_system_theme() -> str:
    try:
        if shutil.which("gsettings"):
            import subprocess
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True, timeout=2
            )
            if "dark" in result.stdout.lower():
                return "dark"
            return "light"
        if os.environ.get("COLORFGBG", "").endswith("0"):
            return "light"
        term = os.environ.get("TERM", "")
        if "kitty" in term or "foot" in term:
            return "dark"
        if os.environ.get("COLORTERM") == "truecolor":
            return "dark"
    except Exception:
        pass
    return "dark"


LIGHT_THEME = Theme(
    name="light",
    color=Color(
        foreground="black",
        background="white",
        primary="blue",
        secondary="cyan",
        success="green",
        warning="yellow",
        error="red",
        subtle="bright_black",
        accent="magenta",
        link="blue",
        border="blue",
    ),
    border_style="blue",
    panel_style="blue",
    input_style="bold blue",
)

DARK_THEME = Theme(
    name="dark",
    color=Color(
        foreground="text",
        background="bg",
        primary="cyan",
        secondary="blue",
        success="green",
        warning="yellow",
        error="red",
        subtle="bright_black",
        accent="magenta",
        link="bright_blue",
        border="cyan",
    ),
    border_style="cyan",
    panel_style="cyan",
    input_style="bold cyan",
)


class ThemeManager:
    _instance: Optional["ThemeManager"] = None

    def __init__(self):
        self._theme: Theme = DARK_THEME
        self._auto = True
        self._listeners: list = []

    @classmethod
    def get(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    @property
    def theme(self) -> Theme:
        return self._theme

    def set_theme(self, name: str):
        self._auto = False
        self._theme = LIGHT_THEME if name == "light" else DARK_THEME
        self._notify()

    def set_auto(self, enabled: bool):
        self._auto = enabled
        if enabled:
            self._theme = DARK_THEME if detect_system_theme() == "dark" else LIGHT_THEME
            self._notify()

    def refresh(self):
        if self._auto:
            self._theme = DARK_THEME if detect_system_theme() == "dark" else LIGHT_THEME
            self._notify()

    def on_change(self, callback):
        self._listeners.append(callback)

    def _notify(self):
        for cb in self._listeners:
            cb(self._theme)

    @property
    def c(self) -> Color:
        return self._theme.color


def theme() -> Theme:
    return ThemeManager.get().theme


def color() -> Color:
    return ThemeManager.get().c
