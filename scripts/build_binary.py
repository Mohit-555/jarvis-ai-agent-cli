#!/usr/bin/env python3
"""
Jarvis Standalone Binary Builder
Compiles Jarvis Agent into a single standalone executable using PyInstaller.
"""
import sys
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent / "jarvis_agent"

def build():
    print("[*] Building standalone Jarvis binary...")
    try:
        import PyInstaller
    except ImportError:
        print("[*] Installing pyinstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    skills_dir = ROOT_DIR / "skills" / "bundled"
    static_dir = ROOT_DIR / "static"
    main_file = ROOT_DIR / "main.py"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=jarvis",
        "--clean",
        "--onefile",
        f"--add-data={skills_dir}:skills/bundled",
        f"--add-data={static_dir}:static",
        "--paths", str(ROOT_DIR),
        str(main_file)
    ]

    print(f"[*] Running: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(ROOT_DIR))
    print("[✓] Build complete! Executable is at jarvis_agent/dist/jarvis")

if __name__ == "__main__":
    build()
