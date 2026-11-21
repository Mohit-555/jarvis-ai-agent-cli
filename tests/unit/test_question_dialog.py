import unittest
import asyncio
from unittest.mock import MagicMock, patch

from ui.question_dialog import QuestionDialog
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

    @patch("prompt_toolkit.application.Application.run_async")
    def test_question_dialog_selection(self, mock_run):
        async def _run():
            mock_run.return_value = "Portfolio"
            q = {
                "title": "Website Setup",
                "question": "Choose website type",
                "options": ["E-commerce", "Portfolio", "Blog"],
                "multiple": False
            }
            res = await QuestionDialog.ask_async(q)
            self.assertEqual(res, "Portfolio")

        asyncio.run(_run())

if __name__ == "__main__":
    unittest.main()
