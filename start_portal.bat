@echo off
REM Opens the Job Hunt Copilot portal in your browser (http://localhost:8501).
REM Close this black window to stop the portal.
cd /d "%~dp0"
if not exist .venv (
    echo Please double-click setup_windows.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
streamlit run app\dashboard.py
