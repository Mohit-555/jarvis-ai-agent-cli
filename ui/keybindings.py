from typing import Callable, Dict, Optional, List, NamedTuple
import re


class Binding(NamedTuple):
    keys: str
    description: str
    handler: Callable
    context: str = "global"


CONTEXT_GLOBAL = "global"
CONTEXT_INPUT = "input"
CONTEXT_DIALOG = "dialog"
CONTEXT_LIST = "list"


DEFAULT_BINDINGS = [
    Binding("Ctrl+C", "Interrupt / Cancel", lambda: None, CONTEXT_GLOBAL),
    Binding("Ctrl+D", "Exit (if empty) / Delete", lambda: None, CONTEXT_INPUT),
    Binding("Tab", "Next suggestion / indent", lambda: None, CONTEXT_INPUT),
    Binding("Shift+Tab", "Previous suggestion", lambda: None, CONTEXT_INPUT),
    Binding("Up", "Previous history", lambda: None, CONTEXT_INPUT),
    Binding("Down", "Next history", lambda: None, CONTEXT_INPUT),
    Binding("Ctrl+R", "Search history", lambda: None, CONTEXT_INPUT),
    Binding("Ctrl+W", "Delete word backward", lambda: None, CONTEXT_INPUT),
    Binding("Ctrl+U", "Delete line", lambda: None, CONTEXT_INPUT),
    Binding("Ctrl+L", "Clear screen", lambda: None, CONTEXT_INPUT),
    Binding("Escape", "Cancel / Close dialog", lambda: None, CONTEXT_DIALOG),
    Binding("Enter", "Confirm", lambda: None, CONTEXT_DIALOG),
    Binding("Ctrl+N", "Next item", lambda: None, CONTEXT_LIST),
    Binding("Ctrl+P", "Previous item", lambda: None, CONTEXT_LIST),
]


class Keybindings:
    """Configurable keybinding registry with context scoping."""

    def __init__(self):
        self._bindings: Dict[str, List[Binding]] = {
            CONTEXT_GLOBAL: [],
            CONTEXT_INPUT: [],
            CONTEXT_DIALOG: [],
            CONTEXT_LIST: [],
        }
        self._user_overrides: Dict[str, str] = {}
        self._load_defaults()

    def _load_defaults(self):
        for b in DEFAULT_BINDINGS:
            self._bindings[b.context].append(b)

    def register(self, binding: Binding):
        if binding.context not in self._bindings:
            self._bindings[binding.context] = []
        self._bindings[binding.context].append(binding)

    def bind(self, keys: str, handler: Callable, description: str = "", context: str = CONTEXT_GLOBAL):
        self.register(Binding(keys, description, handler, context))

    def get(self, context: str = CONTEXT_GLOBAL) -> List[Binding]:
        return self._bindings.get(context, [])

    def get_all(self) -> List[Binding]:
        result = []
        seen = set()
        for ctx_bindings in self._bindings.values():
            for b in ctx_bindings:
                if b.keys not in seen:
                    seen.add(b.keys)
                    result.append(b)
        return result

    def get_by_keys(self, keys: str) -> Optional[Binding]:
        for ctx_bindings in self._bindings.values():
            for b in ctx_bindings:
                if b.keys == keys:
                    return b
        return None

    def override(self, keys: str, new_keys: str):
        self._user_overrides[keys] = new_keys

    def find_handler(self, keys: str, context: str = CONTEXT_GLOBAL) -> Optional[Callable]:
        effective_keys = self._user_overrides.get(keys, keys)
        for b in self._bindings.get(context, []):
            if b.keys == effective_keys:
                return b.handler
        return None

    def display(self, context: str = CONTEXT_GLOBAL) -> str:
        lines = []
        for b in self.get(context):
            lines.append(f"  [{b.keys:12}] {b.description}")
        return "\n".join(lines)


_keybindings = Keybindings()


def get_keybindings() -> Keybindings:
    return _keybindings


def parse_keys(key_str: str) -> tuple:
    """Parse a key string like 'Ctrl+Shift+A' into modifiers and key."""
    parts = key_str.lower().split("+")
    modifiers = set()
    key = parts[-1]
    for p in parts[:-1]:
        if p in ("ctrl", "control"):
            modifiers.add("ctrl")
        elif p in ("shift",):
            modifiers.add("shift")
        elif p in ("alt", "meta"):
            modifiers.add("alt")
        elif p in ("super", "cmd", "win"):
            modifiers.add("super")
    return key, modifiers
