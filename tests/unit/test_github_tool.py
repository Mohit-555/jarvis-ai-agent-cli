import os
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

import sys
jarvis_agent_dir = str(Path(__file__).resolve().parent.parent.parent)
if jarvis_agent_dir not in sys.path:
    sys.path.insert(0, jarvis_agent_dir)

from tools.code.github_tool import GitHubTool
from tools.registry import ToolRegistry
from agent.executor import AgentExecutor


class TestGitHubTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Initialize a real git repo in the temp dir
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, capture_output=True, check=True)
        self.tool = GitHubTool(default_repo_path=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_git_status_and_commit_flow(self):
        # 1. Initial status
        status = self.tool.git_status()
        self.assertIn("Repository:", status)
        self.assertIn("Working Tree Changes:", status)

        # 2. Create a test file
        test_file = os.path.join(self.test_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("hello git\n")

        # 3. Check diff notices untracked or staged file
        diff_initial = self.tool.git_diff()
        self.assertIn("test.txt", diff_initial)

        # 4. Commit
        commit_res = self.tool.git_commit(message="Initial test commit")
        self.assertIn("Commit successful", commit_res)

        # 5. Modify tracked file and check unstaged diff
        with open(test_file, "a") as f:
            f.write("second line\n")
        diff_modified = self.tool.git_diff()
        self.assertIn("second line", diff_modified)

        # 6. Check log
        log_res = self.tool.git_log(limit=5)
        self.assertIn("Initial test commit", log_res)

    def test_git_branch_operations(self):
        # Create initial commit first
        with open(os.path.join(self.test_dir, "file.txt"), "w") as f:
            f.write("test")
        self.tool.git_commit("First commit")

        # Create branch
        create_res = self.tool.git_branch(action="create", branch_name="feature-test")
        self.assertIn("Created branch 'feature-test'", create_res)

        # List branches
        list_res = self.tool.git_branch(action="list")
        self.assertIn("feature-test", list_res)

        # Switch branch
        switch_res = self.tool.git_checkout(target="feature-test")
        self.assertIn("successful", switch_res.lower())

    def test_git_stash_operations(self):
        # Create initial commit
        with open(os.path.join(self.test_dir, "stash_file.txt"), "w") as f:
            f.write("initial\n")
        self.tool.git_commit("Commit before stash")

        # Modify file
        with open(os.path.join(self.test_dir, "stash_file.txt"), "a") as f:
            f.write("work in progress\n")

        # Stash changes
        stash_res = self.tool.git_stash(action="push", message="WIP changes")
        self.assertTrue("Saved working directory" in stash_res or "completed" in stash_res.lower())

        # Pop stash
        pop_res = self.tool.git_stash(action="pop")
        self.assertTrue("Dropped refs/stash" in pop_res or "Applied" in pop_res or "completed" in pop_res.lower())

    def test_git_run(self):
        res = self.tool.git_run("rev-parse --is-inside-work-tree")
        self.assertEqual(res.strip(), "true")

    def test_direct_chat_routing(self):
        executor = AgentExecutor()
        self.assertTrue(executor._is_direct_chat("hii"))
        self.assertTrue(executor._is_direct_chat("hello jarvis"))
        self.assertFalse(executor._is_direct_chat("git status"))
        self.assertFalse(executor._is_direct_chat("push to github"))
        self.assertFalse(executor._is_direct_chat("commit changes with message fix bug"))
        self.assertFalse(executor._is_direct_chat("create pr for feature"))
        self.assertFalse(executor._is_direct_chat("check git repo status"))


class TestDaemonRegistration(unittest.TestCase):
    def test_daemon_registers_git_tools(self):
        from daemon import Daemon
        d = Daemon()
        registry = ToolRegistry()
        d._register_all_tools(registry)

        registered_names = [t["name"] for t in registry.list_tools()]
        expected_tools = [
            "git_status",
            "git_diff",
            "git_log",
            "git_commit",
            "git_push",
            "git_pull",
            "git_branch",
            "git_checkout",
            "git_stash",
            "git_clone",
            "git_run",
            "github_create_pr",
            "github_list_prs",
            "github_view_pr",
            "github_merge_pr",
            "github_create_issue",
            "github_list_issues",
            "github_view_issue",
            "github_close_issue",
            "github_repo_view",
            "github_run",
        ]
        for name in expected_tools:
            self.assertIn(name, registered_names, f"Tool '{name}' was not registered in daemon")


if __name__ == "__main__":
    unittest.main()
