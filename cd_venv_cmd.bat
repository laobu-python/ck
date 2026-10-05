@echo off
setlocal
cd /d "%~dp0"
rem Try project-local venvs first, then a known local venv, else system python.
if exist ".venv311\Scripts\activate.bat" (call ".venv311\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (call ".venv\Scripts\activate.bat"
) else if exist "D:\develop\ck0.10-venv\Scripts\activate.bat" (call "D:\develop\ck0.10-venv\Scripts\activate.bat"
) else (echo [ck1.0] No virtualenv found; falling back to the system python.)
cd /d "%~dp0"
cmd /k
