"""
jarvis_input.py  —  Drop-in replacement for the input system in cli.py

Features:
  • OpenCode-style bordered input box with left-bar accent
  • Type `/` → command menu pops up instantly
  • Arrow keys ↑↓ to hover/highlight commands
  • Enter to select, Esc to dismiss
  • Tab to autocomplete
  • ↑↓ outside menu = history navigation

Usage in cli.py:
    from jarvis_input import JarvisInput
    self._input = JarvisInput(config=self.config)
    user_input = await self._input.ask()
"""

import asyncio
import shutil
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML, AnyFormattedText
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.filters import Condition
from prompt_toolkit.application import get_app
from rich.console import Console
from rich.text import Text

console = Console()

# ── Command registry ──────────────────────────────────────────────────────────

COMMANDS = [
    ("/exit",    "Exit Jarvis"),
    ("/reset",   "Reset conversation"),
    ("/voice",   "Voice input"),
    ("/tools",   "List available tools"),
    ("/skills",  "List available skills"),
    ("/run",     "Execute a skill"),
    ("/memory",  "Search memories"),
    ("/status",  "System status"),
    ("/model",   "Switch LLM model"),
    ("/mode",    "Switch execution mode (normal/power)"),
    ("/power",   "Toggle instant execution (no y/n)"),
    ("/verbose", "Toggle clean vs debug logs"),
    ("/theme",   "Switch theme"),
    ("/help",    "Show help"),
]

# ── Slash completer ───────────────────────────────────────────────────────────

class SlashCompleter(Completer):
    """Shows all /commands when user types `/`, filters as they keep typing."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Only activate on slash commands
        if not text.startswith("/"):
            return

        for cmd, desc in COMMANDS:
            if cmd.startswith(text):
                # How many chars to replace
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=HTML(
                        f"<cyan>{cmd:<12}</cyan>  "
                        f"<ansigray>{desc}</ansigray>"
                    ),
                )

# ── Prompt style ──────────────────────────────────────────────────────────────

def _make_style() -> Style:
    return Style.from_dict({
        # ── Input area ──
        "prompt":                           "bold ansicyan",

        # ── Completion dropdown ──
        "completion-menu":                  "bg:#161b22 ansigray",
        "completion-menu.completion":       "bg:#161b22 ansigray",
        # Highlighted (hovered) row
        "completion-menu.completion.current":
                                            "bg:#1f3a5f bold ansicyan",
        # Scrollbar
        "scrollbar.background":             "bg:#1c2128",
        "scrollbar.button":                 "bg:#388bfd",

        # Bottom toolbar (status bar inside prompt)
        "bottom-toolbar":                   "bg:#161b22 ansigray",
        "bottom-toolbar.text":              "bg:#161b22 ansigray",
    })

# ── Bottom toolbar (model info shown inside the prompt widget) ────────────────

def _make_toolbar(provider: str, model: str, turns: int):
    """Returns a callable that prompt_toolkit calls to render the toolbar."""
    def _toolbar():
        return HTML(
            f"<ansicyan>{provider}</ansicyan>"
            f"<ansigray> · </ansigray>"
            f"<ansicyan>{model}</ansicyan>"
            f"<ansigray> · </ansigray>"
            f"<ansigray>{turns} turns</ansigray>"
            f'<ansigray>    <b>ctrl+p</b> commands</ansigray>'
        )
    return _toolbar

# ── Prompt string (left-bar accent like OpenCode) ─────────────────────────────

def _prompt_str() -> AnyFormattedText:
    return HTML("<ansicyan><b>›  </b></ansicyan>")

# ── Key bindings ──────────────────────────────────────────────────────────────

def _make_bindings() -> KeyBindings:
    kb = KeyBindings()

    # Ctrl+P → open completion menu (like OpenCode's ctrl+p commands)
    @kb.add("c-p")
    def _open_commands(event):
        buf = event.app.current_buffer
        # Insert "/" if buffer is empty, then trigger completion
        if not buf.text:
            buf.insert_text("/")
        event.app.current_buffer.start_completion(select_first=True)

    # Ctrl+L → clear screen
    @kb.add("c-l")
    def _clear(event):
        event.app.renderer.clear()

    return kb

# ── Main input class ──────────────────────────────────────────────────────────

class JarvisInput:
    def __init__(
        self,
        config: dict = None,
        history: Optional[InMemoryHistory] = None,
    ):
        self.config   = config or {}
        self.history  = history or InMemoryHistory()
        self._turns   = 0

        self._session = PromptSession(
            history          = self.history,
            completer        = SlashCompleter(),
            complete_while_typing = True,   # menu appears the instant "/" is typed
            style            = _make_style(),
            key_bindings     = _make_bindings(),
            bottom_toolbar   = self._toolbar,
            complete_in_thread = True,
            mouse_support    = False,        # keep it keyboard-driven
            wrap_lines       = True,
        )

    # ── Toolbar (lazy — reads live config) ───────────────────────────────────

    def _toolbar(self):
        provider = self.config.get("llm_provider", "ollama")
        key      = f"{provider}_model"
        model    = self.config.get(key, "")
        return HTML(
            f" <ansicyan>{provider}</ansicyan>"
            f"<ansigray> · </ansigray>"
            f"<ansicyan>{model}</ansicyan>"
            f"<ansigray> · </ansigray>"
            f"<ansigray>{self._turns} turns</ansigray>"
            f"    <b>ctrl+p</b> commands"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def set_turns(self, n: int):
        self._turns = n

    async def ask(self) -> str:
        """
        Show the prompt and return the user's input string.
        Returns "" on Ctrl+C / Ctrl+D.
        """
        try:
            result = await self._session.prompt_async(_prompt_str())
            return result or ""
        except (EOFError, KeyboardInterrupt):
            return ""

    def ask_sync(self) -> str:
        """Synchronous wrapper — use only outside an async loop."""
        return asyncio.run(self.ask())


# ── Standalone demo ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from rich.panel import Panel
    from rich import box

    # Print a mini banner so the demo looks real
    console.print()
    console.print(
        Panel(
            Text("⬡  JARVIS  —  input demo", style="bold cyan"),
            border_style="cyan", box=box.ROUNDED, expand=False, padding=(0,2)
        )
    )
    console.print(
        Text(
            "  Type anything · Type / to see commands · Ctrl+P to open menu · Ctrl+L clear\n",
            style="bright_black"
        )
    )

    async def _demo():
        cfg = {"llm_provider": "ollama", "ollama_model": "llama3.2:3b"}
        inp = JarvisInput(config=cfg)
        while True:
            val = await inp.ask()
            if not val:
                break
            console.print(Text(f"  got: {val}", style="dim"))
            inp.set_turns(inp._turns + 1)

    asyncio.run(_demo())