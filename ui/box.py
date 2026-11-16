from typing import Optional, List
from rich.console import Console, RenderableType, Group
from rich.padding import Padding
from rich.style import Style
from rich.align import Align
from rich.columns import Columns
from rich import box as rich_box


class Box:
    """Layout container with spacing, padding, and alignment."""

    def __init__(
        self,
        *children,
        width: Optional[int] = None,
        height: Optional[int] = None,
        padding: tuple = (0, 0, 0, 0),
        margin: tuple = (0, 0, 0, 0),
        align: str = "left",
        justify: str = "start",
        flex_direction: str = "column",
        gap: int = 0,
        style: Optional[str] = None,
    ):
        self.children = list(children)
        self.width = width
        self.height = height
        self.padding = padding
        self.margin = margin
        self.align = align
        self.justify = justify
        self.flex_direction = flex_direction
        self.gap = gap
        self.style = style

    def add(self, child):
        self.children.append(child)
        return self

    def _render(self) -> RenderableType:
        if not self.children:
            return ""

        t, r, b, l = self._expand_padding(self.padding)
        mt, mr, mb, ml = self._expand_padding(self.margin)

        items: List[RenderableType] = []
        for child in self.children:
            rendered = child if isinstance(child, (str, RenderableType)) else str(child)
            items.append(rendered)
            if self.gap:
                items.append(" " * self.gap if self.flex_direction == "row" else "\n")

        if self.flex_direction == "row":
            content = Columns(items, equal=False, expand=True)
        else:
            clean = [i for i in items if i is not None and i != "\n"]
            content = Group(*clean)

        if self.align == "center":
            content = Align.center(content)
        elif self.align == "right":
            content = Align.right(content)

        if t or r or b or l:
            content = Padding(content, (t, r, b, l))

        if self.style:
            content = Padding(content, (0, 0), style=Style.parse(self.style))

        if mt or mr or mb or ml:
            content = Padding(content, (mt, mr, mb, ml))

        return content

    def __rich__(self) -> RenderableType:
        return self._render()

    @staticmethod
    def _expand_padding(p):
        if isinstance(p, int):
            return (p, p, p, p)
        if len(p) == 1:
            return (p[0], p[0], p[0], p[0])
        if len(p) == 2:
            return (p[0], p[1], p[0], p[1])
        if len(p) == 3:
            return (p[0], p[1], p[2], p[1])
        return p[:4]
