@echo off
setlocal

rem 1. 保存 .bat 文件所在目录（即你最终想 cd 到的位置）
set "BAT_DIR=%~dp0"
if "%BAT_DIR:~-1%"=="\" set "BAT_DIR=%BAT_DIR:~0,-1%"

rem 2. 切换到 venv 所在目录并激活
cd /d "D:\workspace\python\Python 库\ck7"
call .venv311\Scripts\activate.bat

rem 3. cd 回 .bat 文件所在的目录
cd /d "%BAT_DIR%"

rem 4. 保持命令行窗口打开
cmd /k