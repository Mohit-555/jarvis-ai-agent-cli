import unittest
from core.event_bus import event_bus, EVENTS

class TestUIEvents(unittest.TestCase):
    def test_structured_events_defined(self):
        self.assertIn("ASK_USER", EVENTS)
        self.assertIn("USER_RESPONSE", EVENTS)
        self.assertIn("TASK_STARTED", EVENTS)
        self.assertIn("TASK_COMPLETED", EVENTS)
        self.assertIn("TASK_ERROR", EVENTS)

    def test_event_emission_and_subscription(self):
        received = []

        def on_ask(**kwargs):
            received.append(kwargs)

        event_bus.on(EVENTS["ASK_USER"], on_ask)
        try:
            event_bus.emit(EVENTS["ASK_USER"], question={"question": "Test question"}, step="1")
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["step"], "1")
        finally:
            event_bus.off(EVENTS["ASK_USER"], on_ask)

    def test_user_response_event(self):
        answers = []

        def on_response(**kwargs):
            answers.append(kwargs)

        event_bus.on(EVENTS["USER_RESPONSE"], on_response)
        try:
            event_bus.emit(EVENTS["USER_RESPONSE"], answer="Portfolio")
            self.assertEqual(len(answers), 1)
            self.assertEqual(answers[0]["answer"], "Portfolio")
        finally:
            event_bus.off(EVENTS["USER_RESPONSE"], on_response)

if __name__ == "__main__":
    unittest.main()
