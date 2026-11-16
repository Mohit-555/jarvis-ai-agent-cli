# Jarvis Agent: Comprehensive Testing Guide

This guide walks you through testing every capability and tool operation in **Jarvis Agent**, from quick status checks to interactive natural language prompts and automated diagnostics.

---

## 🛠️ Step 0: Environment Preparation

Before testing, open a terminal in the project directory and activate the virtual environment:

```bash
cd /home/mohit-patel/Desktop/my_project/Jarvis/jarvis_agent
source venv/bin/activate
```

### 1. Verify Configuration & Hardware
Run the built-in system status and hardware detection commands:
```bash
# Check detected hardware (CPU, RAM, GPU)
python main.py detect

# Check active configuration and LLM provider
python main.py status
```

---

## 🚀 Step 1: CLI Built-in Slash Commands

Start the interactive CLI session:
```bash
python main.py cli
```

Once inside the interactive prompt `jarvis>`, verify core subsystems using these slash commands:

| Command | Purpose | Expected Output |
| :--- | :--- | :--- |
| `/status` | Check running daemon services | Table showing `llm`, `tools`, `skills`, `memory` status (green/running) |
| `/tools` | List all registered tools | Formatted table listing all 31 registered agent tools |
| `/skills` | List bundled skills | Table with `research`, `review`, `refactor`, `debug`, `generate_test`, `summarize` |
| `/model` | Check / Switch LLM provider | Dialog / prompt showing current provider (Ollama, Gemini, OpenAI, etc.) |
| `/theme` | Switch UI theme | Interactive dialog to choose dark, light, or auto theme |
| `/memory` | Inspect memory state | List of recent conversation memories / context |
| `/help` | Show keyboard shortcuts & help | Shortcut table (`Ctrl+T` for theme, `Ctrl+L` to clear screen) |

---

## 🧪 Step 2: Testing Core Capabilities Interactively

Type each prompt directly into `jarvis>` to test the agent's **Planner**, **Actor**, and **Tool execution loop**.

### 1. Desktop & OS Operations
- **Launch Apps:**
  ```text
  open calculator
  ```
  *(Check: Calculator app opens on your desktop.)*
  ```text
  open terminal
  ```
- **System Information:**
  ```text
  check system info
  ```
  *(Check: Jarvis returns CPU %, RAM usage, and disk space stats.)*
- **Process Management:**
  ```text
  show running processes
  ```
  *(Check: Jarvis returns list of top running processes and PIDs.)*
- **Screenshot:**
  ```text
  take a screenshot
  ```
  *(Check: Screen capture is saved and the file path is returned.)*
- **Clipboard Management:**
  ```text
  write 'Jarvis Test 2026' to clipboard
  ```
  Followed by:
  ```text
  read clipboard
  ```
  *(Check: Jarvis returns `'Jarvis Test 2026'`.)*
- **Shell Execution:**
  ```text
  run command uname -a
  ```
  *(Check: Linux kernel and architecture details are printed.)*

---

### 2. File Management & Code Execution
- **Write File:**
  ```text
  write a short python hello world script to ~/Downloads/test_hello.py
  ```
  *(Check: File `~/Downloads/test_hello.py` is created with valid Python code.)*
- **Read File:**
  ```text
  read file ~/Downloads/test_hello.py
  ```
  *(Check: Content of the newly created file is displayed.)*
- **List Directory:**
  ```text
  list files in ~/Downloads
  ```
- **Sandboxed Python Code Execution:**
  ```text
  run python code print(sum([i**2 for i in range(10)]))
  ```
  *(Check: Jarvis evaluates the code in a sandbox and returns `285`.)*

---

### 3. Web & Browser Operations
- **API Web Search (No browser pop-up):**
  ```text
  search what is quantum computing
  ```
  *(Check: Text summary fetched from DuckDuckGo search.)*
- **Page Content Scraper:**
  ```text
  fetch https://example.com
  ```
  *(Check: Page title and body text of example.com are extracted.)*
- **Browser Navigation (Opens Brave Browser):**
  ```text
  open youtube.com in browser
  ```
  *(Check: Brave opens with YouTube.)*
- **Search in Browser:**
  ```text
  search artificial intelligence in browser
  ```
  *(Check: Browser opens with Google search results.)*
- **Inspect Open Browser Tabs:**
  ```text
  list browser tabs
  ```
  *(Check: Returns active tabs with URLs if browser remote debugging is enabled.)*

---

### 4. Messaging: WhatsApp Automation
> *Note: WhatsApp uses Playwright or WhatsApp Web. Ensure you are logged into WhatsApp Web on your default browser.*

- **Open WhatsApp:**
  ```text
  open whatsapp
  ```
- **Send Message (Phone number or Contact name):**
  ```text
  send hello to +91XXXXXXXXXX on whatsapp
  ```
- **Check Unread Messages:**
  ```text
  how many unread messages on whatsapp
  ```
- **Read Unread Message Text:**
  ```text
  read my unread messages on whatsapp
  ```
- **Read Specific Chat History:**
  ```text
  what did Faizan say on whatsapp
  ```

---

### 5. Email Management (IMAP / SMTP)
> *Note: Requires `EMAIL_ADDRESS` and `EMAIL_APP_PASSWORD` in `jarvis_agent/.env`.*

- **Check Connection Status:**
  ```text
  check email status
  ```
- **Read Inbox:**
  ```text
  read my emails
  ```
  *(Check: Returns sequence numbers, senders, and subject lines.)*
- **Search Emails:**
  ```text
  search emails for college
  ```
- **Read Specific Email by Number:**
  ```text
  read email number 1
  ```
- **Search and Read Latest Matching:**
  ```text
  check email from Google
  ```

---

### 6. Google Calendar Operations
> *Note: Requires Google OAuth setup in `tools/calendar/credentials.json`.*

- **List Calendars:**
  ```text
  list my google calendars
  ```
- **List Upcoming Events:**
  ```text
  list upcoming events on calendar
  ```
- **Schedule an Event:**
  ```text
  add a meeting 'Sprint Review' tomorrow from 11:00 to 12:00
  ```

---

### 7. Bundled Skills Execution
Skills combine prompts and tools into multi-step workflows. Run them directly using `/run <skill> <target>`:

```text
/run research "Latest advancements in multimodal AI"
/run review "tools/os/shell.py"
/run generate_test "tools/os/clipboard.py"
/run summarize "jarvis_ai_architecture.txt"
```

---

## ⚡ Step 3: Automated Diagnostic Script

To test all tools automatically without typing prompts one-by-one, you can run this quick diagnostic script.

Create and run `test_diagnostic.py` in `jarvis_agent/`:

```bash
python -c "
import sys
sys.path.insert(0, '.')
from daemon import Daemon

daemon = Daemon()
daemon.init_tools()
registry = daemon.services.get('tools')

print(f'\nTotal Tools Registered: {len(registry._tools)}')
print('=' * 50)

# Test 1: System Info
try:
    info = registry.call('system_info')
    print('✅ system_info: PASS (CPU: {}%)'.format(info.get('cpu_percent')))
except Exception as e:
    print('❌ system_info: FAIL -', e)

# Test 2: Clipboard
try:
    registry.call('clipboard_write', text='DiagTest')
    txt = registry.call('clipboard_read')
    assert 'DiagTest' in txt
    print('✅ clipboard: PASS')
except Exception as e:
    print('❌ clipboard: FAIL -', e)

# Test 3: Python Execution
try:
    res = registry.call('run_python', code='print(7 * 6)')
    assert '42' in str(res)
    print('✅ run_python: PASS')
except Exception as e:
    print('❌ run_python: FAIL -', e)

# Test 4: File Operations
try:
    registry.call('write_file', path='/tmp/jarvis_diag.txt', content='diag_ok')
    content = registry.call('read_file', path='/tmp/jarvis_diag.txt')
    assert 'diag_ok' in content
    print('✅ file_manager: PASS')
except Exception as e:
    print('❌ file_manager: FAIL -', e)

# Test 5: Shell Exec
try:
    out = registry.call('shell_exec', command='echo \"jarvis_shell_ok\"')
    assert 'jarvis_shell_ok' in out
    print('✅ shell_exec: PASS')
except Exception as e:
    print('❌ shell_exec: FAIL -', e)

# Test 6: Web Search
try:
    res = registry.call('web_search', query='Python programming')
    print('✅ web_search: PASS')
except Exception as e:
    print('⚠️ web_search: SKIPPED/FAIL (requires network) -', e)

print('=' * 50)
print('Diagnostic Complete!')
"
```

---

## 🌐 Step 4: Web GUI Mode (Optional)

If you wish to test Jarvis with a visual browser interface:

```bash
python main.py start --web --gui --port 7777
```
Then navigate to `http://127.0.0.1:7777` in your browser.
