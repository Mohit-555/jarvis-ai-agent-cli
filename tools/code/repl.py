import sys
import io
import code


class REPLTool:
    def __init__(self):
        self._interp = code.InteractiveInterpreter()
        self._interp.locals["__builtins__"] = __builtins__

    def execute(self, code_str):
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            more = self._interp.runsource(code_str, "<repl>")
            output = sys.stdout.getvalue()
            error = sys.stderr.getvalue()
            return {
                "output": output,
                "error": error,
                "more": more,
            }
        except Exception as e:
            return {"output": "", "error": str(e), "more": False}
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def reset(self):
        self._interp = code.InteractiveInterpreter()
        self._interp.locals["__builtins__"] = __builtins__
        return "REPL session reset"
