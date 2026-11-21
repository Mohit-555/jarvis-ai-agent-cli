"""
ui/question_dialog.py  —  Modern OpenCode CLI-style Centered Interactive Question Dialog

Features:
  • Self-contained component floating over terminal background
  • Dark charcoal background (#222222) with thin cyan border (#24C7DF)
  • Purple (#a855f7) secondary accent for selection arrows & badges
  • Horizontally centered, dynamic width (65–75% of terminal width, clamped 48–86 cols)
  • Dynamic height according to options count, with automatic viewport scrolling for large lists
  • Selected option: highlighted dark background (#2d333b) + bold bright cyan text (#24C7DF)
  • Normal option: light gray (#d4d4d8) on dark charcoal
  • Multi-select with checkmarks ([x] / [ ]), Single-select radio (◉ / ○), Yes/No confirm
  • Instant search filtering on keystroke, inline 'Other' text input
  • Smooth keyboard navigation: ↑/↓, Enter submit, Tab switch actions, Esc cancel
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

# OpenCode-inspired Dark Charcoal (#222222) & Cyan (#24C7DF) with Purple (#a855f7) Accents
STYLE = Style.from_dict({
    # Reset prompt_toolkit built-in dialog background
    "dialog": "noinherit",
    "dialog.body": "noinherit",

    # Base question box & borders
    "qbox.bg": "bg:#222222",
    "qbox.border": "#24C7DF bg:#222222",
    "qbox.title": "#24C7DF bold bg:#222222",
    "qbox.progress": "#9ca3af bg:#222222",
    "qbox.optional": "#eab308 italic bg:#222222",
    "qbox.question": "#ffffff bold bg:#222222",
    "qbox.description": "#9ca3af bg:#222222",
    "qbox.search": "#38bdf8 italic bg:#222222",
    "qbox.scroll": "#6b7280 italic bg:#222222",

    # Normal options (light gray on dark charcoal)
    "opt.normal": "#d4d4d8 bg:#222222",
    "opt.normal.indicator": "#71717a bg:#222222",
    "opt.normal.icon": "#71717a bg:#222222",

    # Selected option (highlighted dark background + bold bright cyan text)
    "opt.selected": "#24C7DF bold bg:#2d333b",
    "opt.selected.indicator": "#a855f7 bold bg:#2d333b",
    "opt.selected.icon": "#24C7DF bold bg:#2d333b",

    # Checked items in multi-select
    "opt.checked": "#10b981 bold bg:#222222",
    "opt.checked.selected": "#10b981 bold bg:#2d333b",

    # Keyboard shortcut hints in footer
    "hint.text": "#71717a bg:#222222",
    "hint.accent": "#24C7DF bg:#222222",

    # Action buttons (Submit / Skip)
    "btn.active": "reverse #24C7DF bold",
    "btn.inactive": "#71717a bg:#222222",
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

        # Headless fallback
        if not sys.stdin.isatty():
            return raw_options[0] if raw_options else ""

        # State tracking
        search_query = [""]
        highlight_idx = [0]
        checked_indices = set()
        user_result = [""]
        focus_target = ["options"]  # "options", "submit", "skip"

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
            term_size = shutil.get_terminal_size((80, 24))
            term_w = term_size.columns
            term_h = term_size.lines

            # Dynamic width: 65% - 75% of terminal width, clamped between 48 and 86
            target_w = int(term_w * 0.70)
            box_w = min(max(48, target_w), 86)
            box_w = min(box_w, max(40, term_w - 4))
            inner_w = box_w - 4

            # Left margin spaces without any background style (transparent terminal bg)
            left_margin = max(0, (term_w - box_w) // 2)
            margin_sp = " " * left_margin

            lines = []

            def append_row(segments, row_bg="class:qbox.bg"):
                """Helper to append a perfectly aligned row inside the dark charcoal box."""
                # Calculate total character width of segments
                seg_len = sum(len(text) for _, text in segments)
                pad_len = max(0, inner_w - seg_len)
                
                # Margin outside the box has NO style (transparent terminal)
                lines.append(("", margin_sp))
                # Left border
                lines.append(("class:qbox.border", "│ "))
                # Content
                for style, text in segments:
                    lines.append((style, text))
                # Inner padding fills up the rest of the dark charcoal row
                if pad_len > 0:
                    lines.append((row_bg, " " * pad_len))
                # Right border
                lines.append(("class:qbox.border", " │\n"))

            # 1. Top rounded border: ╭─ Title ─╮
            clean_title = title.strip()
            title_prefix = f"╭─ {clean_title} "
            if len(title_prefix) > box_w - 4:
                title_prefix = title_prefix[:box_w - 6] + "… "
            dash_len = max(2, box_w - len(title_prefix) - 1)
            lines.append(("", margin_sp))
            lines.append(("class:qbox.border", f"{title_prefix}{'─' * dash_len}╮\n"))

            # 2. Progress & Optional badge line
            prog_text = progress.strip() if progress else ""
            opt_badge = "[Optional]" if not is_required else ""
            if prog_text or opt_badge:
                badge_row = []
                if prog_text:
                    badge_row.append(("class:qbox.progress", prog_text))
                if prog_text and opt_badge:
                    gap = max(1, inner_w - len(prog_text) - len(opt_badge))
                    badge_row.append(("class:qbox.bg", " " * gap))
                if opt_badge:
                    badge_row.append(("class:qbox.optional", opt_badge))
                append_row(badge_row)

            # 3. Question Text (with ellipsis if exceeding inner_w)
            q_display = question.strip()
            if len(q_display) > inner_w:
                q_display = q_display[:inner_w - 1] + "…"
            append_row([("class:qbox.question", q_display)])

            # 4. Description (if provided)
            if description.strip():
                d_display = description.strip()
                if len(d_display) > inner_w:
                    d_display = d_display[:inner_w - 1] + "…"
                append_row([("class:qbox.description", d_display)])

            # 5. Search indicator (if user typed filter)
            if search_query[0]:
                search_str = f"Filter: '{search_query[0]}'"
                if len(search_str) > inner_w:
                    search_str = search_str[:inner_w - 1] + "…"
                append_row([("class:qbox.search", search_str)])

            # Blank separator
            append_row([])

            # 6. Render options with viewport scroll window
            opts = get_filtered_options()
            num_opts = len(opts)
            
            # Viewport windowing: compute max visible options so it fits gracefully
            max_visible = min(8, max(3, term_h - 13))
            curr_idx = highlight_idx[0]
            if curr_idx >= num_opts:
                curr_idx = max(0, num_opts - 1)
                highlight_idx[0] = curr_idx

            # Calculate scroll start
            scroll_start = 0
            if num_opts > max_visible:
                scroll_start = max(0, min(curr_idx - (max_visible // 2), num_opts - max_visible))
            scroll_end = min(num_opts, scroll_start + max_visible)

            # Top scroll indicator
            if scroll_start > 0:
                append_row([("class:qbox.scroll", f"  ▲ ... {scroll_start} more above")])

            if not opts:
                append_row([("class:qbox.progress", "  (No options match your filter)")])
            else:
                for i in range(scroll_start, scroll_end):
                    opt = opts[i]
                    is_cursor = (i == curr_idx and focus_target[0] == "options")
                    is_checked = (opt in checked_indices)

                    # Truncate option text to fit cleanly inside box
                    # Reserve 6 chars for indicator and radio/checkbox
                    avail_text = inner_w - 7
                    opt_display = opt if len(opt) <= avail_text else (opt[:avail_text - 1] + "…")

                    row_segments = []
                    if is_cursor:
                        row_bg = "class:opt.selected"
                        # Secondary purple accent arrow indicator
                        row_segments.append(("class:opt.selected.indicator", "❯ "))
                        if is_confirm:
                            row_segments.append(("class:opt.selected.icon", "◉ "))
                        elif is_multiple:
                            chk_icon = "[x] " if is_checked else "[ ] "
                            row_segments.append(("class:opt.checked.selected" if is_checked else "class:opt.selected.icon", chk_icon))
                        else:
                            row_segments.append(("class:opt.selected.icon", "◉ "))
                        row_segments.append(("class:opt.selected", opt_display))
                    else:
                        row_bg = "class:qbox.bg"
                        row_segments.append(("class:opt.normal.indicator", "  "))
                        if is_confirm:
                            row_segments.append(("class:opt.normal.icon", "○ "))
                            row_segments.append(("class:opt.normal", opt_display))
                        elif is_multiple:
                            chk_icon = "[x] " if is_checked else "[ ] "
                            chk_style = "class:opt.checked" if is_checked else "class:opt.normal.icon"
                            row_segments.append((chk_style, chk_icon))
                            row_segments.append(("class:opt.normal", opt_display))
                        else:
                            row_segments.append(("class:opt.normal.icon", "○ "))
                            row_segments.append(("class:opt.normal", opt_display))

                    append_row(row_segments, row_bg=row_bg)

            # Bottom scroll indicator
            if scroll_end < num_opts:
                append_row([("class:qbox.scroll", f"  ▼ ... {num_opts - scroll_end} more below")])

            # Blank separator
            append_row([])

            # 7. Action buttons row (Submit / Skip)
            actions = []
            if is_multiple:
                sub_focused = (focus_target[0] == "submit")
                actions.append(("class:btn.active" if sub_focused else "class:btn.inactive", " [ Submit ] "))
            if not is_required:
                skip_focused = (focus_target[0] == "skip")
                actions.append(("class:btn.active" if skip_focused else "class:btn.inactive", " [ Skip ] "))

            if actions:
                btn_row = []
                for style, text in actions:
                    btn_row.append((style, text))
                    btn_row.append(("class:qbox.bg", "  "))
                append_row(btn_row)
                append_row([])

            # 8. Keyboard shortcut hints in footer
            if is_multiple:
                hint = "[ ↑/↓ Move • Space Toggle • Enter Submit • Tab Action • Esc Cancel ]"
            else:
                hint = "[ ↑/↓ Move • Enter Select • Tab Skip • Esc Cancel ]"
            if len(hint) > inner_w:
                hint = hint[:inner_w - 3] + "…]"
            append_row([("class:hint.text", hint)])

            # 9. Bottom rounded border: ╰── ──╯
            lines.append(("", margin_sp))
            lines.append(("class:qbox.border", f"╰{'─' * (box_w - 2)}╯\n"))

            return lines

        control = FormattedTextControl(get_formatted_dialog)
        
        # Calculate dynamic window height based on raw options count
        term_h = shutil.get_terminal_size((80, 24)).lines
        calc_h = min(len(raw_options) + 10, 22)
        widget_height = min(max(9, calc_h), max(10, term_h - 4))
        
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
