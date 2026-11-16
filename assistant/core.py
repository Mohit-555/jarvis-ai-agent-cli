import json
import re
from datetime import datetime
from core.config import load_config
from assistant.llm import LLM
from assistant.memory import Memory
from tools.system import SystemTool
from tools.web import WebTool
from tools.os.file_manager import FileManagerTool
from tools.voice import VoiceTool

SYSTEM_PROMPT = """You are Jarvis, a personal AI assistant running on the user's PC.
You can:
1. Run system commands and control the PC
2. Search the web and fetch web pages
3. Read and write files
4. Remember conversation context
5. Use voice input/output

When you need to use a tool, respond with a JSON block like this:
```tool
{{"name": "tool_name", "arguments": {{"key": "value"}}}}
```

Available tools:
- run_command: Run a shell command (args: command)
- get_system_info: Get CPU/memory/disk info (no args)
- open_app: Open an application (args: app_name)
- web_search: Search the web (args: query)
- fetch_page: Fetch a web page (args: url)
- read_file: Read a file (args: path)
- write_file: Write to a file (args: path, content)
- list_dir: List directory (args: path, optional)
- search_memory: Search past conversation (args: query)
- screenshot: Take a screenshot (no args)

Be concise and helpful. Current time: {time}"""

TOOL_MAP = {
    "run_command": lambda a: SystemTool().run_command(a["command"]),
    "get_system_info": lambda a: str(SystemTool().get_system_info()),
    "open_app": lambda a: SystemTool().open_app(a["app_name"]),
    "web_search": lambda a: json.dumps(WebTool().search(a["query"])),
    "fetch_page": lambda a: WebTool().fetch_page(a["url"]),
    "read_file": lambda a: FileManagerTool().read(a["path"]),
    "write_file": lambda a: FileManagerTool().write(a["path"], a["content"]),
    "list_dir": lambda a: json.dumps(FileManagerTool().list(a.get("path", "."))),
    "search_memory": lambda a: str(Memory().search(a["query"])),
    "screenshot": lambda a: SystemTool().screenshot(),
}

TOOL_CALL_PATTERN = re.compile(r'```tool\s*\n?(.*?)```', re.DOTALL)


class Assistant:
    def __init__(self, use_voice=False):
        self.cfg = load_config()
        self.llm = LLM()
        self.memory = Memory()
        self.system = SystemTool()
        self.web = WebTool()
        self.files = FileManagerTool()
        self.voice = VoiceTool() if use_voice else None
        self.messages = []
        self._init_system()

    def _init_system(self):
        self.messages.append({
            "role": "system",
            "content": SYSTEM_PROMPT.format(time=datetime.now().isoformat()),
        })

    def _extract_tool_calls(self, text):
        matches = TOOL_CALL_PATTERN.findall(text)
        calls = []
        for m in matches:
            try:
                parsed = json.loads(m.strip())
                calls.append(parsed)
            except json.JSONDecodeError:
                pass
        return calls

    def _execute_tool(self, call):
        name = call.get("name", "")
        args = call.get("arguments", {})
        fn = TOOL_MAP.get(name)
        if not fn:
            return f"Unknown tool: {name}"
        try:
            return str(fn(args))[:5000]
        except Exception as e:
            return f"Error: {e}"

    def _call_llm(self, messages):
        try:
            result = self.llm.tools_chat(messages, self._get_openai_tools())
            return result, "api"
        except Exception:
            pass
        content = self.llm.chat_blocking(messages)
        return content, "text"

    def _get_openai_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": info.__doc__ or "",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            k: {"type": "string"} for k in (
                                ("command",) if name == "run_command" else
                                ("query",) if name in ("web_search", "search_memory") else
                                ("url",) if name == "fetch_page" else
                                ("app_name",) if name == "open_app" else
                                ("path",) if name == "read_file" else
                                ("path", "content") if name == "write_file" else
                                ()
                            )
                        },
                        "required": (
                            ["command"] if name == "run_command" else
                            ["query"] if name in ("web_search", "search_memory") else
                            ["url"] if name == "fetch_page" else
                            ["app_name"] if name == "open_app" else
                            ["path"] if name == "read_file" else
                            ["path", "content"] if name == "write_file" else
                            []
                        ),
                    },
                },
            }
            for name in TOOL_MAP
        ]

    def chat(self, user_input, stream=True):
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = SYSTEM_PROMPT.format(time=datetime.now().isoformat())
        self.messages.append({"role": "user", "content": user_input})
        self.memory.add("user", user_input)

        for _ in range(5):
            response, mode = self._call_llm(self.messages)

            if mode == "api" and hasattr(response, "tool_calls") and response.tool_calls:
                for tc in response.tool_calls:
                    fn = tc.function
                    try:
                        args = json.loads(fn.arguments)
                        result = TOOL_MAP.get(fn.name, lambda a: f"Unknown: {fn.name}")(args)
                    except Exception as e:
                        result = f"Tool error: {e}"
                    self.messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{"id": tc.id, "type": "function", "function": fn}],
                    })
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result)[:5000],
                    })
                continue

            content = response.content if mode == "api" else response

            tool_calls = self._extract_tool_calls(content)
            if tool_calls:
                clean_text = TOOL_CALL_PATTERN.sub("", content).strip()
                if clean_text:
                    self.messages.append({"role": "assistant", "content": clean_text})
                for tc in tool_calls:
                    result = self._execute_tool(tc)
                    mock_tool_call_id = f"call_{tc.get('name')}_{int(datetime.now().timestamp())}"
                    self.messages.append({
                        "role": "assistant",
                        "content": f"Using {tc.get('name')}...",
                        "tool_calls": [{
                            "id": mock_tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tc.get("name"),
                                "arguments": json.dumps(tc.get("arguments", {}))
                            }
                        }]
                    })
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": mock_tool_call_id,
                        "content": str(result)[:5000],
                    })
                continue

            self.messages.append({"role": "assistant", "content": content})
            self.memory.add("assistant", content)

            if stream:
                for word in content.split(" "):
                    yield word + " "
            else:
                yield content
            return

        yield "I'm having trouble processing that request."

    def speak(self, text):
        if self.voice:
            self.voice.speak(text)

    def transcribe(self):
        if self.voice:
            audio = self.voice.record_until_silence()
            if audio is None:
                return None
            path = self.voice.save_audio(audio)
            return self.voice.transcribe(path)
        return None

    def reset(self):
        self.messages.clear()
        self._init_system()
