import json
from core.config import load_config


class MockFunction:
    def __init__(self, name, arguments_dict):
        self.name = name
        self.arguments = json.dumps(arguments_dict)


class MockToolCall:
    def __init__(self, id, function):
        self.id = id
        self.type = "function"
        self.function = function


class MockMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class LLM:
    def __init__(self):
        self.cfg = load_config()

    def _get_client_and_model(self):
        provider = self.cfg["llm_provider"]
        if provider == "openai":
            from openai import OpenAI
            return (
                OpenAI(api_key=self.cfg["openai_api_key"]),
                self.cfg["openai_model"],
                "openai",
            )
        elif provider == "ollama":
            from openai import OpenAI
            return (
                OpenAI(
                    base_url=f"{self.cfg['ollama_base_url']}/v1",
                    api_key="ollama",
                ),
                self.cfg["ollama_model"],
                "ollama",
            )
        elif provider == "openrouter":
            from openai import OpenAI
            return (
                OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.cfg["openrouter_api_key"],
                    default_headers={"HTTP-Referer": "https://github.com/mohit-patel/jarvis", "X-Title": "Jarvis AI Assistant"},
                ),
                self.cfg["openrouter_model"],
                "openrouter",
            )
        elif provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=self.cfg["gemini_api_key"])
            model = genai.GenerativeModel(self.cfg["gemini_model"])
            return model, self.cfg["gemini_model"], "gemini"
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _convert_to_gemini(self, messages):
        gemini_msgs = []
        system = None
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            elif m["role"] == "user":
                gemini_msgs.append({"role": "user", "parts": [m["content"]]})
            elif m["role"] == "assistant":
                gemini_msgs.append({"role": "model", "parts": [m.get("content", "")]})
            elif m["role"] == "tool":
                gemini_msgs.append({"role": "user", "parts": [f"Tool result: {m['content']}"]})
        return system, gemini_msgs

    def chat(self, messages, stream=True):
        client, model, provider = self._get_client_and_model()
        if provider == "gemini":
            system, gemini_msgs = self._convert_to_gemini(messages)
            gen_model = client
            resp = gen_model.generate_content(
                gemini_msgs,
                stream=stream,
            )
            if stream:
                for chunk in resp:
                    if chunk.text:
                        yield chunk.text
            else:
                yield resp.text
            return

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream,
            temperature=0.7,
        )
        if stream:
            for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        else:
            return response.choices[0].message.content

    def chat_blocking(self, messages):
        client, model, provider = self._get_client_and_model()
        if provider == "gemini":
            system, gemini_msgs = self._convert_to_gemini(messages)
            model_obj = client
            resp = model_obj.generate_content(gemini_msgs, stream=False)
            return resp.text

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
            temperature=0.7,
        )
        return response.choices[0].message.content

    def tools_chat(self, messages, tools):
        client, model, provider = self._get_client_and_model()
        if provider == "gemini":
            import time
            from google.generativeai.types import Tool, FunctionDeclaration
            declarations = []
            for t in tools:
                if t.get("type") == "function":
                    fn = t["function"]
                    params = fn.get("parameters", {})
                    clean_params = json.loads(json.dumps(params))
                    
                    def uppercase_types(d):
                        if isinstance(d, dict):
                            if "type" in d and isinstance(d["type"], str):
                                d["type"] = d["type"].upper()
                            for v in d.values():
                                uppercase_types(v)
                        elif isinstance(d, list):
                            for item in d:
                                uppercase_types(item)
                    
                    uppercase_types(clean_params)
                    fd = FunctionDeclaration(
                        name=fn["name"],
                        description=fn.get("description", ""),
                        parameters=clean_params
                    )
                    declarations.append(fd)
            
            tool = Tool(function_declarations=declarations)
            system, gemini_msgs = self._convert_to_gemini(messages)
            
            import google.generativeai as genai
            gen_model = genai.GenerativeModel(
                self.cfg["gemini_model"],
                tools=[tool],
                system_instruction=system
            )
            resp = gen_model.generate_content(gemini_msgs)
            
            tool_calls = []
            content = ""
            try:
                if resp.candidates and resp.candidates[0].content:
                    for part in resp.candidates[0].content.parts:
                        if part.function_call:
                            call_id = f"call_{part.function_call.name}_{int(time.time())}"
                            args = {}
                            if part.function_call.args:
                                args = dict(part.function_call.args)
                            tool_calls.append(MockToolCall(
                                id=call_id,
                                function=MockFunction(part.function_call.name, args)
                            ))
                        elif part.text:
                            content += part.text
            except Exception:
                pass
            
            return MockMessage(content=content or None, tool_calls=tool_calls)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=False,
            temperature=0.7,
        )
        return response.choices[0].message
