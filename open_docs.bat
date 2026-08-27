@echo off
REM 一键打开项目文档（Windows batch）
REM 使用方法：双击此文件或在命令行运行，若已构建静态文档会直接打开 index.html；否则尝试用 Sphinx 构建（若已安装）。

SETLOCAL
rem 保存脚本所在目录
set "BAT_DIR=%~dp0"
if "%BAT_DIR:~-1%"=="\" set "BAT_DIR=%BAT_DIR:~0,-1%"

rem 切换到脚本目录
cd /d "%BAT_DIR%"

rem 优先尝试激活常见虚拟环境目录（.venv311 -> .venv）
if exist ".venv311\Scripts\activate.bat" (
	call ".venv311\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
	call ".venv\Scripts\activate.bat"
) else (
	echo 未检测到虚拟环境激活脚本（.venv311 或 .venv）。请先创建虚拟环境或手动激活。
)

echo 正在用 MkDocs 构建站点（使用当前 Python 环境的模块）...
python -m mkdocs build

echo 构建完成，尝试打开 site\index.html
IF EXIST "%BAT_DIR%\site\index.html" (
	start "" "%BAT_DIR%\site\index.html"
) ELSE (
	echo 未找到 site\index.html；请确认 mkdocs 是否安装并且构建成功。
)

pause
