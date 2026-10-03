@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python -m venv .venv
) else (
    py -3 -m venv .venv
)
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Close OpenRGB, then run Enroll strip.cmd.
pause
exit /b 0
:failed
echo Setup failed. Install Python 3.11 or newer and check the error above.
pause
exit /b 1
