try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.table import Table
    from rich.progress import Progress
    _HAS_RICH = True
except Exception:
    _HAS_RICH = False


class TerminalUI:
    def __init__(self):
        self.console = Console() if _HAS_RICH else None

    def display_message(self, content, role):
        if self.console is None:
            print(f"[{role}]: {content}")
            return
        prefix = {"user": "[bold blue]You:[/bold blue]", "assistant": "[bold green]Jarvis:[/bold green]"}.get(role, role)
        self.console.print(f"{prefix} {content}")

    def display_table(self, data, headers):
        if self.console is None:
            print("\t".join(headers))
            for row in data:
                print("\t".join(str(c) for c in row))
            return
        table = Table(*headers)
        for row in data:
            table.add_row(*[str(c) for c in row])
        self.console.print(table)

    def display_markdown(self, text):
        if self.console is None:
            print(text)
            return
        self.console.print(Markdown(text))

    def display_progress(self, iterable, description="Processing"):
        if self.console is None:
            for item in iterable:
                yield item
            return
        with Progress() as progress:
            task = progress.add_task(description, total=len(iterable))
            for item in iterable:
                yield item
                progress.update(task, advance=1)
