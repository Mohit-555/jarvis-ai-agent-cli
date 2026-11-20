#!/usr/bin/env python3
import sys
import argparse
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, str(Path(__file__).parent))

from banner import print_banner

def print_banner_cmd():
    from core.config import load_config
    cfg = load_config()
    provider = cfg.get('llm_provider', 'ollama')
    model = cfg.get(f'{provider}_model', '')
    device = cfg.get('device', 'cpu')
    print_banner(version='2.1', provider=provider, model=model, device=device)


def cmd_detect(args=None):
    from daemon import run_detection
    auto_apply = getattr(args, 'yes', False) if args else False
    run_detection(auto_apply=auto_apply)


def cmd_start(args):
    from core.config import load_config
    from daemon import Daemon

    cfg = load_config()
    if getattr(args, 'power', False):
        cfg['execution_mode'] = 'power'
    if getattr(args, 'verbose', False):
        cfg['verbose'] = True

    if cfg.get('hardware_adaptive', True):
        from core.config import detect_and_apply_hardware_config
        try:
            llm_keys = {k: v for k, v in cfg.items() if k in ('llm_provider', 'openai_api_key', 'openai_model', 'openrouter_api_key', 'openrouter_model', 'anthropic_api_key', 'anthropic_model', 'gemini_api_key', 'gemini_model', 'ollama_base_url', 'ollama_model')}
            verbose_hw = getattr(args, 'verbose', False)
            adaptive, hw, profile_id = detect_and_apply_hardware_config(verbose=verbose_hw)
            cfg.update(adaptive)
            cfg.update(llm_keys)
            cfg['hardware_profile'] = profile_id
        except Exception as e:
            print(f"Hardware detection warning: {e}")

    daemon = Daemon()
    daemon.config = cfg

    if args.gui or args.web:
        cfg['enable_api'] = True
        if args.gui:
            cfg['enable_gui'] = True
        daemon.start()
    else:
        daemon.start()


def cmd_cli(args):
    from core.config import load_config, detect_and_apply_hardware_config
    from core.session import session_manager
    from daemon import Daemon

    cfg = load_config()
    if getattr(args, 'power', False):
        cfg['execution_mode'] = 'power'
    if getattr(args, 'verbose', False):
        cfg['verbose'] = True

    if cfg.get('hardware_adaptive', True):
        try:
            llm_keys = {k: v for k, v in cfg.items() if k in ('llm_provider', 'openai_api_key', 'openai_model', 'openrouter_api_key', 'openrouter_model', 'anthropic_api_key', 'anthropic_model', 'gemini_api_key', 'gemini_model', 'ollama_base_url', 'ollama_model')}
            verbose_hw = getattr(args, 'verbose', False)
            adaptive, hw, profile_id = detect_and_apply_hardware_config(verbose=verbose_hw)
            cfg.update(adaptive)
            cfg.update(llm_keys)
            cfg['hardware_profile'] = profile_id
        except Exception as e:
            print(f"Hardware detection warning: {e}")

    daemon = Daemon()
    daemon.config = cfg
    daemon.setup_logging()
    daemon.init_llm()
    daemon.init_memory()
    daemon.init_tools()
    daemon.init_skills()
    daemon._register_skill_tools()
    daemon.init_agent()

    from cli import JarvisCLI
    cli = JarvisCLI(daemon=daemon)
    cli.run_interactive()


def cmd_once(prompt, args):
    from core.config import load_config, detect_and_apply_hardware_config
    from daemon import Daemon

    cfg = load_config()
    if getattr(args, 'power', False):
        cfg['execution_mode'] = 'power'
    if getattr(args, 'verbose', False):
        cfg['verbose'] = True
    if cfg.get('hardware_adaptive', True):
        try:
            llm_keys = {k: v for k, v in cfg.items() if k in ('llm_provider', 'openai_api_key', 'openai_model', 'openrouter_api_key', 'openrouter_model', 'anthropic_api_key', 'anthropic_model', 'gemini_api_key', 'gemini_model', 'ollama_base_url', 'ollama_model')}
            adaptive, hw, profile_id = detect_and_apply_hardware_config(verbose=False)
            cfg.update(adaptive)
            cfg.update(llm_keys)
            cfg['hardware_profile'] = profile_id
        except Exception:
            pass

    daemon = Daemon()
    daemon.config = cfg
    daemon.setup_logging()
    daemon.init_llm()
    daemon.init_memory()
    daemon.init_tools()
    daemon.init_skills()
    daemon._register_skill_tools()
    daemon.init_agent()

    from cli import JarvisCLI
    cli = JarvisCLI(daemon=daemon)
    output = cli.run_once(prompt)
    if output:
        from rich.markdown import Markdown
        from rich.console import Console
        Console().print(Markdown(output))


def cmd_setup():
    from wizard import setup
    setup()


def cmd_status():
    from core.config import load_config, CONFIG_DIR
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    import json

    console = Console()
    cfg = load_config()
    config_file = CONFIG_DIR / 'config.json'

    console.print(Panel.fit(
        f"[bold cyan]Jarvis Status[/bold cyan]\n"
        f"Config: {config_file}\n"
        f"Profile: {cfg.get('hardware_profile', 'none')}\n"
        f"Adaptive: {cfg.get('hardware_adaptive', False)}\n"
        f"LLM: {cfg.get('llm_provider')} / {cfg.get('ollama_model', cfg.get('openai_model', ''))}\n"
        f"Device: {cfg.get('device', 'cpu').upper()}",
        border_style="cyan"
    ))

    try:
        from system.hardware_detector import detect_all
        hw = detect_all()
        table = Table(title="Hardware")
        table.add_column("Resource", style="cyan")
        table.add_column("Value")
        table.add_row("CPU", f"{hw['cpu']['cores']} cores")
        table.add_row("RAM", f"{hw['ram']['total_gb']}GB")
        table.add_row("GPU", hw['gpu']['name'] or 'None')
        console.print(table)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Jarvis v2.0 - Personal AI Assistant System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start         Start Jarvis daemon (default)
  cli           Interactive CLI chat mode
  detect        Run hardware detection and configure
  setup         Run setup wizard
  status        Show system status

Options:
  --gui         Start with web GUI (requires --web flag with start)
  --web         Enable web UI mode
  --port PORT   Web UI port (default: 7777)
  --host HOST   Web UI host (default: 127.0.0.1)
"""
    )
    parser.add_argument('command', nargs='*', default=['cli'],
                       help='Command: start, cli, detect, setup, status, or any natural language prompt')
    parser.add_argument('--gui', action='store_true', help='Start web GUI')
    parser.add_argument('--web', action='store_true', help='Enable web mode')
    parser.add_argument('--port', type=int, default=7777, help='API port')
    parser.add_argument('--host', default='127.0.0.1', help='API host')
    parser.add_argument('--detect', action='store_true', help='Run hardware detection')
    parser.add_argument('-y', '--yes', action='store_true', help='Automatically answer yes to prompts')
    parser.add_argument('--power', action='store_true', help='Enable Power Mode (instant tool execution without confirmation)')
    parser.add_argument('--verbose', action='store_true', help='Show detailed planning and tool execution logs')

    args = parser.parse_args()

    if args.detect:
        cmd_detect(args)
        return

    from core.config import CONFIG_FILE
    if not CONFIG_FILE.exists() and sys.stdin.isatty() and (not args.command or args.command[0] not in ('setup', 'detect', 'status')):
        print("[!] First time running Jarvis. Initializing setup...")
        cmd_setup()

    cmd_list = args.command
    first_cmd = cmd_list[0] if cmd_list else 'cli'

    if first_cmd == 'detect':
        cmd_detect(args)
    elif first_cmd == 'setup':
        cmd_setup()
    elif first_cmd == 'status':
        cmd_status()
    elif first_cmd == 'start':
        print_banner_cmd()
        cmd_start(args)
    elif first_cmd == 'cli':
        cmd_cli(args)
    else:
        # Treat as natural language prompt
        prompt = " ".join(cmd_list)
        print_banner_cmd()
        cmd_once(prompt, args)


if __name__ == '__main__':
    main()
