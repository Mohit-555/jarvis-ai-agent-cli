"""
ShellTool - Secure shell command executor for Jarvis.
Implements dangerous command blocking, timeout guards, and optional workspace isolation.
"""

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# High-risk patterns that pose irreversible system damage or remote execution risks
DANGEROUS_PATTERNS = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*[rfRF][a-zA-Z]*\s+)+(/\s*$|/\*|~/\*|/boot|/etc|/sys)", re.IGNORECASE), "Root or system-level deletion attempted"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:", re.IGNORECASE), "Fork bomb attack detected"),
    (re.compile(r"(>\s*/dev/sd[a-z0-9]*|dd\s+.*of=/dev/sd[a-z0-9]*)", re.IGNORECASE), "Raw disk or block device overwrite detected"),
    (re.compile(r"\b(curl|wget)\s+[^|]+\|\s*(sudo\s+)?(bash|sh|zsh)", re.IGNORECASE), "Unverified remote script execution via pipe detected"),
    (re.compile(r"\bchmod\s+(-[a-zA-Z]*[rR][a-zA-Z]*\s+)?777\s+(/\s*$|/\*|/etc)", re.IGNORECASE), "Insecure root filesystem permission modification detected"),
    (re.compile(r"\bmkfs(\.[a-zA-Z0-9]+)?\s+/dev/", re.IGNORECASE), "Filesystem format command detected"),
]


class ShellTool:
    def __init__(self, workspace: Optional[str] = None):
        self.workspace = Path(workspace).resolve() if workspace else None

    def validate_command(self, cmd_str: str) -> Tuple[bool, str]:
        """Validate whether a command is safe to execute."""
        for pattern, reason in DANGEROUS_PATTERNS:
            if pattern.search(cmd_str):
                return False, f"Security Violation: {reason}."
        return True, ""

    def run(self, command: str, timeout: int = 30, background: bool = False) -> Dict[str, Any]:
        """
        Execute a shell command with security validation and timeout handling.

        Args:
            command: The command string to execute.
            timeout: Max execution time for foreground processes in seconds.
            background: If True, executes the command in the background and returns immediately.
        """
        cmd_str = (command or "").strip()
        if not cmd_str:
            return {"stdout": "", "stderr": "No command provided.", "exit_code": -1}

        # Validate security
        is_safe, error_msg = self.validate_command(cmd_str)
        if not is_safe:
            return {
                "stdout": "",
                "stderr": f"Access Denied: {error_msg}",
                "exit_code": 126,
            }

        # Check background flag
        if cmd_str.endswith("&"):
            background = True
            cmd_str = cmd_str[:-1].strip()

        cwd_path = str(self.workspace) if self.workspace and self.workspace.is_dir() else None

        if background:
            try:
                process = subprocess.Popen(
                    cmd_str,
                    shell=True,
                    cwd=cwd_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                time.sleep(1.0)
                poll = process.poll()
                if poll is not None:
                    stdout, stderr = process.communicate()
                    return {
                        "stdout": stdout.strip(),
                        "stderr": stderr.strip(),
                        "exit_code": poll,
                    }
                return {
                    "stdout": f"Command started in the background (PID {process.pid}).",
                    "stderr": "",
                    "exit_code": 0,
                }
            except Exception as e:
                return {"stdout": "", "stderr": f"Failed to start background process: {e}", "exit_code": -1}

        try:
            result = subprocess.run(
                cmd_str,
                shell=True,
                cwd=cwd_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds.",
                "exit_code": -1,
            }
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "exit_code": -1}
