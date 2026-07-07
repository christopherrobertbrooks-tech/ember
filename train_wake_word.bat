@echo off
echo ========================================================
echo LiveKit Wake Word Training Script for "Hey Ember"
echo ========================================================
echo.
echo Step 1/4: Installing livekit-wakeword and dependencies...
pip install livekit-wakeword[train,eval,export]
if %errorlevel% neq 0 (
    echo Error during installation.
    pause
    exit /b %errorlevel%
)

echo.
echo Step 2/4: Running livekit setup (downloading datasets)...
livekit-wakeword setup
if %errorlevel% neq 0 (
    echo Error during setup.
    pause
    exit /b %errorlevel%
)

echo.
echo Step 3/4: Training the AI model...
echo This will take a while! Grab a coffee.
livekit-wakeword run configs/hey_ember.yaml
if %errorlevel% neq 0 (
    echo Error during training.
    pause
    exit /b %errorlevel%
)

echo.
echo Step 4/4: Copying model to Project_Ember root...
copy /Y output\hey_ember\hey_ember.onnx .\hey_ember.onnx
if %errorlevel% neq 0 (
    echo Error copying the file. Check if output/hey_ember/hey_ember.onnx exists.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo Success! hey_ember.onnx is now ready to use.
echo Please restart your wake_word_listener.py script.
echo ========================================================
pause
