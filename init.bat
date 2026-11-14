@echo off
call "%~dp0uiFiles\ui转py.bat" --no-pause
if errorlevel 1 exit /b %errorlevel%

rem 启用提交前/推送前测试钩子（提交和推送前必须测试全过）
git config core.hooksPath .githooks
exit /b %errorlevel%