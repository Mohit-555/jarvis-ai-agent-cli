import os
import signal
import subprocess
try:
    import psutil
except ImportError:
    psutil = None


class ProcessManagerTool:
    def list(self):
        if not psutil:
            return []
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return sorted(processes, key=lambda p: p.get("cpu_percent", 0) or 0, reverse=True)[:50]

    def kill(self, target):
        try:
            if isinstance(target, int) or target.isdigit():
                os.kill(int(target), signal.SIGTERM)
                return f"Killed PID {target}"
            elif psutil:
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        if target.lower() in (proc.info["name"] or "").lower():
                            os.kill(proc.info["pid"], signal.SIGTERM)
                            return f"Killed {target} (PID {proc.info['pid']})"
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                return f"No process found: {target}"
            else:
                return f"Process manager requires psutil for process name search: {target}"
        except Exception as e:
            return f"Error: {e}"

    def launch(self, command):
        try:
            proc = subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Launched {command} (PID {proc.pid})"
        except Exception as e:
            return f"Error: {e}"

    def monitor(self, pid):
        try:
            proc = psutil.Process(int(pid))
            return {
                "pid": proc.pid,
                "name": proc.name(),
                "cpu_percent": proc.cpu_percent(interval=0.5),
                "memory_percent": proc.memory_percent(),
                "status": proc.status(),
                "connections": len(proc.connections()),
                "threads": proc.num_threads(),
            }
        except Exception as e:
            return f"Error: {e}"
