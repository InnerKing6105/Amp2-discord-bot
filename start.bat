@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [ZYGARDE] Virtual environment missing.
    echo Run: py -3 -m venv .venv
    echo Then: .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" bot.py
if errorlevel 1 (
    echo [ZYGARDE] Bot exited with an error; review logs\zygarde.log
    pause
)
