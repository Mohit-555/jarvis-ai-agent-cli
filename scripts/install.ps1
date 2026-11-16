# ==============================================================================
# Jarvis AI Assistant - Universal 1-Line Installer (Windows PowerShell)
# ==============================================================================
$ErrorActionPreference = "Stop"

Write-Host "`n    ===========================================" -ForegroundColor Cyan
Write-Host "       JARVIS AI ASSISTANT CLI (WINDOWS)       " -ForegroundColor Cyan
Write-Host "    ===========================================`n" -ForegroundColor Cyan

# 1. Check Python
try {
    $pyVer = & python --version 2>&1
    Write-Host "[✓] Found $pyVer" -ForegroundColor Green
} catch {
    Write-Error "[✗] Python is not installed or not in PATH. Please install Python 3.10+ from python.org."
    exit 1
}

# 2. Directories
$jarvisHome = Join-Path $HOME ".jarvis"
$venvDir = Join-Path $jarvisHome "venv"
$binDir = Join-Path $HOME "AppData\Local\Microsoft\WindowsApps"

if (-not (Test-Path $jarvisHome)) {
    New-Item -ItemType Directory -Path $jarvisHome | Out-Null
}

# 3. Create venv
if (-not (Test-Path $venvDir)) {
    Write-Host "[*] Creating virtual environment at $venvDir..." -ForegroundColor Cyan
    & python -m venv $venvDir
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"

# 4. Install
Write-Host "[*] Installing Jarvis CLI dependencies..." -ForegroundColor Cyan
& $venvPip install --upgrade pip setuptools wheel | Out-Null

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$parentDir = Split-Path -Parent $scriptDir
$localPkg = Join-Path $parentDir "jarvis_agent"

if (Test-Path (Join-Path $localPkg "pyproject.toml")) {
    & $venvPip install -e $localPkg
} else {
    & $venvPip install "git+https://github.com/mohit-patel/Jarvis.git#subdirectory=jarvis_agent"
}

# 5. Create runner script in WindowsApps (already in PATH)
$runnerPath = Join-Path $binDir "jarvis.cmd"
$runnerContent = "@echo off`r`n`"$venvDir\Scripts\jarvis.exe`" %*"
Set-Content -Path $runnerPath -Value $runnerContent

Write-Host "`n[✓] Successfully installed!" -ForegroundColor Green
Write-Host "You can now open a new Command Prompt or PowerShell and type: jarvis`n" -ForegroundColor Cyan
