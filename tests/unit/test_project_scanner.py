import os
import tempfile
import unittest
from pathlib import Path
from tools.code.project_scanner import ProjectScannerTool, SECURITY_IGNORE_PATTERNS


class TestProjectScannerTool(unittest.TestCase):
    def setUp(self):
        self.scanner = ProjectScannerTool()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Create dummy project files
        (self.root / "main.py").write_text("print('hello')")
        (self.root / "app.py").write_text("import os")
        (self.root / "config.py").write_text("DEBUG = True")
        (self.root / "requirements.txt").write_text("pytest\nrich")
        (self.root / "README.md").write_text("# Test Project")

        # Create src subfolder with python files
        src_dir = self.root / "src"
        src_dir.mkdir()
        (src_dir / "helper.py").write_text("def help(): pass")

        # Create sensitive files that MUST BE IGNORED
        (self.root / ".bashrc").write_text("export SECRET=1")
        (self.root / ".profile").write_text("PATH=$PATH")
        (self.root / ".env").write_text("API_KEY=xyz")
        (self.root / "secret_key.pem").write_text("PRIVATE KEY")
        (self.root / "whatsapp_profile").mkdir()
        (self.root / "whatsapp_profile" / "Cookies").write_text("session")
        (self.root / ".whatsapp_brave_profile").mkdir()
        (self.root / "__pycache__").mkdir()
        (self.root / "__pycache__" / "main.cpython-310.pyc").write_text("bytecode")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_security_ignore_patterns(self):
        """Ensure sensitive and system patterns are identified as ignored."""
        self.assertTrue(self.scanner.is_ignored(".bashrc"))
        self.assertTrue(self.scanner.is_ignored(".profile"))
        self.assertTrue(self.scanner.is_ignored(".env"))
        self.assertTrue(self.scanner.is_ignored(".env.local"))
        self.assertTrue(self.scanner.is_ignored("whatsapp_profile"))
        self.assertTrue(self.scanner.is_ignored(".whatsapp_brave_profile"))
        self.assertTrue(self.scanner.is_ignored("my_brave_profile"))
        self.assertTrue(self.scanner.is_ignored("secret_key.pem"))
        self.assertTrue(self.scanner.is_ignored("__pycache__"))
        self.assertTrue(self.scanner.is_ignored(".git"))

        # Legitimate source files must NOT be ignored
        self.assertFalse(self.scanner.is_ignored("main.py"))
        self.assertFalse(self.scanner.is_ignored("app.py"))
        self.assertFalse(self.scanner.is_ignored("requirements.txt"))
        self.assertFalse(self.scanner.is_ignored("config.py"))

    def test_scan_filters_sensitive_files(self):
        """Ensure scan() output does not expose any sensitive or dotfile data."""
        result = self.scanner.scan(str(self.root))
        self.assertNotIn("error", result)

        tree_str = "\n".join(result["file_tree"])

        # Sensitive files must NOT be present in file tree
        self.assertNotIn(".bashrc", tree_str)
        self.assertNotIn(".profile", tree_str)
        self.assertNotIn(".env", tree_str)
        self.assertNotIn("whatsapp_profile", tree_str)
        self.assertNotIn("secret_key.pem", tree_str)
        self.assertNotIn("__pycache__", tree_str)

        # Legitimate files MUST be present
        self.assertIn("main.py", tree_str)
        self.assertIn("app.py", tree_str)
        self.assertIn("requirements.txt", tree_str)
        self.assertIn("src/", tree_str)

    def test_scan_identifies_entry_points_and_configs(self):
        """Ensure scan() identifies entry points and dependencies."""
        result = self.scanner.scan(str(self.root))

        entry_points = result["entry_points"]
        self.assertIn("main.py", entry_points)
        self.assertIn("app.py", entry_points)

        config_files = result["config_files"]
        self.assertIn("requirements.txt", config_files)
        self.assertIn("config.py", config_files)

        self.assertIn(".py", result["code_files_count"])
        self.assertEqual(result["project_type"], "Python Application")

    def test_jarvis_internal_detection(self):
        """Ensure internal Jarvis path is detected."""
        fake_jarvis_path = Path("/home/test/Desktop/my_project/Jarvis/jarvis_agent")
        self.assertTrue("jarvis_agent" in fake_jarvis_path.parts)


if __name__ == "__main__":
    unittest.main()
