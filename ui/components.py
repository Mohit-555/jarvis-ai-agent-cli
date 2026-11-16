from typing import Optional
from rich.console import RenderableType, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text as RichText
from rich.style import Style
from rich import box as rich_box
from .theme import theme, color as theme_color


def Pane(
    content: RenderableType,
    title: str = "",
    color: Optional[str] = None,
    border_style: Optional[str] = None,
    subtitle: Optional[str] = None,
    padding: tuple = (1, 2),
    fit: bool = False,
) -> Panel:
    bstyle = border_style or theme().border_style
    title_obj = None
    if title:
        t = RichText(title)
        t.stylize(Style.parse(bstyle))
        if subtitle:
            sub = RichText(f" {subtitle}")
            sub.stylize("dim")
            t.append(sub)
        title_obj = t
    return Panel(
        content,
        title=title_obj,
        border_style=bstyle,
        padding=padding,
        box=rich_box.ROUNDED if fit else rich_box.HEAVY,
    )


def Divider(
    label: str = "",
    char: str = "",
    style: Optional[str] = None,
    width: Optional[int] = None,
) -> RenderableType:
    t = theme()
    c = char or t.divider_char
    s = style or t.color.subtle
    text = f" {label} " if label else ""
    return RichText(f"{c * 40}{text}", style=s)


def Byline(*items) -> Group:
    parts = []
    for item in items:
        if isinstance(item, str):
            parts.append(RichText(item, style="dim"))
        else:
            parts.append(item)
    return Group(*parts)


def KeyboardHint(
    keys: str,
    description: str = "",
    key_style: Optional[str] = None,
    dim: bool = True,
) -> RichText:
    ks = key_style or "bold cyan"
    result = RichText(f"[{keys}]", style=ks)
    if description:
        result.append(f" {description}", style="dim" if dim else "")
    return result


def Spacer(height: int = 1) -> str:
    return "\n" * height
