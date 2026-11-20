import sys
import asyncio
import html
import shutil
import time
from typing import AsyncGenerator, Optional

from rich.console import Console, Group as RGroup
from rich.markdown import Markdown
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich import box
from rich.columns import Columns
from rich.syntax import Syntax
from rich.prompt import Prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PTKStyle

from core.config import load_config, save_config, CONFIG_DIR
from core.session import session_manager
from banner import print_mini_banner
from ui import (
    ThemeManager, Theme, Color, theme, color,
    Pane, Divider, Byline, KeyboardHint, Spacer,
    SpinnerAnimation, shimmer_text,
    Dialog,
    StatusLine,
    EnhancedInput,
    Keybindings, Binding, get_keybindings,
    ProgressBar, Stats, MemoryBar,
)
from jarvis_input import JarvisInput

console = Console()
cfg = load_config()
NAME = cfg.get('assistant_name', 'Jarvis')

# ── Palette ──────────────────────────────────────────────────────────────────
P = {
    "primary":   "bold cyan",
    "dim":       "dim",
    "user":      "bold bright_red",
    "ai":        "bold cyan",
    "tool":      "cyan",
    "tool_arg":  "bright_blue",
    "tool_res":  "bright_black",
    "success":   "bold green",
    "warn":      "bold yellow",
    "error":     "bold red",
    "sep":       "bright_black",
    "hint_key":  "bold cyan",
    "code":      "bright_cyan",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _tw() -> int:
    return shutil.get_terminal_size().columns


def _rule(label: str = "", char: str = "─") -> Text:
    tw = _tw()
    t = Text()
    if label:
        side = (tw - len(label) - 4) // 2
        t.append(char * side, style=P["sep"])
        t.append(f"  {label}  ", style=P["dim"])
        t.append(char * side, style=P["sep"])
    else:
        t.append(char * tw, style=P["sep"])
    return t


def _render_tool_call(name: str, arg: str = "", result: str = "") -> Text:
    """Single-line tool call block with left-bar accent."""
    t = Text()
    t.append("  ⚙ ", style=P["tool"])
    t.append(name, style=P["tool"])
    if arg:
        t.append(f"  {arg}", style=P["tool_arg"])
    if result:
        t.append(f"\n    {result}", style=P["tool_res"])
    return t


def _user_line(text: str) -> Text:
    t = Text()
    t.append("you  ", style=P["user"])
    t.append(text)
    return t


def _ai_prefix() -> Text:
    t = Text()
    t.append("J›   ", style=P["ai"])
    return t


def _hint(*pairs) -> Text:
    """pairs = (key, desc), (key, desc) ..."""
    t = Text()
    for i, (k, d) in enumerate(pairs):
        if i:
            t.append("  ", style=P["sep"])
        t.append(f"[{k}]", style=P["hint_key"])
        t.append(f" {d}", style=P["dim"])
    return t


def _status_bar(left: list, right: list) -> Text:
    """left/right = [(label, value, style)]"""
    tw = _tw()
    t = Text()
    t.append(_rule().plain, style=P["sep"])
    t.append("\n")

    def _seg(items):
        seg = Text()
        for i, (label, val, style) in enumerate(items):
            if i:
                seg.append("  │  ", style=P["sep"])
            seg.append(f"{label} ", style=P["dim"])
            seg.append(str(val), style=style or P["primary"])
        return seg

    left_seg = _seg(left)
    right_seg = _seg(right)
    pad = max(0, tw - len(left_seg.plain) - len(right_seg.plain) - 2)
    t.append_text(left_seg)
    t.append(" " * pad)
    t.append_text(right_seg)
    return t


# ── Main CLI ──────────────────────────────────────────────────────────────────

class JarvisCLI:
    def __init__(self, daemon=None):
        self.daemon = daemon
        self.config = load_config()
        self._theme_mgr = ThemeManager.get()
        self._session = session_manager.create_session()
        self._input = JarvisInput(config=self.config)
        self._history = InMemoryHistory()
        self._ptk_session = PromptSession(
            style=PTKStyle([("prompt", "bold ansicyan")]),
        )

        self._setup_keybindings()

    # ── Setup ────────────────────────────────────────────────────────────────

    def _setup_keybindings(self):
        kb = get_keybindings()
        kb.bind("Ctrl+T", lambda: self._cycle_theme(), "Cycle theme", "global")
        kb.bind("Ctrl+L", lambda: console.clear(), "Clear screen", "global")

    def _cycle_theme(self):
        current = self._theme_mgr.theme.name
        new = "light" if current == "dark" else "dark"
        self._theme_mgr.set_theme(new)
        self._print_inline(f"Theme → {new}", style=P["success"])

    def _active_model(self) -> str:
        provider = self.config.get("llm_provider", "ollama")
        return self.config.get(f"{provider}_model", "")

    # ── Print helpers ────────────────────────────────────────────────────────

    def _print_inline(self, text, style=""):
        console.print(Text(text, style=style))

    def _print_rule(self, label=""):
        console.print(_rule(label))

    # ── Banner ───────────────────────────────────────────────────────────────

    def print_banner(self):
        from banner import print_banner as _banner
        _banner(
            version="2.1.1",
            provider=self.config.get("llm_provider", "ollama"),
            model=self._active_model(),
            device=self.config.get("device", "cpu"),
    )
    # ── Status bar ───────────────────────────────────────────────────────────

    def _render_status(self):
        turns = len(self._session.messages) // 2
        profile = self.config.get("hardware_profile", "default")
        exec_mode = self.config.get("execution_mode", "normal")
        user_name = self.config.get("user_name", "")
        mode_style = "bold red" if exec_mode == "power" else "green"
        mode_label = "power ⚡" if exec_mode == "power" else "normal"
        left = [
            ("model", self._active_model() or "unknown", "cyan"),
            ("mode", mode_label, mode_style),
        ]
        right = [
            (f"{turns} turns", "", "bright_black"),
            (f"@{user_name}" if user_name else profile, "", "bright_black"),
        ]
        console.print(_status_bar(left, right))

    # ── Prompt ───────────────────────────────────────────────────────────────

    async def _ask(self) -> str:
        self._input.set_turns(len(self._session.messages) // 2)
        return await self._input.ask()

    # ── /slash commands ───────────────────────────────────────────────────────

    def handle_slash(self, cmd: str) -> Optional[str]:
        parts = cmd.strip().split(maxsplit=1)
        verb = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if verb == "/exit":
            console.print(Text("Goodbye!", style=P["warn"]))
            if self.daemon:
                self.daemon.stop()
            sys.exit(0)

        elif verb == "/reset":
            if self.daemon:
                agent = self.daemon.get_service("agent")
                if agent and hasattr(agent, "reset"):
                    agent.reset()
            self._session = session_manager.create_session()
            self._history = InMemoryHistory()
            print_mini_banner(
                provider=self.config.get("llm_provider", "ollama"),
                model=self._active_model(),
            )

        elif verb == "/profile":
            name = self.config.get("user_name", "Not set")
            lang = self.config.get("user_language", "Not set")
            console.print(Panel(
                f"[bold cyan]User Profile[/bold cyan]\n"
                f"  Name:     [yellow]{name}[/yellow]\n"
                f"  Language: [green]{lang}[/green]\n\n"
                f"[dim]Commands:\n  /name <your_name>            - Change your name\n  /language <Hinglish|English> - Change language[/dim]",
                title="[bold]Profile[/bold]",
                border_style="cyan",
            ))

        elif verb == "/name":
            if not arg:
                self._print_inline("Usage: /name <your_name>", style=P["warn"])
            else:
                self.config["user_name"] = arg
                save_config(self.config)
                if self.daemon:
                    self.daemon.config["user_name"] = arg
                    agent = self.daemon.get_service("agent")
                    if agent and hasattr(agent, "config"):
                        agent.config["user_name"] = arg
                    mem = self.daemon.get_service("memory")
                    if mem and hasattr(mem, "profile"):
                        mem.profile.set("name", arg)
                self._print_inline(f"Name updated to: {arg}", style=P["success"])

        elif verb == "/language":
            if not arg or arg.lower() not in ("hinglish", "english"):
                self._print_inline("Usage: /language <Hinglish|English>", style=P["warn"])
            else:
                lang = "Hinglish" if arg.lower() == "hinglish" else "English"
                self.config["user_language"] = lang
                save_config(self.config)
                if self.daemon:
                    self.daemon.config["user_language"] = lang
                    agent = self.daemon.get_service("agent")
                    if agent and hasattr(agent, "config"):
                        agent.config["user_language"] = lang
                    mem = self.daemon.get_service("memory")
                    if mem and hasattr(mem, "profile"):
                        mem.profile.set("language", lang)
                self._print_inline(f"Language updated to: {lang}", style=P["success"])

        elif verb in ("/sessions", "/session"):
            self._handle_sessions_command(arg)

        elif verb == "/tools":
            if not self.daemon:
                self._print_inline("Daemon not running", style=P["warn"]); return None
            registry = self.daemon.get_service("tools")
            if not registry:
                self._print_inline("Tools not initialized", style=P["warn"]); return None
            tools = registry.list_tools()
            t = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", title="")
            t.add_column("Tool", style="cyan")
            t.add_column("Description", style="bright_black")
            for tool in tools:
                t.add_row(tool["name"], tool.get("description", ""))
            console.print(Panel(t, title="[bold cyan]Tools[/bold cyan]", border_style="bright_black", box=box.ROUNDED))

        elif verb == "/memory":
            if not self.daemon:
                self._print_inline("Daemon not running", style=P["warn"]); return None
            manager = self.daemon.get_service("memory")
            if not manager:
                self._print_inline("Memory not initialized", style=P["warn"]); return None
            results = manager.recall(arg) if arg else manager.get_recent(5)
            if results:
                for r in results:
                    console.print(Text(f"  {r}", style="bright_black"))
            else:
                self._print_inline("No memories found", style="dim")

        elif verb == "/skills":
            if not self.daemon:
                self._print_inline("Daemon not running", style=P["warn"]); return None
            registry = self.daemon.get_service("skills")
            if not registry:
                self._print_inline("Skills not initialized", style=P["warn"]); return None
            skills = registry.list_skills()
            if not skills:
                self._print_inline("No skills discovered", style=P["warn"]); return None
            t = Table(box=box.SIMPLE, header_style="bold cyan")
            t.add_column("Name", style="cyan")
            t.add_column("Description", style="bright_black")
            for s in skills:
                t.add_row(s.name, s.description[:60])
            console.print(Panel(t, title="[bold cyan]Skills[/bold cyan]", border_style="bright_black", box=box.ROUNDED))
            self._print_inline("Tip: /run <skill-name> [args]", style="dim")

        elif verb == "/run":
            if not arg:
                self._print_inline("Usage: /run <skill-name> [args]", style=P["warn"]); return None
            sparts = arg.split(maxsplit=1)
            skill_name = sparts[0]
            skill_args = sparts[1] if len(sparts) > 1 else ""
            if not self.daemon:
                self._print_inline("Daemon not running", style=P["warn"]); return None
            registry = self.daemon.get_service("skills")
            executor = self.daemon.get_service("skill_executor")
            if not registry or not executor:
                self._print_inline("Skill system not available", style=P["warn"]); return None
            skill = registry.get(skill_name)
            if not skill:
                self._print_inline(f"Skill '{skill_name}' not found", style=P["error"]); return None
            with console.status(f"[cyan]Running {skill.name}…[/cyan]", spinner="dots"):
                try:
                    result = asyncio.run(executor.execute(skill, {"target": skill_args} if skill_args else None))
                    console.print(Panel(Text(result), title=f"[cyan]{skill.name}[/cyan]", border_style="bright_black", box=box.ROUNDED))
                except Exception as e:
                    self._print_inline(f"Skill error: {e}", style=P["error"])

        elif verb == "/status":
            if not self.daemon:
                self._print_inline("Daemon status: not running", style=P["warn"]); return None
            status = self.daemon.status()
            t = Table(box=box.SIMPLE, header_style="bold cyan")
            t.add_column("Service", style="cyan")
            t.add_column("Status")
            for name, info in status["services"].items():
                s = "green" if info["status"] == "running" else "yellow"
                t.add_row(f"{info['type']}:{name}", Text(info["status"], style=s))
            console.print(Panel(t, title="[bold cyan]System Status[/bold cyan]", border_style="bright_black", box=box.ROUNDED))

        elif verb == "/theme":
            idx = Dialog.select("Theme", ["dark", "light", "auto"])
            if idx == 0: self._theme_mgr.set_theme("dark")
            elif idx == 1: self._theme_mgr.set_theme("light")
            elif idx == 2: self._theme_mgr.set_auto(True)
            if idx is not None:
                self._print_inline(f"✓ Theme → {self._theme_mgr.theme.name}", style=P["success"])

        elif verb == "/model":
            self._handle_model_switch(arg)

        elif verb in ("/mode", "/power"):
            current_mode = self.config.get("execution_mode", "normal")
            target_mode = None

            if verb == "/power":
                target_mode = "normal" if current_mode == "power" else "power"
            elif arg:
                clean_arg = arg.strip().lower()
                if clean_arg in ("power", "auto", "turbo", "on"):
                    target_mode = "power"
                elif clean_arg in ("normal", "safe", "off", "chat"):
                    target_mode = "normal"
                else:
                    self._print_inline(f"Unknown mode: {arg}. Use 'normal' or 'power'", style=P["warn"])
                    return None
            else:
                idx = Dialog.select(
                    "Execution Mode",
                    [
                        "normal  🛡️ (Safe mode: asks confirmation before running sensitive tools)",
                        "power   ⚡ (Power mode: executes tools immediately without asking)",
                    ],
                )
                if idx is None:
                    return None
                target_mode = "normal" if idx == 0 else "power"

            self.config["execution_mode"] = target_mode
            save_config(self.config)
            if self.daemon:
                self.daemon.config["execution_mode"] = target_mode
                agent = self.daemon.get_service("agent")
                if agent and hasattr(agent, "set_mode"):
                    agent.set_mode(target_mode)

            if target_mode == "power":
                self._print_inline("⚡ Power Mode Enabled: Tools will execute immediately without confirmation.", style="bold red")
            else:
                self._print_inline("🛡️ Normal Mode Enabled: Sensitive tools will ask for confirmation.", style="green")

        elif verb == "/verbose":
            current_verbose = self.config.get("verbose", False)
            new_verbose = not current_verbose
            self.config["verbose"] = new_verbose
            save_config(self.config)
            if self.daemon:
                self.daemon.config["verbose"] = new_verbose
            if new_verbose:
                self._print_inline("🔍 Verbose Mode Enabled: Detailed planner and tool execution logs will be shown.", style="cyan")
            else:
                self._print_inline("✨ Clean Mode Enabled: Only final direct answers will be shown.", style="green")

        elif verb == "/voice":
            try:
                from perception.stt.audio_capture import AudioCapture
                from perception.stt.whisper_engine import WhisperEngine
                with console.status("[cyan]Recording…[/cyan]", spinner="dots"):
                    capture = AudioCapture()
                    audio = capture.record(duration=5)
                if audio is not None:
                    with console.status("[cyan]Transcribing…[/cyan]", spinner="dots"):
                        engine = WhisperEngine(self.config)
                        text = engine.transcribe_array(audio)
                    if text:
                        self._print_inline(f"You said: {text}", style="dim")
                        return text
                self._print_inline("Voice input failed", style=P["error"])
            except Exception as e:
                self._print_inline(f"Voice not available: {e}", style=P["error"])

        elif verb == "/help":
            self._print_help()

        else:
            self._print_inline(f"Unknown command: {verb}. Type /help.", style=P["error"])

        return None

    def _print_help(self):
        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column("cmd", style="cyan", no_wrap=True)
        t.add_column("desc", style="bright_black")
        cmds = [
            ("/exit", "Exit Jarvis"),
            ("/reset", "Reset conversation"),
            ("/voice", "Voice input"),
            ("/tools", "List available tools"),
            ("/skills", "List available skills"),
            ("/run <name> [args]", "Execute a skill"),
            ("/memory [query]", "Search memories"),
            ("/status", "System status"),
            ("/model", "Switch LLM provider / model"),
            ("/mode [normal|power]", "Switch execution mode (normal / power ⚡)"),
            ("/power", "Toggle instant tool execution (no y/n prompts)"),
            ("/verbose", "Toggle clean vs detailed debug logs"),
            ("/profile", "View or change user name & language"),
            ("/sessions", "List, load, view, or manage conversation sessions"),
            ("/theme", "Switch theme"),
            ("/help", "This help"),
        ]
        for cmd, desc in cmds:
            t.add_row(cmd, desc)

        shortcuts = Table(box=box.SIMPLE, show_header=False)
        shortcuts.add_column("key", style="cyan", no_wrap=True)
        shortcuts.add_column("desc", style="bright_black")
        shortcuts.add_row("Ctrl+T", "Cycle theme")
        shortcuts.add_row("Ctrl+L", "Clear screen")
        shortcuts.add_row("↑ / ↓", "Navigate history")

        console.print(Panel(
            RGroup(Text("Commands", style="bold cyan"), t, Text("Shortcuts", style="bold cyan"), shortcuts),
            title="[bold cyan]Help[/bold cyan]",
            border_style="bright_black",
            box=box.ROUNDED,
        ))

    def _handle_sessions_command(self, arg: str):
        parts = arg.strip().split(maxsplit=1) if arg else []
        subcmd = parts[0].lower() if parts else "list"
        param = parts[1] if len(parts) > 1 else ""

        # Handle shortcuts like `/sessions 1` or `/sessions <id>` directly
        if subcmd not in ("list", "ls", "load", "view", "show", "resume", "delete", "rm", "clear", "new") and not param:
            param = subcmd
            subcmd = "load"

        if subcmd in ("list", "ls"):
            sessions = session_manager.list_sessions()
            if not sessions:
                self._print_inline("No saved sessions found.", style="dim")
                return

            t = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
            t.add_column("#", style="dim", width=3)
            t.add_column("ID", style="cyan", width=10)
            t.add_column("Date & Time", style="bright_black", width=18)
            t.add_column("Turns", justify="right", style="yellow", width=7)
            t.add_column("Title / Topic", style="white")

            import datetime
            active_id = self._session.session_id if self._session else ""

            for i, s in enumerate(sessions[:20], 1):
                sid = s.get("session_id", "")
                is_active = (sid == active_id)
                short_id = sid[:8] + ("*" if is_active else "")
                id_style = "bold green" if is_active else "cyan"

                mtime = s.get("last_active", s.get("created_at", 0))
                dt_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                turns = str(s.get("turns", 0))
                title = s.get("title", "New Session")
                if is_active:
                    title += " [green](current)[/green]"

                t.add_row(str(i), f"[{id_style}]{short_id}[/{id_style}]", dt_str, turns, title)

            console.print(Panel(t, title="[bold cyan]Saved Sessions[/bold cyan]", border_style="bright_black", box=box.ROUNDED))
            self._print_inline("Commands: /sessions load <#|id> | /sessions view <#|id> | /sessions new | /sessions delete <#|id>", style="dim")

        elif subcmd in ("load", "resume"):
            if not param:
                self._print_inline("Usage: /sessions load <# or session_id>", style=P["warn"])
                return
            target = session_manager.get_session(param)
            if not target:
                sessions = session_manager.list_sessions()
                if param.isdigit() and 1 <= int(param) <= len(sessions):
                    target = session_manager.get_session(sessions[int(param) - 1]["session_id"])

            if not target:
                self._print_inline(f"Session '{param}' not found.", style=P["error"])
                return

            self._session = target
            turns = len(target.messages) // 2
            self._print_inline(f"✓ Resumed session {target.session_id[:8]} ({turns} turns: '{target.get_title()}')", style=P["success"])

        elif subcmd in ("view", "show"):
            if not param:
                target = self._session
            else:
                target = session_manager.get_session(param)
                if not target:
                    sessions = session_manager.list_sessions()
                    if param.isdigit() and 1 <= int(param) <= len(sessions):
                        target = session_manager.get_session(sessions[int(param) - 1]["session_id"])

            if not target or not target.messages:
                self._print_inline("No messages in this session.", style="dim")
                return

            console.print(Panel(
                f"[bold cyan]Transcript: {target.get_title()}[/bold cyan] [dim]({target.session_id[:8]})[/dim]",
                border_style="cyan"
            ))
            for m in target.messages:
                role = m.get("role", "")
                content = m.get("content", "")
                if role == "user":
                    console.print(_user_line(content))
                elif role == "assistant":
                    console.print(_ai_prefix() + Text(content, style="white"))
                    console.print()

        elif subcmd == "new":
            if self.daemon:
                agent = self.daemon.get_service("agent")
                if agent and hasattr(agent, "reset"):
                    agent.reset()
            self._session = session_manager.create_session()
            self._history = InMemoryHistory()
            self._print_inline(f"✓ Started new session {self._session.session_id[:8]}", style=P["success"])

        elif subcmd in ("delete", "rm"):
            if not param:
                self._print_inline("Usage: /sessions delete <# or session_id>", style=P["warn"])
                return
            target = session_manager.get_session(param)
            if not target:
                sessions = session_manager.list_sessions()
                if param.isdigit() and 1 <= int(param) <= len(sessions):
                    target = session_manager.get_session(sessions[int(param) - 1]["session_id"])

            if target:
                target_id = target.session_id
                session_manager.delete_session(target_id)
                self._print_inline(f"✓ Deleted session {target_id[:8]}", style=P["success"])
                if self._session and self._session.session_id == target_id:
                    self._session = session_manager.create_session()
            else:
                self._print_inline(f"Session '{param}' not found.", style=P["error"])

        elif subcmd == "clear":
            count = session_manager.clear_all_sessions()
            self._session = session_manager.create_session()
            self._print_inline(f"✓ Cleared {count} saved sessions.", style=P["success"])

        else:
            self._print_inline(f"Unknown sessions command: '{subcmd}'. Try: /sessions list, load, view, new, delete", style=P["warn"])

    def _handle_model_switch(self, arg: str):
        """Provider + model selector — identical logic to original, just cleaner UI."""
        PROVIDERS = [
            {"id": "ollama",     "label": "Ollama",       "needs_key": False, "key_field": None},
            {"id": "openai",     "label": "OpenAI",       "needs_key": True,  "key_field": "openai_api_key"},
            {"id": "anthropic",  "label": "Anthropic",    "needs_key": True,  "key_field": "anthropic_api_key"},
            {"id": "gemini",     "label": "Gemini",       "needs_key": True,  "key_field": "gemini_api_key"},
            {"id": "openrouter", "label": "OpenRouter",   "needs_key": True,  "key_field": "openrouter_api_key"},
            {"id": "opencode",   "label": "OpenCode Zen", "needs_key": True,  "key_field": "opencode_api_key"},
        ]
        MODEL_PRESETS = {
            "openai":     ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
            "anthropic":  ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
            "gemini":     ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
            "openrouter": ["openai/gpt-4o", "anthropic/claude-3.5-sonnet", "google/gemini-2.0-flash", "meta-llama/llama-3.2-3b-instruct"],
            "opencode":   ["deepseek-v4-flash-free", "gpt-5.4", "gpt-5.4-mini"],
        }

        def _sync_daemon():
            if not self.daemon: return
            self.daemon.config.update(self.config)
            llm = self.daemon.get_service("llm")
            if llm:
                llm.config = self.daemon.config
                llm._providers.clear()

        if arg:
            provider = self.config.get("llm_provider", "ollama")
            self.config[f"{provider}_model"] = arg
            save_config(self.config)
            _sync_daemon()
            self._print_inline(f"✓ Model → {arg}", style=P["success"])
            return

        active = self.config.get("llm_provider", "ollama")
        cur_model = self._active_model()
        opts = []
        for p in PROVIDERS:
            tag = "[bold cyan]● active[/]" if p["id"] == active else \
                  "[yellow]no key[/]" if p["needs_key"] and not self.config.get(p.get("key_field", ""), "") else \
                  "[green]ready[/]"
            opts.append(f"{p['label']:<14}  {tag}" + (f"  ({cur_model})" if p["id"] == active else ""))

        idx = Dialog.select("Select Provider", opts)
        if idx is None: return
        provider = PROVIDERS[idx]

        if provider["needs_key"]:
            existing = self.config.get(provider["key_field"], "")
            if not existing:
                self._print_inline(f"API key required for {provider['label']}", style=P["warn"])
                key = Dialog.prompt(f"Enter {provider['label']} API key", password=True)
                if not key:
                    self._print_inline("No key provided.", style=P["error"]); return
                self.config[provider["key_field"]] = key
                save_config(self.config)
                self._print_inline(f"✓ Key saved", style=P["success"])

        choices = list(MODEL_PRESETS.get(provider["id"], []))
        if provider["id"] == "ollama":
            try:
                import httpx
                base = self.config.get("ollama_base_url", "http://localhost:11434").rstrip("/")
                resp = httpx.get(f"{base}/api/tags", timeout=3)
                if resp.status_code == 200:
                    choices = [m["name"] for m in resp.json().get("models", [])]
            except Exception:
                pass

        if not choices:
            selected = Dialog.prompt(f"{provider['label']} model name", default="")
        else:
            midx = Dialog.select(f"{provider['label']} model", choices + ["[custom]"])
            if midx is None: return
            if midx == len(choices):
                selected = Dialog.prompt("Model name", default="")
            else:
                selected = choices[midx]

        if not selected: return
        self.config["llm_provider"] = provider["id"]
        self.config[f"{provider['id']}_model"] = selected
        save_config(self.config)
        _sync_daemon()
        self._print_inline(f"✓ {provider['label']} → {selected}", style=P["success"])

    # ── Response rendering ────────────────────────────────────────────────────

    def _render_response(self, text: str):
        """Print AI response: markdown if it has markers, plain otherwise."""
        console.print(_ai_prefix(), end="")
        _md = ("**", "```", "`", "## ", "### ", "# ", "\n- ", "\n1.")
        if any(m in text for m in _md):
            console.print(Markdown(text))
        else:
            console.print(text)

    # ── Chat ─────────────────────────────────────────────────────────────────

    async def chat_once(self, user_input: str) -> AsyncGenerator[str, None]:
        if not self.daemon:
            yield "System not initialized."; return
        agent = self.daemon.get_service("agent")
        if not agent:
            yield "Agent not initialized."; return
        self._session.add_message("user", user_input)
        full = ""
        async for chunk in agent.execute_stream(user_input, self._session, config=self.config):
            if agent._pending_ask:
                answer = await self._ptk_session.prompt_async(HTML(f"<ansicyan><b>? </b></ansicyan>{html.escape(agent._pending_ask)} "))
                agent.submit_answer(answer)
            else:
                full += chunk
                yield chunk
        if full:
            self._session.add_message("assistant", full)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run_interactive(self):
        self.print_banner()
        self._check_first_time_onboarding()
        try:
            asyncio.run(self._run_async_loop())
        except KeyboardInterrupt:
            pass

    def _check_first_time_onboarding(self):
        if self.config.get("user_name") and self.config.get("user_language"):
            return

        if not sys.stdin.isatty():
            return

        console.print()
        console.print(Panel(
            "[bold cyan]Welcome to Jarvis![/bold cyan]\n"
            "[dim]Let's personalize your assistant in two quick steps.[/dim]",
            border_style="cyan",
            title="[bold]Profile Setup[/bold]"
        ))

        # 1. Language selection
        console.print("\n[bold]Select your preferred language / Apni bhasha chunein:[/bold]")
        console.print("  [cyan]1[/cyan] Hinglish (Hindi + English)")
        console.print("  [cyan]2[/cyan] English")
        lang_choice = Prompt.ask("Choice", choices=["1", "2", "hinglish", "english"], default="1").strip().lower()
        language = "Hinglish" if lang_choice in ("1", "hinglish") else "English"

        # 2. User name based on chosen language
        console.print()
        if language == "Hinglish":
            name = Prompt.ask("[bold cyan]Aapka naam kya hai?[/bold cyan] (Enter your name)").strip()
        else:
            name = Prompt.ask("[bold cyan]What is your name?[/bold cyan] (Enter your name)").strip()

        if not name:
            name = "User"

        # 3. Save configuration
        self.config["user_name"] = name
        self.config["user_language"] = language
        save_config(self.config)

        if self.daemon:
            self.daemon.config["user_name"] = name
            self.daemon.config["user_language"] = language
            agent = self.daemon.get_service("agent")
            if agent and hasattr(agent, "config"):
                agent.config["user_name"] = name
                agent.config["user_language"] = language
            mem = self.daemon.get_service("memory")
            if mem and hasattr(mem, "profile"):
                mem.profile.set("name", name)
                mem.profile.set("language", language)

        # 4. Greet
        console.print()
        if language == "Hinglish":
            console.print(f"[bold green]Bahut badhiya, {name}! Main hoon Jarvis, aapka personal AI assistant.[/bold green]\n")
        else:
            console.print(f"[bold green]Great to meet you, {name}! I am Jarvis, your personal AI assistant.[/bold green]\n")

    async def _run_async_loop(self):
        _eof = 0
        while True:
            self._render_status()

            user_input = await self._ask()
            if not user_input:
                user_input = user_input.strip()

            if not user_input:
                _eof += 1
                if _eof >= 3: break
                continue
            _eof = 0

            if user_input.startswith("/"):
                result = self.handle_slash(user_input)
                if result:
                    user_input = result
                else:
                    continue

            self._history.append_string(user_input)

            # Echo user message
            console.print(_user_line(user_input))
            console.print()

            # Stream response
            full = ""
            status = console.status("[cyan]thinking…[/cyan]", spinner="dots")
            status.start()
            live = None

            def on_step(**kwargs):
                desc = kwargs.get("description", "")
                tool = kwargs.get("tool", "")
                label = desc or tool or "processing"
                try:
                    status.update(f"[cyan]{label}…[/cyan]")
                except Exception:
                    pass

            from core.event_bus import event_bus, EVENTS
            event_bus.on(EVENTS["AGENT_STEP"], on_step)

            try:
                async for chunk in self.chat_once(user_input):
                    if chunk:
                        if status:
                            try:
                                status.stop()
                            except Exception:
                                pass
                        if live is None:
                            live = Live(console=console, refresh_per_second=12)
                            live.start()
                        full += chunk
                        live.update(Markdown(full))
            except Exception as e:
                if status:
                    try: status.stop()
                    except Exception: pass
                if live:
                    try: live.stop()
                    except Exception: pass
                    live = None
                console.print(f"\n[red]Error: {e}[/red]")
            finally:
                if status:
                    try: status.stop()
                    except Exception: pass
                if live:
                    try: live.stop()
                    except Exception: pass
                event_bus.off(EVENTS["AGENT_STEP"], on_step)
            console.print()

    def run_once(self, user_input: str) -> str:
        async def _run():
            acc = ""
            async for chunk in self.chat_once(user_input):
                acc += chunk
            return acc
        return asyncio.run(_run())