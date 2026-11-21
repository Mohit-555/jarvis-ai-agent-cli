import asyncio
import unittest
from pathlib import Path
import sys

jarvis_agent_dir = str(Path(__file__).resolve().parent.parent.parent)
if jarvis_agent_dir not in sys.path:
    sys.path.insert(0, jarvis_agent_dir)

from jarvis_input import JarvisInput, SlashCompleter, COMMANDS
from prompt_toolkit.document import Document
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.menus import CompletionsMenuControl
from prompt_toolkit.buffer import CompletionState
from prompt_toolkit.application import set_app


class TestClickableInput(unittest.TestCase):
    def test_completer_all_commands(self):
        completer = SlashCompleter()
        doc = Document("/")
        completions = list(completer.get_completions(doc, CompleteEvent()))
        self.assertEqual(len(completions), len(COMMANDS))
        cmd_texts = [c.text for c in completions]
        self.assertIn("/tools", cmd_texts)
        self.assertIn("/skills", cmd_texts)
        self.assertIn("/help", cmd_texts)
        self.assertIn("/profile", cmd_texts)
        self.assertIn("/sessions", cmd_texts)

    def test_mouse_click_selection(self):
        async def _run():
            inp = JarvisInput(config={"llm_provider": "gemini", "gemini_model": "gemini-3.5-flash-lite"})
            self.assertTrue(callable(inp._session.mouse_support))
            # Initially no completions -> mouse_support is False so mousepad scrolls terminal
            self.assertFalse(inp._session.mouse_support())

            completer = SlashCompleter()
            doc = Document("/")
            completions = list(completer.get_completions(doc, CompleteEvent()))

            app = inp._session._create_application("› ", "")
            with set_app(app):
                b = app.current_buffer
                b.insert_text("/")
                b.complete_state = CompletionState(original_document=b.document, completions=completions)

                # Click on /tools
                tools_idx = next(i for i, c in enumerate(completions) if c.text == "/tools")
                ctrl = CompletionsMenuControl()
                ev = MouseEvent(position=Point(x=5, y=tools_idx), event_type=MouseEventType.MOUSE_UP, button=MouseButton.LEFT, modifiers=set())
                ctrl.mouse_handler(ev)
                self.assertEqual(b.text, "/tools")

                # Click on /run (requires args -> should append space)
                b.text = "/"
                b.cursor_position = 1
                b.complete_state = CompletionState(original_document=b.document, completions=completions)
                run_idx = next(i for i, c in enumerate(completions) if c.text == "/run")
                ev = MouseEvent(position=Point(x=5, y=run_idx), event_type=MouseEventType.MOUSE_UP, button=MouseButton.LEFT, modifiers=set())
                ctrl.mouse_handler(ev)
                self.assertEqual(b.text, "/run ")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
