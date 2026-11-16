import json
import re
from assistant.llm import LLM

TOOL_CALL_PATTERN = re.compile(r'```tool\s*\n?(.*?)```', re.DOTALL)
SHELL_PATTERN = re.compile(r'```(?:bash|sh|shell)\s*\n?(.*?)```', re.DOTALL)


class BaseAgent:
    name = ""
    description = ""
    system_prompt = ""

    def __init__(self):
        self.llm = LLM()
        self.messages = []

    def get_tools(self):
        return []

    def get_system_prompt(self):
        return self.system_prompt

    def get_tool_defs(self):
        return {}

    def chat(self, user_input, history=None):
        self.messages = [{"role": "system", "content": self._build_prompt()}]
        if history:
            self.messages.extend(history[-10:])
        self.messages.append({"role": "user", "content": user_input})

        for _ in range(5):
            text = self.llm.chat_blocking(self.messages)

            tool_calls = self._extract_tool_calls(text)
            if tool_calls:
                clean = TOOL_CALL_PATTERN.sub("", text).strip()
                if clean:
                    self.messages.append({"role": "assistant", "content": clean})
                for tc in tool_calls:
                    result = self._execute_tool(tc)
                    self.messages.append({"role": "assistant", "content": f"Running {tc.get('name')}..."})
                    self.messages.append({"role": "user", "content": f"Result: {result}"})
                continue

            shell_cmds = self._extract_shell_commands(text)
            if shell_cmds and hasattr(self, 'tool_run_command'):
                clean = SHELL_PATTERN.sub("", text).strip()
                if clean:
                    self.messages.append({"role": "assistant", "content": clean})
                for cmd in shell_cmds:
                    result = self.tool_run_command({"command": cmd})
                    self.messages.append({"role": "assistant", "content": f"Running command..."})
                    self.messages.append({"role": "user", "content": f"Output:\n{result[:2000]}"})
                continue

            return text.strip()

        return "I couldn't complete that request."

    def _build_prompt(self):
        prompt = self.get_system_prompt() + "\n\nAvailable tools:\n"
        for name, info in self.get_tool_defs().items():
            desc, args = info
            args_str = ", ".join(args) if args else "none"
            prompt += f"- {name}: {desc} (args: {args_str})\n"
        prompt += "\nTo call a tool, use:\n"
        prompt += '```tool\n{"name": "tool_name", "arguments": {"key": "value"}}\n```'
        return prompt

    def get_tool_defs(self):
        return {}

    def _extract_tool_calls(self, text):
        matches = TOOL_CALL_PATTERN.findall(text)
        calls = []
        for m in matches:
            try:
                calls.append(json.loads(m.strip()))
            except json.JSONDecodeError:
                pass
        return calls

    def _extract_shell_commands(self, text):
        matches = SHELL_PATTERN.findall(text)
        return [m.strip() for m in matches if m.strip()]

    def _execute_tool(self, call):
        name = call.get("name", "")
        args = call.get("arguments", {})
        handler = getattr(self, f"tool_{name}", None)
        if handler:
            try:
                return str(handler(args))[:5000]
            except Exception as e:
                return f"Error: {e}"
        return f"Unknown tool: {name}"
