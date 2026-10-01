@echo off
REM Fetches jobs from all sources without opening the portal (same as the "Fetch now" button).
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python run_daily.py
pause
