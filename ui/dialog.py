from typing import Optional, Callable, List, Any
from rich.console import Console, RenderableType, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.style import Style
from rich import box as rich_box
from rich.prompt import Prompt, Confirm
from .theme import theme, color as theme_color
from .components import Pane, Byline, KeyboardHint


class Dialog:
    """Modal dialog with title, body, actions, and keyboard hints."""

    def __init__(
        self,
        title: str = "",
        body: RenderableType = "",
        subtitle: Optional[str] = None,
        color: Optional[str] = None,
        actions: Optional[List[dict]] = None,
        width: int = 60,
    ):
        self.title = title
        self.body = body
        self.subtitle = subtitle
        self.color = color or theme().color.primary
        self.actions = actions or [{"key": "Enter", "label": "OK", "action": "confirm"}]
        self.width = width
        self._console = Console()

    def render(self) -> Panel:
        c = self.color
        items = []

        title_t = Text(self.title, style=f"bold {c}")

        if self.subtitle:
            items.append(Text(self.subtitle, style="dim"))

        if self.body:
            items.append(self.body)

        hints = []
        for a in self.actions:
            hints.append(KeyboardHint(a.get("key", "?"), a.get("label", "")))
        if hints:
            items.append(Byline(*hints))

        content = Group(*items) if items else ""
        return Pane(content, title=self.title, color=c, fit=False)

    def show(self) -> Optional[str]:
        self._console.print(self.render())

    @staticmethod
    def confirm(
        message: str,
        title: str = "Confirm",
        default: bool = True,
    ) -> bool:
        console = Console()
        console.print(Pane(Text(message), title=title))
        return Confirm.ask("", default=default)

    @staticmethod
    def prompt(
        message: str,
        title: str = "Input",
        default: str = "",
        password: bool = False,
    ) -> str:
        console = Console()
        console.print(Pane(Text(message), title=title))
        return Prompt.ask("", default=default, password=password)

    @staticmethod
    def select(
        title: str,
        options: List[str],
        prompt_text: str = "Select an option",
    ) -> Optional[int]:
        console = Console()
        table = Table(box=rich_box.SIMPLE, show_header=False)
        table.add_column("#", style="bold cyan", width=4)
        table.add_column("Option")
        for i, opt in enumerate(options, 1):
            table.add_row(str(i), opt)
        console.print(Pane(Group(Text(title, style="bold"), table)))
        try:
            choice = Prompt.ask(prompt_text, default="")
            if not choice:
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
        return None
