import os
import tempfile
import unittest
from pathlib import Path
from tools.os.file_manager import FileManagerTool


class TestFileManagerSecurity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.fm = FileManagerTool(workspace=str(self.root))

        # Create safe files
        (self.root / "app.py").write_text("print('safe app')")
        (self.root / "data.txt").write_text("safe content")

        # Create sensitive files
        (self.root / ".bashrc").write_text("SECRET_BASHRC_TOKEN=123")
        (self.root / ".env").write_text("PRIVATE_KEY=supersecret")
        (self.root / "whatsapp_profile").mkdir()
        (self.root / "whatsapp_profile" / "Cookies").write_text("session")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_read_blocks_sensitive_files(self):
        """Ensure sensitive files cannot be read."""
        res_env = self.fm.read(str(self.root / ".env"))
        self.assertIn("Access Denied", res_env)

        res_bashrc = self.fm.read(str(self.root / ".bashrc"))
        self.assertIn("Access Denied", res_bashrc)

        # Safe files can be read normally
        res_app = self.fm.read(str(self.root / "app.py"))
        self.assertEqual(res_app, "print('safe app')")

    def test_list_excludes_hidden_and_sensitive_by_default(self):
        """Ensure list() excludes dotfiles and sensitive directories by default."""
        items = self.fm.list(str(self.root))
        names = [item["name"] for item in items]

        self.assertIn("app.py", names)
        self.assertIn("data.txt", names)

        # Sensitive and dotfiles must NOT be listed
        self.assertNotIn(".bashrc", names)
        self.assertNotIn(".env", names)
        self.assertNotIn("whatsapp_profile", names)


if __name__ == "__main__":
    unittest.main()
