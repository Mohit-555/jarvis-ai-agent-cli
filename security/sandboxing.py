import logging

logger = logging.getLogger('jarvis.security.sandbox')

try:
    import restrictedpython
    from restrictedpython import Guards
    from restrictedpython.Compile import compile_restricted_exec
    HAS_RESTRICTED = True
except ImportError:
    HAS_RESTRICTED = False

BLOCKED_IMPORTS = [
    "os", "subprocess", "sys", "shutil", "ctypes",
    "socket", "requests", "urllib", "http",
    "multiprocessing", "threading", "signal",
    "importlib", "__import__", "eval", "exec",
    "compile", "open", "builtins.__import__",
]

BLOCKED_KEYWORDS = [
    "__import__", "__builtins__", "__class__",
    "__subclasses__", "__globals__", "__code__",
    "system(", "popen(", "subprocess",
]


class Sandbox:
    def __init__(self):
        self._timeout = 5
        self._allowed_modules = {"math", "json", "datetime", "random", "string", "re", "collections", "itertools", "typing"}

    def check_code(self, code: str) -> bool:
        for blocked in BLOCKED_IMPORTS:
            if f"import {blocked}" in code or f"from {blocked}" in code:
                logger.warning(f"Blocked import detected: {blocked}")
                return False
        for keyword in BLOCKED_KEYWORDS:
            if keyword in code:
                logger.warning(f"Blocked keyword detected: {keyword}")
                return False
        if HAS_RESTRICTED:
            try:
                compile_restricted_exec(code)
            except Exception as e:
                logger.warning(f"RestrictedPython compile failed: {e}")
                return False
        return True

    def run_sandboxed(self, code: str, timeout: int = 5) -> dict:
        result = {"success": False, "output": "", "error": ""}
        if not self.check_code(code):
            result["error"] = "Code failed security check"
            return result

        import shutil
        import subprocess

        has_docker = shutil.which("docker") is not None
        if has_docker:
            wrapped_code = code + "\nif 'result' in locals(): print(result)"
            try:
                res = subprocess.run(
                    [
                        "docker", "run", "--rm",
                        "--network", "none",
                        "--read-only",
                        "--memory", "128m",
                        "--cpus", "0.5",
                        "-i", "python:3.11-slim",
                        "python3", "-c", wrapped_code
                    ],
                    capture_output=True, text=True, timeout=timeout
                )
                if res.returncode == 0:
                    result["success"] = True
                    result["output"] = res.stdout.strip()
                    return result
                logger.debug(f"Docker sandbox execution returned {res.returncode}, falling back to local sandbox: {res.stderr.strip()}")
            except subprocess.TimeoutExpired:
                result["error"] = "Execution timed out"
                return result
            except Exception as e:
                logger.debug(f"Docker sandbox unavailable ({e}), falling back to local sandbox")

        if HAS_RESTRICTED:
            try:
                safe_globals = {
                    "__builtins__": {
                        "abs": abs, "bool": bool, "dict": dict, "enumerate": enumerate,
                        "float": float, "int": int, "len": len, "list": list,
                        "max": max, "min": min, "range": range, "round": round,
                        "str": str, "sum": sum, "tuple": tuple, "type": type,
                        "zip": zip, "True": True, "False": False, "None": None,
                        "isinstance": isinstance, "hasattr": hasattr, "getattr": getattr,
                        "setattr": setattr, "sorted": sorted, "reversed": reversed,
                        "map": map, "filter": filter, "any": any, "all": all,
                    }
                }
                bytecode = compile_restricted_exec(code)
                exec(bytecode, safe_globals)
                if "result" in safe_globals:
                    result["output"] = str(safe_globals["result"])
                result["success"] = True
            except Exception as e:
                result["error"] = str(e)
            return result

        safe_globals = {
            "__builtins__": {
                "abs": abs, "bool": bool, "dict": dict, "len": len,
                "int": int, "float": float, "str": str, "list": list,
                "range": range, "True": True, "False": False, "None": None,
                "max": max, "min": min, "sum": sum, "sorted": sorted,
                "isinstance": isinstance, "enumerate": enumerate,
            }
        }
        try:
            exec(code, safe_globals)
            if "result" in safe_globals:
                result["output"] = str(safe_globals["result"])
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)
        return result
