@echo off
setlocal
set "PYTHONPATH=%CD%\src"
chcp 65001 >nul 2>&1

rem Keep unrelated DLLs on the caller's PATH out of PyInstaller's dependency scan.
set "DUMPBIN_DIR="
for %%I in (dumpbin.exe) do set "DUMPBIN_DIR=%%~dp$PATH:I"
if not defined DUMPBIN_DIR (
    echo ERROR: dumpbin.exe is required. Run from the Visual Studio developer environment.
    exit /b 1
)
if not exist "%CD%\.venv\Scripts\pyinstaller.exe" (
    echo ERROR: Install PyInstaller in .venv before building.
    exit /b 1
)
set "PATH=%CD%\.venv\Scripts;%SystemRoot%\System32;%SystemRoot%\System32\WindowsPowerShell\v1.0;%SystemRoot%;%DUMPBIN_DIR%"

set OUT=dist\app
set DEST=%OUT%\metaminsweeper
set EXCLUDES=--exclude-module debugpy --exclude-module numpy --exclude-module PIL --exclude-module Pillow --exclude-module Cython --exclude-module setuptools --exclude-module pkg_resources --exclude-module psutil --exclude-module pytest --exclude-module _pytest --exclude-module PySide6.QtQuickWidgets --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml --exclude-module PySide6.QtCharts --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtMultimediaWidgets --exclude-module PySide6.QtPdf --exclude-module PySide6.QtPdfWidgets --exclude-module PySide6.QtOpenGL --exclude-module PySide6.QtOpenGLWidgets

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

if exist "%DEST%" (
    echo ERROR: %DEST% already exists. Move or back up the existing output before building.
    exit /b 1
)
if exist "%OUT%\plugin_manager" rmdir /s /q "%OUT%\plugin_manager"

pyside6-lrelease src\ui\en_US.ts -qm src\en_US.qm
if errorlevel 1 exit /b 1
pyside6-lrelease src\ui\de_DE.ts -qm src\de_DE.qm
if errorlevel 1 exit /b 1
pyside6-lrelease src\ui\pl_PL.ts -qm src\pl_PL.qm
if errorlevel 1 exit /b 1
pyside6-lrelease src\ui\ja_JP.ts -qm src\ja_JP.qm
if errorlevel 1 exit /b 1
python develop_tools\compile_plugin_translations.py
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --clean --name metaminsweeper --windowed --distpath "%OUT%" ^
    %EXCLUDES% ^
    --icon src/media/cat.ico ^
    --paths src ^
    --add-data "src/media;media" ^
    --add-data "src/plugins;plugins" ^
    --add-data "src/en_US.qm;." ^
    --add-data "src/de_DE.qm;." ^
    --add-data "src/pl_PL.qm;." ^
    --add-data "src/ja_JP.qm;." ^
    src\main.py
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --clean --name plugin_manager --windowed --icon src/media/plugin_manager.ico ^
    %EXCLUDES% ^
    --paths src ^
    --additional-hooks-dir package_tool\pyinstaller_hooks ^
    --collect-all pip ^
    --exclude-module test --exclude-module unittest ^
    --exclude-module _tkinter --exclude-module tkinter --exclude-module idlelib --exclude-module lib2to3 ^
    --exclude-module pip._vendor.certifi.tests ^
    --exclude-module pip._vendor.platformdirs.pytest_plugin ^
    --hidden-import plugin_manager.__main__ ^
    --collect-submodules plugin_manager ^
    --add-data "src/media/plugin_manager.ico;media" ^
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
    --hidden-import requests --hidden-import packaging ^
    --hidden-import win32api --hidden-import win32event --hidden-import winerror ^
    --hidden-import PySide6.QtSvg ^
    --hidden-import PySide6.QtNetwork ^
    --hidden-import ms_toollib ^
    --hidden-import shared_types.aes_gcm --hidden-import config.constants --hidden-import utils.app_logger ^
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
xcopy /e /y /i "%SP%\msgspec" "%DEST%\_internal\msgspec" >nul 2>nul
copy /y plugin-dev-tutorial.md "%DEST%\" >nul

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "package_tool\trim_qt_runtime.ps1" -PackageDir "%DEST%" -Apply
if errorlevel 1 exit /b 1

for /f "tokens=3" %%i in ('powershell -Command "(Get-ChildItem -Recurse '%DEST%' -File | Measure-Object -Property Length -Sum).Sum / 1MB"') do echo Final size: %%i MB
echo Build complete: %OUT%\
