import imaplib
import email
import os
from email.header import decode_header

IMAP_SERVERS = {
    "gmail": "imap.gmail.com",
    "outlook": "imap-mail.outlook.com",
    "yahoo": "imap.mail.yahoo.com",
}


class EmailTool:
    def __init__(self):
        self.mail = None
        self._email_address = ""
        self._app_password = ""
        self._provider = "gmail"
        self._load_credentials()

    def _load_credentials(self):
        self._email_address = os.environ.get("EMAIL_ADDRESS", "")
        self._app_password = os.environ.get("EMAIL_APP_PASSWORD", "")
        self._provider = os.environ.get("EMAIL_PROVIDER", "gmail").lower()
        if self._email_address and self._app_password:
            self._connect()

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

    def _ensure_connected(self, folder: str = "INBOX"):
        if self.mail:
            try:
                self.mail.noop()
                self.mail.select(folder)
                return None
            except Exception:
                self.mail = None
        return self._connect(folder)

    def _connect(self, folder: str = "INBOX"):
        server = IMAP_SERVERS.get(self._provider, IMAP_SERVERS["gmail"])
        try:
            self.mail = imaplib.IMAP4_SSL(server)
            self.mail.login(self._email_address, self._app_password)
            self.mail.select(folder)
            return None
        except Exception as e:
            return f"Failed to connect: {e}"

    def read_inbox(self, limit: int = 10, folder: str = "INBOX") -> str:
        err = self._ensure_connected()
        if err:
            return err
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

    def search_emails(self, query: str, folder: str = "INBOX", field: str = "from") -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            self.mail.select(folder)
            search_cmd = self._build_search_cmd(query, field)
            status, msg_ids = self.mail.search(None, search_cmd)
            if status != "OK" or not msg_ids[0]:
                return "No matches found"
            ids = msg_ids[0].split()[-10:]
            results = []
            for seq in ids:
                status, data = self.mail.fetch(seq, "(RFC822)")
                raw = email.message_from_bytes(data[0][1])
                results.append(f"[{seq.decode()}] {self._decode_hdr(raw['Subject'])} - {self._decode_hdr(raw['From'])}")
            return "\n".join(results)
        except Exception as e:
            return f"Error: {e}"

    def _build_search_cmd(self, query: str, field: str = "from") -> str:
        field = field.lower()
        if field == "from":
            return f'FROM "{query}"'
        elif field == "subject":
            return f'SUBJECT "{query}"'
        elif field == "body":
            return f'BODY "{query}"'
        elif field == "all":
            return f'OR FROM "{query}" OR SUBJECT "{query}" BODY "{query}"'
        else:
            return f'BODY "{query}"'

    def read_email(self, seq_num: int, folder: str = "INBOX") -> str:
        err = self._ensure_connected(folder)
        if err:
            return err
        try:
            seq = str(seq_num)
            status, data = self.mail.fetch(seq.encode(), "(RFC822)")
            if status != "OK":
                return "Could not fetch email"
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

    def read_matching(self, query: str, field: str = "from", folder: str = "INBOX") -> str:
        err = self._ensure_connected()
        if err:
            return err
        try:
            self.mail.select(folder)
            search_cmd = self._build_search_cmd(query, field)
            status, msg_ids = self.mail.search(None, search_cmd)
            if status != "OK" or not msg_ids[0]:
                return f"No emails found matching '{query}'."
            ids = msg_ids[0].split()
            latest_seq = ids[-1]
            status, data = self.mail.fetch(latest_seq, "(RFC822)")
            if status != "OK":
                return "Found matching email but could not fetch it."
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

    def status(self) -> str:
        if self._email_address and self._app_password:
            err = self._ensure_connected()
            if err:
                return f"Email configured ({self._email_address}) but disconnected: {err}"
            return f"Connected to {self._email_address}"
        return "Email not configured. Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env"
