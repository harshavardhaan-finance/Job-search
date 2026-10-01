@echo off
REM One-time setup: creates the private Python environment and installs packages.
REM Double-click this file once. Needs Python 3.11+ installed ("Add python.exe to PATH" ticked).
cd /d "%~dp0"
if not exist .venv (
    echo Creating virtual environment...
    py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
if not exist config\answers.yaml copy config\answers.example.yaml config\answers.yaml
echo.
echo Setup finished. Now double-click start_portal.bat
pause
