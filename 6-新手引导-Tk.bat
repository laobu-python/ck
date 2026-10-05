@echo off
cd /d "%~dp0"
rem Pick an interpreter automatically (novices should not need to fix PATH).
rem Order: project-local .venv311/.venv -> a known local venv (see below) -> system python.
rem Note: the fixed venv path below is a local venv from the author's machine
rem       (it already has PySide6 installed); other machines fall through to python.
rem Why: guides 7/8 need PySide6; the system python often lacks it, and a wrong
rem pick makes the console flash by with a message nobody can read.
set "PYEXE=python"
if exist ".venv311\Scripts\python.exe" set "PYEXE=.venv311\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
if exist "D:\develop\ck0.10-venv\Scripts\python.exe" set "PYEXE=D:\develop\ck0.10-venv\Scripts\python.exe"
echo [ck1.0] interpreter: %PYEXE%
echo Starting ck1.0 Tk guide...
"%PYEXE%" guide_tk.py
if errorlevel 1 (
  echo.
  echo [ck1.0] Failed to start. If a module is missing, install it first:
  echo          pip install PySide6 Pillow
  echo          Self-check: python guide_tk.py --selftest
  pause
)
