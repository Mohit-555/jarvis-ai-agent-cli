#!/usr/bin/env python3
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.config import load_config, save_config, CONFIG_FILE
from system.hardware_detector import detect_all, check_ollama
from system.hardware_profile import get_adaptive_config, HARDWARE_PROFILES


def print_header():
    print("=" * 56)
    print("   JARVIS v2.0 - Setup Wizard")
    print("   Hardware-Adaptive AI Assistant")
    print("=" * 56)
    print()


def run_hardware_detect():
    print("[*] Detecting hardware capabilities...")
    hw = detect_all()
    adaptive, profile_id, profile = get_adaptive_config(hw)

    print(f"    CPU: {hw['cpu']['cores']} cores")
    print(f"    RAM: {hw['ram']['total_gb']}GB (available: {hw['ram']['available_gb']}GB)")
    gpu_name = hw['gpu']['name'] or 'None'
    print(f"    GPU: {gpu_name}")
    print(f"    Audio: {'Yes' if hw['audio']['input'] else 'No'}")
    print(f"    Ollama: {'Installed' if hw['ollama']['installed'] else 'Not found'}")
    print()
    print(f"  [>] Recommended profile: [bold]{profile['label']}[/]")
    print(f"  [>] LLM: {adaptive.get('ollama_model', 'N/A')} via Ollama")
    print(f"  [>] STT: whisper-{adaptive.get('stt_model', 'tiny')}")
    print(f"  [>] TTS: {adaptive.get('tts_engine', 'pyttsx3')}")
    print(f"  [>] Voice: {'On' if adaptive.get('enable_voice') else 'Off'}")
    print(f"  [>] Vision: {'On' if adaptive.get('enable_vision') else 'Off'}")
    print()

    return hw, adaptive, profile_id


def ask_user_profile(cfg):
    if not cfg.get("user_name") or not cfg.get("user_language"):
        print()
        print("User Profile Setup:")
        print("  1. Hinglish (Hindi + English)")
        print("  2. English")
        lang_choice = input("  Preferred Language [1]: ").strip() or "1"
        language = "Hinglish" if lang_choice in ("1", "hinglish") else "English"
        if language == "Hinglish":
            name = input("  Aapka naam kya hai? (Enter your name): ").strip() or "User"
        else:
            name = input("  What is your name? (Enter your name): ").strip() or "User"
        cfg["user_name"] = name
        cfg["user_language"] = language


def setup():
    cfg = load_config()
    print_header()

    choice = input("Run hardware detection? (Y/n): ").strip().lower() or 'y'
    hw = None
    if choice != 'n':
        hw, adaptive, profile_id = run_hardware_detect()
        use_auto = input("Use this hardware-adaptive configuration? (Y/n): ").strip().lower() or 'y'
        if use_auto != 'n':
            cfg.update(adaptive)
            cfg['hardware_profile'] = profile_id
            cfg['hardware_adaptive'] = True

            voice_opt = input(f"Enable voice I/O? ({'Y/n' if adaptive.get('enable_voice') else 'y/N'}): ").strip().lower()
            if voice_opt == 'y':
                cfg['enable_voice'] = True
            elif voice_opt == 'n':
                cfg['enable_voice'] = False

            ask_user_profile(cfg)
            save_config(cfg)
            print(f"\n[+] Configuration saved to {CONFIG_FILE}")
            print("[+] Run 'python main.py' to start Jarvis")
            return

    print()
    print("Manual LLM Configuration:")
    print("  1. Ollama (local - recommended for your hardware)")
    print("  2. OpenAI (cloud)")
    print("  3. Google Gemini (cloud)")
    print("  4. OpenRouter (multi-model gateway)")

    if hw and not hw['ollama']['installed']:
        print("\n  [i] Ollama not detected. Install from https://ollama.com for local AI.")
        default_choice = '2'
    else:
        default_choice = '1'

    choice = input(f"\n  Choice [{default_choice}]: ").strip() or default_choice

    if choice == "4":
        cfg["llm_provider"] = "openrouter"
        key = input("  OpenRouter API Key: ").strip()
        if key:
            cfg["openrouter_api_key"] = key
        cfg["openrouter_model"] = input(f"  Model [{cfg['openrouter_model']}]: ") or cfg["openrouter_model"]
    elif choice == "3":
        cfg["llm_provider"] = "gemini"
        key = input("  Gemini API Key: ").strip()
        if key:
            cfg["gemini_api_key"] = key
        cfg["openrouter_model"] = input(f"  Model [{cfg['gemini_model']}]: ") or cfg["gemini_model"]
    elif choice == "2":
        cfg["llm_provider"] = "openai"
        key = input("  OpenAI API Key: ").strip()
        if key:
            cfg["openai_api_key"] = key
        cfg["openai_model"] = input(f"  Model [{cfg['openai_model']}]: ") or cfg["openai_model"]
    else:
        cfg["llm_provider"] = "ollama"
        cfg["ollama_base_url"] = input(f"  Ollama URL [{cfg['ollama_base_url']}]: ") or cfg["ollama_base_url"]
        suggested = adaptive.get('ollama_model', 'llama3.2:3b') if hw else 'llama3.2:3b'
        available_models = []
        if hw and hw['ollama']['installed']:
            available_models = hw['ollama']['models']
            if available_models:
                print(f"  Available models: {', '.join(available_models)}")
        cfg["ollama_model"] = input(f"  Model [{suggested}]: ") or suggested

    cfg['hardware_adaptive'] = False
    ask_user_profile(cfg)
    save_config(cfg)
    print(f"\n[+] Configuration saved to {CONFIG_FILE}")
    print("[+] Run 'python main.py' to start Jarvis")
    print()
    print("Tips:")
    print("  - Get an OpenAI key at: https://platform.openai.com/api-keys")
    print("  - Get a Gemini key at: https://aistudio.google.com/apikey")
    print("  - Get an OpenRouter key at: https://openrouter.ai/keys")
    print("  - Install Ollama at: https://ollama.com")


if __name__ == "__main__":
    setup()
