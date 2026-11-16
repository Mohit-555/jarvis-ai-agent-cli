import sys

try:
    from plyer import notification
    _HAS_PLYER = True
except Exception:
    _HAS_PLYER = False


class Notifier:
    def notify(self, title, message, urgency="normal"):
        if _HAS_PLYER:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    timeout=5,
                )
                return
            except Exception:
                pass

        try:
            import subprocess
            subprocess.run(
                ["notify-send", "-u", urgency, title, message],
                capture_output=True, timeout=5,
            )
        except Exception:
            print(f"\a{title}: {message}", file=sys.stderr)

    def notify_done(self):
        self.notify("Jarvis", "Task completed")
