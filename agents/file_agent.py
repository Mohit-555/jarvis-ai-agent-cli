import json
from agents.base import BaseAgent
from tools.files import FileTool
from tools.web import WebTool

SYSTEM_PROMPT = """You are a file and code assistant. Help the user read, write, search files,
run Python code, and search the web for documentation. Be concise."""


class FileAgent(BaseAgent):
    name = "file"
    description = "File operations, code, reading/writing files"

    def __init__(self):
        super().__init__()
        self.file_tool = FileTool()
        self.web_tool = WebTool()

    def get_system_prompt(self):
        return SYSTEM_PROMPT

    def get_tool_defs(self):
        return {
            "read_file": ("Read a file's contents", ["path"]),
            "write_file": ("Write content to a file", ["path", "content"]),
            "list_dir": ("List directory contents", ["path (optional)"]),
            "search_files": ("Find files by name pattern", ["pattern", "path (optional)"]),
            "run_python": ("Execute Python code and return output", ["code"]),
        }

    def tool_read_file(self, args):
        return self.file_tool.read_file(args["path"])

    def tool_write_file(self, args):
        return self.file_tool.write_file(args["path"], args["content"])

    def tool_list_dir(self, args):
        return json.dumps(self.file_tool.list_dir(args.get("path", ".")), indent=2)

    def tool_search_files(self, args):
        return str(self.file_tool.search_files(args["pattern"], args.get("path", ".")))

    def tool_run_python(self, args):
        return self.file_tool.run_python(args["code"])
