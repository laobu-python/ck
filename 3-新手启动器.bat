@echo off
cd /d "%~dp0"
echo Starting ck8 launcher...
python launcher.py
if errorlevel 1 (
  echo.
  echo Failed to run. Is Python installed and added to PATH?
  pause
)
