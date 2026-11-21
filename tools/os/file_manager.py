import fnmatch
import os
import shutil
import subprocess
from pathlib import Path


SENSITIVE_PATTERNS = {
    # System / Shell dotfiles
    ".bashrc", ".bash_profile", ".bash_history", ".bash_logout", ".profile",
    ".zshrc", ".zprofile", ".zhistory",
    # Browser profiles & session state
    "*whatsapp*", "*profile*", "*brave*", "*chrome*", "Default",
    "IndexedDB", "Local Storage", "Cookies", "Session Storage",
    # Credentials & secrets
    ".env*", "*.pem", "*.key", "*id_rsa*", "*token*", "*secret*",
    "credentials.json", "client_secret*.json",
    # Caches and internal git
    "__pycache__", ".pytest_cache", ".git"
}


class FileManagerTool:
    def __init__(self, workspace=None):
        self.workspace = Path(workspace).resolve() if workspace else None

    @staticmethod
    def is_sensitive(name: str, path_obj: Path = None) -> bool:
        """Check if a file or directory name matches sensitive or credential patterns."""
        name_lower = name.lower()
        for pat in SENSITIVE_PATTERNS:
            if fnmatch.fnmatch(name_lower, pat.lower()) or fnmatch.fnmatch(name, pat):
                return True
        if path_obj:
            for part in path_obj.parts:
                part_lower = part.lower()
                for pat in SENSITIVE_PATTERNS:
                    if fnmatch.fnmatch(part_lower, pat.lower()):
                        return True
        return False

    def _safe_path(self, path):
        p = Path(path).expanduser().resolve()
        if self.workspace and not str(p).startswith(str(self.workspace)):
            raise PermissionError(f"Path outside workspace: {path}")
        return p

    def read(self, path):
        try:
            p = self._safe_path(path)
            if not p.exists():
                return f"File not found: {path}"
            if self.is_sensitive(p.name, p):
                return f"Access Denied: Reading sensitive file or credential ({p.name}) is blocked for security."
            return p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error: {e}"

    def write(self, path, content):
        try:
            p = self._safe_path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Written to {p}"
        except Exception as e:
            return f"Error: {e}"

    def list(self, path=".", include_hidden=False, filter_sensitive=True):
        try:
            p = self._safe_path(path)
            items = []
            for item in p.iterdir():
                if not include_hidden and item.name.startswith("."):
                    continue
                if filter_sensitive and self.is_sensitive(item.name, item):
                    continue
                items.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                })
            return items
        except Exception as e:
            return f"Error: {e}"

    def search(self, pattern, path="."):
        try:
            p = self._safe_path(path)
            result = subprocess.run(
                ["find", str(p), "-name", pattern],
                capture_output=True, text=True, timeout=10,
            )
            files = result.stdout.strip().split("\n") if result.stdout.strip() else []
            return files[:50]
        except Exception as e:
            return f"Error: {e}"

    def delete(self, path):
        try:
            p = self._safe_path(path)
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
            return f"Deleted {path}"
        except Exception as e:
            return f"Error: {e}"

    def move(self, src, dst):
        try:
            src_p = self._safe_path(src)
            dst_p = self._safe_path(dst)
            dst_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_p), str(dst_p))
            return f"Moved {src} to {dst}"
        except Exception as e:
            return f"Error: {e}"
