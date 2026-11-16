from agents.base import BaseAgent
from tools.system import SystemTool

SYSTEM_PROMPT = """You are a system control assistant. You can monitor and control the user's PC.
Run commands, check system health, manage processes, open apps.
Always be careful with destructive commands and ask before making major changes."""


class SystemAgent(BaseAgent):
    name = "system"
    description = "System control, commands, processes, apps"

    def __init__(self):
        super().__init__()
        self.tool = SystemTool()

    def get_system_prompt(self):
        return SYSTEM_PROMPT

    def get_tool_defs(self):
        return {
            "run_command": ("Run a shell command", ["command"]),
            "get_system_info": ("Get CPU, memory, disk info", []),
            "open_app": ("Open an application", ["app_name"]),
            "list_processes": ("List running processes", ["filter (optional)"]),
            "screenshot": ("Take a screenshot", []),
        }

    def tool_run_command(self, args):
        return self.tool.run_command(args["command"])

    def tool_get_system_info(self, _=None):
        return str(self.tool.get_system_info())

    def tool_open_app(self, args):
        return self.tool.open_app(args["app_name"])

    def tool_list_processes(self, args):
        return str(self.tool.list_processes(args.get("filter")))

    def tool_screenshot(self, _=None):
        return self.tool.screenshot()
