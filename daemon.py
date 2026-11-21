import sys
import os
import signal
import threading
import time
import asyncio
from typing import Any
from pathlib import Path
from dotenv import load_dotenv

# Prioritize global config in ~/.jarvis/.env, then package directory, then local CWD
global_env = Path.home() / ".jarvis" / ".env"
pkg_env = Path(__file__).parent / ".env"
if global_env.exists():
    load_dotenv(global_env)
if pkg_env.exists():
    load_dotenv(pkg_env)
load_dotenv()

from core.event_bus import event_bus, EVENTS
from core.config import load_config, CONFIG_DIR, LOGS_DIR
from core.session import session_manager

import logging
logger = logging.getLogger('jarvis.daemon')


class Daemon:
    def __init__(self):
        self.config = load_config()
        self.running = False
        self.services: dict[str, Any] = {}
        self._threads: list[threading.Thread] = []
        self._shutdown_event = threading.Event()

    def setup_logging(self):
        global logger
        log_level = self.config.get('log_level', 'INFO')
        log_file = LOGS_DIR / 'jarvis.log'

        import logging
        root = logging.getLogger()
        root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        fmt = logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)s | %(message)s')

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(fmt)
        console_handler.setLevel(logging.WARNING)
        root.addHandler(console_handler)

        logger = logging.getLogger('jarvis.daemon')
        logger.info(f"Jarvis daemon starting. Log: {log_file}")

    def init_llm(self):
        from llm.router import LLMRouter
        self.services['llm'] = LLMRouter(self.config)
        logger.info("LLM router initialized")

    def init_memory(self):
        from memory.memory_manager import MemoryManager
        self.services['memory'] = MemoryManager(self.config)
        logger.info("Memory manager initialized")

    def init_tools(self):
        from tools.registry import ToolRegistry
        registry = ToolRegistry()
        self._register_all_tools(registry)
        self.services['tools'] = registry
        logger.info(f"Tool registry initialized with {len(registry._tools)} tools")

    def _register_all_tools(self, registry):
        import functools
        tool_defs = []

        try:
            from tools.web.search import WebSearchTool
            _inst = WebSearchTool()
            tool_defs.append({
                'name': 'web_search',
                'description': 'Search the web for information',
                'handler': functools.partial(WebSearchTool.search, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {'query': {'type': 'string', 'description': 'Search query'}},
                    'required': ['query'],
                },
            })
        except Exception as e:
            logger.warning(f"WebSearchTool not loaded: {e}")

        try:
            from tools.web.scraper import ScraperTool
            _inst = ScraperTool()
            tool_defs.append({
                'name': 'web_fetch',
                'description': 'Fetch and extract content from a web page',
                'handler': functools.partial(ScraperTool.fetch, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {'url': {'type': 'string', 'description': 'Page URL'}},
                    'required': ['url'],
                },
            })
        except Exception as e:
            logger.warning(f"ScraperTool not loaded: {e}")

        try:
            from tools.os.shell import ShellTool
            _inst = ShellTool()
            tool_defs.append({
                'name': 'shell_exec',
                'description': 'Execute a shell command (use as fallback only)',
                'handler': functools.partial(ShellTool.run, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'command': {'type': 'string', 'description': 'Shell command'},
                        'background': {'type': 'boolean', 'description': 'Whether to run the command in the background (default: false)'},
                    },
                    'required': ['command'],
                },
            })
        except Exception:
            pass

        try:
            from tools.system import SystemTool
            _inst = SystemTool()
            tool_defs.append({
                'name': 'open_app',
                'description': 'Open a desktop application by name (calculator, clock, browser, brave, terminal, settings, files, editor, vlc, telegram)',
                'handler': functools.partial(SystemTool.open_app, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {'app_name': {'type': 'string', 'description': 'Application name (e.g. brave browser, calculator, terminal)'}},
                    'required': ['app_name'],
                },
            })
            tool_defs.append({
                'name': 'browse_url',
                'description': 'Open a specific URL in the browser (brave-browser). Use for opening websites like whatsapp.com, youtube.com, etc.',
                'handler': functools.partial(SystemTool.browse_url, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {'url': {'type': 'string', 'description': 'Full URL to open (e.g. https://web.whatsapp.com)'}},
                    'required': ['url'],
                },
            })
            tool_defs.append({
                'name': 'search_in_browser',
                'description': 'Google-search for a query and open results in the browser. Use when user says "search X in browser" or "open X in browser".',
                'handler': functools.partial(SystemTool.search_in_browser, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {'query': {'type': 'string', 'description': 'Search query (e.g. whatsapp web)'}},
                    'required': ['query'],
                },
            })
            tool_defs.append({
                'name': 'screenshot',
                'description': 'Take a screenshot of the current screen',
                'handler': functools.partial(SystemTool.screenshot, _inst),
                'parameters': {'type': 'object', 'properties': {}},
            })
            tool_defs.append({
                'name': 'list_browser_tabs',
                'description': 'List all open tabs in the Brave browser via CDP remote debugging',
                'handler': functools.partial(SystemTool.list_browser_tabs, _inst),
                'parameters': {'type': 'object', 'properties': {}},
            })
        except Exception:
            pass


        try:
            from tools.os.file_manager import FileManagerTool
            _inst = FileManagerTool()
            tool_defs.append({
                'name': 'read_file',
                'description': 'Read a file from the filesystem',
                'handler': functools.partial(FileManagerTool.read, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {'path': {'type': 'string', 'description': 'File path'}},
                    'required': ['path'],
                },
            })
            tool_defs.append({
                'name': 'write_file',
                'description': 'Write content to a file',
                'handler': functools.partial(FileManagerTool.write, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'path': {'type': 'string', 'description': 'File path'},
                        'content': {'type': 'string', 'description': 'File content'},
                    },
                    'required': ['path', 'content'],
                },
            })
            tool_defs.append({
                'name': 'list_directory',
                'description': 'List contents of a directory',
                'handler': functools.partial(FileManagerTool.list, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {'path': {'type': 'string', 'description': 'Directory path'}},
                },
            })
        except Exception:
            pass

        try:
            from tools.system.monitor import SystemMonitor
            _inst = SystemMonitor()
            tool_defs.append({
                'name': 'system_info',
                'description': 'Get system information (CPU, memory, disk)',
                'handler': functools.partial(SystemMonitor.all_stats, _inst),
                'parameters': {'type': 'object', 'properties': {}},
            })
        except Exception:
            pass

        try:
            from tools.code.executor import CodeExecutor
            _inst = CodeExecutor()
            tool_defs.append({
                'name': 'run_python',
                'description': 'Execute Python code in a sandbox',
                'handler': functools.partial(CodeExecutor.run_python, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {'code': {'type': 'string', 'description': 'Python code'}},
                    'required': ['code'],
                },
            })
        except Exception:
            pass

        try:
            from tools.os.clipboard import ClipboardTool
            _inst = ClipboardTool()
            tool_defs.append({
                'name': 'clipboard_read',
                'description': 'Read text from clipboard',
                'handler': functools.partial(ClipboardTool.read, _inst),
                'parameters': {'type': 'object', 'properties': {}},
            })
            tool_defs.append({
                'name': 'clipboard_write',
                'description': 'Write text to clipboard',
                'handler': functools.partial(ClipboardTool.write, _inst),
                'parameters': {
                    'type': 'object',
                    'properties': {'text': {'type': 'string', 'description': 'Text to copy'}},
                    'required': ['text'],
                },
            })
        except Exception:
            pass

        try:
            from tools.os.process_manager import ProcessManagerTool
            _inst = ProcessManagerTool()
            tool_defs.append({
                'name': 'process_list',
                'description': 'List running processes',
                'handler': functools.partial(ProcessManagerTool.list, _inst),
                'parameters': {'type': 'object', 'properties': {}},
            })
        except Exception:
            pass

        try:
            from tools.messaging.whatsapp import WhatsAppTool
            _wa = WhatsAppTool()
            tool_defs.append({
                'name': 'whatsapp_send',
                'description': (
                    'Send a WhatsApp message to a phone number. '
                    'Opens WhatsApp Web with the message pre-filled (user clicks Send), '
                    'or sends automatically if Playwright is available.'
                ),
                'handler': functools.partial(WhatsAppTool.send_message, _wa),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'phone':   {'type': 'string', 'description': 'Phone number with country code, e.g. +919315878702 or 9315878702'},
                        'message': {'type': 'string', 'description': 'Message text to send'},
                    },
                    'required': ['phone', 'message'],
                },
            })
            tool_defs.append({
                'name': 'whatsapp_send_file',
                'description': (
                    'Send a document, PDF, image, video, or any file to a phone number or contact on WhatsApp Web, '
                    'with an optional caption.'
                ),
                'handler': functools.partial(WhatsAppTool.send_file, _wa),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'phone':     {'type': 'string', 'description': 'Phone number with country code (e.g. +919315878702) or contact name'},
                        'file_path': {'type': 'string', 'description': 'Absolute or relative path to the file/image/document/pdf to send'},
                        'caption':   {'type': 'string', 'description': 'Optional caption or message text to accompany the file'},
                    },
                    'required': ['phone', 'file_path'],
                },
            })
            tool_defs.append({
                'name': 'whatsapp_open_chat',
                'description': 'Open a WhatsApp chat with a phone number in the browser (without sending a message)',
                'handler': functools.partial(WhatsAppTool.open_chat, _wa),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'phone': {'type': 'string', 'description': 'Phone number, e.g. +919315878702'},
                    },
                    'required': ['phone'],
                },
            })
            tool_defs.append({
                'name': 'whatsapp_open',
                'description': 'Open WhatsApp Web in the browser',
                'handler': functools.partial(WhatsAppTool.open_whatsapp, _wa),
                'parameters': {'type': 'object', 'properties': {}},
            })
            tool_defs.append({
                'name': 'whatsapp_check_unread',
                'description': 'Check for unread WhatsApp messages. Reads contact names and unread counts using Playwright.',
                'handler': functools.partial(WhatsAppTool.check_unread, _wa),
                'parameters': {'type': 'object', 'properties': {}},
            })
            tool_defs.append({
                'name': 'whatsapp_read_unread',
                'description': (
                    'Open each unread WhatsApp chat and read back the actual message text '
                    '(not just the unread count). Use when the user asks to "read" unread '
                    'messages, as opposed to just checking how many there are.'
                ),
                'handler': functools.partial(WhatsAppTool.read_unread_messages, _wa),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'max_chats': {'type': 'integer', 'description': 'Max number of unread chats to open and read (default 5)'},
                        'max_messages_per_chat': {'type': 'integer', 'description': 'Max number of recent messages to read per chat (default 5)'},
                    },
                },
            })
            tool_defs.append({
                'name': 'whatsapp_read_chat',
                'description': (
                    'Open a specific WhatsApp chat by contact name and read the last messages '
                    'with timestamps. Use when the user asks "what did X say" or "last message '
                    'from X" or wants to read messages from a specific contact, regardless of '
                    'whether they have unread messages.'
                ),
                'handler': functools.partial(WhatsAppTool.read_chat, _wa),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'contact': {'type': 'string', 'description': 'Contact name to read messages from (e.g., "Faizan", "mohit")'},
                        'max_messages': {'type': 'integer', 'description': 'Number of recent messages to read (default 5)'},
                    },
                    'required': ['contact'],
                },
            })
            tool_defs.append({
                'name': 'whatsapp_search_contact',
                'description': (
                    'Search for a phone number or contact name in WhatsApp Web to find out who it belongs to '
                    'and view their profile/status details.'
                ),
                'handler': functools.partial(WhatsAppTool.search_contact, _wa),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string', 'description': 'Phone number (e.g. "9315878702") or contact name to search on WhatsApp'},
                    },
                    'required': ['query'],
                },
            })
        except Exception as e:
            logger.warning(f"WhatsApp tool not loaded: {e}")


        try:
            from tools.messaging.email import EmailTool
            _et = EmailTool()
            tool_defs.append({
                'name': 'email_read_inbox',
                'description': 'Read recent emails from the inbox. Returns a list with sequence numbers, subjects, and senders.',
                'handler': functools.partial(EmailTool.read_inbox, _et),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'limit': {'type': 'integer', 'description': 'Number of recent emails to fetch (default 10)'},
                        'folder': {'type': 'string', 'description': 'Folder to read from (default INBOX)'},
                    },
                },
            })
            tool_defs.append({
                'name': 'email_search',
                'description': 'Search emails by keyword in from/subject/body. Use field="from" to find emails from a person/domain, field="subject" to search titles, field="body" for body text, or field="all" for everything.',
                'handler': functools.partial(EmailTool.search_emails, _et),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string', 'description': 'Keyword to search for'},
                        'folder': {'type': 'string', 'description': 'Folder to search in (default INBOX)'},
                        'field': {'type': 'string', 'description': 'Search field: "from" (sender, default), "subject", "body", or "all"'},
                    },
                    'required': ['query'],
                },
            })
            tool_defs.append({
                'name': 'email_read',
                'description': 'Read the full content of a specific email by its sequence number (from email_read_inbox or email_search). Shows sender, subject, date, and body.',
                'handler': functools.partial(EmailTool.read_email, _et),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'seq_num': {'type': 'integer', 'description': 'Sequence number of the email to read (e.g., 1, 2, 3)'},
                    },
                    'required': ['seq_num'],
                },
            })
            tool_defs.append({
                'name': 'email_read_matching',
                'description': 'Find the latest email matching a query and read its full content (sender, subject, date, body). Useful when you want to read the most recent email from a person or about a topic without knowing the sequence number.',
                'handler': functools.partial(EmailTool.read_matching, _et),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string', 'description': 'Search query (name, email domain, or keyword)'},
                        'field': {'type': 'string', 'description': 'Search field: "from" (default), "subject", "body", or "all"'},
                        'folder': {'type': 'string', 'description': 'Folder to search in (default INBOX)'},
                    },
                    'required': ['query'],
                },
            })
            tool_defs.append({
                'name': 'email_status',
                'description': 'Check if email is configured and connected. Returns the configured email address or a message asking to set up credentials.',
                'handler': functools.partial(EmailTool.status, _et),
                'parameters': {'type': 'object', 'properties': {}},
            })
        except Exception as e:
            logger.warning(f"Email tool not loaded: {e}")


        try:
            from tools.calendar.google_calendar import GoogleCalendarTool
            _gc = GoogleCalendarTool()
            tool_defs.append({
                'name': 'calendar_list_events',
                'description': 'List upcoming events from Google Calendar. Shows event titles, times, and locations.',
                'handler': functools.partial(GoogleCalendarTool.list_events, _gc),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'max_results': {'type': 'integer', 'description': 'Number of events to show (default 10)'},
                        'calendar_id': {'type': 'string', 'description': 'Calendar ID (default primary)'},
                    },
                },
            })
            tool_defs.append({
                'name': 'calendar_create_event',
                'description': 'Create a new event on Google Calendar. Requires ISO 8601 datetime strings like "2026-07-01T10:00:00".',
                'handler': functools.partial(GoogleCalendarTool.create_event, _gc),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'summary': {'type': 'string', 'description': 'Event title'},
                        'start_datetime': {'type': 'string', 'description': 'Start time in ISO 8601 format, e.g. 2026-07-01T10:00:00'},
                        'end_datetime': {'type': 'string', 'description': 'End time in ISO 8601 format, e.g. 2026-07-01T11:00:00'},
                        'description': {'type': 'string', 'description': 'Event description (optional)'},
                        'location': {'type': 'string', 'description': 'Event location (optional)'},
                        'calendar_id': {'type': 'string', 'description': 'Calendar ID (default primary)'},
                    },
                    'required': ['summary', 'start_datetime', 'end_datetime'],
                },
            })
            tool_defs.append({
                'name': 'calendar_list_calendars',
                'description': 'List all available Google Calendars with their IDs.',
                'handler': functools.partial(GoogleCalendarTool.list_calendars, _gc),
                'parameters': {'type': 'object', 'properties': {}},
            })
        except Exception as e:
            logger.warning(f"Google Calendar tool not loaded: {e}")

        try:
            from tools.code.github_tool import GitHubTool
            _gh_tool = GitHubTool()
            tool_defs.append({
                'name': 'git_status',
                'description': 'Get current Git repository status (active branch, staged/unstaged changes, untracked files, recent commits).',
                'handler': functools.partial(GitHubTool.git_status, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'repo_path': {'type': 'string', 'description': 'Optional repository path (defaults to current directory or detected git root)'},
                    },
                },
            })
            tool_defs.append({
                'name': 'git_diff',
                'description': 'Show git diff of unstaged or staged changes, optionally for a specific file.',
                'handler': functools.partial(GitHubTool.git_diff, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'cached': {'type': 'boolean', 'description': 'Show staged changes (--staged/--cached) if true, unstaged if false'},
                        'file_path': {'type': 'string', 'description': 'Optional file path to limit the diff'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                },
            })
            tool_defs.append({
                'name': 'git_log',
                'description': 'View recent git commit history.',
                'handler': functools.partial(GitHubTool.git_log, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'limit': {'type': 'integer', 'description': 'Number of commits to show (default 10)'},
                        'oneline': {'type': 'boolean', 'description': 'Show one-line summary if true'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                },
            })
            tool_defs.append({
                'name': 'git_commit',
                'description': 'Stage files and create a git commit with a message.',
                'handler': functools.partial(GitHubTool.git_commit, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string', 'description': 'Commit message'},
                        'files': {'type': 'string', 'description': 'Optional specific file(s) to stage (defaults to all files)'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                    'required': ['message'],
                },
            })
            tool_defs.append({
                'name': 'git_push',
                'description': 'Push commits to remote git repository (e.g. origin main).',
                'handler': functools.partial(GitHubTool.git_push, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'branch': {'type': 'string', 'description': 'Branch name to push (optional, pushes current branch by default)'},
                        'remote': {'type': 'string', 'description': 'Remote name (default: origin)'},
                        'set_upstream': {'type': 'boolean', 'description': 'Set upstream (-u) on push'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                },
            })
            tool_defs.append({
                'name': 'git_pull',
                'description': 'Pull latest changes from remote git repository.',
                'handler': functools.partial(GitHubTool.git_pull, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'branch': {'type': 'string', 'description': 'Branch name to pull (optional)'},
                        'remote': {'type': 'string', 'description': 'Remote name (default: origin)'},
                        'rebase': {'type': 'boolean', 'description': 'Use --rebase if true'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                },
            })
            tool_defs.append({
                'name': 'git_branch',
                'description': 'Manage git branches: list all branches, create a branch, delete a branch, or switch to a branch.',
                'handler': functools.partial(GitHubTool.git_branch, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'description': 'Action to perform: "list" (default), "create", "delete", or "switch"'},
                        'branch_name': {'type': 'string', 'description': 'Branch name (required for create, delete, switch)'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                },
            })
            tool_defs.append({
                'name': 'git_checkout',
                'description': 'Switch to a branch or commit (or create a new branch with create=true).',
                'handler': functools.partial(GitHubTool.git_checkout, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'target': {'type': 'string', 'description': 'Branch name or commit hash'},
                        'create': {'type': 'boolean', 'description': 'Create new branch (-b) if true'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                    'required': ['target'],
                },
            })
            tool_defs.append({
                'name': 'git_stash',
                'description': 'Stash uncommitted changes (push, pop, list, drop).',
                'handler': functools.partial(GitHubTool.git_stash, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'description': 'Action: "push" (default), "pop", "list", "drop"'},
                        'message': {'type': 'string', 'description': 'Optional stash message'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                },
            })
            tool_defs.append({
                'name': 'git_clone',
                'description': 'Clone a git repository to local directory.',
                'handler': functools.partial(GitHubTool.git_clone, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'url': {'type': 'string', 'description': 'Git repository URL'},
                        'directory': {'type': 'string', 'description': 'Optional destination directory'},
                    },
                    'required': ['url'],
                },
            })
            tool_defs.append({
                'name': 'git_run',
                'description': 'Run an arbitrary git command directly in the repository.',
                'handler': functools.partial(GitHubTool.git_run, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'command': {'type': 'string', 'description': 'Git command to run (e.g. "remote -v", "tag -l", "reset HEAD~1")'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                    'required': ['command'],
                },
            })
            tool_defs.append({
                'name': 'github_create_pr',
                'description': 'Create a pull request on GitHub via gh CLI.',
                'handler': functools.partial(GitHubTool.github_create_pr, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string', 'description': 'PR title'},
                        'body': {'type': 'string', 'description': 'PR description/body'},
                        'base': {'type': 'string', 'description': 'Base branch (e.g. main)'},
                        'head': {'type': 'string', 'description': 'Head branch (e.g. feature-branch)'},
                        'draft': {'type': 'boolean', 'description': 'Create as draft PR if true'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                    'required': ['title'],
                },
            })
            tool_defs.append({
                'name': 'github_list_prs',
                'description': 'List pull requests on GitHub (state: open, closed, merged, all).',
                'handler': functools.partial(GitHubTool.github_list_prs, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'state': {'type': 'string', 'description': 'PR state: "open" (default), "closed", "merged", "all"'},
                        'limit': {'type': 'integer', 'description': 'Maximum number of PRs to return (default 10)'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                },
            })
            tool_defs.append({
                'name': 'github_view_pr',
                'description': 'View details and comments for a pull request on GitHub.',
                'handler': functools.partial(GitHubTool.github_view_pr, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'pr_number': {'type': 'integer', 'description': 'Pull request number'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                    'required': ['pr_number'],
                },
            })
            tool_defs.append({
                'name': 'github_merge_pr',
                'description': 'Merge a GitHub pull request.',
                'handler': functools.partial(GitHubTool.github_merge_pr, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'pr_number': {'type': 'integer', 'description': 'Pull request number to merge'},
                        'merge_method': {'type': 'string', 'description': 'Merge method: "merge" (default), "squash", or "rebase"'},
                        'delete_branch': {'type': 'boolean', 'description': 'Delete head branch after merge'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                    'required': ['pr_number'],
                },
            })
            tool_defs.append({
                'name': 'github_create_issue',
                'description': 'Create an issue on GitHub.',
                'handler': functools.partial(GitHubTool.github_create_issue, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string', 'description': 'Issue title'},
                        'body': {'type': 'string', 'description': 'Issue description/body'},
                        'labels': {'type': 'string', 'description': 'Comma-separated labels'},
                        'assignees': {'type': 'string', 'description': 'Comma-separated GitHub usernames to assign'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                    'required': ['title'],
                },
            })
            tool_defs.append({
                'name': 'github_list_issues',
                'description': 'List issues on GitHub (state: open, closed, all).',
                'handler': functools.partial(GitHubTool.github_list_issues, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'state': {'type': 'string', 'description': 'Issue state: "open" (default), "closed", "all"'},
                        'limit': {'type': 'integer', 'description': 'Maximum number of issues to return (default 10)'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                },
            })
            tool_defs.append({
                'name': 'github_view_issue',
                'description': 'View details and comments of a GitHub issue.',
                'handler': functools.partial(GitHubTool.github_view_issue, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'issue_number': {'type': 'integer', 'description': 'Issue number'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                    'required': ['issue_number'],
                },
            })
            tool_defs.append({
                'name': 'github_close_issue',
                'description': 'Close a GitHub issue with an optional comment.',
                'handler': functools.partial(GitHubTool.github_close_issue, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'issue_number': {'type': 'integer', 'description': 'Issue number to close'},
                        'comment': {'type': 'string', 'description': 'Optional closing comment'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                    'required': ['issue_number'],
                },
            })
            tool_defs.append({
                'name': 'github_repo_view',
                'description': 'View repository details on GitHub (stars, description, README, URL).',
                'handler': functools.partial(GitHubTool.github_repo_view, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'repo': {'type': 'string', 'description': 'Optional repository owner/name (e.g. Mohit-555/jarvis-ai-agent-cli), defaults to current repository'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                },
            })
            tool_defs.append({
                'name': 'github_run',
                'description': 'Run an arbitrary GitHub CLI ("gh") command.',
                'handler': functools.partial(GitHubTool.github_run, _gh_tool),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'command': {'type': 'string', 'description': 'gh command to run (e.g. "release list", "repo fork")'},
                        'repo_path': {'type': 'string', 'description': 'Optional repository path'},
                    },
                    'required': ['command'],
                },
            })
        except Exception as e:
            logger.warning(f"GitHub tool not loaded: {e}")


        if self.config.get('enable_browser'):
            try:
                from tools.web.browser import BrowserTool
                _inst = BrowserTool()
                tool_defs.append({
                    'name': 'browser_navigate',
                    'description': 'Navigate a web browser to a URL',
                    'handler': functools.partial(BrowserTool.navigate, _inst),
                    'parameters': {
                        'type': 'object',
                        'properties': {'url': {'type': 'string', 'description': 'URL'}},
                        'required': ['url'],
                    },
                })
            except Exception as e:
                logger.warning(f"BrowserTool not loaded: {e}")

        for td in tool_defs:
            registry.register(td)

    def init_skills(self):
        from skills.registry import SkillRegistry
        from skills.executor import SkillExecutor
        registry = SkillRegistry()
        registry.discover()
        executor = SkillExecutor(
            llm_router=self.services.get('llm'),
            tool_registry=self.services.get('tools'),
        )
        self.services['skills'] = registry
        self.services['skill_executor'] = executor
        logger.info(f"Skill system initialized with {registry.count()} skills")

    def _register_skill_tools(self):
        registry = self.services.get('tools')
        skills_registry = self.services.get('skills')
        if not registry or not skills_registry:
            return
        executor = self.services.get('skill_executor')
        if not executor:
            return
        for skill in skills_registry.list_skills():
            if not skill.user_invocable:
                continue
            spec = skill.to_tool_spec()
            if spec:
                import functools
                skill_name = skill.name
                spec['handler'] = functools.partial(self._run_skill, skill_name)
                registry.register(spec)
        logger.info(f"Registered {skills_registry.count()} skills as tools")

    def _run_skill(self, skill_name: str, **kwargs):
        import asyncio
        registry = self.services.get('skills')
        executor = self.services.get('skill_executor')
        if not registry or not executor:
            return "Skill system not available"
        skill = registry.get(skill_name)
        if not skill:
            return f"Skill '{skill_name}' not found"
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(executor.execute(skill, kwargs))
            return result
        except Exception as e:
            return f"Skill execution error: {e}"
        finally:
            loop.close()

    def init_agent(self):
        from agent.executor import AgentExecutor
        agent = AgentExecutor(
            llm_router=self.services.get('llm'),
            tool_registry=self.services.get('tools'),
            session_manager=session_manager,
            config=self.config,
        )
        mode = self.config.get('execution_mode', 'normal')
        agent.set_mode(mode)
        self.services['agent'] = agent
        logger.info(f"Agent executor initialized in {mode} mode")

    def init_api(self):
        if not self.config.get('enable_api'):
            logger.info("API server disabled by config")
            return
        try:
            from api.gateway import APIGateway
            gateway = APIGateway(self.config, self)
            self.services['api'] = gateway
            logger.info(f"API gateway initialized on {self.config.get('api_host')}:{self.config.get('api_port')}")
        except Exception as e:
            logger.warning(f"API gateway not available: {e}")

    def init_scheduler(self):
        if not self.config.get('enable_scheduler'):
            return
        try:
            from scheduler.cron_manager import CronManager
            self.services['scheduler'] = CronManager()
            logger.info("Scheduler initialized")
        except Exception as e:
            logger.warning(f"Scheduler not available: {e}")

    def init_plugins(self):
        try:
            from plugins.loader import PluginLoader
            loader = PluginLoader()
            plugins = loader.load_all()
            self.services['plugins'] = plugins
            if plugins:
                logger.info(f"Loaded {len(plugins)} plugins")
        except Exception as e:
            logger.debug(f"Plugin loader: {e}")

    def start(self):
        self.setup_logging()
        logger.info("=" * 50)
        logger.info("JARVIS DAEMON STARTING")
        logger.info("=" * 50)

        event_bus.emit(EVENTS['SYSTEM_STARTUP'])

        self.init_llm()
        self.init_memory()
        self.init_tools()
        self.init_skills()
        self._register_skill_tools()
        self.init_agent()
        self.init_api()
        self.init_scheduler()
        self.init_plugins()

        self.running = True
        logger.info("Jarvis daemon started successfully")

        api = self.services.get('api')
        if api:
            import uvicorn
            host = self.config.get('api_host', '127.0.0.1')
            port = self.config.get('api_port', 7777)
            t = threading.Thread(
                target=uvicorn.run,
                args=(api.get_app(),),
                kwargs={'host': host, 'port': port, 'log_level': 'info'},
                daemon=True,
            )
            t.start()
            self._threads.append(t)
            logger.info(f"API server running on http://{host}:{port}")

        if self.config.get('enable_gui'):
            try:
                from interface.gui import GUI
                host = self.config.get('api_host', '127.0.0.1')
                gui = GUI(daemon=self, host=host, port=7778)
                t_gui = threading.Thread(
                    target=gui.run,
                    daemon=True,
                )
                t_gui.start()
                self._threads.append(t_gui)
                logger.info(f"GUI server running on http://{host}:7778")
            except Exception as e:
                logger.error(f"Failed to start GUI: {e}")

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self._shutdown_event.wait()

    def _handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def stop(self):
        logger.info("Shutting down Jarvis daemon...")
        self.running = False
        event_bus.emit(EVENTS['SYSTEM_SHUTDOWN'])

        for name, service in self.services.items():
            if hasattr(service, 'close'):
                try:
                    res = service.close()
                    if asyncio.iscoroutine(res):
                        try:
                            loop = None
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                pass
                            if loop and loop.is_running():
                                asyncio.create_task(res)
                            elif loop and not loop.is_closed():
                                loop.run_until_complete(res)
                            else:
                                res.close()
                        except Exception:
                            res.close()
                    logger.debug(f"Closed service: {name}")
                except Exception as e:
                    logger.warning(f"Error closing {name}: {e}")

        self._shutdown_event.set()
        logger.info("Jarvis daemon stopped")

    def get_service(self, name):
        return self.services.get(name)

    def status(self) -> dict:
        return {
            'running': self.running,
            'services': {
                name: {
                    'status': 'running',
                    'type': type(svc).__name__,
                }
                for name, svc in self.services.items()
            },
        }


def run_detection(auto_apply=False):
    from core.config import detect_and_apply_hardware_config, save_config, load_config
    adaptive_config, hw, profile_id = detect_and_apply_hardware_config(verbose=True)

    from rich.console import Console
    from rich.prompt import Confirm
    console = Console()

    should_apply = auto_apply or (sys.stdin.isatty() and Confirm.ask("Apply this hardware-adaptive configuration?"))

    if should_apply:
        cfg = load_config()
        llm_keys = {k: v for k, v in cfg.items() if k in ('llm_provider', 'openai_api_key', 'openai_model', 'openrouter_api_key', 'openrouter_model', 'anthropic_api_key', 'anthropic_model', 'gemini_api_key', 'gemini_model', 'ollama_base_url', 'ollama_model')}
        cfg.update(adaptive_config)
        cfg.update(llm_keys)
        cfg['hardware_profile'] = profile_id
        cfg['hardware_adaptive'] = True
        save_config(cfg)
        console.print("[green]Hardware profile applied and saved.[/]")
    else:
        console.print("[yellow]Configuration not saved.[/]")


if __name__ == '__main__':
    if '--detect' in sys.argv:
        run_detection()
    else:
        daemon = Daemon()
        daemon.start()
