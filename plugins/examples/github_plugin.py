import logging

logger = logging.getLogger('jarvis.plugins.github')

try:
    from plugins.base_plugin import JarvisPlugin
except ImportError:
    from plugins.base_plugin import JarvisPlugin

try:
    from github import Github, GithubException
    HAS_PYGITHUB = True
except ImportError:
    HAS_PYGITHUB = False


class GitHubPlugin(JarvisPlugin):
    name = "github"
    description = "GitHub integration for repository management"
    version = "1.0.0"
    tools = [
        {"name": "github_create_issue", "description": "Create a GitHub issue", "parameters": {"repo": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"}}},
        {"name": "github_list_prs", "description": "List pull requests", "parameters": {"repo": {"type": "string"}}},
        {"name": "github_review_pr", "description": "Review a pull request", "parameters": {"repo": {"type": "string"}, "pr_number": {"type": "integer"}}},
    ]

    def __init__(self):
        self._client = None
        self._token = ""

    def setup(self, config: dict = None):
        config = config or {}
        self._token = config.get("token", "")
        if self._token and HAS_PYGITHUB:
            try:
                self._client = Github(self._token)
                logger.info("GitHub plugin connected")
            except Exception as e:
                logger.error(f"GitHub auth failed: {e}")
        else:
            logger.warning("GitHub plugin: no token or PyGithub not installed")

    def teardown(self):
        self._client = None
        logger.info("GitHub plugin torn down")

    def _get_repo(self, repo: str):
        if self._client:
            return self._client.get_repo(repo)
        return None

    def create_issue(self, repo: str, title: str, body: str = "") -> dict:
        if not HAS_PYGITHUB or not self._client:
            return {"status": "stub", "repo": repo, "title": title, "note": "PyGithub not available"}
        try:
            r = self._get_repo(repo)
            if not r:
                return {"error": f"Repository '{repo}' not found"}
            issue = r.create_issue(title=title, body=body)
            return {"status": "created", "number": issue.number, "url": issue.html_url}
        except Exception as e:
            logger.error(f"GitHub create issue error: {e}")
            return {"error": str(e)}

    def list_prs(self, repo: str) -> dict:
        if not HAS_PYGITHUB or not self._client:
            return {"status": "stub", "repo": repo, "prs": [], "note": "PyGithub not available"}
        try:
            r = self._get_repo(repo)
            if not r:
                return {"error": f"Repository '{repo}' not found"}
            prs = r.get_pulls(state="open")
            return {"status": "ok", "repo": repo, "prs": [{"number": pr.number, "title": pr.title, "state": pr.state} for pr in prs]}
        except Exception as e:
            logger.error(f"GitHub list PRs error: {e}")
            return {"error": str(e)}

    def review_pr(self, repo: str, pr_number: int) -> dict:
        if not HAS_PYGITHUB or not self._client:
            return {"status": "stub", "repo": repo, "pr": pr_number, "note": "PyGithub not available"}
        try:
            r = self._get_repo(repo)
            if not r:
                return {"error": f"Repository '{repo}' not found"}
            pr = r.get_pull(pr_number)
            files = pr.get_files()
            return {
                "status": "ok",
                "repo": repo,
                "pr": pr_number,
                "title": pr.title,
                "state": pr.state,
                "files": [f.filename for f in files],
                "note": "Review stub - use create_review for actual review",
            }
        except Exception as e:
            logger.error(f"GitHub review PR error: {e}")
            return {"error": str(e)}
