import unittest
from agent.executor import AgentExecutor
from core.session import Session


class TestGeneralIntelligenceCapabilities(unittest.TestCase):
    """
    Verification of Tasks 1–15: General Intelligence & Conversation.
    """

    def setUp(self):
        self.executor = AgentExecutor()

    def test_task_01_02_self_introduction_and_capabilities(self):
        """Task 1 & 2: Self introduction and capabilities."""
        prompt = self.executor._get_system_prompt()
        self.assertIn("You are Jarvis", prompt)
        self.assertIn("Using your tools", prompt)
        self.assertTrue(self.executor._is_direct_chat("introduce yourself"))
        self.assertTrue(self.executor._is_direct_chat("what can you do?"))

    def test_task_03_06_direct_conversational_queries(self):
        """Tasks 3-6: AI/ML explanations, complex topics, real world examples."""
        self.assertTrue(self.executor._is_direct_chat("what is artificial intelligence"))
        self.assertTrue(self.executor._is_direct_chat("explain machine learning"))
        self.assertTrue(self.executor._is_direct_chat("who are you"))

    def test_task_07_09_multilingual_and_hinglish_preferences(self):
        """Tasks 7-9: Hindi / Hinglish translation & explanations."""
        cfg_hinglish = {"user_language": "Hinglish", "user_name": "Mohit"}
        executor_h = AgentExecutor(config=cfg_hinglish)
        prompt_h = executor_h._get_system_prompt()
        self.assertIn("Hinglish", prompt_h)
        self.assertIn("Mohit", prompt_h)

        cfg_en = {"user_language": "English"}
        executor_en = AgentExecutor(config=cfg_en)
        prompt_en = executor_en._get_system_prompt()
        self.assertIn("English", prompt_en)

    def test_task_10_12_session_context_and_follow_up(self):
        """Tasks 10-12: Multi-turn session context and follow-up without asking to repeat."""
        session = Session(session_id="test-session")
        session.add_message("user", "My favorite programming language is Python.")
        session.add_message("assistant", "Noted, Python is great.")

        msgs = self.executor._build_messages("What is my favorite language?", session)
        self.assertGreater(len(msgs), 2)
        # Context contains previous turns
        self.assertTrue(any("favorite programming language is Python" in m["content"] for m in msgs))


if __name__ == "__main__":
    unittest.main()
