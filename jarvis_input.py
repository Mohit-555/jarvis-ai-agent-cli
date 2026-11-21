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
import html
import shutil
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML, AnyFormattedText, FormattedText
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.filters import Condition, has_completions
from prompt_toolkit.application import get_app
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.layout.menus import CompletionsMenuControl, MultiColumnCompletionMenuControl
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
    ("/run",     "Execute a skill (/run <name>)"),
    ("/memory",  "Search memories"),
    ("/status",  "System status"),
    ("/model",   "Switch LLM model"),
    ("/mode",    "Switch execution mode (normal/power)"),
    ("/power",   "Toggle instant execution (no y/n)"),
    ("/verbose", "Toggle clean vs debug logs"),
    ("/profile", "User profile and preferences"),
    ("/sessions","Manage conversation sessions"),
    ("/theme",   "Switch theme (dark/light)"),
    ("/help",    "Show all commands"),
]

COMMANDS_WITH_ARGS = {"/run", "/model", "/name", "/language"}

# ── Make Completion Menu Clickable ────────────────────────────────────────────

def _apply_and_execute_completion(b, cmd_text: str):
    """Handle mouse click selection of a command."""
    b.complete_state = None
    if any(cmd_text == c or cmd_text.startswith(c + " ") for c in COMMANDS_WITH_ARGS):
        if not b.text.endswith(" "):
            b.insert_text(" ")
    else:
        # Self-contained command: execute immediately
        try:
            app = get_app()
            if app.is_running:
                b.validate_and_handle()
        except Exception:
            pass


_orig_single_mouse = CompletionsMenuControl.mouse_handler

def _custom_single_mouse(self, mouse_event: MouseEvent):
    b = get_app().current_buffer
    if mouse_event.event_type == MouseEventType.MOUSE_UP:
        if b.complete_state and b.complete_state.completions:
            idx = mouse_event.position.y
            completions = b.complete_state.completions
            if 0 <= idx < len(completions):
                comp = completions[idx]
                cmd_text = comp.text
                b.go_to_completion(idx)
                _apply_and_execute_completion(b, cmd_text)
                return None
    return _orig_single_mouse(self, mouse_event)

CompletionsMenuControl.mouse_handler = _custom_single_mouse


_orig_multi_mouse = MultiColumnCompletionMenuControl.mouse_handler

def _custom_multi_mouse(self, mouse_event: MouseEvent):
    b = get_app().current_buffer
    if mouse_event.event_type == MouseEventType.MOUSE_UP:
        x, y = mouse_event.position.x, mouse_event.position.y
        if hasattr(self, "_render_pos_to_completion"):
            completion = self._render_pos_to_completion.get((x, y))
            if completion:
                cmd_text = completion.text
                b.apply_completion(completion)
                _apply_and_execute_completion(b, cmd_text)
                return None
    return _orig_multi_mouse(self, mouse_event)

MultiColumnCompletionMenuControl.mouse_handler = _custom_multi_mouse

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
                safe_desc = html.escape(desc)
                # How many chars to replace
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=HTML(
                        f"<cyan>{cmd:<12}</cyan>  "
                        f"<ansigray>{safe_desc}</ansigray>"
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
    def _on_prompt_click(mouse_event: MouseEvent):
        if mouse_event.event_type == MouseEventType.MOUSE_UP:
            try:
                b = get_app().current_buffer
                if not b.text:
                    b.insert_text("/")
                b.start_completion(select_first=False)
            except Exception:
                pass

    return FormattedText([("class:prompt", "›  ", _on_prompt_click)])

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

        # Ensure terminal mouse tracking is explicitly reset on startup so touchpad scrolls cleanly
        try:
            import sys
            sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1015l")
            sys.stdout.flush()
        except Exception:
            pass

        self._session = PromptSession(
            history          = self.history,
            completer        = SlashCompleter(),
            complete_while_typing = True,   # menu appears the instant "/" is typed
            style            = _make_style(),
            key_bindings     = _make_bindings(),
            bottom_toolbar   = self._toolbar,
            complete_in_thread = True,
            mouse_support    = has_completions if self.config.get("mouse_support", True) else Condition(lambda: False),
            wrap_lines       = True,
        )

    # ── Toolbar (lazy — reads live config) ───────────────────────────────────

    def _toolbar(self):
        provider = self.config.get("llm_provider", "ollama")
        key      = f"{provider}_model"
        model    = self.config.get(key, "")

        def _on_commands_click(mouse_event: MouseEvent):
            if mouse_event.event_type == MouseEventType.MOUSE_UP:
                try:
                    b = get_app().current_buffer
                    if not b.text.startswith("/"):
                        b.text = "/"
                        b.cursor_position = 1
                    b.start_completion(select_first=False)
                except Exception:
                    pass

        return FormattedText([
            ("class:ansicyan", f" {provider}"),
            ("class:ansigray", " · "),
            ("class:ansicyan", f"{model}"),
            ("class:ansigray", " · "),
            ("class:ansigray", f"{self._turns} turns"),
            ("class:ansigray", "    "),
            ("class:ansicyan", "ctrl+p commands", _on_commands_click),
        ])

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
        finally:
            try:
                import sys
                sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1015l")
                sys.stdout.flush()
            except Exception:
                pass

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