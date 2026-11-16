#!/usr/bin/env bash
# ==============================================================================
# Jarvis AI Assistant - Universal 1-Line Installer (Linux & macOS)
# ==============================================================================
set -e

RESET="\033[0m"
BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"

echo -e "${CYAN}${BOLD}"
echo "    ╔═══════════════════════════════════════════╗"
echo "    ║     JARVIS AI ASSISTANT CLI INSTALLER     ║"
echo "    ╚═══════════════════════════════════════════╝"
echo -e "${RESET}"

# 1. Check Python installation (>= 3.10)
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}[✗] Error: python3 is not installed.${RESET}"
    echo "Please install Python 3.10 or newer (e.g. sudo apt install python3 python3-venv)"
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo -e "${RED}[✗] Error: Python 3.10+ required. Detected Python $PY_VER${RESET}"
    exit 1
fi

echo -e "${GREEN}[✓] Detected Python $PY_VER${RESET}"

# 2. Setup directories
JARVIS_HOME="$HOME/.jarvis"
VENV_DIR="$JARVIS_HOME/venv"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$JARVIS_HOME"
mkdir -p "$BIN_DIR"

# 3. Create Virtual Environment
echo -e "${CYAN}[*] Setting up isolated environment in $VENV_DIR...${RESET}"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# 4. Install / Update Jarvis
echo -e "${CYAN}[*] Installing Jarvis CLI and dependencies...${RESET}"
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel >/dev/null 2>&1

# Check if installing from local directory or remote
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$PARENT_DIR/jarvis_agent/pyproject.toml" ]; then
    echo -e "${CYAN}[*] Installing from local repository source...${RESET}"
    "$VENV_DIR/bin/pip" install -e "$PARENT_DIR/jarvis_agent"
elif [ -f "$SCRIPT_DIR/../pyproject.toml" ]; then
    "$VENV_DIR/bin/pip" install -e "$SCRIPT_DIR/.."
else
    echo -e "${CYAN}[*] Installing from repository source...${RESET}"
    "$VENV_DIR/bin/pip" install "git+https://github.com/Mohit-555/jarvis-ai-agent-cli.git" || true
fi

# 5. Link executable to PATH
ln -sf "$VENV_DIR/bin/jarvis" "$BIN_DIR/jarvis"
ln -sf "$VENV_DIR/bin/jarvis-cli" "$BIN_DIR/jarvis-cli"

echo -e "${GREEN}[✓] Executables linked:${RESET}"
echo "    - $BIN_DIR/jarvis"
echo "    - $BIN_DIR/jarvis-cli"

# 6. Check PATH
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo -e "${YELLOW}[!] Note: $BIN_DIR is not in your current PATH.${RESET}"
        echo "    Add this line to your ~/.bashrc or ~/.zshrc:"
        echo -e "    ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
        export PATH="$BIN_DIR:$PATH"
        ;;
esac

echo ""
echo -e "${GREEN}${BOLD}🎉 Installation Complete!${RESET}"
echo "You can now run:"
echo -e "  ${CYAN}jarvis${RESET}          -> Start interactive assistant"
echo -e "  ${CYAN}jarvis status${RESET}   -> Check system status"
echo -e "  ${CYAN}jarvis detect${RESET}   -> Run hardware detection"
echo -e "  ${CYAN}jarvis setup${RESET}    -> Reconfigure AI models and keys"
echo ""
