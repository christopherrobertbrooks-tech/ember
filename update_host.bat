@echo off
title Ember Host Update Tool
echo ===================================================
echo            E.M.B.E.R. HOST UPDATE TOOL
echo ===================================================
echo.

:: ---------------------------------------------------------
:: CONFIGURATION
:: Host PC Tailscale IP
:: ---------------------------------------------------------
set HOST_IP=100.100.150.74
set SHARE_NAME=Project_Ember

:: The folder where this script is currently running
set LOCAL_DIR=%~dp0
:: Remove trailing backslash
set LOCAL_DIR=%LOCAL_DIR:~0,-1%

echo Authenticating with Host PC...
net use "\\%HOST_IP%\IPC$" /user:embersync EmberSync2026!

echo.
echo Syncing files from %LOCAL_DIR% to \\%HOST_IP%\%SHARE_NAME%...
echo.

:: Use Robocopy to push only new/modified files to the host
:: Exclude: node_modules, myenv, .git, companion_images, caches, data, output, ingest
:: Exclude files: config, logs, batch files (update_host.bat)
robocopy "%LOCAL_DIR%" "\\%HOST_IP%\%SHARE_NAME%" /E /MT:8 /XD node_modules myenv .git companion_images __pycache__ Pixtral data output ingest /XF ember_config.json update_host.bat *.zip *.vrm *.vroid *.exe *.db

echo.
echo Cleaning up network connection...
net use "\\%HOST_IP%\IPC$" /delete /y

echo.
echo ===================================================
echo Host Update Complete!
echo ===================================================
pause
