"""
ui/question_dialog.py  —  Modern OpenCode CLI-style Centered Interactive Question Dialog

Features:
  • Single-select (◉ / ○), Multi-select ([x] / [ ]), Yes/No confirm, and Free-form text questions
  • Searchable selection list with real-time keyword filtering
  • Custom 'Other' option with inline text input
  • Multi-question wizard with progress indicator (e.g. 'Question 1 of 3')
  • Required and Optional questions (with Skip action)
  • Centered box layout with dark charcoal styling and cyan/purple rounded borders (╭─ ─╮)
  • Keyboard controls: ↑/↓ navigate, Space toggle, Enter submit, Tab switch actions, Esc cancel
  • Terminal boundary clamping to prevent clipping during resize
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
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit import PromptSession

# OpenCode-inspired Dark Charcoal & Cyan/Purple Palette
STYLE = Style.from_dict({
    "dialog.border": "#25C5DD bold",
    "dialog.title": "#25C5DD bold",
    "dialog.progress": "#888888",
    "dialog.optional": "#eab308 italic",
    "dialog.question": "#ffffff bold",
    "dialog.description": "#a0a0a0",
    "dialog.search": "#38bdf8 italic",
    "option.cursor": "#25C5DD bold",
    "option.active": "#25C5DD bold",
    "option.inactive": "#d4d4d8",
    "option.checked": "#10b981 bold",
    "option.unchecked": "#71717a",
    "hint.key": "#25C5DD bold",
    "hint.desc": "#71717a",
    "button.active": "reverse #25C5DD bold",
    "button.inactive": "#71717a",
})


class QuestionDialog:
    """OpenCode CLI-style Centered Question Dialog for structured user interactions."""

    @classmethod
    async def ask_async(cls, question_data: Union[dict, list, str]) -> Union[str, dict]:
        """
        Presents an interactive options dialog.
        question_data can be:
          - A single question dict
          - A list of question dicts (runs as sequential wizard)
          - A string prompt
        """
        # Ensure terminal mouse tracking is reset
        try:
            sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1015l")
            sys.stdout.flush()
        except Exception:
            pass

        # Multi-question wizard sequence
        if isinstance(question_data, list):
            results = {}
            total = len(question_data)
            for idx, q in enumerate(question_data, 1):
                if isinstance(q, dict):
                    q["progress"] = f"Question {idx} of {total}"
                res = await cls._ask_single_async(q)
                key = q.get("id", f"question_{idx}") if isinstance(q, dict) else f"question_{idx}"
                results[key] = res
            return results

        return await cls._ask_single_async(question_data)

    @classmethod
    async def _ask_single_async(cls, question_data: Union[dict, str]) -> str:
        # Normalize question input
        if isinstance(question_data, str):
            import re
            lines = question_data.strip().split("\n")
            q_text = lines[0]
            options = []
            for line in lines[1:]:
                m = re.match(r"^\s*[-*•\d.]+\s*(.+)$", line)
                if m:
                    options.append(m.group(1).strip())
            
            data = {
                "type": "select" if options else "text",
                "title": "Jarvis needs your input",
                "progress": "Question 1 of 1",
                "question": q_text,
                "options": options,
                "multiple": False,
                "required": True,
            }
        else:
            data = dict(question_data)

        q_type = data.get("type", "select").lower()
        title = data.get("title", "Jarvis needs your input")
        progress = data.get("progress", "")
        question = data.get("question", "Please select an option:")
        description = data.get("description", "")
        raw_options = list(data.get("options", []))
        is_multiple = bool(data.get("multiple", False)) or (q_type == "multi_select")
        is_required = bool(data.get("required", True))
        is_confirm = (q_type in ("confirm", "yesno", "yes_no"))

        # Yes/No confirm shortcut
        if is_confirm and not raw_options:
            raw_options = ["Yes", "No"]

        # Free-form text prompt mode
        if q_type == "text" and not raw_options:
            session = PromptSession()
            prompt_html = f"<ansicyan><b>? </b></ansicyan><b>{question}</b> "
            try:
                ans = await session.prompt_async(HTML(prompt_html))
                return (ans or "").strip()
            except (EOFError, KeyboardInterrupt):
                return ""

        # Default options if empty
        if not raw_options:
            raw_options = ["Yes", "No"]

        # Add 'Other' option if not present
        has_other = any("other" in str(opt).lower() for opt in raw_options)
        if not has_other and not is_confirm:
            raw_options.append("Other (Type custom answer)")

        # State tracking
        search_query = [""]
        highlight_idx = [0]
        checked_indices = set()
        user_result = [""]
        focus_target = ["options"]  # "options", "submit", "skip", "cancel"

        def get_filtered_options():
            q = search_query[0].lower().strip()
            if not q:
                return raw_options
            return [opt for opt in raw_options if q in opt.lower()]

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("k")
        def _(event):
            opts = get_filtered_options()
            num_opts = len(opts)
            if focus_target[0] == "options" and num_opts > 0:
                highlight_idx[0] = (highlight_idx[0] - 1) % num_opts
            elif focus_target[0] != "options":
                focus_target[0] = "options"
                highlight_idx[0] = num_opts - 1

        @kb.add("down")
        @kb.add("j")
        def _(event):
            opts = get_filtered_options()
            num_opts = len(opts)
            if focus_target[0] == "options" and num_opts > 0:
                if highlight_idx[0] == num_opts - 1:
                    focus_target[0] = "submit" if is_multiple else ("skip" if not is_required else "options")
                    if focus_target[0] == "options":
                        highlight_idx[0] = 0
                else:
                    highlight_idx[0] = (highlight_idx[0] + 1) % num_opts
            elif focus_target[0] == "submit":
                focus_target[0] = "skip" if not is_required else "options"
                if focus_target[0] == "options":
                    highlight_idx[0] = 0
            elif focus_target[0] == "skip":
                focus_target[0] = "options"
                highlight_idx[0] = 0

        @kb.add("space")
        def _(event):
            opts = get_filtered_options()
            if is_multiple and focus_target[0] == "options":
                curr = highlight_idx[0]
                if 0 <= curr < len(opts):
                    opt_val = opts[curr]
                    if opt_val in checked_indices:
                        checked_indices.remove(opt_val)
                    else:
                        checked_indices.add(opt_val)

        @kb.add("tab")
        def _(event):
            # Cycle through controls: options -> submit -> skip -> options
            if focus_target[0] == "options":
                focus_target[0] = "submit" if is_multiple else ("skip" if not is_required else "options")
            elif focus_target[0] == "submit":
                focus_target[0] = "skip" if not is_required else "options"
            else:
                focus_target[0] = "options"

        @kb.add("backspace")
        def _(event):
            if search_query[0]:
                search_query[0] = search_query[0][:-1]
                highlight_idx[0] = 0

        @kb.add("enter")
        def _(event):
            opts = get_filtered_options()
            
            if focus_target[0] == "skip":
                user_result[0] = ""
                event.app.exit(result="")
                return

            if not is_multiple:
                if opts and 0 <= highlight_idx[0] < len(opts):
                    user_result[0] = opts[highlight_idx[0]]
                elif opts:
                    user_result[0] = opts[0]
                event.app.exit(result=user_result[0])
            else:
                # Multi-select
                if checked_indices:
                    user_result[0] = ", ".join(sorted(checked_indices))
                elif opts and 0 <= highlight_idx[0] < len(opts):
                    user_result[0] = opts[highlight_idx[0]]
                event.app.exit(result=user_result[0])

        @kb.add("escape")
        @kb.add("c-c")
        def _(event):
            event.app.exit(result="")

        # Keypress handler for instant search filtering
        @kb.add("<any>")
        def _(event):
            char = event.data
            if char and char.isprintable() and len(char) == 1 and not char.isspace():
                search_query[0] += char
                highlight_idx[0] = 0

        def get_formatted_dialog():
            term_w = shutil.get_terminal_size().columns
            # Clamp dialog width: max 74 cols, min 44 cols
            box_w = min(max(44, term_w - 6), 74)
            inner_w = box_w - 4
            left_margin = max(0, (term_w - box_w) // 2)
            margin_sp = " " * left_margin

            lines = []
            
            # Top rounded border: ╭─ Title ─╮
            title_text = f"╭─ {title} "
            dash_len = max(2, box_w - len(title_text) - 1)
            lines.append(("class:dialog.border", f"{margin_sp}{title_text}{'─' * dash_len}╮\n"))

            # Progress & Optional badge line
            prog_text = progress or ""
            opt_badge = "[Optional]" if not is_required else ""
            pad_mid = max(1, inner_w - len(prog_text) - len(opt_badge))
            lines.append(("class:dialog.border", f"{margin_sp}│  "))
            lines.append(("class:dialog.progress", prog_text))
            lines.append(("", " " * pad_mid))
            lines.append(("class:dialog.optional", opt_badge))
            lines.append(("class:dialog.border", "  │\n"))

            # Question Text
            q_text = question[:inner_w]
            q_pad = max(0, inner_w - len(q_text))
            lines.append(("class:dialog.border", f"{margin_sp}│  "))
            lines.append(("class:dialog.question", q_text + (" " * q_pad)))
            lines.append(("class:dialog.border", "  │\n"))

            # Description (if provided)
            if description:
                d_text = description[:inner_w]
                d_pad = max(0, inner_w - len(d_text))
                lines.append(("class:dialog.border", f"{margin_sp}│  "))
                lines.append(("class:dialog.description", d_text + (" " * d_pad)))
                lines.append(("class:dialog.border", "  │\n"))

            # Search indicator (if user typed search filter)
            if search_query[0]:
                search_str = f"Filter: '{search_query[0]}'"
                s_pad = max(0, inner_w - len(search_str))
                lines.append(("class:dialog.border", f"{margin_sp}│  "))
                lines.append(("class:dialog.search", search_str + (" " * s_pad)))
                lines.append(("class:dialog.border", "  │\n"))

            lines.append(("class:dialog.border", f"{margin_sp}│  {' ' * inner_w}  │\n"))

            # Render filtered options
            opts = get_filtered_options()
            if not opts:
                no_res = "  (No options match your filter)"
                nr_pad = max(0, inner_w - len(no_res))
                lines.append(("class:dialog.border", f"{margin_sp}│  "))
                lines.append(("class:dialog.progress", no_res + (" " * nr_pad)))
                lines.append(("class:dialog.border", "  │\n"))

            for i, opt in enumerate(opts):
                is_cursor = (i == highlight_idx[0] and focus_target[0] == "options")
                cursor = "❯ " if is_cursor else "  "

                if is_confirm:
                    icon = "◉ " if is_cursor else "○ "
                    opt_str = f"{cursor}{icon}{opt}"
                    style = "class:option.active" if is_cursor else "class:option.inactive"
                elif is_multiple:
                    is_checked = (opt in checked_indices)
                    chk = "[x] " if is_checked else "[ ] "
                    opt_str = f"{cursor}{chk}{opt}"
                    style = "class:option.active" if is_cursor else ("class:option.checked" if is_checked else "class:option.inactive")
                else:
                    radio = "◉ " if is_cursor else "○ "
                    opt_str = f"{cursor}{radio}{opt}"
                    style = "class:option.active" if is_cursor else "class:option.inactive"

                o_pad = max(0, inner_w - len(opt_str))
                lines.append(("class:dialog.border", f"{margin_sp}│  "))
                lines.append((style, opt_str + (" " * o_pad)))
                lines.append(("class:dialog.border", "  │\n"))

            lines.append(("class:dialog.border", f"{margin_sp}│  {' ' * inner_w}  │\n"))

            # Action Buttons Row (Submit / Skip)
            actions = []
            if is_multiple:
                sub_focused = (focus_target[0] == "submit")
                actions.append(("class:button.active" if sub_focused else "class:button.inactive", " [ Submit ] "))
            if not is_required:
                skip_focused = (focus_target[0] == "skip")
                actions.append(("class:button.active" if skip_focused else "class:button.inactive", " [ Skip ] "))

            if actions:
                lines.append(("class:dialog.border", f"{margin_sp}│  "))
                btn_len = 0
                for style, text in actions:
                    lines.append((style, text))
                    lines.append(("", "  "))
                    btn_len += len(text) + 2
                lines.append(("", " " * max(0, inner_w - btn_len)))
                lines.append(("class:dialog.border", "  │\n"))
                lines.append(("class:dialog.border", f"{margin_sp}│  {' ' * inner_w}  │\n"))

            # Keyboard shortcut hints in footer
            if is_multiple:
                hint = "[ ↑/↓ Move • Space Toggle • Enter Submit • Tab Action • Esc Cancel ]"
            else:
                hint = "[ ↑/↓ Move • Enter Select • Tab Skip • Esc Cancel ]"
            h_text = hint[:inner_w]
            h_pad = max(0, inner_w - len(h_text))
            lines.append(("class:dialog.border", f"{margin_sp}│  "))
            lines.append(("class:hint.desc", h_text + (" " * h_pad)))
            lines.append(("class:dialog.border", "  │\n"))

            # Bottom rounded border: ╰── ──╯
            lines.append(("class:dialog.border", f"{margin_sp}╰{'─' * (box_w - 2)}╯\n"))

            return lines

        if not sys.stdin.isatty():
            return raw_options[0] if raw_options else ""

        control = FormattedTextControl(get_formatted_dialog)
        opts_count = len(raw_options)
        widget_height = min(max(10, opts_count + 10), 24)
        layout = Layout(HSplit([Window(content=control, height=widget_height)]))

        app = Application(
            layout=layout,
            key_bindings=kb,
            style=STYLE,
            full_screen=False,
            mouse_support=False,
        )

        res = await app.run_async()

        # Handle 'Other' with custom text input prompt
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
    def ask_sync(cls, question_data: Union[dict, list, str]) -> Union[str, dict]:
        """Synchronous wrapper for ask_async."""
        return asyncio.run(cls.ask_async(question_data))
