import time
from dataclasses import dataclass
from typing import Any

from core.exceptions import ToolExecutionError
from core.logger import central_logger


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str = ""
    tool_name: str = ""


TOOL_ALIASES = {
    "run_command": "shell_exec",
    "shell": "shell_exec",
    "python_interpreter": "run_python",
    "python": "run_python",
    "fetch_page": "web_fetch",
    "list_dir": "list_directory",
    "get_system_info": "system_info",
    "search_memory": "memory_search",
    # NOTE: "open_app" is the actual registered tool name — do NOT alias it
    "app_launch": "open_app",      # alias the old name TO the real name
    "screenshot": "screen_capture",
    "project_scan": "scan_project",
    "project_scanner": "scan_project",
    "scan_codebase": "scan_project",
    "sql_query": "db_query",
    "database_query": "db_query",
    "list_tables": "db_list_tables",
    "generate_doc": "doc_generate",
    "read_doc": "doc_read",
    "convert_doc": "doc_convert",
}


class Actor:
    def __init__(self, tool_registry=None):
        self._registry = tool_registry or {}

    def register_tool(self, name: str, fn):
        self._registry[name] = fn

    def _resolve_tool(self, name: str, registry) -> object | None:
        def _try_get(r, n):
            val = r.get(n)
            if isinstance(val, dict) and 'handler' in val:
                return val['handler']
            if callable(val):
                return val
            if isinstance(val, dict) and callable(val.get('handler')):
                return val['handler']
            return None

        fn = _try_get(registry, name)
        if fn:
            return fn
        aliased = TOOL_ALIASES.get(name)
        if aliased:
            fn = _try_get(registry, aliased)
            if fn:
                return fn
        return None

    def execute_step(self, step, tool_registry=None, timeout: int = 35) -> ToolResult:
        registry = tool_registry or self._registry
        tool_name = step.tool
        if not tool_name:
            return ToolResult(success=True, data=step.description, tool_name="")
        fn = self._resolve_tool(tool_name, registry)
        if not fn:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
                tool_name=tool_name,
            )
        try:
            import inspect
            final_args = dict(step.args) if isinstance(step.args, dict) else step.args
            if isinstance(final_args, dict):
                try:
                    sig = inspect.signature(fn)
                    params = sig.parameters
                    param_names = [p for p in params.keys() if p != "self"]
                    has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

                    # If single argument passed with a generic or mismatched key, remap to first param
                    if len(final_args) == 1 and param_names:
                        passed_key = list(final_args.keys())[0]
                        if passed_key not in param_names and not has_var_keyword:
                            final_args = {param_names[0]: final_args[passed_key]}

                    # Filter unexpected arguments if function does not take **kwargs
                    if not has_var_keyword:
                        final_args = {k: v for k, v in final_args.items() if k in param_names}
                except Exception:
                    pass

            # Timeout-protected execution
            start_t = time.time()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fn, **final_args) if isinstance(final_args, dict) else executor.submit(fn, final_args)
                result = future.result(timeout=timeout)

            duration = time.time() - start_t
            formatted_data = self._format_result(result, tool_name)
            central_logger.log_tool_execution(tool_name, final_args, duration, success=True)
            return ToolResult(success=True, data=formatted_data, tool_name=tool_name)
        except concurrent.futures.TimeoutError:
            duration = time.time() - start_t
            err = f"Tool '{tool_name}' timed out after {timeout} seconds."
            central_logger.log_tool_execution(tool_name, final_args, duration, success=False, error=err)
            return ToolResult(success=False, error=err, tool_name=tool_name)
        except ToolExecutionError as e:
            duration = time.time() - start_t
            central_logger.log_tool_execution(tool_name, final_args, duration, success=False, error=str(e))
            raise
        except Exception as e:
            duration = time.time() - start_t
            central_logger.log_tool_execution(tool_name, final_args, duration, success=False, error=str(e))
            return ToolResult(success=False, error=str(e), tool_name=tool_name)

    def _format_result(self, result, tool_name: str) -> str:
        """Convert raw tool output to a clean human-readable string."""
        if result is None:
            return "(no output)"

        # Shell execution result
        if isinstance(result, dict) and "stdout" in result:
            stdout = (result.get("stdout") or "").strip()
            stderr = (result.get("stderr") or "").strip()
            exit_code = result.get("exit_code", result.get("returncode", 0))
            if stdout:
                return stdout
            if stderr:
                return f"[stderr] {stderr}"
            return f"Command completed (exit code: {exit_code})"

        # Python execution result
        if isinstance(result, dict) and "success" in result and "stdout" in result:
            stdout = (result.get("stdout") or "").strip()
            stderr = (result.get("stderr") or "").strip()
            if stdout:
                return stdout
            if stderr:
                return f"[error] {stderr}"
            return "Code executed successfully (no output)"

        # Web search results (list of dicts with title/snippet)
        if isinstance(result, list) and result and isinstance(result[0], dict):
            # Check if it looks like search results
            if "snippet" in result[0] or "title" in result[0]:
                lines = []
                for i, r in enumerate(result[:5], 1):
                    title = r.get("title", "").strip()
                    snippet = r.get("snippet", "").strip()
                    link = r.get("link", "").strip()
                    if title or snippet:
                        lines.append(f"{i}. {title}")
                        if snippet and snippet != title:
                            lines.append(f"   {snippet[:200]}")
                        if link:
                            lines.append(f"   {link}")
                return "\n".join(lines) if lines else "(no results)"
            # Process list (pid, name, cpu)
            if "pid" in result[0] or "name" in result[0]:
                lines = []
                for p in result[:15]:
                    name = p.get("name", "?")
                    pid = p.get("pid", "?")
                    cpu = p.get("cpu_percent", 0)
                    mem = p.get("memory_percent", 0)
                    lines.append(f"  PID {pid:>6}  {name:<30}  CPU {cpu:.1f}%  MEM {mem:.1f}%")
                return "\n".join(lines)
            # File list
            if "name" in result[0] and "type" in result[0]:
                lines = []
                for f in result[:30]:
                    icon = "📁" if f.get("type") == "dir" else "📄"
                    size_str = ""
                    if f.get("type") == "file":
                        size = f.get("size") or f.get("sizeBytes") or f.get("size_bytes")
                        if size is not None:
                            try:
                                size = int(size)
                                if size > 1024 * 1024 * 1024:
                                    size_str = f" ({size / (1024*1024*1024):.1f} GB)"
                                elif size > 1024 * 1024:
                                    size_str = f" ({size / (1024*1024):.1f} MB)"
                                elif size > 1024:
                                    size_str = f" ({size / 1024:.1f} KB)"
                                else:
                                    size_str = f" ({size} B)"
                            except Exception:
                                pass
                    lines.append(f"  {icon}  {f['name']}{size_str}")
                return "\n".join(lines)

        # System info dict
        if isinstance(result, dict) and "cpu" in result:
            cpu = result.get("cpu", {})
            mem = result.get("memory", {})
            disk = result.get("disk", {})
            return (
                f"CPU: {cpu.get('percent', '?')}% used ({cpu.get('count', '?')} cores)\n"
                f"RAM: {round(mem.get('used', 0)/1e9, 1)}GB / {round(mem.get('total', 0)/1e9, 1)}GB "
                f"({mem.get('percent', '?')}% used)\n"
                f"Disk: {round(disk.get('free', 0)/1e9, 1)}GB free / {round(disk.get('total', 0)/1e9, 1)}GB total"
            )

        # Plain string or anything else
        text = str(result).strip()
        return text[:5000] if text else "(no output)"

