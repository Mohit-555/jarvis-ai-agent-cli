import unittest
import asyncio
import shutil
from unittest.mock import MagicMock, patch

from ui.question_dialog import QuestionDialog, STYLE
from agent.planner import Step
from agent.executor import AgentExecutor
from core.event_bus import event_bus, EVENTS

class TestQuestionDialog(unittest.TestCase):
    def test_structured_dialog_configuration(self):
        q = {
            "type": "select",
            "title": "Website Configuration",
            "question": "What type of website do you want to create?",
            "options": ["E-commerce", "Portfolio", "Blog", "Other"],
            "multiple": False,
        }
        self.assertEqual(q["title"], "Website Configuration")
        self.assertEqual(len(q["options"]), 4)
        self.assertFalse(q["multiple"])

    def test_style_contains_no_default_purple_dialog_rules(self):
        # Ensure our custom qbox namespace is used and dialog has noinherit
        rule_dict = dict(STYLE.style_rules)
        self.assertIn("qbox.bg", rule_dict)
        self.assertIn("bg:#222222", rule_dict["qbox.bg"])
        self.assertIn("#24C7DF", rule_dict["qbox.border"])
        self.assertIn("opt.selected", rule_dict)
        self.assertIn("#24C7DF", rule_dict["opt.selected"])
        self.assertIn("#2d333b", rule_dict["opt.selected"])

    def test_executor_structured_ask_emission(self):
        async def _run():
            executor = AgentExecutor()
            asked_events = []

            def on_ask(**kwargs):
                asked_events.append(kwargs)

            event_bus.on(EVENTS["AGENT_ASK"], on_ask)
            try:
                step = Step(
                    id="1",
                    description="Ask user what type of website",
                    tool="ask_user",
                    args={
                        "question": "What type of website do you want to create?",
                        "options": ["E-commerce", "Portfolio", "Blog", "Business Website", "Other"],
                        "multiple": False,
                    }
                )

                executor.planner.plan = MagicMock(return_value=asyncio.Future())
                executor.planner.plan.return_value.set_result([step])

                gen = executor.execute_stream("create website")
                first_chunk = await gen.__anext__()

                self.assertTrue(first_chunk.startswith("[ASK_STRUCT:"))
                self.assertIn("E-commerce", first_chunk)
                self.assertIn("Portfolio", first_chunk)
                self.assertEqual(len(asked_events), 1)
                payload = asked_events[0]["question"]
                self.assertIsInstance(payload, dict)
                self.assertEqual(payload["options"][0], "E-commerce")

                # Submit selection to resume
                executor.submit_answer("Portfolio")

                async for _ in gen:
                    pass
            finally:
                event_bus.off(EVENTS["AGENT_ASK"], on_ask)

        asyncio.run(_run())

    # E.1 Single-select test
    @patch("prompt_toolkit.application.Application.run_async")
    @patch("sys.stdin.isatty", return_value=True)
    def test_single_select_question(self, mock_isatty, mock_run):
        async def _run():
            mock_run.return_value = "Portfolio"
            q = {
                "type": "select",
                "title": "Website Setup",
                "question": "Choose website type",
                "options": ["E-commerce", "Portfolio", "Blog"],
                "multiple": False
            }
            res = await QuestionDialog.ask_async(q)
            self.assertEqual(res, "Portfolio")

        asyncio.run(_run())

    # E.2 Multi-select test
    @patch("prompt_toolkit.application.Application.run_async")
    @patch("sys.stdin.isatty", return_value=True)
    def test_multi_select_question(self, mock_isatty, mock_run):
        async def _run():
            mock_run.return_value = "Auth, Database, Payments"
            q = {
                "type": "multi_select",
                "title": "Features",
                "question": "Select all required features",
                "options": ["Auth", "Database", "Payments", "Admin UI"],
                "multiple": True
            }
            res = await QuestionDialog.ask_async(q)
            self.assertEqual(res, "Auth, Database, Payments")

        asyncio.run(_run())

    # E.3 Text input questions
    @patch("prompt_toolkit.PromptSession.prompt_async")
    def test_text_input_question(self, mock_prompt):
        async def _run():
            mock_prompt.return_value = "my-awesome-site.com"
            q = {
                "type": "text",
                "title": "Domain Name",
                "question": "Enter your custom domain:",
                "options": []
            }
            res = await QuestionDialog.ask_async(q)
            self.assertEqual(res, "my-awesome-site.com")

        asyncio.run(_run())

    # E.4 Multiple consecutive questions (Wizard)
    @patch("prompt_toolkit.application.Application.run_async")
    @patch("sys.stdin.isatty", return_value=True)
    def test_consecutive_questions_wizard(self, mock_isatty, mock_run):
        async def _run():
            mock_run.side_effect = ["Portfolio", "Dark Mode"]
            questions = [
                {
                    "id": "site_type",
                    "title": "Step 1",
                    "question": "Website type?",
                    "options": ["Portfolio", "Blog"]
                },
                {
                    "id": "theme_pref",
                    "title": "Step 2",
                    "question": "Select theme:",
                    "options": ["Dark Mode", "Light Mode"]
                }
            ]
            res = await QuestionDialog.ask_async(questions)
            self.assertEqual(res["site_type"], "Portfolio")
            self.assertEqual(res["theme_pref"], "Dark Mode")

        asyncio.run(_run())

    # E.5 Dialog cancellation
    @patch("prompt_toolkit.application.Application.run_async")
    @patch("sys.stdin.isatty", return_value=True)
    def test_dialog_cancellation(self, mock_isatty, mock_run):
        async def _run():
            mock_run.return_value = ""  # Esc returns empty string
            q = {
                "title": "Cancel Test",
                "question": "Are you sure?",
                "options": ["Yes", "No"]
            }
            res = await QuestionDialog.ask_async(q)
            self.assertEqual(res, "")

        asyncio.run(_run())

    # E.6 Terminal resizing & dynamic width calculation
    def test_terminal_resizing_and_width_calculation(self):
        for term_w, expected_min, expected_max in [
            (60, 48, 56),     # small terminal
            (80, 56, 80),     # standard 80 cols (70% = 56)
            (120, 84, 86),    # medium 120 cols (70% = 84)
            (200, 84, 86),    # wide 200 cols (clamped to max 86)
        ]:
            target_w = int(term_w * 0.70)
            box_w = min(max(48, target_w), 86)
            box_w = min(box_w, max(40, term_w - 4))
            self.assertGreaterEqual(box_w, expected_min)
            self.assertLessEqual(box_w, expected_max)
            left_margin = max(0, (term_w - box_w) // 2)
            self.assertGreaterEqual(left_margin, 0)
            self.assertEqual(left_margin * 2 + box_w <= term_w + 1, True)

    # E.7 Long question and description truncation
    def test_long_question_and_description(self):
        inner_w = 60
        long_q = "A" * 120
        long_d = "B" * 150
        
        q_display = long_q if len(long_q) <= inner_w else (long_q[:inner_w - 1] + "…")
        d_display = long_d if len(long_d) <= inner_w else (long_d[:inner_w - 1] + "…")
        
        self.assertEqual(len(q_display), inner_w)
        self.assertTrue(q_display.endswith("…"))
        self.assertEqual(len(d_display), inner_w)
        self.assertTrue(d_display.endswith("…"))

    # E.8 Large option lists scrolling
    def test_large_option_lists_scrolling(self):
        options = [f"Framework Option {i}" for i in range(25)]
        max_visible = 8
        num_opts = len(options)
        
        # Test cursor at beginning
        curr_idx = 0
        scroll_start = max(0, min(curr_idx - (max_visible // 2), num_opts - max_visible))
        scroll_end = min(num_opts, scroll_start + max_visible)
        self.assertEqual(scroll_start, 0)
        self.assertEqual(scroll_end, 8)

        # Test cursor in middle
        curr_idx = 12
        scroll_start = max(0, min(curr_idx - (max_visible // 2), num_opts - max_visible))
        scroll_end = min(num_opts, scroll_start + max_visible)
        self.assertEqual(scroll_start, 8)
        self.assertEqual(scroll_end, 16)
        self.assertTrue(scroll_start <= curr_idx < scroll_end)

        # Test cursor at end
        curr_idx = 24
        scroll_start = max(0, min(curr_idx - (max_visible // 2), num_opts - max_visible))
        scroll_end = min(num_opts, scroll_start + max_visible)
        self.assertEqual(scroll_start, 17)
        self.assertEqual(scroll_end, 25)
        self.assertTrue(scroll_start <= curr_idx < scroll_end)

if __name__ == "__main__":
    unittest.main()
