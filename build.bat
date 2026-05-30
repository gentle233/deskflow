@echo off
chcp 65001 >nul
echo ================================
echo    DeskFlow - Windows Build
echo ================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.11+ first.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Install dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

:: Install PyInstaller
echo [2/3] Installing PyInstaller...
pip install pyinstaller
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller install failed.
    pause
    exit /b 1
)

:: Build
echo [3/3] Building DeskFlow.exe...
pyinstaller --onedir ^
    --collect-all flask ^
    --collect-all jinja2 ^
    --collect-all werkzeug ^
    --collect-all markupsafe ^
    --collect-all pandas ^
    --collect-all openpyxl ^
    --collect-all apscheduler ^
    --collect-all watchdog ^
    --collect-all pywinauto ^
    --hidden-import core.config ^
    --hidden-import core.llm_gateway ^
    --hidden-import core.file_ops ^
    --hidden-import core.shortcuts ^
    --hidden-import core.logger ^
    --hidden-import core.file_monitor ^
    --hidden-import core.task_scheduler ^
    --hidden-import core.provider_tester ^
    --hidden-import agents.base_agent ^
    --hidden-import agents.file_manager ^
    --hidden-import agents.document ^
    --hidden-import agents.excel ^
    --hidden-import agents.web_search ^
    --hidden-import agents.memory ^
    --hidden-import agents.window_ops ^
    --hidden-import orchestrator.engine ^
    --hidden-import orchestrator.intent_router ^
    --hidden-import orchestrator.workflows ^
    --hidden-import orchestrator.scheduler ^
    --hidden-import autolearn.models ^
    --hidden-import autolearn.collector ^
    --hidden-import autolearn.analyzer ^
    --hidden-import autolearn.hooks ^
    --hidden-import memory.store ^
    --hidden-import memory.profile ^
    --hidden-import memory.learner ^
    --hidden-import apscheduler.triggers.cron ^
    --hidden-import apscheduler.triggers.interval ^
    --hidden-import apscheduler.schedulers.background ^
    --hidden-import pyperclip ^
    --hidden-import win32gui ^
    --hidden-import webview ^
    --add-data "ui/templates;ui/templates" ^
    --add-data "ui/static;ui/static" ^
    --add-data "ui/icons;ui/icons" ^
    --icon ui/icons/deskflow.ico ^
    --name DeskFlow ^
    --noconsole ^
    run.py

if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ================================
echo    Build Complete!
echo    Output: dist\DeskFlow\
echo    Files:
dir /b dist\DeskFlow\ 2>nul
echo ================================
echo.
echo 提示: 运行 dist\DeskFlow\DeskFlow.exe 启动桌面版
echo 首次运行会在 %%USERPROFILE%%\.deskflow\
echo 创建配置文件，请打开软件后配置 API Key。
echo.
pause
