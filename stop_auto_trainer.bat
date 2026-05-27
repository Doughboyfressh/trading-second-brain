@echo off
:: stop_auto_trainer.bat
:: Stops the auto-trainer daemon immediately.
:: The VBScript in the Startup folder will restart it on next login.

echo Stopping Trading Brain Auto-Trainer…

:: Kill pythonw.exe running auto_trainer.py
wmic process where "name='pythonw.exe' and commandline like '%%auto_trainer%%'" delete >nul 2>&1
wmic process where "name='python.exe'  and commandline like '%%auto_trainer%%'" delete >nul 2>&1

:: Remove lock file
del /F /Q "%~dp0logs\auto_trainer.lock" >nul 2>&1

echo Auto-trainer stopped.
echo.
echo NOTE: It will restart automatically on your next login.
echo       To permanently disable: delete the file from your Startup folder:
echo       %%APPDATA%%\Microsoft\Windows\Start Menu\Programs\Startup\TradingBrain_AutoTrainer.vbs
echo.
pause
