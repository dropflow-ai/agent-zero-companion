#!/bin/bash
# Agent Zero Companion - macOS Launcher
# Double-click this file to start the app without keeping terminal open

cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start the app in background
nohup python3 main.py > /tmp/agent-zero-companion.log 2>&1 &

# Close this terminal window after 1 second
sleep 1
osascript -e 'tell application "Terminal" to close first window' &
