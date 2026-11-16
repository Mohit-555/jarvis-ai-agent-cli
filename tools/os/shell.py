import subprocess
import time


class ShellTool:
    def run(self, command, timeout=30, background=False):
        """
        Execute a shell command.
        
        Args:
            command: The command string to execute.
            timeout: Max execution time for foreground processes.
            background: If True, executes the command in the background and returns immediately.
        """
        cmd_str = command.strip()
        # If the user ended their command with an ampersand, treat it as background
        if cmd_str.endswith("&"):
            background = True
            cmd_str = cmd_str[:-1].strip()

        if background:
            try:
                # Start process in background
                process = subprocess.Popen(
                    cmd_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                # Give it a short moment to check if it crashes immediately
                time.sleep(1.5)
                poll = process.poll()
                if poll is not None:
                    # Process exited immediately (likely failed)
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
                cmd_str, shell=True, capture_output=True, text=True, timeout=timeout,
            )
            return {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Command timed out", "exit_code": -1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "exit_code": -1}
