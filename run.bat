@echo off
REM Convenience launcher for Windows.
REM Creates a venv on first run, installs deps, then starts the bot.
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -q -r requirements.txt

if not exist .env (
    echo No .env found. Copy .env.example to .env and add your bot token first.
    exit /b 1
)

python bot.py
