class CalendarTool:
    def __init__(self):
        self._events = []

    def list_events(self, date=None):
        if not self._events:
            return "Calendar not configured"
        if date:
            return [e for e in self._events if e.get("date") == date]
        return self._events

    def add_event(self, summary, date, time=None):
        self._events.append({
            "summary": summary,
            "date": date,
            "time": time or "00:00",
        })
        return f"Event added: {summary} on {date}"
