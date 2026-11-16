class BrowserTool:
    def __init__(self):
        self._page = None
        self._browser = None
        self._playwright = None

    def _ensure_browser(self):
        if self._page is not None:
            return True
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self._page = self._browser.new_page()
            return True
        except Exception:
            return False

    def navigate(self, url):
        if not self._ensure_browser():
            return "Browser not available"
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            return f"Navigated to {url}"
        except Exception as e:
            return f"Error: {e}"

    def screenshot(self):
        if not self._ensure_browser():
            return "Browser not available"
        try:
            path = "/tmp/jarvis_browser_screenshot.png"
            self._page.screenshot(path=path)
            return path
        except Exception as e:
            return f"Error: {e}"

    def click(self, selector):
        if not self._ensure_browser():
            return "Browser not available"
        try:
            self._page.click(selector)
            return f"Clicked {selector}"
        except Exception as e:
            return f"Error: {e}"

    def type(self, selector, text):
        if not self._ensure_browser():
            return "Browser not available"
        try:
            self._page.fill(selector, text)
            return f"Typed into {selector}"
        except Exception as e:
            return f"Error: {e}"

    def get_html(self):
        if not self._ensure_browser():
            return "Browser not available"
        try:
            return self._page.content()
        except Exception as e:
            return f"Error: {e}"

    def close(self):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._page = None
        self._browser = None
        self._playwright = None
