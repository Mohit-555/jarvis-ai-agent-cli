import imaplib
import email
from email.header import decode_header
from agents.base import BaseAgent

SYSTEM_PROMPT = """You are an email assistant. Help the user manage their email.
You can check inbox, read emails, search for specific emails.
Be concise and focus on the information the user needs."""

IMAP_SERVERS = {
    "gmail": "imap.gmail.com",
    "outlook": "imap-mail.outlook.com",
    "yahoo": "imap.mail.yahoo.com",
}


class EmailAgent(BaseAgent):
    name = "email"
    description = "Check emails, read inbox, search and manage email"

    def __init__(self):
        super().__init__()
        self.mail = None

    def get_system_prompt(self):
        return SYSTEM_PROMPT

    def get_tool_defs(self):
        return {
            "connect": ("Connect to IMAP email server", ["email_address", "password", "provider (gmail/outlook/yahoo)"]),
            "fetch_inbox": ("Fetch recent emails from inbox", ["limit (optional, default 10)", "folder (optional)"]),
            "search_emails": ("Search emails by keyword", ["query", "folder (optional)"]),
            "read_email": ("Read full content of an email by sequence number", ["seq_num"]),
        }

    def _decode(self, part):
        try:
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
        except Exception:
            return ""

    def _decode_hdr(self, raw):
        parts = decode_header(raw)
        return " ".join(
            p.decode(c or "utf-8", errors="replace") if isinstance(p, bytes) else str(p)
            for p, c in parts
        )

    def tool_connect(self, args):
        user = args["email_address"]
        password = args["password"]
        provider = args.get("provider", "gmail").lower()
        server = IMAP_SERVERS.get(provider, IMAP_SERVERS["gmail"])
        try:
            self.mail = imaplib.IMAP4_SSL(server)
            self.mail.login(user, password)
            return f"Connected to {user} via {server}"
        except Exception as e:
            return f"Failed: {e}"

    def tool_fetch_inbox(self, args):
        if not self.mail:
            return "Not connected. Use connect first."
        limit = args.get("limit", 10)
        folder = args.get("folder", "INBOX")
        try:
            self.mail.select(folder)
            status, msg_ids = self.mail.search(None, "ALL")
            if status != "OK":
                return "No emails found"
            ids = msg_ids[0].split()[-limit:]
            results = []
            for seq in ids:
                status, data = self.mail.fetch(seq, "(RFC822)")
                if status != "OK":
                    continue
                raw = email.message_from_bytes(data[0][1])
                results.append(
                    f"[{seq.decode()}] {self._decode_hdr(raw['Subject'] or '(No subject)')} - {self._decode_hdr(raw['From'])}"
                )
            return "\n".join(results) if results else "Inbox empty"
        except Exception as e:
            return f"Error: {e}"

    def tool_search_emails(self, args):
        if not self.mail:
            return "Not connected."
        query = args["query"]
        folder = args.get("folder", "INBOX")
        try:
            self.mail.select(folder)
            status, msg_ids = self.mail.search(None, f'BODY "{query}"')
            if status != "OK" or not msg_ids[0]:
                return "No matches"
            ids = msg_ids[0].split()[-10:]
            results = []
            for seq in ids:
                status, data = self.mail.fetch(seq, "(RFC822)")
                raw = email.message_from_bytes(data[0][1])
                results.append(f"[{seq.decode()}] {self._decode_hdr(raw['Subject'])} - {self._decode_hdr(raw['From'])}")
            return "\n".join(results)
        except Exception as e:
            return f"Error: {e}"

    def tool_read_email(self, args):
        if not self.mail:
            return "Not connected."
        seq = str(args["seq_num"])
        try:
            status, data = self.mail.fetch(seq.encode(), "(RFC822)")
            if status != "OK":
                return "Could not fetch"
            raw = email.message_from_bytes(data[0][1])
            parts = []
            if raw.is_multipart():
                for part in raw.walk():
                    if part.get_content_type() == "text/plain":
                        parts.append(self._decode(part))
            else:
                parts.append(self._decode(raw))
            body = "\n".join(parts)[:5000]
            return (
                f"From: {self._decode_hdr(raw['From'])}\n"
                f"Subject: {self._decode_hdr(raw['Subject'])}\n"
                f"Date: {raw['Date']}\n---\n{body}"
            )
        except Exception as e:
            return f"Error: {e}"
