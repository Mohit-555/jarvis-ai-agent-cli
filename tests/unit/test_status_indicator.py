import unittest
from ui.status_indicator import StatusIndicator, StatusState

class TestStatusIndicator(unittest.TestCase):
    def test_all_status_states_render(self):
        ready = StatusIndicator.render(StatusState.READY)
        self.assertIn("Ready", ready.plain)

        thinking = StatusIndicator.render(StatusState.THINKING)
        self.assertIn("Thinking", thinking.plain)

        waiting = StatusIndicator.render(StatusState.WAITING_FOR_USER, "Question 1")
        self.assertIn("Waiting for input", waiting.plain)
        self.assertIn("Question 1", waiting.plain)

        executing = StatusIndicator.render(StatusState.EXECUTING, "web_search")
        self.assertIn("Executing: web_search", executing.plain)

        completed = StatusIndicator.render(StatusState.COMPLETED, duration=1.25)
        self.assertIn("Completed", completed.plain)
        self.assertIn("1.25s", completed.plain)

        error = StatusIndicator.render(StatusState.ERROR, "Network failure")
        self.assertIn("Error: Network failure", error.plain)

if __name__ == "__main__":
    unittest.main()
