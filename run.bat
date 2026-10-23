@echo off
title Flow STT - Voice Dictation & Audio Studio
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please run:
    echo   python -m venv .venv
    echo   .\.venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting Flow STT...
start "" ".\.venv\Scripts\pythonw.exe" -m app.main
exit
