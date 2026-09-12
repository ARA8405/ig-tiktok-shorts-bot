#!/usr/bin/env bash
# Convenience launcher for macOS / Linux.
# Creates a venv on first run, installs deps, then starts the bot.
set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    echo "No .env found. Copy .env.example to .env and add your bot token first."
    exit 1
fi

python bot.py
