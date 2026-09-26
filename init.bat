@echo off
call "%~dp0uiFiles\ui转py.bat" --no-pause
exit /b %errorlevel%