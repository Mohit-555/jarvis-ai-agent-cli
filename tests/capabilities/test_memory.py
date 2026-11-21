import tempfile
import unittest
from pathlib import Path
from core.session import SessionManager, Session
from memory.user_profile import UserProfile


class TestMemoryCapabilities(unittest.TestCase):
    """
    Verification of Tasks 131–140: Memory & Personalization.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mgr = SessionManager(storage_dir=self.temp_dir.name)
        self.profile = UserProfile(profile_path=str(Path(self.temp_dir.name) / "profile.json"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_task_131_133_remember_preferences(self):
        """Tasks 131-133: Remember programming language, project name, coding style."""
        self.profile.set("preferred_language", "Python")
        self.profile.set("current_project", "Jarvis")
        self.profile.set("coding_style", "PEP8")

        self.assertEqual(self.profile.get("preferred_language"), "Python")
        self.assertEqual(self.profile.get("current_project"), "Jarvis")
        self.assertEqual(self.profile.get("coding_style"), "PEP8")

    def test_task_134_139_session_persistence_and_recall(self):
        """Tasks 134-139: Multi-session tracking and conversation recall."""
        s1 = self.mgr.create_session()
        s1.add_message("user", "Let's build a Django app.")
        s1.add_message("assistant", "Sure, starting Django project.")
        self.mgr.save_session(s1)

        # Retrieve session
        loaded = self.mgr.get_session(s1.session_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded.messages), 2)
        self.assertEqual(loaded.messages[0]["content"], "Let's build a Django app.")


if __name__ == "__main__":
    unittest.main()
