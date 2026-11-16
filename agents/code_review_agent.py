from agents.base import BaseAgent
from tools.files import FileTool

SYSTEM_PROMPT = """You are a senior code reviewer. Analyze code for bugs, security issues,
performance problems, style violations, and improvement opportunities.
Be thorough but constructive. Provide specific line-number references and clear explanations.

When asked to review code, read the relevant files first, then give a structured review covering:
- Bugs & logic errors
- Security vulnerabilities
- Performance concerns
- Code style & readability
- Suggestions for improvement"""


class CodeReviewAgent(BaseAgent):
    name = "codereview"
    description = "Code review, analyze code quality, find bugs"

    def __init__(self):
        super().__init__()
        self.file_tool = FileTool()

    def get_system_prompt(self):
        return SYSTEM_PROMPT

    def get_tool_defs(self):
        return {
            "read_file": ("Read a file's contents", ["path"]),
            "list_dir": ("List directory contents", ["path (optional)"]),
            "search_files": ("Find files matching a pattern", ["pattern", "path (optional)"]),
        }

    def tool_read_file(self, args):
        return self.file_tool.read_file(args["path"])

    def tool_list_dir(self, args):
        import json
        return json.dumps(self.file_tool.list_dir(args.get("path", ".")), indent=2)

    def tool_search_files(self, args):
        return str(self.file_tool.search_files(args["pattern"], args.get("path", ".")))
