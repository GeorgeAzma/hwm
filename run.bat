@echo off

pip install -r requirements.txt

REM Kill any process using port 8085
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8085') do (
    echo Killing process %%a on port 8085...
    taskkill /f /pid %%a >nul 2>&1
)

REM Run the Python script without window
cd c:/code/hwm/main.py && start /b "" pythonw

echo Hardware monitor daemon started on port 8085