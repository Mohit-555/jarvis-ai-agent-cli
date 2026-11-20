"""GitHub and Git operations tool for Jarvis.

Provides comprehensive support for local Git operations (status, diff, log, commit,
push, pull, branch, checkout, stash, clone) and GitHub operations via GitHub CLI (`gh`)
(pull requests, issues, repo details, cloning).
"""

import os
import re
import shlex
import shutil
import subprocess
from typing import Optional, Union


def _find_git_root(start_path: Optional[str] = None) -> str:
    """Find the root of a git repository, starting from start_path or cwd."""
    p = os.path.abspath(os.path.expanduser(start_path)) if start_path else os.getcwd()
    # Check if p or any parent is inside a git repo
    curr = p
    while curr and curr != os.path.dirname(curr):
        if os.path.isdir(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)

    # If not found looking upward, check direct subdirectories (e.g. jarvis_agent)
    try:
        for entry in os.scandir(p):
            if entry.is_dir() and os.path.isdir(os.path.join(entry.path, ".git")):
                return entry.path
    except Exception:
        pass

    return p


class GitHubTool:
    """Unified tool for local Git operations and remote GitHub CLI interactions."""

    def __init__(self, default_repo_path: Optional[str] = None):
        self.default_repo_path = default_repo_path

    def _resolve_repo(self, repo_path: Optional[str] = None) -> str:
        target = repo_path or self.default_repo_path
        return _find_git_root(target)

    def _run_git(
        self,
        args: Union[list[str], str],
        repo_path: Optional[str] = None,
        timeout: int = 60,
    ) -> tuple[int, str, str]:
        cwd = self._resolve_repo(repo_path)
        if isinstance(args, str):
            cmd = f"git {args}"
            shell = True
        else:
            cmd = ["git"] + list(args)
            shell = False

        try:
            r = subprocess.run(
                cmd,
                shell=shell,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", f"Git command timed out after {timeout}s."
        except Exception as e:
            return -1, "", f"Failed to execute git command: {e}"

    def _run_gh(
        self,
        args: Union[list[str], str],
        repo_path: Optional[str] = None,
        timeout: int = 60,
    ) -> tuple[int, str, str]:
        if not shutil.which("gh"):
            return -1, "", (
                "GitHub CLI ('gh') is not installed on this system. "
                "Install it using 'sudo apt install gh' or visit https://cli.github.com."
            )

        cwd = self._resolve_repo(repo_path)
        if isinstance(args, str):
            cmd = f"gh {args}"
            shell = True
        else:
            cmd = ["gh"] + list(args)
            shell = False

        try:
            r = subprocess.run(
                cmd,
                shell=shell,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = r.stdout.strip()
            stderr = r.stderr.strip()

            if "To log in, run: gh auth login" in stderr or "You are not logged into" in stderr:
                return r.returncode, stdout, (
                    "GitHub CLI is not authenticated. Please run 'gh auth login' "
                    "in your terminal to connect your GitHub account."
                )
            return r.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"GitHub CLI command timed out after {timeout}s."
        except Exception as e:
            return -1, "", f"Failed to execute gh command: {e}"

    # ---------------- Local Git Operations ---------------- #

    def git_status(self, repo_path: Optional[str] = None) -> str:
        """Get current git repository status: active branch, changes, and sync with remote."""
        cwd = self._resolve_repo(repo_path)
        code, branch, _ = self._run_git(["branch", "--show-current"], cwd)
        if code != 0:
            return f"Not a git repository (or git error): {cwd}"

        code, short_status, _ = self._run_git(["status", "--short"], cwd)
        code, branch_status, _ = self._run_git(["status", "-sb"], cwd)
        code, recent_log, _ = self._run_git(["log", "-n", "3", "--oneline"], cwd)

        lines = [
            f"Repository: {cwd}",
            f"Branch: {branch or '(detached HEAD)'}",
            f"Status overview: {branch_status.splitlines()[0] if branch_status else ''}",
            "",
            "Working Tree Changes:",
            short_status if short_status else "(working tree clean)",
            "",
            "Recent Commits:",
            recent_log if recent_log else "(no commits yet)",
        ]
        return "\n".join(lines).strip()

    def git_diff(
        self,
        cached: bool = False,
        file_path: Optional[str] = None,
        repo_path: Optional[str] = None,
    ) -> str:
        """Show diff of unstaged or staged changes."""
        cwd = self._resolve_repo(repo_path)
        args = ["diff"]
        if cached:
            args.append("--staged")
        if file_path:
            args.extend(["--", file_path])

        code, out, err = self._run_git(args, cwd)
        if code != 0:
            return f"Git diff error: {err}"
        if not out:
            _, untracked, _ = self._run_git(["ls-files", "--others", "--exclude-standard"], cwd)
            msg = "No changes detected (" + ("staged" if cached else "unstaged") + ")."
            if untracked:
                untracked_list = ", ".join(untracked.splitlines()[:5])
                msg += f"\nUntracked files present: {untracked_list}"
            return msg
        # Truncate if diff is huge
        if len(out) > 5000:
            return out[:5000] + f"\n\n... [diff truncated, total {len(out)} characters]"
        return out

    def git_log(
        self,
        limit: int = 10,
        oneline: bool = False,
        repo_path: Optional[str] = None,
    ) -> str:
        """View recent git commit history."""
        args = ["log", f"-n{max(1, limit)}"]
        if oneline:
            args.append("--oneline")
        else:
            args.extend(["--pretty=format:%h - %an (%cr): %s"])

        code, out, err = self._run_git(args, repo_path)
        if code != 0:
            return f"Git log error: {err}"
        return out or "No commit history found."

    def git_commit(
        self,
        message: str,
        files: Optional[Union[list[str], str]] = None,
        add_all: bool = True,
        repo_path: Optional[str] = None,
    ) -> str:
        """Stage files and create a git commit."""
        cwd = self._resolve_repo(repo_path)
        if not message or not message.strip():
            return "Error: Commit message cannot be empty."

        # Stage files
        if files:
            if isinstance(files, str):
                file_list = [f.strip() for f in files.split() if f.strip()]
            else:
                file_list = list(files)
            code, out, err = self._run_git(["add"] + file_list, cwd)
            if code != 0:
                return f"Git add error: {err or out}"
        elif add_all:
            code, out, err = self._run_git(["add", "-A"], cwd)
            if code != 0:
                return f"Git add error: {err or out}"

        # Commit
        code, out, err = self._run_git(["commit", "-m", message.strip()], cwd)
        if code != 0:
            if "nothing to commit" in (out + err):
                return "Nothing to commit, working tree clean."
            return f"Git commit error: {err or out}"
        return f"Commit successful:\n{out}"

    def git_push(
        self,
        branch: Optional[str] = None,
        remote: str = "origin",
        set_upstream: bool = False,
        repo_path: Optional[str] = None,
    ) -> str:
        """Push committed changes to remote repository."""
        cwd = self._resolve_repo(repo_path)
        args = ["push"]
        if set_upstream:
            args.append("-u")
        if remote:
            args.append(remote)
        if branch:
            args.append(branch)

        code, out, err = self._run_git(args, cwd, timeout=90)
        output = (out + "\n" + err).strip()
        if code != 0:
            return f"Git push failed:\n{output}"
        return f"Git push succeeded:\n{output}"

    def git_pull(
        self,
        branch: Optional[str] = None,
        remote: str = "origin",
        rebase: bool = False,
        repo_path: Optional[str] = None,
    ) -> str:
        """Pull latest changes from remote repository."""
        cwd = self._resolve_repo(repo_path)
        args = ["pull"]
        if rebase:
            args.append("--rebase")
        if remote:
            args.append(remote)
        if branch:
            args.append(branch)

        code, out, err = self._run_git(args, cwd, timeout=90)
        output = (out + "\n" + err).strip()
        if code != 0:
            return f"Git pull failed:\n{output}"
        return f"Git pull succeeded:\n{output}"

    def git_branch(
        self,
        action: str = "list",
        branch_name: Optional[str] = None,
        repo_path: Optional[str] = None,
    ) -> str:
        """Manage git branches (list, create, delete, switch)."""
        cwd = self._resolve_repo(repo_path)
        action = (action or "list").lower().strip()

        if action == "list":
            code, out, err = self._run_git(["branch", "-a"], cwd)
            return out if code == 0 else f"Error listing branches: {err}"

        if not branch_name:
            return f"Error: branch_name required for action '{action}'"

        if action == "create":
            code, out, err = self._run_git(["branch", branch_name], cwd)
            return f"Created branch '{branch_name}'" if code == 0 else f"Error creating branch: {err or out}"

        if action in ("delete", "remove"):
            code, out, err = self._run_git(["branch", "-d", branch_name], cwd)
            return f"Deleted branch '{branch_name}'" if code == 0 else f"Error deleting branch: {err or out}"

        if action in ("switch", "checkout"):
            code, out, err = self._run_git(["checkout", branch_name], cwd)
            return f"Switched to branch '{branch_name}'" if code == 0 else f"Error switching branch: {err or out}"

        return f"Unknown branch action: {action}. Use 'list', 'create', 'delete', or 'switch'."

    def git_checkout(
        self,
        target: str,
        create: bool = False,
        repo_path: Optional[str] = None,
    ) -> str:
        """Checkout a branch, commit, or file (creates branch if create=True)."""
        cwd = self._resolve_repo(repo_path)
        args = ["checkout"]
        if create:
            args.extend(["-b", target])
        else:
            args.append(target)

        code, out, err = self._run_git(args, cwd)
        output = (out + "\n" + err).strip()
        if code != 0:
            return f"Git checkout error:\n{output}"
        return f"Git checkout successful:\n{output}"

    def git_stash(
        self,
        action: str = "push",
        message: Optional[str] = None,
        repo_path: Optional[str] = None,
    ) -> str:
        """Stash uncommitted changes (push, pop, list, drop)."""
        cwd = self._resolve_repo(repo_path)
        act = (action or "push").lower().strip()
        args = ["stash", act]
        if act == "push" and message:
            args.extend(["-m", message])

        code, out, err = self._run_git(args, cwd)
        output = (out + "\n" + err).strip()
        if code != 0:
            return f"Git stash error:\n{output}"
        return output or f"Stash {act} completed."

    def git_clone(self, url: str, directory: Optional[str] = None) -> str:
        """Clone a git repository to a local directory."""
        if not url or not url.strip():
            return "Error: Repository URL cannot be empty."

        args = ["clone", url.strip()]
        if directory:
            args.append(directory.strip())

        code, out, err = self._run_git(args, repo_path=os.getcwd(), timeout=180)
        output = (out + "\n" + err).strip()
        if code != 0:
            return f"Git clone failed:\n{output}"
        return f"Git clone succeeded:\n{output}"

    def git_run(self, command: str, repo_path: Optional[str] = None) -> str:
        """Run an arbitrary git command."""
        clean_cmd = command.strip()
        if clean_cmd.startswith("git "):
            clean_cmd = clean_cmd[4:].strip()

        code, out, err = self._run_git(clean_cmd, repo_path=repo_path)
        output = (out + "\n" + err).strip()
        return output or f"Command 'git {clean_cmd}' executed successfully with no output."

    # ---------------- GitHub CLI (gh) Operations ---------------- #

    def github_create_pr(
        self,
        title: str,
        body: str = "",
        base: Optional[str] = None,
        head: Optional[str] = None,
        draft: bool = False,
        repo_path: Optional[str] = None,
    ) -> str:
        """Create a pull request on GitHub."""
        args = ["pr", "create", "--title", title, "--body", body or ""]
        if base:
            args.extend(["--base", base])
        if head:
            args.extend(["--head", head])
        if draft:
            args.append("--draft")

        code, out, err = self._run_gh(args, repo_path)
        if code != 0:
            return f"Failed to create PR:\n{err or out}"
        return f"Pull Request created successfully:\n{out}"

    def github_list_prs(
        self,
        state: str = "open",
        limit: int = 10,
        repo_path: Optional[str] = None,
    ) -> str:
        """List pull requests in the repository (open, closed, merged, all)."""
        args = ["pr", "list", "--state", state or "open", "--limit", str(max(1, limit))]
        code, out, err = self._run_gh(args, repo_path)
        if code != 0:
            return f"Failed to list PRs:\n{err or out}"
        return out or f"No {state} pull requests found."

    def github_view_pr(
        self,
        pr_number: Union[int, str],
        repo_path: Optional[str] = None,
    ) -> str:
        """View details and comments for a pull request."""
        args = ["pr", "view", str(pr_number), "--comments"]
        code, out, err = self._run_gh(args, repo_path)
        if code != 0:
            return f"Failed to view PR #{pr_number}:\n{err or out}"
        return out

    def github_merge_pr(
        self,
        pr_number: Union[int, str],
        merge_method: str = "merge",
        delete_branch: bool = False,
        repo_path: Optional[str] = None,
    ) -> str:
        """Merge a pull request (merge, squash, rebase)."""
        method_flag = f"--{merge_method}" if merge_method in ("merge", "squash", "rebase") else "--merge"
        args = ["pr", "merge", str(pr_number), method_flag]
        if delete_branch:
            args.append("--delete-branch")

        code, out, err = self._run_gh(args, repo_path)
        if code != 0:
            return f"Failed to merge PR #{pr_number}:\n{err or out}"
        return f"Pull Request #{pr_number} merged successfully:\n{out}"

    def github_create_issue(
        self,
        title: str,
        body: str = "",
        labels: Optional[Union[str, list[str]]] = None,
        assignees: Optional[Union[str, list[str]]] = None,
        repo_path: Optional[str] = None,
    ) -> str:
        """Create a GitHub issue."""
        args = ["issue", "create", "--title", title, "--body", body or ""]
        if labels:
            lbl_str = ",".join(labels) if isinstance(labels, list) else labels
            args.extend(["--label", lbl_str])
        if assignees:
            ass_str = ",".join(assignees) if isinstance(assignees, list) else assignees
            args.extend(["--assignee", ass_str])

        code, out, err = self._run_gh(args, repo_path)
        if code != 0:
            return f"Failed to create issue:\n{err or out}"
        return f"Issue created successfully:\n{out}"

    def github_list_issues(
        self,
        state: str = "open",
        limit: int = 10,
        repo_path: Optional[str] = None,
    ) -> str:
        """List issues in the repository."""
        args = ["issue", "list", "--state", state or "open", "--limit", str(max(1, limit))]
        code, out, err = self._run_gh(args, repo_path)
        if code != 0:
            return f"Failed to list issues:\n{err or out}"
        return out or f"No {state} issues found."

    def github_view_issue(
        self,
        issue_number: Union[int, str],
        repo_path: Optional[str] = None,
    ) -> str:
        """View details of a GitHub issue."""
        args = ["issue", "view", str(issue_number), "--comments"]
        code, out, err = self._run_gh(args, repo_path)
        if code != 0:
            return f"Failed to view issue #{issue_number}:\n{err or out}"
        return out

    def github_close_issue(
        self,
        issue_number: Union[int, str],
        comment: Optional[str] = None,
        repo_path: Optional[str] = None,
    ) -> str:
        """Close an issue."""
        args = ["issue", "close", str(issue_number)]
        if comment:
            args.extend(["--comment", comment])

        code, out, err = self._run_gh(args, repo_path)
        if code != 0:
            return f"Failed to close issue #{issue_number}:\n{err or out}"
        return f"Issue #{issue_number} closed successfully:\n{out}"

    def github_repo_view(
        self,
        repo: Optional[str] = None,
        repo_path: Optional[str] = None,
    ) -> str:
        """View information about a repository (description, README, URL, stars)."""
        args = ["repo", "view"]
        if repo:
            args.append(repo)

        code, out, err = self._run_gh(args, repo_path)
        if code != 0:
            return f"Failed to view repository:\n{err or out}"
        return out

    def github_run(self, command: str, repo_path: Optional[str] = None) -> str:
        """Run an arbitrary GitHub CLI ('gh') command."""
        clean_cmd = command.strip()
        if clean_cmd.startswith("gh "):
            clean_cmd = clean_cmd[3:].strip()

        code, out, err = self._run_gh(clean_cmd, repo_path=repo_path)
        output = (out + "\n" + err).strip()
        return output or f"Command 'gh {clean_cmd}' executed successfully with no output."
