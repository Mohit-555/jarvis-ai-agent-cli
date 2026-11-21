import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from tools.code.github_tool import GitHubTool


class TestGitGitHubCapabilities(unittest.TestCase):
    """
    Verification of Tasks 91–105: Git & GitHub Management.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.git = GitHubTool(default_repo_path=str(self.root))

        # Init git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=str(self.root), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(self.root), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.root), capture_output=True)

        # Initial commit
        (self.root / "README.md").write_text("# Project")
        subprocess.run(["git", "add", "."], cwd=str(self.root), capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(self.root), capture_output=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_task_92_git_status(self):
        """Task 92: Check Git status."""
        res = self.git.git_status()
        self.assertIn("Branch: main", res)
        self.assertIn("Working Tree Changes:", res)

    def test_task_94_95_commit_and_log(self):
        """Tasks 94 & 95: Create git commit and view log history."""
        (self.root / "file.txt").write_text("hello")
        res_commit = self.git.git_commit("add file.txt", files="file.txt")
        self.assertIn("Commit successful", res_commit)

        res_log = self.git.git_log(limit=5)
        self.assertIn("initial commit", res_log)
        self.assertIn("add file.txt", res_log)

    def test_task_96_97_branch_management(self):
        """Tasks 96 & 97: Create and switch branches."""
        res_create = self.git.git_branch(action="create", branch_name="feature-test")
        self.assertIn("Created branch", res_create)

        res_checkout = self.git.git_checkout(target="feature-test")
        self.assertIn("Switched to", res_checkout)


if __name__ == "__main__":
    unittest.main()
