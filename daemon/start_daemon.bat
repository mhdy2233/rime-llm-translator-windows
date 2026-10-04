@echo off
cd /d "%~dp0"
start "" pythonw daemon.py
echo [OK] rime-llm-daemon started.
