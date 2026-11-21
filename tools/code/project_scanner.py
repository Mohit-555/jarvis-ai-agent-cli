"""
ProjectScannerTool - Intelligent, security-conscious codebase scanner.
Scans codebases for high-signal architectural files, entry points, dependencies,
and project structure while strictly filtering out sensitive files (dotfiles,
credentials, browser profiles, tokens, virtualenvs, and caches).
"""

import os
import fnmatch
from pathlib import Path
from typing import Dict, List, Any, Optional


# Patterns strictly excluded from scanning to protect privacy and security
SECURITY_IGNORE_PATTERNS = {
    # System / Shell dotfiles
    ".bashrc", ".bash_profile", ".bash_history", ".bash_logout", ".profile",
    ".zshrc", ".zprofile", ".zhistory",
    # Browser profiles & session state
    "*whatsapp*", "*profile*", "*brave*", "*chrome*", "Default",
    "IndexedDB", "Local Storage", "Session Storage", "Cookies", "History",
    # Credentials & secrets
    ".env*", "*.pem", "*.key", "*id_rsa*", "*token*", "*secret*",
    "credentials.json", "client_secret*.json", "*.pfx", "*.p12",
    # Build artifacts, caches & virtual environments
    "__pycache__", ".pytest_cache", ".git", ".github", ".venv", "venv", "env",
    "node_modules", "dist", "build", "*.pyc", "*.pyo", "*.egg-info", ".mypy_cache",
    ".cache", ".local", ".config", ".jarvis"
}

# High-priority source extensions for codebases
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".c", ".cpp",
    ".h", ".hpp", ".java", ".html", ".css", ".scss", ".json", ".yaml", ".yml",
    ".toml", ".sh", ".sql", ".md"
}

# Key entry points & architecture files
ENTRY_POINT_NAMES = {
    "main.py", "app.py", "server.py", "cli.py", "index.py", "manage.py",
    "run.py", "wsgi.py", "asgi.py", "index.js", "index.ts", "server.js",
    "main.rs", "main.go"
}

CONFIG_DEPENDENCY_FILES = {
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile",
    "package.json", "Cargo.toml", "go.mod", "Makefile", "Dockerfile",
    "docker-compose.yml", "docker-compose.yaml", "config.py", "settings.py"
}


class ProjectScannerTool:
    """Tool for scanning project directories intelligently and securely."""

    def __init__(self, workspace: Optional[str] = None):
        self.workspace = Path(workspace).resolve() if workspace else None

    @staticmethod
    def is_ignored(name: str, path_obj: Optional[Path] = None) -> bool:
        """Check if a file or directory matches security or noise patterns."""
        name_lower = name.lower()

        # Check explicit ignore patterns
        for pattern in SECURITY_IGNORE_PATTERNS:
            if fnmatch.fnmatch(name_lower, pattern.lower()) or fnmatch.fnmatch(name, pattern):
                return True

        # Check any parent directory component if path_obj provided
        if path_obj:
            for part in path_obj.parts:
                part_lower = part.lower()
                for pattern in SECURITY_IGNORE_PATTERNS:
                    if fnmatch.fnmatch(part_lower, pattern.lower()):
                        return True

        return False

    def scan(self, path: str = ".", depth: int = 3) -> Dict[str, Any]:
        """
        Intelligently scan the target directory.
        Returns a structured dictionary with detected architecture, entry points,
        dependencies, high-priority code files, and a clean directory tree.
        """
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return {"error": f"Directory not found: {path}"}
        if not target.is_dir():
            return {"error": f"Path is not a directory: {path}"}

        # Check if target is inside Jarvis's own internal directory
        home = Path.home().resolve()
        jarvis_home = (home / ".jarvis").resolve()
        is_jarvis_internal = (
            target == jarvis_home or
            str(target).startswith(str(jarvis_home) + os.sep) or
            "jarvis_agent" in target.parts
        )

        entry_points: List[str] = []
        config_files: List[str] = []
        code_files: Dict[str, int] = {}
        top_directories: List[str] = []
        file_tree: List[str] = []

        total_scanned = 0
        max_scan_limit = 200

        def _walk(curr_dir: Path, curr_depth: int, prefix: str = ""):
            nonlocal total_scanned
            if curr_depth > depth or total_scanned >= max_scan_limit:
                return

            try:
                entries = sorted(curr_dir.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            except PermissionError:
                return
            except Exception:
                return

            # Filter entries
            filtered = [
                e for e in entries
                if not self.is_ignored(e.name, e) and not (e.name.startswith(".") and e.name not in (".env.example", ".gitignore"))
            ]

            total_entries = len(filtered)
            for idx, entry in enumerate(filtered):
                if total_scanned >= max_scan_limit:
                    break

                is_last = (idx == total_entries - 1)
                connector = "└── " if is_last else "├── "
                sub_prefix = "    " if is_last else "│   "

                rel_path = str(entry.relative_to(target))

                if entry.is_dir():
                    if curr_depth == 1:
                        top_directories.append(entry.name)
                    file_tree.append(f"{prefix}{connector}{entry.name}/")
                    _walk(entry, curr_depth + 1, prefix + sub_prefix)
                else:
                    total_scanned += 1
                    file_tree.append(f"{prefix}{connector}{entry.name}")

                    # Check entry points
                    if entry.name.lower() in ENTRY_POINT_NAMES:
                        entry_points.append(rel_path)

                    # Check config/dependency files
                    if entry.name.lower() in CONFIG_DEPENDENCY_FILES:
                        config_files.append(rel_path)

                    # Count code extensions
                    ext = entry.suffix.lower()
                    if ext in CODE_EXTENSIONS:
                        code_files[ext] = code_files.get(ext, 0) + 1

        # Build tree from target
        file_tree.append(f"{target.name}/")
        _walk(target, 1, "")

        # Infer project type
        project_type = "Generic Codebase"
        if "requirements.txt" in [os.path.basename(f) for f in config_files] or ".py" in code_files:
            if any("fastapi" in f.lower() or "flask" in f.lower() for f in entry_points):
                project_type = "Python Web Application"
            elif any("cli" in f.lower() for f in entry_points):
                project_type = "Python CLI Application"
            elif "setup.py" in [os.path.basename(f) for f in config_files] or "pyproject.toml" in [os.path.basename(f) for f in config_files]:
                project_type = "Python Package / Library"
            else:
                project_type = "Python Application"
        elif "package.json" in [os.path.basename(f) for f in config_files]:
            project_type = "Node.js / JavaScript Project"
        elif "Cargo.toml" in [os.path.basename(f) for f in config_files]:
            project_type = "Rust Project"
        elif "go.mod" in [os.path.basename(f) for f in config_files]:
            project_type = "Go Project"

        # Format readable markdown summary
        summary_lines = [
            f"### Project Analysis: `{target.name}`",
            f"- **Path**: `{target}`",
            f"- **Detected Type**: {project_type}",
            f"- **Jarvis System Directory**: {'Yes (Internal)' if is_jarvis_internal else 'No (External User Project)'}",
        ]

        if entry_points:
            summary_lines.append(f"- **Key Entry Points**: {', '.join(f'`{ep}`' for ep in entry_points)}")
        if config_files:
            summary_lines.append(f"- **Configs & Dependencies**: {', '.join(f'`{cf}`' for cf in config_files)}")
        if code_files:
            ext_counts = ", ".join(f"{ext}: {count}" for ext, count in sorted(code_files.items(), key=lambda x: -x[1]))
            summary_lines.append(f"- **Source Files**: {ext_counts}")

        summary_lines.append("\n**Structure Overview**:")
        summary_lines.append("```text")
        summary_lines.extend(file_tree[:40])
        if len(file_tree) > 40:
            summary_lines.append(f"... ({len(file_tree) - 40} more items hidden)")
        summary_lines.append("```")

        formatted_summary = "\n".join(summary_lines)

        return {
            "path": str(target),
            "project_type": project_type,
            "is_jarvis_internal": is_jarvis_internal,
            "entry_points": entry_points,
            "config_files": config_files,
            "code_files_count": code_files,
            "top_directories": top_directories,
            "file_tree": file_tree,
            "summary": formatted_summary,
        }
