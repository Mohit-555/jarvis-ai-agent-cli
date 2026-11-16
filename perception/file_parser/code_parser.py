import ast
import os
from pathlib import Path

_LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".r": "r",
    ".lua": "lua",
    ".pl": "perl",
    ".m": "matlab",
}


class CodeParser:
    def parse(self, path):
        ext = Path(path).suffix.lower()
        language = _LANG_MAP.get(ext, "unknown")

        with open(path, "r") as f:
            content = f.read()

        lines = content.splitlines()
        info = {
            "language": language,
            "lines": len(lines),
            "imports": [],
            "functions": [],
            "classes": [],
        }

        if language == "python":
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            info["imports"].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        for alias in node.names:
                            info["imports"].append(f"{module}.{alias.name}" if module else alias.name)
                    elif isinstance(node, ast.FunctionDef):
                        info["functions"].append(node.name)
                    elif isinstance(node, ast.ClassDef):
                        info["classes"].append(node.name)
            except SyntaxError:
                pass

        return info
