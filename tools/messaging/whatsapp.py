import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
from typing import List, Optional, Tuple

BRAVE_CDP_PORT = 9222
PROFILE_DIR = os.path.expanduser("~/.config/BraveSoftware/Brave-Browser")
WHATSAPP_PROFILE = os.path.expanduser("~/.jarvis/whatsapp_profile")

CHAT_SEARCH_SELECTORS = [
    'input[role="textbox"][data-tab="3"]',
    'input[aria-label="Search or start a new chat"]',
]

MESSAGE_INPUT_SELECTORS = [
    'div[contenteditable="true"][aria-label="Type a message"]',
    'div[contenteditable="true"][data-tab="10"]',
    'footer div[contenteditable="true"]',
]

SEND_BUTTON_SELECTORS = [
    'button[aria-label="Send"]',
    'button[data-testid="send"]',
    'span[data-icon="send"]',
    'span[data-icon="wds-ic-send-filled"]',
]

CHAT_ROW_SELECTORS = [
    '#pane-side div[role="row"]',
    'div[role="grid"] div[role="row"]',
    'div[role="row"]',
]

UNREAD_BADGE_SELECTORS = [
    'span[aria-label*="unread message"]',
    '[aria-label*="unread"]',
    '[aria-label*="Unread"]',
]

MESSAGE_BUBBLE_SELECTORS = [
    'span.selectable-text',
    'div[role="row"] span[dir="ltr"]',
    'div[data-pre-plain-text]',
]


def _is_phone_number(val: str) -> bool:
    clean_val = val.strip()
    return not any(c.isalpha() for c in clean_val)


def _normalize_number(phone: str) -> str:
    digits = re.sub(r"[^\d+]", "", phone.strip())
    if digits.startswith("+"):
        return digits.lstrip("+")
    if digits.startswith("91") and len(digits) == 12:
        return digits
    if len(digits) == 10:
        return "91" + digits
    return digits


def _find_browser() -> Optional[str]:
    for b in ["brave-browser", "brave", "google-chrome", "chromium-browser", "chromium"]:
        path = shutil.which(b)
        if path:
            return path
    return None


def _open_browser(url: str) -> bool:
    browser = _find_browser()
    if not browser:
        return False
    subprocess.Popen([browser, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def _ensure_brave_with_cdp():
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sock.connect_ex(('127.0.0.1', BRAVE_CDP_PORT)) == 0:
        sock.close()
        return f"http://127.0.0.1:{BRAVE_CDP_PORT}"
    sock.close()

    browser = _find_browser()
    if not browser:
        return None

    subprocess.run(["pkill", "-f", "brave"], capture_output=True, timeout=5)
    time.sleep(1)

    subprocess.Popen(
        [browser, f"--remote-debugging-port={BRAVE_CDP_PORT}",
         "--no-first-run", "--no-default-browser-check"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    for _ in range(30):
        time.sleep(1)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sock.connect_ex(('127.0.0.1', BRAVE_CDP_PORT)) == 0:
            sock.close()
            return f"http://127.0.0.1:{BRAVE_CDP_PORT}"
        sock.close()

    return None


def _first_visible(page_or_row, selectors: List[str], timeout: int = 1500):
    for sel in selectors:
        try:
            loc = page_or_row.locator(sel).first
            if loc.is_visible(timeout=timeout):
                return loc
        except Exception:
            continue
    return None


def _wait_for_wa_loaded(page, timeout: int = 90000) -> Optional[str]:
    try:
        page.wait_for_selector(
            'canvas, div[role="row"], '
            'button:has-text("Use here"), [role="button"]:has-text("Use here")',
            timeout=timeout,
        )
    except Exception:
        return ("Timed out waiting for WhatsApp Web to load. "
                "Open https://web.whatsapp.com manually in the Brave window once "
                "and scan the QR code, then try again.")

    use_here = _first_visible(page, [
        'button:has-text("Use here")',
        '[role="button"]:has-text("Use here")',
    ], timeout=1000)
    if use_here:
        try:
            use_here.click()
        except Exception:
            try:
                use_here.evaluate("(el) => el.click()")
            except Exception:
                pass
        page.wait_for_timeout(2000)

    qr_canvas = _first_visible(page, ['canvas'], timeout=500)
    if qr_canvas:
        return ("WhatsApp Web is showing a QR code (not logged in on this browser "
                "profile). Open Brave, go to web.whatsapp.com, and scan the QR code "
                "with your phone once, then try again.")

    try:
        page.wait_for_selector('[role="row"], div[contenteditable="true"]', timeout=20000)
    except Exception:
        return "WhatsApp Web loaded but the chat interface never appeared."

    return None


def _open_chat_by_search(page, name_or_query: str) -> Optional[str]:
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    except Exception:
        pass

    search_box = _first_visible(page, CHAT_SEARCH_SELECTORS, timeout=10000)
    if not search_box:
        search_btn = _first_visible(page, ['button[aria-label="Search"]'], timeout=3000)
        if search_btn:
            try:
                search_btn.click()
                page.wait_for_timeout(1000)
                search_box = _first_visible(page, CHAT_SEARCH_SELECTORS, timeout=10000)
            except Exception:
                pass
    if not search_box:
        return (f"Could not find the chat search box (selectors tried: "
                f"{CHAT_SEARCH_SELECTORS}). WhatsApp Web's layout may have "
                f"changed - run scratch/inspect_whatsapp.py to see the current DOM.")

    try:
        search_box.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.wait_for_timeout(200)
        search_box.type(name_or_query, delay=40)
        page.wait_for_timeout(1500)
    except Exception as e:
        return f"Failed to type into the search box: {e}"

    result_rows = []
    for sel in CHAT_ROW_SELECTORS:
        try:
            rows = page.locator(sel).all()
            visible_rows = [r for r in rows if r.is_visible(timeout=200)]
            if visible_rows:
                result_rows = visible_rows
                break
        except Exception:
            continue

    if not result_rows:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return f"No contact found matching '{name_or_query}'."

    def _get_row_name(row) -> str:
        for sel in ['span[title]', 'span[dir="auto"]']:
            try:
                el = row.locator(sel).first
                if el.is_visible(timeout=50):
                    txt = el.get_attribute("title") or el.inner_text()
                    if txt:
                        return txt.strip()
            except Exception:
                continue
        return ""

    target = name_or_query.strip().lower()
    matched_row = None
    for row in result_rows:
        name = _get_row_name(row)
        if name.lower() == target:
            matched_row = row
            break

    if not matched_row:
        for row in result_rows:
            name = _get_row_name(row)
            if target in name.lower():
                matched_row = row
                break

    if not matched_row:
        matched_row = result_rows[0]

    try:
        matched_row.click()
        page.wait_for_timeout(1000)
    except Exception as e:
        return f"Found a result for '{name_or_query}' but could not open it: {e}"

    return None


DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class WhatsAppTool:
    """Send and read WhatsApp messages via WhatsApp Web (CDP + Playwright)."""

    def send_message(self, phone: str, message: str) -> str:
        phone_clean = phone.strip()
        is_num = _is_phone_number(phone_clean)

        if is_num:
            number = _normalize_number(phone_clean)
            if not number:
                return "Invalid phone number provided."
        else:
            number = phone_clean

        result = [None]
        def _run_send():
            result[0] = self._send_playwright(number, message, is_num=is_num)
        t = threading.Thread(target=_run_send, daemon=True)
        t.start()
        t.join(timeout=120)
        result = result[0] or "Playwright automation timed out."
        if result.startswith("Sent"):
            return result

        if is_num:
            return self._send_wame(number, message) + f"\n(Automation note: {result})"

        if _open_browser("https://web.whatsapp.com"):
            return (
                f"Could not automatically send to contact '{number}'.\n"
                f"Reason: {result}\n"
                f"Opened WhatsApp Web in your browser. Please select '{number}' manually and send: \"{message}\""
            )
        return f"No browser found. Reason: {result}"

    def open_chat(self, phone: str) -> str:
        phone_clean = phone.strip()
        is_num = _is_phone_number(phone_clean)

        if is_num:
            number = _normalize_number(phone_clean)
            url = f"https://wa.me/{number}"
            if _open_browser(url):
                return f"Opened WhatsApp for '{phone_clean}'"
            return "No browser found."

        result = [None]
        def _run():
            result[0] = self._open_chat_playwright(phone_clean)
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=90)
        return result[0] or "Timed out opening chat."

    def open_whatsapp(self) -> str:
        if _open_browser("https://web.whatsapp.com"):
            return "Opened WhatsApp Web in browser"
        return "No browser found."

    def check_unread(self) -> str:
        result = []
        def _run():
            result.append(self._check_unread_playwright())
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=120)
        if result:
            return result[0]
        return "Timed out checking for unread messages."

    def read_unread_messages(self, max_chats: int = 5, max_messages_per_chat: int = 5) -> str:
        result = []
        def _run():
            result.append(self._read_unread_messages_playwright(max_chats, max_messages_per_chat))
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=180)
        if result:
            return result[0]
        return "Timed out reading unread messages."

    def read_chat(self, contact: str, max_messages: int = 5) -> str:
        result = []
        def _run():
            result.append(self._read_chat_playwright(contact, max_messages))
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=120)
        if result:
            return result[0]
        return "Timed out reading chat."

    def _send_wame(self, number: str, message: str) -> str:
        encoded = urllib.parse.quote(message)
        url = f"https://wa.me/{number}?text={encoded}"
        if _open_browser(url):
            return (
                f"Opened WhatsApp Web with message pre-filled for +{number}.\n"
                f"Message: \"{message}\"\n"
                f"Click the Send button in the browser to send it."
            )
        return "No browser found. Install brave-browser: sudo apt install brave-browser"

    def _send_playwright(self, number: str, message: str, is_num: bool = True) -> str:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            return "Playwright not available"

        try:
            cdp_url = _ensure_brave_with_cdp()
            if not cdp_url:
                return "Could not start Brave with remote debugging."

            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0]

                if is_num:
                    page = context.new_page()
                    url = f"https://web.whatsapp.com/send?phone={number}&text={urllib.parse.quote(message)}"
                    page.goto(url, timeout=45000)
                else:
                    page = None
                    for existing in context.pages:
                        if "web.whatsapp.com" in existing.url:
                            page = existing
                            break
                    if page is None:
                        page = context.new_page()
                        page.goto("https://web.whatsapp.com", timeout=45000)
                    page.bring_to_front()

                load_err = _wait_for_wa_loaded(page, timeout=90000)
                if load_err:
                    return load_err

                if not is_num:
                    search_err = _open_chat_by_search(page, number)
                    if search_err:
                        return search_err

                msg_box = _first_visible(page, MESSAGE_INPUT_SELECTORS, timeout=20000)
                if not msg_box:
                    return ("Opened the chat but could not find the message input box "
                            "(selectors tried: " + str(MESSAGE_INPUT_SELECTORS) + ").")

                try:
                    msg_box.click()
                    msg_box.type(message, delay=10)
                    page.wait_for_timeout(300)
                except Exception as e:
                    return f"Found the message box but could not type into it: {e}"

                send_btn = _first_visible(page, SEND_BUTTON_SELECTORS, timeout=3000)
                try:
                    if send_btn:
                        send_btn.click()
                    else:
                        page.keyboard.press("Enter")
                    page.wait_for_timeout(2000)
                    return f"Sent WhatsApp message to {number}: \"{message}\""
                except Exception as e:
                    return f"Typed the message but failed to send it: {e}"
        except Exception as e:
            return f"Playwright automation failed: {e}"

    def _open_chat_playwright(self, name_or_query: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return "Playwright not available"

        try:
            cdp_url = _ensure_brave_with_cdp()
            if not cdp_url:
                return "Could not start Brave with remote debugging."

            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0]

                page = None
                for existing in context.pages:
                    if "web.whatsapp.com" in existing.url:
                        page = existing
                        break
                if page is None:
                    page = context.new_page()
                    page.goto("https://web.whatsapp.com", timeout=45000)
                page.bring_to_front()

                load_err = _wait_for_wa_loaded(page)
                if load_err:
                    return load_err

                search_err = _open_chat_by_search(page, name_or_query)
                if search_err:
                    return search_err

                return f"Opened chat with '{name_or_query}'."
        except Exception as e:
            return f"Playwright automation failed: {e}"

    def _check_unread_playwright(self) -> str:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            return "Playwright not available"

        try:
            cdp_url = _ensure_brave_with_cdp()
            if not cdp_url:
                return "Could not start Brave with remote debugging."

            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0]

                wa_page = None
                for page in context.pages:
                    if "web.whatsapp.com" in page.url:
                        wa_page = page
                        break
                if not wa_page:
                    wa_page = context.new_page()
                    wa_page.goto("https://web.whatsapp.com", timeout=45000)
                wa_page.bring_to_front()

                load_err = _wait_for_wa_loaded(wa_page)
                if load_err:
                    return load_err

                unread = self._collect_unread_chats(wa_page)
                if not unread:
                    return "No unread messages found on WhatsApp Web."

                lines = ["Unread WhatsApp Messages:"]
                for contact, count in unread:
                    lines.append(f"  {contact}: {count} unread message(s)")
                return "\n".join(lines)
        except Exception as e:
            return f"Playwright automation failed: {e}"

    def _read_unread_messages_playwright(self, max_chats: int, max_messages_per_chat: int) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return "Playwright not available"

        try:
            cdp_url = _ensure_brave_with_cdp()
            if not cdp_url:
                return "Could not start Brave with remote debugging."

            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0]

                wa_page = None
                for page in context.pages:
                    if "web.whatsapp.com" in page.url:
                        wa_page = page
                        break
                if not wa_page:
                    wa_page = context.new_page()
                    wa_page.goto("https://web.whatsapp.com", timeout=45000)
                wa_page.bring_to_front()

                load_err = _wait_for_wa_loaded(wa_page)
                if load_err:
                    return load_err

                unread = self._collect_unread_chats(wa_page)
                if not unread:
                    return "No unread messages found on WhatsApp Web."

                report = []
                for contact, count in unread[:max_chats]:
                    open_err = _open_chat_by_search(wa_page, contact)
                    if open_err:
                        report.append(f"--- {contact} ({count} unread) ---\n  Could not open chat: {open_err}")
                        continue

                    wa_page.wait_for_timeout(1200)
                    bubbles = []
                    for sel in MESSAGE_BUBBLE_SELECTORS:
                        try:
                            els = wa_page.locator(sel).all()
                            if els:
                                bubbles = els
                                break
                        except Exception:
                            continue

                    if not bubbles:
                        report.append(f"--- {contact} ({count} unread) ---\n  (Could not read message text - chat may use media-only messages, or selectors are stale.)")
                        continue

                    last_texts = []
                    for b in bubbles[-max_messages_per_chat:]:
                        try:
                            t = b.inner_text().strip()
                            if t:
                                last_texts.append(t)
                        except Exception:
                            continue

                    if last_texts:
                        body = "\n".join(f"  {line}" for line in last_texts)
                        report.append(f"--- {contact} ({count} unread) ---\n{body}")
                    else:
                        report.append(f"--- {contact} ({count} unread) ---\n  (No readable text found in the last messages.)")

                if not report:
                    return "Found unread chats but could not read any message content."
                return "\n\n".join(report)
        except Exception as e:
            return f"Playwright automation failed: {e}"

    def _read_chat_playwright(self, contact: str, max_messages: int) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return "Playwright not available"

        try:
            cdp_url = _ensure_brave_with_cdp()
            if not cdp_url:
                return "Could not start Brave with remote debugging."

            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0]

                wa_page = None
                for page in context.pages:
                    if "web.whatsapp.com" in page.url:
                        wa_page = page
                        break
                if not wa_page:
                    wa_page = context.new_page()
                    wa_page.goto("https://web.whatsapp.com", timeout=45000)
                wa_page.bring_to_front()

                load_err = _wait_for_wa_loaded(wa_page)
                if load_err:
                    return load_err

                open_err = _open_chat_by_search(wa_page, contact)
                if open_err:
                    return open_err
                wa_page.wait_for_timeout(1500)

                messages = wa_page.evaluate(
                    f"""
                    () => {{
                        const containers = Array.from(document.querySelectorAll('div[data-pre-plain-text]'));
                        const out = [];
                        for (const c of containers.slice(-{max_messages})) {{
                            const attr = c.getAttribute('data-pre-plain-text') || '';
                            const textSpan = c.querySelector('span.selectable-text');
                            const text = textSpan ? textSpan.innerText.trim() : c.innerText.trim();
                            const timeEl = c.querySelector('span.x1c4vz4f');
                            const time = timeEl ? timeEl.innerText.trim() : '';
                            out.push({{ attr, text, time }});
                        }}
                        if (out.length === 0) {{
                            const spans = Array.from(document.querySelectorAll('span.selectable-text'));
                            for (const s of spans.slice(-{max_messages})) {{
                                const text = s.innerText.trim();
                                if (text) out.push({{ attr: '', text, time: '' }});
                            }}
                        }}
                        return out;
                    }}
                    """
                )

                if not messages:
                    return f"No messages found in chat with '{contact}'."

                lines = [f"--- Last messages with {contact} ---"]
                for m in messages:
                    ts = m.get('time') or ''
                    txt = m.get('text') or ''
                    attr = m.get('attr') or ''
                    if attr:
                        parts = attr.strip('[] ').split(']')
                        if len(parts) > 0:
                            ts = parts[0]
                    if ts and txt:
                        lines.append(f"  [{ts}] {txt}")
                    elif txt:
                        lines.append(f"  {txt}")
                return "\n".join(lines)
        except Exception as e:
            return f"Playwright automation failed: {e}"

    def _collect_unread_chats(self, page) -> List[Tuple[str, str]]:
        rows = []
        for sel in CHAT_ROW_SELECTORS:
            try:
                found = page.locator(sel).all()
                if found:
                    rows = found
                    break
            except Exception:
                continue

        unread_chats = []
        for row in rows:
            try:
                badge = _first_visible(row, UNREAD_BADGE_SELECTORS, timeout=50)
                if not badge:
                    continue

                badge_text = badge.inner_text() or badge.get_attribute("aria-label") or "1"
                count_match = re.search(r"\d+", badge_text)
                unread_count = count_match.group() if count_match else "1"

                name_selectors = ['span[title]', 'span[dir="auto"]', 'div[class*="title"]']
                contact_name = "Unknown Contact"
                for sel in name_selectors:
                    name_el = row.locator(sel).first
                    if name_el.is_visible(timeout=50):
                        contact_name = name_el.get_attribute("title") or name_el.inner_text() or "Unknown Contact"
                        if contact_name != "Unknown Contact":
                            break

                unread_chats.append((contact_name.strip(), unread_count))
            except Exception:
                continue

        return unread_chats
