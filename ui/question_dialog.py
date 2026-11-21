"""
ui/question_dialog.py  —  OpenCode CLI-style Interactive Question Dialog

Renders an interactive terminal dialog box with selectable options:
  • Single-select (◉ / ○) and multi-select ([x] / [ ])
  • Arrow keys ↑↓ (or j/k) to navigate
  • Space to toggle (in multi-select mode)
  • Enter to confirm / submit
  • 'Other' option prompts for custom free-form text
  • Inline rendering preserving terminal scrollback
"""

import sys
import shutil
import asyncio
from typing import Optional, List, Dict, Any, Union

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML, to_formatted_text
from prompt_toolkit import PromptSession

STYLE = Style.from_dict({
    "dialog.border": "#00d7ff bold",
    "dialog.title": "#00d7ff bold",
    "dialog.progress": "#888888",
    "dialog.question": "#ffffff bold",
    "option.cursor": "#00d7ff bold",
    "option.active": "#00d7ff bold",
    "option.inactive": "#d0d0d0",
    "option.checked": "#00ff87 bold",
    "option.unchecked": "#707070",
    "hint.key": "#00d7ff bold",
    "hint.desc": "#777777",
    "button.active": "reverse #00d7ff bold",
    "button.inactive": "#777777",
})


class QuestionDialog:
    """OpenCode CLI-style Question Dialog for structured user input."""

    @classmethod
    async def ask_async(cls, question_data: Union[dict, str]) -> str:
        """
        Presents an interactive options dialog.
        question_data can be a dictionary or a plain string prompt.
        """
        # Reset mouse tracking so terminal works smoothly
        try:
            sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1015l")
            sys.stdout.flush()
        except Exception:
            pass

        # Parse question input
        if isinstance(question_data, str):
            # Check if string contains structured markdown list options
            import re
            lines = question_data.strip().split("\n")
            q_text = lines[0]
            options = []
            for line in lines[1:]:
                m = re.match(r"^\s*[-*•\d.]+\s*(.+)$", line)
                if m:
                    options.append(m.group(1).strip())
            
            data = {
                "title": "Jarvis needs your input",
                "progress": "Question 1 of 1",
                "question": q_text,
                "options": options if options else [],
                "multiple": False,
            }
        else:
            data = dict(question_data)

        title = data.get("title", "Jarvis needs your input")
        progress = data.get("progress", "Question 1 of 1")
        question = data.get("question", "Please select an option:")
        options = list(data.get("options", []))
        is_multiple = bool(data.get("multiple", False))

        # Fallback to simple text prompt if no options provided
        if not options:
            session = PromptSession()
            prompt_html = f"<ansicyan><b>? </b></ansicyan><b>{question}</b> "
            try:
                ans = await session.prompt_async(HTML(prompt_html))
                return (ans or "").strip()
            except (EOFError, KeyboardInterrupt):
                return ""

        # Ensure an "Other" option exists
        has_other = any("other" in opt.lower() for opt in options)
        if not has_other:
            options.append("Other (Type custom answer)")

        items = list(options)
        if is_multiple:
            items.append("[ Submit Selection ]")

        highlight_idx = [0]
        checked_indices = set()
        user_result = [""]

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("k")
        def _(event):
            highlight_idx[0] = (highlight_idx[0] - 1) % len(items)

        @kb.add("down")
        @kb.add("j")
        def _(event):
            highlight_idx[0] = (highlight_idx[0] + 1) % len(items)

        @kb.add("space")
        def _(event):
            if is_multiple:
                curr = highlight_idx[0]
                if curr < len(options):
                    if curr in checked_indices:
                        checked_indices.remove(curr)
                    else:
                        checked_indices.add(curr)

        @kb.add("enter")
        def _(event):
            curr = highlight_idx[0]
            if not is_multiple:
                user_result[0] = options[curr]
                event.app.exit(result=user_result[0])
            else:
                # If on submit button or pressed enter
                if curr == len(options) or checked_indices:
                    # Collect checked
                    selected = [options[i] for i in sorted(checked_indices)]
                    user_result[0] = ", ".join(selected) if selected else options[min(curr, len(options)-1)]
                    event.app.exit(result=user_result[0])
                else:
                    # Toggle selection
                    checked_indices.add(curr)

        @kb.add("escape")
        @kb.add("c-c")
        def _(event):
            event.app.exit(result="")

        def get_formatted_dialog():
            term_width = min(shutil.get_terminal_size().columns - 2, 78)
            inner_w = max(40, term_width - 4)

            lines = []
            
            # Header
            border_top = f"┌─ {title} " + "─" * max(2, inner_w - len(title) - 1) + "┐\n"
            lines.append(("class:dialog.border", border_top))
            
            # Subtitle / progress
            if progress:
                prog_line = f"│  {progress:<{inner_w}}│\n"
                lines.append(("class:dialog.progress", prog_line))
            
            # Question text
            q_wrapped = question[:inner_w]
            lines.append(("class:dialog.question", f"│  {q_wrapped:<{inner_w}}│\n"))
            lines.append(("class:dialog.border", f"│  {' ' * inner_w}│\n"))

            # Options
            for i, opt in enumerate(items):
                is_cursor = (i == highlight_idx[0])
                cursor = "❯ " if is_cursor else "  "

                if is_multiple:
                    if i < len(options):
                        box = "[x] " if i in checked_indices else "[ ] "
                        line_text = f"{cursor}{box}{opt}"
                        style = "class:option.active" if is_cursor else ("class:option.checked" if i in checked_indices else "class:option.inactive")
                    else:
                        line_text = f"{cursor}{opt}"
                        style = "class:button.active" if is_cursor else "class:button.inactive"
                else:
                    radio = "◉ " if is_cursor else "○ "
                    line_text = f"{cursor}{radio}{opt}"
                    style = "class:option.active" if is_cursor else "class:option.inactive"

                pad = max(0, inner_w - len(line_text))
                lines.append(("class:dialog.border", "│  "))
                lines.append((style, line_text + (" " * pad)))
                lines.append(("class:dialog.border", "│\n"))

            # Blank separator
            lines.append(("class:dialog.border", f"│  {' ' * inner_w}│\n"))

            # Keyboard hints footer
            if is_multiple:
                hint = "[ ↑/↓ Navigate • Space Select • Enter Submit • Esc Dismiss ]"
            else:
                hint = "[ ↑/↓ Navigate • Enter Select • Esc Dismiss ]"
            hint_pad = max(0, inner_w - len(hint))
            lines.append(("class:dialog.border", "│  "))
            lines.append(("class:hint.desc", hint + (" " * hint_pad)))
            lines.append(("class:dialog.border", "│\n"))

            # Bottom border
            border_bottom = "└" + "─" * (inner_w + 4) + "┘\n"
            lines.append(("class:dialog.border", border_bottom))

            return lines

        control = FormattedTextControl(get_formatted_dialog)
        layout = Layout(HSplit([Window(content=control, height=len(items) + 8)]))
        app = Application(
            layout=layout,
            key_bindings=kb,
            style=STYLE,
            full_screen=False,
            mouse_support=False,
        )

        res = await app.run_async()

        # Check if "Other" was chosen and needs custom input
        if res and ("other" in res.lower() or "custom answer" in res.lower()):
            session = PromptSession()
            try:
                custom_ans = await session.prompt_async(HTML("<ansicyan><b>Specify your custom requirements: </b></ansicyan>"))
                if custom_ans and custom_ans.strip():
                    return custom_ans.strip()
            except (EOFError, KeyboardInterrupt):
                pass

        return res or ""

    @classmethod
    def ask_sync(cls, question_data: Union[dict, str]) -> str:
        """Synchronous wrapper for ask_async."""
        return asyncio.run(cls.ask_async(question_data))
