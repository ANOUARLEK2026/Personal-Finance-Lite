@echo off
setlocal
cd /d "%~dp0"

rem End-user launcher: never installs packages every time you open the app.
if exist "%~dp0release\Personal Finance Pro.exe" (
    start "Personal Finance Pro" "%~dp0release\Personal Finance Pro.exe"
    exit /b 0
)

if exist "%~dp0dist\Personal Finance Pro.exe" (
    start "Personal Finance Pro" "%~dp0dist\Personal Finance Pro.exe"
    exit /b 0
)

where pythonw >nul 2>&1
if errorlevel 1 (
    echo Personal Finance Pro is not built yet.
    echo Run "Build EXE.bat" first, or install Python 3.10+ for source mode.
    pause
    exit /b 1
)

start "Personal Finance Pro" pythonw "%~dp0main.py"
exit /b 0
