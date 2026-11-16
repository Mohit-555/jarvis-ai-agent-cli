# Jarvis Agent CLI

Jarvis is a local-first, privacy-focused, autonomous AI assistant and PC controller CLI. It plans and executes complex tasks across your operating system, web browser, file system, messaging apps, and developer tools.

## 🚀 Quick Install

### Method 1: Using pipx (Recommended)
`pipx` installs Jarvis into an isolated environment and makes the command globally available:
```bash
pipx install jarvis-ai-agent-cli
```
or directly from source:
```bash
pipx install .
```

### Method 2: One-Line Installer
```bash
curl -fsSL https://raw.githubusercontent.com/Mohit-555/jarvis-ai-agent-cli/main/scripts/install.sh | bash
```

### Method 3: Standard pip (inside a virtualenv)
```bash
python3 -m venv ~/.jarvis/venv
source ~/.jarvis/venv/bin/activate
pip install -e .
```

## 🎮 Usage

Start the interactive assistant:
```bash
jarvis
# or
jarvis cli
```

Check system status:
```bash
jarvis status
```

Run hardware detection:
```bash
jarvis detect
```

Reconfigure settings and API keys:
```bash
jarvis setup
```

## ⚡ Key Capabilities
- **Desktop & OS Control:** App launcher, process manager, screenshot capture, clipboard read/write.
- **Web & Browser:** Playwright browser automation, CDP tab inspector, page scraper, search.
- **Messaging:** WhatsApp automation (send, read unread, chat history) & IMAP Email.
- **Developer Tools:** Sandboxed Python code executor, shell runner, file reader/writer.
- **Google Calendar:** List and create events.
- **Skills System:** Bundled AI reasoning chains (`research`, `review`, `refactor`, `debug`, etc.).
