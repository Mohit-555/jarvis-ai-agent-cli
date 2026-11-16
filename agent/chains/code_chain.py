from core.exceptions import LLMError


class CodeChain:
    def __init__(self, llm_router=None):
        self.llm = llm_router

    async def generate(self, spec: str) -> str:
        if not self.llm:
            return "# Code generation requires an LLM"
        prompt = (
            f"Generate Python code for the following specification:\n{spec}\n\n"
            "Return only the code inside a single python code block. "
            "Include imports, error handling, and a main() function if applicable."
        )
        try:
            response = await self.llm.generate([{"role": "user", "content": prompt}])
            return self._extract_code(response)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Code generation failed: {e}") from e

    async def review(self, code: str) -> str:
        if not self.llm:
            return "Code review requires an LLM"
        prompt = (
            f"Review the following Python code for bugs, style issues, security problems, "
            f"and performance concerns:\n\n```python\n{code}\n```\n\n"
            "Provide a structured review with: Issues Found, Severity, Suggestions."
        )
        try:
            return await self.llm.generate([{"role": "user", "content": prompt}])
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Code review failed: {e}") from e

    def _extract_code(self, text: str) -> str:
        import re
        match = re.search(r"```(?:python)?\n?(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        lines = text.strip().split("\n")
        code_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
        return "\n".join(code_lines) if code_lines else text.strip()
