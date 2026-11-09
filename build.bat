@echo off
setlocal
chcp 65001 >nul 2>&1

set OUT=dist\app
set DEST=%OUT%\metaminsweeper
set EXCLUDES=--exclude-module numpy --exclude-module PIL --exclude-module Pillow --exclude-module Cython --exclude-module setuptools --exclude-module pkg_resources --exclude-module psutil --exclude-module pytest --exclude-module _pytest

if not exist "src\media\cat.ico" (
    pushd package_tool
    python randomize_cat_icon.py
    if errorlevel 1 (
        popd
        exit /b 1
    )
    popd
    copy /y "package_tool\cat.ico" "src\media\cat.ico"
    if errorlevel 1 exit /b 1
)

if exist "%OUT%\metaminsweeper" rmdir /s /q "%OUT%\metaminsweeper"
if exist "%OUT%\plugin_manager" rmdir /s /q "%OUT%\plugin_manager"

pyside6-lrelease src\ui\en_US.ts -qm src\en_US.qm
if errorlevel 1 exit /b 1
pyside6-lrelease src\ui\de_DE.ts -qm src\de_DE.qm
if errorlevel 1 exit /b 1
pyside6-lrelease src\ui\pl_PL.ts -qm src\pl_PL.qm
if errorlevel 1 exit /b 1
pyside6-lrelease src\ui\ja_JP.ts -qm src\ja_JP.qm
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --clean --name metaminsweeper --windowed --distpath "%OUT%" ^
    %EXCLUDES% ^
    --icon src/media/cat.ico ^
    --paths src ^
    --runtime-hook package_tool\hook-debugpy-pyinstaller.py ^
    --add-data "src/media;media" ^
    --add-data "src/plugins;plugins" ^
    --add-data "src/en_US.qm;." ^
    --add-data "src/de_DE.qm;." ^
    --add-data "src/pl_PL.qm;." ^
    --add-data "src/ja_JP.qm;." ^
    src\main.py
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --clean --name plugin_manager --windowed --icon src/media/cat.ico ^
    %EXCLUDES% ^
    --runtime-hook package_tool\hook-debugpy-pyinstaller.py ^
    --add-data "src/plugins;plugins" ^
    --add-data "src/shared_types;shared_types" ^
    --add-data "src/en_US.qm;." ^
    --add-data "src/de_DE.qm;." ^
    --add-data "src/pl_PL.qm;." ^
    --add-data "src/ja_JP.qm;." ^
    --hidden-import sqlite3 --hidden-import code ^
    --hidden-import xmlrpc --hidden-import xmlrpc.server --hidden-import xmlrpc.client ^
    --hidden-import http.server --hidden-import socketserver ^
    --hidden-import email --hidden-import email.utils ^
    --hidden-import requests --hidden-import Crypto.Cipher.AES --hidden-import Crypto.Random ^
    --hidden-import win32api --hidden-import win32event --hidden-import winerror ^
    --hidden-import ms_toollib --hidden-import PySide6.QtQuickWidgets ^
    --hidden-import PySide6.QtQuick --hidden-import PySide6.QtQml ^
    --hidden-import PySide6.QtCharts ^
    --distpath "%OUT%" src\plugin_manager\_run.py
if errorlevel 1 exit /b 1

copy /y "%OUT%\plugin_manager\plugin_manager.exe" "%DEST%\"
if errorlevel 1 exit /b 1
copy /y "AI_AGENT_POLICY.md" "%DEST%\"
if errorlevel 1 exit /b 1
copy /y "README.md" "%DEST%\"
if errorlevel 1 exit /b 1
xcopy /e /y /i "%OUT%\plugin_manager\_internal" "%DEST%\_internal" >nul
if errorlevel 1 exit /b 1
mkdir "%DEST%\user_plugins" >nul 2>&1

set SP=.venv\Lib\site-packages
xcopy /e /y /i "%SP%\debugpy" "%DEST%\_internal\debugpy" >nul
xcopy /e /y /i "%SP%\msgspec" "%DEST%\_internal\msgspec" >nul 2>nul
copy /y plugin-dev-tutorial.md "%DEST%\" >nul

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "package_tool\trim_qt_runtime.ps1" -PackageDir "%DEST%" -Apply
if errorlevel 1 exit /b 1

for /f "tokens=3" %%i in ('powershell -Command "(Get-ChildItem -Recurse '%DEST%' -File | Measure-Object -Property Length -Sum).Sum / 1MB"') do echo Final size: %%i MB
echo Build complete: %OUT%\
