@echo off
cd /d "%~dp0"
start "" wscript.exe "%~dp0silent_start.vbs"
echo [OK] rime-llm-daemon started silently.
