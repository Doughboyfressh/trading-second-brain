@echo off
:: start_auto_trainer.bat
:: Starts the auto-trainer daemon RIGHT NOW in the background.
:: No console window — check logs\auto_trainer_YYYYMMDD.log for output.

set SCRIPT_DIR=%~dp0
set VENV_PYW=%SCRIPT_DIR%.venv\Scripts\pythonw.exe
set AUTO_TRAINER=%SCRIPT_DIR%auto_trainer.py
set STATUS_FILE=%SCRIPT_DIR%logs\auto_trainer_status.json

if not exist "%VENV_PYW%" (
    echo ERROR: .venv not found. Run setup first.
    pause
    exit /b 1
)

:: Kill any previous instance
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq pythonw.exe" /FO CSV ^| findstr /i "pythonw"') do (
    taskkill /PID %%~a /F >nul 2>&1
)

echo Starting Trading Brain Auto-Trainer (background)…
start "" "%VENV_PYW%" "%AUTO_TRAINER%"

timeout /t 3 /nobreak >nul

echo.
echo  Auto-trainer is running silently in the background.
echo  Logs: %SCRIPT_DIR%logs\
echo.
echo  Status check (PowerShell):
echo    Get-Content "%STATUS_FILE%"
echo.
echo  Stop it:
echo    stop_auto_trainer.bat
echo.
pause
