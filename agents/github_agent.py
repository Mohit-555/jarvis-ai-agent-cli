import os
import subprocess
from agents.base import BaseAgent

SYSTEM_PROMPT = """You are a GitHub assistant. Help the user manage git repositories,
create commits, push code, manage PRs and issues. Always explain what you're doing before running commands."""


class GitHubAgent(BaseAgent):
    name = "github"
    description = "Git operations, commits, pushes, PRs, issues"

    def get_system_prompt(self):
        return SYSTEM_PROMPT

    def get_tool_defs(self):
        return {
            "git_run": ("Run any git command", ["args", "repo_path (optional)"]),
            "get_status": ("Get current git status and branch info", ["repo_path (optional)"]),
            "clone_repo": ("Clone a git repository", ["url", "directory (optional)"]),
            "push_code": ("Stage all, commit, and push in one step", ["commit_message", "repo_path (optional)", "branch (optional)"]),
            "create_pr": ("Create a GitHub PR", ["title", "body", "repo_path (optional)"]),
            "list_prs": ("List open PRs", ["repo_path (optional)"]),
            "list_issues": ("List open issues", ["repo_path (optional)"]),
        }

    def _git(self, args, repo_path=None):
        cwd = repo_path or os.getcwd()
        try:
            r = subprocess.run(f"git {args}", shell=True, capture_output=True, text=True, timeout=30, cwd=cwd)
            return (r.stdout or r.stderr).strip()[:3000]
        except subprocess.TimeoutExpired:
            return "Timed out"
        except Exception as e:
            return f"Error: {e}"

    def _gh(self, args, repo_path=None):
        cwd = repo_path or os.getcwd()
        try:
            r = subprocess.run(f"gh {args}", shell=True, capture_output=True, text=True, timeout=30, cwd=cwd)
            return (r.stdout or r.stderr).strip()[:3000]
        except Exception as e:
            return f"gh error: {e}"

    def tool_git_run(self, args):
        return self._git(args["args"], args.get("repo_path"))

    def tool_get_status(self, args):
        p = args.get("repo_path", os.getcwd())
        branch = self._git("branch --show-current", p)
        status = self._git("status --short", p)
        log = self._git("log --oneline -5", p)
        return f"Branch: {branch}\nStatus:\n{status}\nRecent:\n{log}"

    def tool_clone_repo(self, args):
        url = args["url"]
        directory = args.get("directory", "")
        return self._git(f"clone {url} {directory}".strip())

    def tool_push_code(self, args):
        p = args.get("repo_path")
        msg = args["commit_message"]
        branch = args.get("branch", "")
        self._git("add .", p)
        self._git(f'commit -m "{msg}"', p)
        push = f"push origin {branch}" if branch else "push"
        return self._git(push, p)

    def tool_create_pr(self, args):
        path = args.get("repo_path")
        title = args["title"]
        body = args.get("body", "")
        return self._gh(f'pr create --title "{title}" --body "{body}"', path)

    def tool_list_prs(self, args):
        return self._gh("pr list --state open", args.get("repo_path"))

    def tool_list_issues(self, args):
        return self._gh("issue list --state open", args.get("repo_path"))
