from __future__ import annotations
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from skills.base import Skill
from core.exceptions import ToolError

logger = logging.getLogger('jarvis.skills.executor')


class SkillExecutor:
    def __init__(self, llm_router=None, tool_registry=None):
        self.llm = llm_router
        self.tools = tool_registry

    async def execute(self, skill: Skill, arguments: dict | None = None, context: dict | None = None) -> str:
        if skill.shell:
            return self._execute_shell(skill, arguments)
        if not self.llm:
            return f"Cannot execute skill '{skill.name}': no LLM available"
        return await self._execute_llm(skill, arguments, context)

    def _execute_shell(self, skill: Skill, arguments: dict | None = None) -> str:
        if not skill.content:
            return f"Skill '{skill.name}' has no content"
        try:
            result = subprocess.run(
                skill.content,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout + result.stderr
            return output[:5000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return "Skill execution timed out"
        except Exception as e:
            return f"Skill execution error: {e}"

    async def _execute_llm(self, skill: Skill, arguments: dict | None = None, context: dict | None = None) -> str:
        prompt_parts = [f"Execute the following skill: {skill.name}"]
        if skill.description:
            prompt_parts.append(f"Description: {skill.description}")
        if skill.content:
            prompt_parts.append(f"\nInstructions:\n{skill.content}")
        if arguments:
            prompt_parts.append(f"\nArguments: {arguments}")
        if context:
            prompt_parts.append(f"\nContext: {context}")

        prompt = '\n'.join(prompt_parts)

        messages = [{'role': 'user', 'content': prompt}]

        if self.tools and skill.allowed_tools:
            available = self.tools.list_tools()
            filtered = [t for t in available if t['name'] in skill.allowed_tools]
            tool_specs = []
            for t in filtered:
                tool_specs.append({
                    'type': 'function',
                    'function': {
                        'name': t['name'],
                        'description': t.get('description', ''),
                        'parameters': {'type': 'object', 'properties': {}},
                    }
                })
            if tool_specs:
                result = await self.llm.generate_with_tools(messages, tool_specs)
                if result.get('tool_calls'):
                    for tc in result['tool_calls']:
                        fn_name = tc['function']['name']
                        fn_args = tc['function']['arguments']
                        import json
                        if isinstance(fn_args, str):
                            fn_args = json.loads(fn_args)
                        if self.tools:
                            tool_result = self.tools.call(fn_name, **fn_args)
                            messages.append({'role': 'assistant', 'content': f"Called {fn_name}"})
                            messages.append({'role': 'user', 'content': f"Result: {tool_result}"})
                    final = await self.llm.generate(messages)
                    return final

        return await self.llm.generate(messages)
