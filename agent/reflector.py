from core.exceptions import AgentError, ToolError, LLMError, MemoryError


class Reflector:
    ERROR_CATEGORIES = {
        "tool_not_found": ["unknown tool", "not found", "no such tool"],
        "tool_timeout": ["timed out", "timeout", "too long"],
        "tool_permission": ["permission denied", "access denied", "forbidden"],
        "llm_error": ["api error", "rate limit", "provider", "token limit"],
        "memory_error": ["memory", "chroma", "vector", "embedding"],
        "syntax_error": ["syntaxerror", "invalid syntax", "traceback"],
        "resource_exhausted": ["out of memory", "disk full", "no space"],
        "network_error": ["connection", "network", "dns", "refused"],
    }

    def reflect(self, error: str, context: str = "") -> str:
        category = self._categorize(error)
        diagnosis = f"[{category}] "

        if category == "tool_not_found":
            diagnosis += f"The tool or resource was not available. Error: {error[:100]}"
        elif category == "tool_timeout":
            diagnosis += "The operation took too long. Consider retrying with a simpler request."
        elif category == "tool_permission":
            diagnosis += "Permission denied. The action requires elevated privileges or access rights."
        elif category == "llm_error":
            diagnosis += "The language model encountered an issue. Check provider configuration or retry."
        elif category == "memory_error":
            diagnosis += "Memory system error. The storage backend may be unavailable or corrupted."
        elif category == "syntax_error":
            diagnosis += f"A syntax error occurred. Review the command or input for correctness. Details: {error[:150]}"
        elif category == "resource_exhausted":
            diagnosis += "System resources are exhausted. Free up memory or disk space and retry."
        elif category == "network_error":
            diagnosis += "A network error occurred. Check internet connectivity."
        else:
            diagnosis += f"Uncategorized error: {error[:200]}"

        return diagnosis

    def suggest_fix(self, error: str) -> str:
        category = self._categorize(error)
        suggestions = {
            "tool_not_found": "Verify the tool name and ensure all dependencies are installed.",
            "tool_timeout": "Increase timeout limits or split the task into smaller steps.",
            "tool_permission": "Run with appropriate permissions or use sudo for system commands.",
            "llm_error": "Check API keys, switch providers, or reduce prompt length.",
            "memory_error": "Reinstall chromadb or switch to in-memory fallback mode.",
            "syntax_error": "Review the generated code/command for syntax issues.",
            "resource_exhausted": "Close other applications or increase system resources.",
            "network_error": "Check internet connection and retry the operation.",
        }
        return suggestions.get(category, "Review the error details and retry with a different approach.")

    def _categorize(self, error: str) -> str:
        error_lower = str(error).lower()
        for category, patterns in self.ERROR_CATEGORIES.items():
            for pattern in patterns:
                if pattern in error_lower:
                    return category
        return "unknown"
