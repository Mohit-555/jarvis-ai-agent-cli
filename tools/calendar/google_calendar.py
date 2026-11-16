import os
import json
import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_FILE = Path.home() / ".jarvis" / "keys" / "google_calendar_credentials.json"
TOKEN_FILE = Path.home() / ".jarvis" / "keys" / "google_calendar_token.json"


class GoogleCalendarTool:
    def __init__(self):
        self.service = None
        self._authenticate()

    def _authenticate(self):
        creds = None
        if TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if not CREDENTIALS_FILE.exists():
                self.service = None
                return
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
                creds = flow.run_local_server(port=0, open_browser=True)
            except Exception:
                self.service = None
                return

            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(creds.to_json())

        try:
            self.service = build("calendar", "v3", credentials=creds)
        except Exception:
            self.service = None

    def _ensure_auth(self) -> str | None:
        if self.service:
            return None
        if not CREDENTIALS_FILE.exists():
            return (
                "Google Calendar not set up. Download OAuth credentials:\n"
                "1. Go to https://console.cloud.google.com/\n"
                "2. Create a project → Enable Google Calendar API\n"
                "3. Credentials → Create OAuth 2.0 Client ID (Desktop app)\n"
                "4. Download JSON and save to: ~/.jarvis/keys/google_calendar_credentials.json\n"
                "5. Then try again — the browser will open for you to authorize."
            )
        self._authenticate()
        if not self.service:
            return "Auth failed — delete ~/.jarvis/keys/google_calendar_token.json and try again."
        return None

    def _format_event(self, event: dict) -> str:
        summary = event.get("summary", "(No title)")
        start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "?")
        end = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date", "?")
        location = event.get("location", "")
        loc_str = f" @ {location}" if location else ""
        return f"  {summary}{loc_str}\n    {start} → {end}"

    def list_calendars(self) -> str:
        err = self._ensure_auth()
        if err:
            return err
        try:
            result = self.service.calendarList().list().execute()
            items = result.get("items", [])
            if not items:
                return "No calendars found."
            lines = ["Your Calendars:"]
            for cal in items:
                primary = " (primary)" if cal.get("primary") else ""
                lines.append(f"  {cal['summary']}{primary} — {cal['id']}")
            return "\n".join(lines)
        except HttpError as e:
            return f"API error: {e}"

    def list_events(self, max_results: int = 10, calendar_id: str = "primary") -> str:
        err = self._ensure_auth()
        if err:
            return err
        try:
            now = datetime.datetime.utcnow().isoformat() + "Z"
            events_result = (
                self.service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=now,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
            if not events:
                return "No upcoming events found."
            lines = [f"Upcoming events ({len(events)}):"]
            for event in events:
                lines.append(self._format_event(event))
            return "\n".join(lines)
        except HttpError as e:
            return f"API error: {e}"

    def create_event(
        self,
        summary: str,
        start_datetime: str,
        end_datetime: str,
        description: str = "",
        location: str = "",
        calendar_id: str = "primary",
    ) -> str:
        err = self._ensure_auth()
        if err:
            return err
        try:
            event = {
                "summary": summary,
                "start": {"dateTime": start_datetime, "timeZone": "Asia/Kolkata"},
                "end": {"dateTime": end_datetime, "timeZone": "Asia/Kolkata"},
            }
            if description:
                event["description"] = description
            if location:
                event["location"] = location

            created = self.service.events().insert(calendarId=calendar_id, body=event).execute()
            link = created.get("htmlLink", "")
            return f"Created: {summary}\n  {start_datetime} → {end_datetime}\n  {link}"
        except HttpError as e:
            return f"API error: {e}"
