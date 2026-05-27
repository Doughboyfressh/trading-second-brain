@echo off
:: setup_auto_trainer.bat
:: ─────────────────────────────────────────────────────────────────────────────
:: Registers Trading Brain Auto-Trainer with Windows Task Scheduler.
:: Run this ONCE (as Administrator recommended, but not required).
:: After registration the task starts automatically at every login and
:: keeps running in the background — no terminal window needed.
::
:: To unregister:   schtasks /Delete /TN "TradingBrain_AutoTrainer" /F
:: To check status: schtasks /Query /TN "TradingBrain_AutoTrainer" /V /FO LIST
:: ─────────────────────────────────────────────────────────────────────────────

set TASK_NAME=TradingBrain_AutoTrainer
set SCRIPT_DIR=%~dp0
set VENV_PY=%SCRIPT_DIR%.venv\Scripts\pythonw.exe
set AUTO_TRAINER=%SCRIPT_DIR%auto_trainer.py

:: Verify the venv python exists
if not exist "%VENV_PY%" (
    echo ERROR: .venv\Scripts\pythonw.exe not found.
    echo        Please create the virtual environment first:
    echo        python -m venv .venv
    echo        .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo  Trading Brain — Auto-Trainer Task Scheduler Setup
echo  ==================================================
echo  Task name   : %TASK_NAME%
echo  Python      : %VENV_PY%
echo  Script      : %AUTO_TRAINER%
echo  Trigger     : At logon (runs in background, no window)
echo  Interval    : Every 6 hours (default, change AUTO_TRAIN_INTERVAL_HOURS env var)
echo.

:: Delete existing task if it exists (ignore error if not found)
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

:: Create the scheduled task
:: - TRIGGER: At logon of current user (runs immediately when Windows starts)
:: - RUN LEVEL: Highest available
:: - HIDDEN: yes (no console window pops up)
schtasks /Create ^
  /TN "%TASK_NAME%" ^
  /TR "\"%VENV_PY%\" \"%AUTO_TRAINER%\"" ^
  /SC ONLOGON ^
  /RL HIGHEST ^
  /F

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Task Scheduler registration failed.
    echo        Try running this batch file as Administrator.
    pause
    exit /b 1
)

echo.
echo  SUCCESS: Task registered.
echo.
echo  The auto-trainer will start automatically at your next login.
echo  To start it RIGHT NOW without logging out:
echo.
echo      schtasks /Run /TN "%TASK_NAME%"
echo.
echo  Or just double-click start_auto_trainer.bat
echo.

:: Ask if user wants to start it now
set /p START_NOW=Start the auto-trainer right now? (Y/N):
if /i "%START_NOW%"=="Y" (
    echo Starting auto-trainer…
    schtasks /Run /TN "%TASK_NAME%"
    echo Done. Training will begin in a few seconds.
    echo Check logs\ folder for output.
)

echo.
pause
