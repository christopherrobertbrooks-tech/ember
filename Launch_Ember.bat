@echo off
title Ember Launcher
echo ===================================================
echo            E.M.B.E.R. BOOTSTRAPPER
echo ===================================================
echo.

echo Checking Python Environment...
IF NOT EXIST ".\myenv\Scripts\activate.bat" (
    echo [!] Virtual environment not found. Creating 'myenv' with Python 3.12...
    py -3.12 -m venv myenv
    echo [!] Installing requirements. This might take a few minutes...
    call .\myenv\Scripts\activate
    pip install -r requirements.txt
) ELSE (
    call .\myenv\Scripts\activate
)

echo.
echo Checking Node Dependencies...
IF NOT EXIST ".\clients\ember-desktop-client\node_modules\" (
    echo [!] Installing desktop client dependencies...
    cd clients\ember-desktop-client
    call npm install
    cd ..\..
)
IF NOT EXIST ".\clients\ember-web-client\node_modules\" (
    echo [!] Installing web client dependencies...
    cd clients\ember-web-client
    call npm install
    cd ..\..
)

echo.
echo Launching Orchestrator...
python launcher.py

pause
