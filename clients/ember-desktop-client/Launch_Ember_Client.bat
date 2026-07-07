@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Ember Desktop Client

cd /d "%~dp0"
set "LOG_FILE=%~dp0launch_ember_client.log"

echo ============================================== > "%LOG_FILE%"
echo Starting Ember Desktop Client at %DATE% %TIME% >> "%LOG_FILE%"
echo Working directory: %CD% >> "%LOG_FILE%"
echo ============================================== >> "%LOG_FILE%"

echo ==============================================
echo       Starting Ember Desktop Client
echo ==============================================
echo.
echo A launch log is being written to:
echo %LOG_FILE%
echo.

echo [1/4] Checking Python...
set "PYTHON_EXE="
where python >> "%LOG_FILE%" 2>&1
if not errorlevel 1 set "PYTHON_EXE=python"

if not defined PYTHON_EXE (
    where py >> "%LOG_FILE%" 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py"
)

if not defined PYTHON_EXE (
    echo [!] Python was not found in PATH.
    echo [!] Python was not found in PATH. >> "%LOG_FILE%"
    echo.
    echo Install Python, then run this launcher again.
    pause
    exit /b 1
)

%PYTHON_EXE% --version >> "%LOG_FILE%" 2>&1

echo [2/4] Checking Python client dependencies...
%PYTHON_EXE% -m pip install pyautogui websocket-client >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo.
    echo [!] Failed to install Python dependencies.
    echo [!] Failed to install Python dependencies. >> "%LOG_FILE%"
    echo See the log above for details.
    pause
    exit /b 1
)

echo.
echo [3/4] Checking Node dependencies...
where npm >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [!] npm was not found in PATH.
    echo [!] npm was not found in PATH. >> "%LOG_FILE%"
    echo.
    echo Install Node.js, then run this launcher again.
    pause
    exit /b 1
)

call npm --version >> "%LOG_FILE%" 2>&1

if not exist "node_modules\" (
    echo     node_modules not found. Running npm install...
    echo node_modules not found. Running npm install... >> "%LOG_FILE%"
    call npm install >> "%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo.
        echo [!] npm install failed.
        echo [!] npm install failed. >> "%LOG_FILE%"
        echo See the log above for details.
        pause
        exit /b 1
    )
)

echo.
echo [4/4] Starting Automation Daemon and UI...
echo Starting automation daemon... >> "%LOG_FILE%"
start "Ember Automation Daemon" /MIN cmd /k "%PYTHON_EXE% client_automation_daemon.py"

echo Starting npm run electron:dev... >> "%LOG_FILE%"
call npm run electron:dev >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=!ERRORLEVEL!"

echo.
echo Ember Desktop Client exited with code !EXIT_CODE!.
echo Ember Desktop Client exited with code !EXIT_CODE!. >> "%LOG_FILE%"
echo.
echo See log:
echo %LOG_FILE%
pause
exit /b !EXIT_CODE!
