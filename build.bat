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
pyinstaller build.spec
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
