from dataclasses import dataclass, field
from typing import Optional

from core.exceptions import AgentError


@dataclass
class Step:
    id: str
    description: str
    tool: str = ""
    args: dict = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"


PLANNER_SYSTEM_PROMPT = """You are Jarvis, a personal AI assistant that plans how to accomplish user requests.

You decide whether a request needs tools or is just casual conversation.
You also decide what steps are needed and what arguments each step requires.

CRITICAL RULES:
- When a user asks to write content (essay, note, story, email, etc.), the 'content' argument of write_file must be the FULL GENERATED CONTENT — not the user's request, not a placeholder.
- When a user specifies a path like "Downloads folder" or "~/Downloads/", use that EXACT path with the correct filename.
- If the user just says "write a note" or "write an essay" without specifying content, GENERATE the content yourself.
- Never ask the user what to write — they've already told you. Just write it."""


class Planner:
    def __init__(self, llm_router=None):
        self.llm = llm_router

    async def plan(self, goal: str, context: str = "") -> list[Step]:
        if not self.llm:
            return [Step(id="1", description=goal, tool="", args={})]
        prompt = (
            f"Determine if the following is a conversational message or a task needing steps.\n"
            f"User: {goal}\n"
            f"Context: {context}\n\n"
            "If this is a greeting, casual chat, or simple social exchange (no tools needed), "
            "return exactly: NO_PLANNING_NEEDED\n\n"
            "Otherwise, break down this task into sequential steps. Each line: "
            "STEP_ID | DESCRIPTION | TOOL | ARGS_JSON\n"
            "AVAILABLE TOOLS (use ONLY these exact names):\n"
            "- open_app: Open a desktop application (args: {\"app_name\": \"...\"}) — use for: calculator, clock, brave browser, brave, terminal, settings, files, vlc, telegram\n"
            "  NOTE: The installed browser is Brave. Use app_name='brave browser' to open it. Do NOT use 'Google Chrome' or 'chrome'.\n"
            "- browse_url: Open a specific URL in the browser (args: {\"url\": \"...\"}) — use when user wants to open a website\n"
            "  Example: browse_url {\"url\": \"https://web.whatsapp.com\"}\n"
            "- search_in_browser: Google-search and open results in browser (args: {\"query\": \"...\"}) — use when user says 'search X in browser'\n"
            "  Example: search_in_browser {\"query\": \"whatsapp web\"}\n"
            "- shell_exec: Run a shell command (args: {\"command\": \"...\", \"background\": true/false}) — use for packages, file ops, system commands. Set background to true for long-running servers/commands that do not exit (like ngrok, flask, databases).\n"
            "- web_search: Search the web via API and return text results (args: {\"query\": \"...\"}) — does NOT open browser\n"
            "- web_fetch: Fetch a URL and return page content as text (args: {\"url\": \"...\"}) — does NOT open browser\n"
            "- read_file: Read a file (args: {\"path\": \"...\"})\n"
            "- write_file: Write a file (args: {\"path\": \"...\", \"content\": \"...\"})\n"
            "  CRITICAL: The 'content' must be the FULL actual content to write (e.g., a complete essay, full note text). NEVER use the user's request as content."
            "  CRITICAL: If user says ~/Downloads/, use EXACTLY ~/Downloads/filename.txt as path.\n"
            "- list_directory: List a directory (args: {\"path\": \"...\"})\n"
            "- run_python: Execute Python code (args: {\"code\": \"...\"})\n"
            "- system_info: Get system info (no args needed)\n"
            "- screenshot: Take a screenshot of the current screen (no args needed)\n"
            "- clipboard_read: Read clipboard\n"
            "- clipboard_write: Write clipboard (args: {\"text\": \"...\"})\n"
            "- process_list: List running processes\n"
            "- list_browser_tabs: List all open tabs in the Brave browser with their titles and URLs (no args). Use when user asks 'kaun se tab khule hain', 'kitne tabs hain', 'list browser tabs'.\n"
            "- whatsapp_send: Send a WhatsApp message (args: {\"phone\": \"+91XXXXXXXXXX or contact name\", \"message\": \"...\"})\n"
            "  Use when user says 'send message to X on whatsapp' or 'whatsapp X hello'. The 'phone' argument can be a phone number or a contact name (e.g., 'mohit'). Do not ask for phone number if name is provided.\n"
            "- whatsapp_open_chat: Open a WhatsApp chat (args: {\"phone\": \"+91XXXXXXXXXX or contact name\"})\n"
            "- whatsapp_open: Open WhatsApp Web (no args)\n"
            "- whatsapp_check_unread: Check WHICH contacts have unread WhatsApp messages and how many (no args). Does NOT return message text.\n"
            "- whatsapp_read_unread: Open each unread WhatsApp chat and read the actual message TEXT (args optional: {\"max_chats\": 5, \"max_messages_per_chat\": 5})\n"
            "- whatsapp_read_chat: Open a SPECIFIC WhatsApp chat by contact name and read the last messages with timestamps (args: {\"contact\": \"Faizan\", \"max_messages\": 5}). Use when user asks 'what did X say', 'last message from X', or wants to read messages from one specific contact.\n"
            "- whatsapp_search_contact: Look up a phone number or contact name in WhatsApp Web to find out who it belongs to (args: {\"query\": \"9315878702\"}). Use when user asks 'batao X kiska number hai', 'who is this number on WhatsApp', 'search number on WhatsApp'.\n"
            "- email_read_inbox: Read recent emails from inbox (args optional: {\"limit\": 10, \"folder\": \"INBOX\"}). Returns list with sequence numbers, subjects, and senders.\n"
            "- email_search: Search emails by keyword in from/subject/body (args: {\"query\": \"...\", \"field\": \"from\", \"folder\": \"INBOX\"}). Use field='from' to find emails from a person/domain, field='subject' for titles, field='body' for body text, field='all' for everything.\n"
            "- email_read: Read full content of a specific email by sequence number (args: {\"seq_num\": 1}). Shows sender, subject, date, and body.\n"
            "- email_read_matching: Find and read the latest email matching a query (args: {\"query\": \"galgotias\", \"field\": \"from\"}). Use instead of email_search+email_read when you want the most recent matching email in one step.\n"
            "- email_status: Check if email is configured and connected (no args).\n"
            "- calendar_list_events: List upcoming events from Google Calendar (args optional: {\"max_results\": 10, \"calendar_id\": \"primary\"}).\n"
            "- calendar_create_event: Create a new event on Google Calendar (args: {\"summary\": \"...\", \"start_datetime\": \"2026-07-01T10:00:00\", \"end_datetime\": \"2026-07-01T11:00:00\", \"description\": \"...\", \"location\": \"...\"}).\n"
            "- calendar_list_calendars: List all Google Calendars (no args).\n"
            "- ask_user: Ask the user a question (args: {\"question\": \"...\"})\n"
            "If no tool is needed, leave TOOL empty.\n"
            "ROUTING RULES:\n"
            "- 'send message/hii/hello to X on whatsapp' → whatsapp_send with phone='X' (where X can be a name or a number)\n"
            "- 'send whatsapp to +91XXXXXXXXXX' → whatsapp_send\n"
            "- 'open whatsapp' → whatsapp_open\n"
            "- 'open whatsapp chat with X' → whatsapp_open_chat with phone='X'\n"
            "- 'check/how many unread messages on whatsapp' (count/who only) → whatsapp_check_unread\n"
            "- 'read my unread messages/show me unread whatsapp messages' (wants actual text from multiple unread chats) → whatsapp_read_unread\n"
            "- 'batao X kiska number hai / who is number X / search contact X on whatsapp' → whatsapp_search_contact with query='X'\n"
            "- 'what did X say/last message from X/read messages from X/dikhao X ne kya bheja/dekho X se baat' (wants messages from a specific contact) → whatsapp_read_chat with contact='X'\n"
            "- 'search X in browser' → search_in_browser\n"
            "- 'open whatsapp.com/youtube.com/etc' → browse_url with the website URL\n"
            "- 'open brave/browser' → open_app with app_name='brave browser'\n"
            "- 'search X' (no browser mention) → web_search (returns text, no browser)\n"
            "- 'read my emails/check inbox/show recent emails/dikhao emails/inbox dikhao' → email_read_inbox\n"
            "- 'search emails for X/find email about X/koi email hai X ke baare mein' → email_search with query='X'\n"
            "- 'check email from X/email from college/parents/school aaya/koi email aaya X se' → email_read_matching with query='X' and field='from'\n"
            "- 'check class schedule from college/read schedule from X and add to calendar' — multi-step: first email_read_matching with query='X' and field='from', then after reading the schedule content, create events using calendar_create_event for each day/time.\n"
            "- 'read latest email from X' → email_read_matching with query='X' and field='from'\n"
            "- 'read email number X/padho email number X/email number X dikhao' → email_read with seq_num=X\n"
            "- 'check email status/email configured hai' → email_status\n"
            "- 'add event to calendar/calendar mein event add karo/create reminder/reminder set karo' → calendar_create_event with summary, start_datetime, end_datetime\n"
            "- 'dikhao calendar/show my events/kya schedule hai/upcoming events' → calendar_list_events\n"
            "- 'list calendars/calendar list' → calendar_list_calendars\n"
            "Example:\n1 | Send WhatsApp message | whatsapp_send | {\"phone\": \"mohit\", \"message\": \"hii\"}\n"
            "2 | Open WhatsApp Web | whatsapp_open | {}\n"
            "3 | Check unread WhatsApp messages | whatsapp_check_unread | {}\n"
            "4 | Read unread WhatsApp messages | whatsapp_read_unread | {}"
        )
        try:
            resp = await self.llm.generate([
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
            if "NO_PLANNING_NEEDED" in resp:
                return []
            steps = self._parse_steps(resp)
            return steps if steps else [Step(id="1", description=goal)]
        except Exception:
            return []

    async def replan(self, failed_step: Step, error: str) -> list[Step]:
        if not self.llm:
            return []
        prompt = (
            f"Step '{failed_step.id}: {failed_step.description}' failed with error:\n{error}\n\n"
            "Suggest alternative steps to recover. Format: STEP_ID | DESCRIPTION | TOOL | ARGS_JSON"
        )
        try:
            resp = await self.llm.generate([
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
            return self._parse_steps(resp)
        except Exception:
            return []

    def _parse_steps(self, text: str) -> list[Step]:
        import json
        steps = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|", 3)]
            if len(parts) >= 2:
                step_id = parts[0].strip()
                description = parts[1]
                tool = parts[2] if len(parts) > 2 else ""
                args = {}
                if len(parts) > 3:
                    try:
                        args = json.loads(parts[3])
                    except (json.JSONDecodeError, ValueError):
                        args = {"input": parts[3]}
                steps.append(Step(id=step_id, description=description, tool=tool, args=args))
        return steps
