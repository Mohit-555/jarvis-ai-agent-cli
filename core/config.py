import os
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".jarvis"
CONFIG_FILE = CONFIG_DIR / "config.json"
DB_DIR = CONFIG_DIR / "memory"
LOGS_DIR = CONFIG_DIR / "logs"
PLUGINS_DIR = CONFIG_DIR / "plugins"
WORKSPACE_DIR = CONFIG_DIR / "workspace"
UPLOADS_DIR = CONFIG_DIR / "uploads"
KEYS_DIR = CONFIG_DIR / "keys"
SESSIONS_DIR = CONFIG_DIR / "sessions"

try:
    for d in [CONFIG_DIR, DB_DIR, LOGS_DIR, PLUGINS_DIR, WORKSPACE_DIR, UPLOADS_DIR, KEYS_DIR, SESSIONS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
except OSError:
    CONFIG_DIR = Path("/tmp/.jarvis")
    CONFIG_FILE = CONFIG_DIR / "config.json"
    DB_DIR = CONFIG_DIR / "memory"
    LOGS_DIR = CONFIG_DIR / "logs"
    PLUGINS_DIR = CONFIG_DIR / "plugins"
    WORKSPACE_DIR = CONFIG_DIR / "workspace"
    UPLOADS_DIR = CONFIG_DIR / "uploads"
    KEYS_DIR = CONFIG_DIR / "keys"
    SESSIONS_DIR = CONFIG_DIR / "sessions"
    for d in [CONFIG_DIR, DB_DIR, LOGS_DIR, PLUGINS_DIR, WORKSPACE_DIR, UPLOADS_DIR, KEYS_DIR, SESSIONS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "assistant_name": "Jarvis",
    "wake_word": "jarvis",
    "hardware_adaptive": True,
    "hardware_profile": None,
    "device": "cpu",
    "llm_provider": "ollama",
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "llama3.2:3b",
    "openai_api_key": "",
    "openai_model": "gpt-4o-mini",
    "anthropic_api_key": "",
    "anthropic_model": "claude-3-haiku-20240307",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.0-flash",
    "openrouter_api_key": "",
    "openrouter_model": "openai/gpt-4o-mini",
    "opencode_api_key": "",
    "opencode_model": "deepseek-v4-flash-free",
    "stt_model": "tiny",
    "stt_engine": "whisper",
    "tts_engine": "pyttsx3",
    "voice_input": False,
    "voice_output": False,
    "enable_vision": False,
    "enable_browser": False,
    "enable_code_exec": True,
    "enable_web_search": True,
    "enable_system_control": True,
    "enable_memory": True,
    "enable_mcp": False,
    "enable_scheduler": False,
    "execution_mode": "normal",
    "verbose": False,
    "enable_api": False,
    "memory_backend": "chroma",
    "rag_chunk_size": 512,
    "max_concurrent_tools": 1,
    "agent_max_iterations": 5,
    "session_ttl": 1800,
    "api_host": "127.0.0.1",
    "api_port": 7777,
    "web_ui_port": 7778,
    "enable_auth": False,
    "api_key": "",
    "log_level": "INFO",
}


KEY_FIELDS = {
    "openai_api_key",
    "anthropic_api_key",
    "gemini_api_key",
    "openrouter_api_key",
    "opencode_api_key",
    "api_key"
}


def load_config():
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text())
        enc_key = os.environ.get("JARVIS_ENCRYPTION_KEY", "")
        if enc_key:
            try:
                from security.encryption import EncryptionEngine
                engine = EncryptionEngine()
                for field in KEY_FIELDS:
                    val = data.get(field, "")
                    if val and val.startswith("enc::"):
                        data[field] = engine.decrypt_text(enc_key.encode(), val[5:])
            except Exception:
                pass
        return {**DEFAULT_CONFIG, **data}
    return DEFAULT_CONFIG.copy()


def save_config(config):
    data = config.copy()
    enc_key = os.environ.get("JARVIS_ENCRYPTION_KEY", "")
    if enc_key:
        try:
            from security.encryption import EncryptionEngine
            engine = EncryptionEngine()
            for field in KEY_FIELDS:
                val = data.get(field, "")
                if val and not val.startswith("enc::"):
                    data[field] = "enc::" + engine.encrypt_text(enc_key.encode(), val)
        except Exception:
            pass
    CONFIG_FILE.write_text(json.dumps(data, indent=2))
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass


def detect_and_apply_hardware_config(verbose=False):
    from system.hardware_detector import detect_all
    from system.hardware_profile import get_adaptive_config

    hw = detect_all()
    adaptive_config, profile_id, profile = get_adaptive_config(hw)

    if verbose:
        _print_hardware_report(hw, profile_id, profile, adaptive_config)

    return adaptive_config, hw, profile_id


def _print_hardware_report(hw, profile_id, profile, adaptive_config=None):
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    console = Console()

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column(style="white")

    gpu_name = hw['gpu']['name'] or 'None detected'
    gpu_vram = f" ({hw['gpu'].get('vram_gb', 0)}GB VRAM)" if hw['gpu']['available'] else ''
    gpu_line = f"{gpu_name}{gpu_vram}"
    if hw['gpu']['cuda']:
        gpu_line += " [CUDA]"
    elif hw['gpu']['rocm']:
        gpu_line += " [ROCm]"
    elif hw['gpu']['mps']:
        gpu_line += " [MPS]"

    table.add_row("CPU Cores", str(hw['cpu']['cores']))
    table.add_row("RAM", f"{hw['ram']['total_gb']}GB (available: {hw['ram']['available_gb']}GB)")
    table.add_row("GPU", gpu_line)
    table.add_row("Disk", f"{hw['disk']['free_gb']}GB free / {hw['disk']['total_gb']}GB total")
    table.add_row("Platform", f"{hw['platform']['system']} {hw['platform']['release']} ({hw['platform']['machine']})")
    table.add_row("Audio Input", "Yes" if hw['audio']['input'] else "No")
    table.add_row("Ollama", f"Installed ({len(hw['ollama']['models'])} models)" if hw['ollama']['installed'] else "Not installed")
    table.add_row("Docker", "Yes" if hw['docker'] else "No")

    info_lines = [
        f"[bold green]Profile:[/] {profile['label']}",
        f"[bold green]Device:[/] {adaptive_config.get('device', 'cpu').upper()}",
        f"[bold green]LLM:[/] {adaptive_config.get('ollama_model', 'N/A')} via Ollama",
        f"[bold green]STT:[/] whisper-{adaptive_config.get('stt_model', 'tiny')}",
        f"[bold green]TTS:[/] {adaptive_config.get('tts_engine', 'pyttsx3')}",
        f"[bold green]Voice:[/] {'Enabled' if adaptive_config.get('enable_voice') else 'Disabled'}",
        f"[bold green]Vision:[/] {'Enabled' if adaptive_config.get('enable_vision') else 'Disabled'}",
        f"[bold green]Browser:[/] {'Enabled' if adaptive_config.get('enable_browser') else 'Disabled'}",
        f"[bold green]Memory:[/] {adaptive_config.get('memory_backend', 'chroma')}",
    ]

    console.print()
    console.print(Panel.fit("[bold yellow]Jarvis Hardware Detection Report[/]", border_style="yellow"))
    console.print(table)
    console.print(Panel.fit("\n".join(info_lines), title="[bold cyan]Adaptive Configuration[/]", border_style="cyan"))
    console.print()
