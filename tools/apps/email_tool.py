import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.header import decode_header


class EmailTool:
    def __init__(self):
        self.imap = None
        self.smtp = None

    def _decode_hdr(self, raw):
        parts = decode_header(raw)
        return " ".join(
            p.decode(c or "utf-8", errors="replace") if isinstance(p, bytes) else str(p)
            for p, c in parts
        )

    def _decode_body(self, part):
        try:
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
        except Exception:
            return ""

    def connect(self, imap_server, user, password):
        try:
            self.imap = imaplib.IMAP4_SSL(imap_server)
            self.imap.login(user, password)
            return f"Connected to {user} via {imap_server}"
        except Exception as e:
            return f"Error: {e}"

    def list_inbox(self, limit=10):
        if not self.imap:
            return "Not connected"
        try:
            self.imap.select("INBOX")
            _, msg_ids = self.imap.search(None, "ALL")
            ids = msg_ids[0].split()[-limit:]
            messages = []
            for seq in ids:
                _, data = self.imap.fetch(seq, "(RFC822)")
                raw = email.message_from_bytes(data[0][1])
                messages.append({
                    "id": seq.decode(),
                    "from": self._decode_hdr(raw["From"]),
                    "subject": self._decode_hdr(raw["Subject"] or "(No subject)"),
                    "date": raw["Date"],
                })
            return messages
        except Exception as e:
            return f"Error: {e}"

    def read(self, id):
        if not self.imap:
            return "Not connected"
        try:
            self.imap.select("INBOX")
            _, data = self.imap.fetch(id.encode(), "(RFC822)")
            raw = email.message_from_bytes(data[0][1])
            parts = []
            if raw.is_multipart():
                for part in raw.walk():
                    if part.get_content_type() == "text/plain":
                        parts.append(self._decode_body(part))
            else:
                parts.append(self._decode_body(raw))
            return {
                "from": self._decode_hdr(raw["From"]),
                "to": self._decode_hdr(raw["To"]) if raw["To"] else "",
                "subject": self._decode_hdr(raw["Subject"] or "(No subject)"),
                "date": raw["Date"],
                "body": "\n".join(parts)[:5000],
            }
        except Exception as e:
            return f"Error: {e}"

    def send(self, smtp_server, to, subject, body, user=None, password=None):
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["To"] = to
            if user:
                msg["From"] = user
            with smtplib.SMTP_SSL(smtp_server) as server:
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
            return f"Email sent to {to}"
        except Exception as e:
            return f"Error: {e}"
