import time
from dataclasses import dataclass, field
from typing import Optional

from core.exceptions import AgentError
from core.logger import central_logger


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

    def get_prompt(self, goal: str = "task", context: str = "") -> str:
        return (
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
            "- scan_project: Intelligently and securely scan a project directory to discover its architecture, entry points (.py, main.py, app.py), dependencies (requirements.txt, pyproject.toml), and file tree while ignoring sensitive dotfiles, browser profiles, and caches (args optional: {\"path\": \".\", \"depth\": 3})\n"
            "- db_query: Execute SQL query on SQLite, MySQL, or Postgres (args: {\"query\": \"SELECT ...\", \"db_type\": \"sqlite\"|\"mysql\"|\"postgres\", \"db_name\": \"...\"})\n"
            "- db_list_tables: List tables in database (args optional: {\"db_type\": \"sqlite\", \"db_name\": \"...\"})\n"
            "- db_export_csv: Export SQL query results to CSV (args: {\"query\": \"SELECT ...\", \"output_path\": \"output.csv\", \"db_name\": \"...\"})\n"
            "- doc_read: Read text from Word (.docx), PDF (.pdf), Excel (.xlsx), or CSV (args: {\"file_path\": \"...\"})\n"
            "- doc_generate: Generate Word (.docx), Excel (.xlsx), PDF (.pdf), or PowerPoint (.pptx) documents (args: {\"doc_type\": \"docx\"|\"xlsx\"|\"pdf\"|\"pptx\", \"output_path\": \"...\", \"title\": \"...\", \"content\": \"...\", \"table_data\": [...]})\n"
            "- doc_convert: Convert document between formats (args: {\"src_path\": \"...\", \"dest_path\": \"...\"})\n"
            "- run_python: Execute Python code (args: {\"code\": \"...\"})\n"
            "- system_info: Get system info (no args needed)\n"
            "- screenshot: Take a screenshot of the current screen (no args needed)\n"
            "- clipboard_read: Read clipboard\n"
            "- clipboard_write: Write clipboard (args: {\"text\": \"...\"})\n"
            "- process_list: List running processes\n"
            "- list_browser_tabs: List all open tabs in the Brave browser with their titles and URLs (no args). Use when user asks 'kaun se tab khule hain', 'kitne tabs hain', 'list browser tabs'.\n"
            "- whatsapp_send: Send a WhatsApp message (args: {\"phone\": \"+91XXXXXXXXXX or contact name\", \"message\": \"...\"})\n"
            "  Use when user says 'send message to X on whatsapp' or 'whatsapp X hello'. The 'phone' argument can be a phone number or a contact name (e.g., 'mohit'). Do not ask for phone number if name is provided.\n"
            "- whatsapp_send_file: Send a document, PDF, image, video, or file on WhatsApp (args: {\"phone\": \"+91XXXXXXXXXX or contact name\", \"file_path\": \"/path/to/file.ext\", \"caption\": \"optional caption\"})\n"
            "  Use when user says 'send file/document/image/photo/pdf to X on whatsapp'.\n"
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
            "- git_status: Get Git status, current branch, changed files, untracked files, recent commits (args optional: {\"repo_path\": \"...\"})\n"
            "- git_diff: Show git diff of unstaged or staged changes (args optional: {\"cached\": true/false, \"file_path\": \"...\"})\n"
            "- git_log: View recent git commits (args optional: {\"limit\": 10, \"oneline\": true/false})\n"
            "- git_commit: Stage files and commit (args: {\"message\": \"commit message\", \"files\": \"file1 file2 (optional)\"})\n"
            "- git_push: Push commits to remote (args optional: {\"branch\": \"main\", \"remote\": \"origin\", \"set_upstream\": false})\n"
            "- git_pull: Pull latest changes from remote (args optional: {\"branch\": \"main\", \"remote\": \"origin\", \"rebase\": false})\n"
            "- git_branch: Manage branches (args optional: {\"action\": \"list\"|\"create\"|\"delete\"|\"switch\", \"branch_name\": \"...\"})\n"
            "- git_checkout: Switch branch or checkout commit (args: {\"target\": \"branch_or_commit\", \"create\": false})\n"
            "- git_stash: Stash changes (args optional: {\"action\": \"push\"|\"pop\"|\"list\", \"message\": \"...\"})\n"
            "- git_clone: Clone repository (args: {\"url\": \"https://github.com/...\", \"directory\": \"...\"})\n"
            "- git_run: Run arbitrary git command (args: {\"command\": \"...\"})\n"
            "- github_create_pr: Create a pull request on GitHub (args: {\"title\": \"...\", \"body\": \"...\", \"base\": \"main\"})\n"
            "- github_list_prs: List pull requests (args optional: {\"state\": \"open\"|\"closed\"|\"all\", \"limit\": 10})\n"
            "- github_view_pr: View details and comments of a PR (args: {\"pr_number\": 1})\n"
            "- github_merge_pr: Merge a pull request (args: {\"pr_number\": 1, \"merge_method\": \"merge\"|\"squash\"|\"rebase\"})\n"
            "- github_create_issue: Create an issue on GitHub (args: {\"title\": \"...\", \"body\": \"...\", \"labels\": \"...\"})\n"
            "- github_list_issues: List issues on GitHub (args optional: {\"state\": \"open\"|\"closed\"|\"all\", \"limit\": 10})\n"
            "- github_view_issue: View details of a GitHub issue (args: {\"issue_number\": 1})\n"
            "- github_close_issue: Close a GitHub issue (args: {\"issue_number\": 1, \"comment\": \"...\"})\n"
            "- github_repo_view: View repository info on GitHub (args optional: {\"repo\": \"owner/repo\"})\n"
            "- github_run: Run arbitrary GitHub CLI command (args: {\"command\": \"...\"})\n"
            "- ask_user: Ask the user an interactive question with selectable options (args: {\"question\": \"...\", \"options\": [\"opt1\", \"opt2\", \"Other\"], \"multiple\": false, \"title\": \"...\"})\n"
            "- get_current_media: Check currently playing song, video, artist, and playback status from YouTube (Chrome/Brave/Firefox), Spotify, VLC, etc. (args optional: {\"player\": \"youtube|spotify|all\"})\n"
            "- media_control: Control media playback (args: {\"action\": \"play_pause|next|previous|stop\"})\n"
            "- play_youtube: Search and play a song, video, or music directly on YouTube in the current browser window (args: {\"query\": \"song or video title\"})\n"
            "If no tool is needed, leave TOOL empty.\n"
            "ROUTING RULES:\n"
            "- 'play song X / gana chalao X / X song chalao / Tum Hi Ho isko chalao / play X on youtube / X chalao / gana bajao X / play music X / song chala do X' → play_youtube with query='X'\n"
            "- CRITICAL MUSIC GUARD: When the user asks to play a song/music or video (e.g. 'Tum Hi Ho isko chalao', 'gana chalao'), NEVER call search_in_browser or Google search. ALWAYS call play_youtube.\n"
            "- 'mai kaun sa gana sun rha hu / kaun sa song chal raha hai / what song is playing / what am I listening to / current song / current video / song batao / gana batao / kya chal raha hai / music batao' → get_current_media\n"
            "- 'youtube pe / spotify pe / youtube per / browser me / youtube par' (when specifying where music is playing or in song context) → get_current_media with player='youtube' or 'spotify' (NEVER call browse_url or search_in_browser)\n"
            "- 'pause song / gana roko / gana pause karo / agla gana / next song / previous song / stop music' → media_control with action='play_pause'|'next'|'previous'|'stop'\n"
            "- CRITICAL GUARD: If the user is asking what song/video is playing, or answering where they are listening to it ('youtube per', 'spotify pe'), NEVER call browse_url, open_app, or search_in_browser. ALWAYS call get_current_media.\n"
            "- 'ask user X / ask me X / first ask X / clarify X / prompt user X / ask what type of X' → ask_user with question='X' and appropriate options\n"
            "- 'git status/check git/repo status/kya changes hain' → git_status\n"
            "- 'git diff/show diff/kya change hua hai' → git_diff\n"
            "- 'git log/show commits/recent commits' → git_log\n"
            "- 'git commit/commit karo/commit changes' → git_commit with message\n"
            "- 'git push/push code/push to github/changes push karo' → git_push\n"
            "- 'git pull/pull changes/pull code/update repo' → git_pull\n"
            "- 'create branch X/nayi branch banao X' → git_branch with action='create' and branch_name='X'\n"
            "- 'switch branch X/checkout branch X' → git_checkout with target='X'\n"
            "- 'list branches/branches dikhao' → git_branch with action='list'\n"
            "- 'clone repo X/git clone X' → git_clone with url='X'\n"
            "- 'create pr/pull request banao' → github_create_pr with title and body\n"
            "- 'list prs/show prs/open prs' → github_list_prs\n"
            "- 'view pr X/pr number X dikhao' → github_view_pr with pr_number=X\n"
            "- 'merge pr X' → github_merge_pr with pr_number=X\n"
            "- 'create issue/issue banao/report issue' → github_create_issue with title and body\n"
            "- 'list issues/open issues' → github_list_issues\n"
            "- 'view issue X/issue X dikhao' → github_view_issue with issue_number=X\n"
            "- 'close issue X' → github_close_issue with issue_number=X\n"
            "- 'repo info/github repo view/details of repo' → github_repo_view\n"
            "- 'send message/hii/hello to X on whatsapp' → whatsapp_send with phone='X' (where X can be a name or a number)\n"
            "- 'send document/file/image/photo/pdf X to Y on whatsapp' → whatsapp_send_file with phone='Y', file_path='X', caption='...'\n"
            "- 'whatsapp pe photo/document/image/pdf/file bhejo' → whatsapp_send_file\n"
            "- 'send whatsapp to +91XXXXXXXXXX' → whatsapp_send\n"
            "- 'open whatsapp' → whatsapp_open\n"
            "- 'open whatsapp chat with X' → whatsapp_open_chat with phone='X'\n"
            "- 'check/how many unread messages on whatsapp' (count/who only) → whatsapp_check_unread\n"
            "- 'read my unread messages/show me unread whatsapp messages' (wants actual text from multiple unread chats) → whatsapp_read_unread\n"
            "- 'batao X kiska number hai / who is number X / search contact X on whatsapp' → whatsapp_search_contact with query='X'\n"
            "- 'kya jarvis ka folder dekh sakte ho / show jarvis folder / list project files / inspect project / scan project / scan codebase / project files dikhao' → scan_project with path='.'\n"
            "- 'list directory / list files in X' → list_directory with path='X'\n"
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
            "- 'query database / run sql / select from table / db query' → db_query with query='...'\n"
            "- 'list tables / show tables / database tables' → db_list_tables\n"
            "- 'export database to csv / export query to csv' → db_export_csv with query and output_path\n"
            "- 'read pdf / read word doc / read docx / read excel / read xlsx' → doc_read with file_path\n"
            "- 'create/generate word document / docx' → doc_generate with doc_type='docx', output_path, title, content\n"
            "- 'create/generate excel / xlsx / spreadsheet' → doc_generate with doc_type='xlsx', output_path, title\n"
            "- 'create/generate pdf report' → doc_generate with doc_type='pdf', output_path, title, content\n"
            "- 'create presentation / pptx / powerpoint' → doc_generate with doc_type='pptx', output_path, title, content\n"
            "- 'convert csv to excel / convert excel to csv / convert to pdf / convert to docx' → doc_convert with src_path and dest_path\n"
            "Example:\n1 | Send WhatsApp message | whatsapp_send | {\"phone\": \"mohit\", \"message\": \"hii\"}\n"
            "2 | Open WhatsApp Web | whatsapp_open | {}\n"
            "3 | Check unread WhatsApp messages | whatsapp_check_unread | {}\n"
            "4 | Read unread WhatsApp messages | whatsapp_read_unread | {}"
        )

    async def plan(self, goal: str, context: str = "") -> list[Step]:
        if not self.llm:
            return [Step(id="1", description=goal, tool="", args={})]
        start_t = time.time()
        central_logger.agent_logger.info(f"Planner started for task: '{goal[:80]}'")
        prompt = self.get_prompt(goal, context)
        try:
            resp = await self.llm.generate([
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
            duration = time.time() - start_t
            if "NO_PLANNING_NEEDED" in resp:
                central_logger.agent_logger.info(f"Planner finished in {duration:.2f}s: NO_PLANNING_NEEDED (conversational)")
                return []
            steps = self._parse_steps(resp)
            final_steps = steps if steps else [Step(id="1", description=goal)]
            central_logger.log_plan_generated(len(final_steps), duration)
            return final_steps
        except Exception as e:
            duration = time.time() - start_t
            central_logger.agent_logger.error(f"Planner error after {duration:.2f}s: {e}")
            return []

    async def replan(self, failed_step: Step, error: str) -> list[Step]:
        if not self.llm:
            return []
        start_t = time.time()
        central_logger.agent_logger.info(f"Replanning for failed step '{failed_step.id}'")
        prompt = (
            f"Step '{failed_step.id}: {failed_step.description}' failed with error:\n{error}\n\n"
            "Suggest alternative steps to recover. Format: STEP_ID | DESCRIPTION | TOOL | ARGS_JSON"
        )
        try:
            resp = await self.llm.generate([
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
            duration = time.time() - start_t
            new_steps = self._parse_steps(resp)
            central_logger.agent_logger.info(f"Replanned {len(new_steps)} recovery steps in {duration:.2f}s")
            return new_steps
        except Exception as e:
            duration = time.time() - start_t
            central_logger.agent_logger.error(f"Replanning error after {duration:.2f}s: {e}")
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
