from typing import Optional, List, Callable, Generator
from rich.console import Console
from rich.text import Text
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich import box as rich_box
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import ANSI, HTML
from prompt_toolkit.styles import Style as PTKStyle
from .theme import theme, color as theme_color

_RICH_TO_PTK = {
    "bright_black": "gray",
    "bright_red": "#ff4444",
    "bright_green": "#44ff44",
    "bright_yellow": "#ffff44",
    "bright_blue": "#4488ff",
    "bright_magenta": "#ff44ff",
    "bright_cyan": "#44ffff",
    "bright_white": "#ffffff",
    "text": "default",
    "bg": "bg:default",
    "black": "black",
    "red": "red",
    "green": "green",
    "yellow": "yellow",
    "blue": "blue",
    "magenta": "magenta",
    "cyan": "cyan",
    "white": "white",
    "subtle": "gray",
    "primary": "cyan",
    "accent": "magenta",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "secondary": "blue",
    "link": "#4488ff",
    "border": "cyan",
}

def _ptk_color(name: str) -> str:
    return _RICH_TO_PTK.get(name, name)


class EnhancedInput:
    """Enhanced prompt input with suggestions, history search, and inline hints."""

    def __init__(
        self,
        prompt_char: str = "",
        suggestions: Optional[List[str]] = None,
        history: Optional[InMemoryHistory] = None,
        multiline: bool = False,
    ):
        t = theme()
        self.prompt_char = prompt_char or t.prompt_prefix
        self.suggestions = suggestions or []
        self.history = history or InMemoryHistory()
        self.multiline = multiline
        self._console = Console()
        self._bindings = KeyBindings()
        self._suggestion_index = 0
        self._setup_keybindings()
        self._session = PromptSession(
            history=self.history,
            key_bindings=self._bindings,
            style=self._get_ptk_style(),
            multiline=self.multiline,
        )

    def _setup_keybindings(self):
        @self._bindings.add("tab")
        def _(event):
            if self.suggestions:
                buf = event.app.current_buffer
                current = buf.text
                matching = [s for s in self.suggestions if s.startswith(current)]
                if matching:
                    self._suggestion_index = (self._suggestion_index + 1) % len(matching)
                    buf.text = matching[self._suggestion_index]
                    buf.cursor_position = len(buf.text)

    def _get_ptk_style(self) -> PTKStyle:
        t = theme()
        primary = _ptk_color(t.color.primary)
        subtle = _ptk_color(t.color.subtle)
        return PTKStyle([
            ("prompt", f"bold {primary}"),
            ("suggestion", f"fg:{subtle}"),
        ])

    def _formatted_prompt(self) -> HTML:
        t = theme()
        primary = _ptk_color(t.color.primary)
        return HTML(f"<style fg='{primary}'><b>{self.prompt_char} </b></style>")

    async def ask(
        self,
        prompt: str = "",
        default: str = "",
        placeholder: str = "",
    ) -> str:
        t = theme()
        if prompt:
            self._console.print(Text(prompt, style=t.color.subtle))

        try:
            return await self._session.prompt_async(self._formatted_prompt(), default=default)
        except (EOFError, KeyboardInterrupt):
            return ""

    async def search_history(self, query: str = "") -> Optional[str]:
        entries = list(self.history.get_strings())
        if not entries:
            return None
        if query:
            entries = [e for e in entries if query.lower() in e.lower()]
        if not entries:
            return None
        table = Table(box=rich_box.SIMPLE, show_header=False)
        for i, entry in enumerate(entries[-10:], 1):
            table.add_row(f"{i}", entry[:80])
        self._console.print(table)
        return await self.ask("Select entry number (or Enter to skip): ")

    def show_suggestions(self, prefix: str = ""):
        if not self.suggestions:
            return
        matching = [s for s in self.suggestions if s.startswith(prefix)]
        if matching:
            t = theme()
            text = Text()
            for i, s in enumerate(matching[:5]):
                if i > 0:
                    text.append("  ", style=t.color.subtle)
                text.append(s, style=t.color.primary)
            self._console.print(text)
