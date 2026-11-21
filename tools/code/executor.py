import ast
import subprocess


class CodeExecutor:
    ALLOWED_IMPORTS = {"json", "math", "random", "datetime", "collections", "itertools", "re", "string", "typing", "pathlib"}

    def _check_code(self, code):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] not in self.ALLOWED_IMPORTS:
                            return False, f"Import not allowed: {alias.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split(".")[0] not in self.ALLOWED_IMPORTS:
                        return False, f"Import not allowed: {node.module}"
            return True, ""
        except SyntaxError as e:
            return False, str(e)

    def run_python(self, code, timeout=15):
        import shutil
        import subprocess

        has_docker = shutil.which("docker") is not None
        if has_docker:
            try:
                result = subprocess.run(
                    [
                        "docker", "run", "--rm",
                        "--network", "none",
                        "--read-only",
                        "--memory", "128m",
                        "--cpus", "0.5",
                        "-i", "python:3.11-slim",
                        "python3", "-c", code
                    ],
                    capture_output=True, text=True, timeout=timeout,
                )
                if result.returncode == 0 or ("docker" not in result.stderr.lower() and "daemon" not in result.stderr.lower()):
                    return {
                        "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip(),
                        "success": result.returncode == 0,
                    }
            except subprocess.TimeoutExpired:
                return {"stdout": "", "stderr": "Execution timed out", "success": False}
            except Exception:
                pass

        try:
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True, text=True, timeout=timeout,
            )
            return {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Execution timed out", "success": False}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "success": False}
