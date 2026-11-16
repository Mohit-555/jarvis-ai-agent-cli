import json
from agents.base import BaseAgent
from tools.web import WebTool

SYSTEM_PROMPT = """You are a web research assistant. You can search the internet and fetch web pages
to answer the user's questions. Always cite sources and summarize key information."""


class WebAgent(BaseAgent):
    name = "web"
    description = "Web search, browse pages, research"

    def __init__(self):
        super().__init__()
        self.tool = WebTool()

    def get_system_prompt(self):
        return SYSTEM_PROMPT

    def get_tool_defs(self):
        return {
            "web_search": ("Search the web", ["query"]),
            "fetch_page": ("Read the full content of a web page", ["url"]),
        }

    def tool_web_search(self, args):
        return json.dumps(self.tool.search(args["query"]), indent=2)

    def tool_fetch_page(self, args):
        return self.tool.fetch_page(args["url"])
