@echo off
chcp 65001 >nul 2>&1

set OUT=dist\app
set DEST=%OUT%\metaminsweeper

echo [Clean] Removing old builds...
if exist "%OUT%\metaminsweeper" rmdir /s /q "%OUT%\metaminsweeper"
if exist "%OUT%\plugin_manager" rmdir /s /q "%OUT%\plugin_manager"

echo.
echo.
echo [1/3] metaminsweeper.exe
pyinstaller --noconfirm --name metaminsweeper --windowed --distpath %OUT% ^
    --icon src/media/cat.ico ^
    --clean ^
    --paths src ^
    --hidden-import mineSweeperGUIEvent ^
    --runtime-hook package_tool\hook-debugpy-pyinstaller.py ^
    --add-data "src/media;media" ^
    src\main.py

echo.
echo [2/3] plugin_manager.exe
pyinstaller --noconfirm --name plugin_manager --windowed --icon src/media/cat.ico --runtime-hook package_tool\hook-debugpy-pyinstaller.py --add-data "src/plugins;plugins" --add-data "src/shared_types;shared_types" --hidden-import sqlite3 --hidden-import code --hidden-import xmlrpc --hidden-import xmlrpc.server --hidden-import xmlrpc.client --hidden-import http.server --hidden-import socketserver --hidden-import email --hidden-import email.utils --hidden-import requests --hidden-import Crypto.Cipher.AES --hidden-import Crypto.Random --hidden-import ms_toollib --distpath %OUT% src\plugin_manager\_run.py

echo.
echo [3/3] Copy resources to metaminsweeper\
copy /y "%OUT%\plugin_manager\plugin_manager.exe" "%DEST%\"
xcopy /e /y /i "%OUT%\plugin_manager\_internal" "%DEST%\_internal" >nul
if exist "%DEST%\plugin_manager\_run.py" del /f /q "%DEST%\plugin_manager\_run.py"
mkdir "%DEST%\user_plugins" >nul 2>&1

echo [4/4] Copy debugpy from venv to _internal\
set SP=.venv\Lib\site-packages
xcopy /e /y /i "%SP%\debugpy" "%DEST%\_internal\debugpy" >nul
xcopy /e /y /i "%SP%\msgspec" "%DEST%\_internal\msgspec" >nul 2>nul
xcopy /e /y /i "%SP%\setuptools" "%DEST%\_internal\setuptools" >nul 2>nul

echo [5/5] Strip unnecessary Qt binaries
set QT_BIN=%DEST%\_internal\PyQt5\Qt5\bin
if exist "%QT_BIN%" (
    del "%QT_BIN%\Qt5Quick.dll"     2>nul & echo  Removed Qt5Quick.dll
    del "%QT_BIN%\Qt5Qml.dll"       2>nul & echo  Removed Qt5Qml.dll
    del "%QT_BIN%\Qt5QmlModels.dll" 2>nul & echo  Removed Qt5QmlModels.dll
    del "%QT_BIN%\Qt5DBus.dll"      2>nul & echo  Removed Qt5DBus.dll
    del "%QT_BIN%\Qt5Svg.dll"       2>nul & echo  Removed Qt5Svg.dll
    del "%QT_BIN%\opengl32sw.dll"   2>nul & echo  Removed opengl32sw.dll
    del "%QT_BIN%\libcrypto-1_1*.dll" 2>nul & echo  Removed old OpenSSL
    del "%QT_BIN%\libssl-1_1*.dll"    2>nul
)
set QT_PLATFORM=%DEST%\_internal\PyQt5\Qt5\plugins\platforms
if exist "%QT_PLATFORM%" (
    del "%QT_PLATFORM%\qminimal.dll"  2>nul & echo  Removed qminimal.dll
    del "%QT_PLATFORM%\qoffscreen.dll" 2>nul & echo  Removed qoffscreen.dll
    del "%QT_PLATFORM%\qwebgl.dll"    2>nul & echo  Removed qwebgl.dll
)
set QT_TRANS=%DEST%\_internal\PyQt5\Qt5\translations
if exist "%QT_TRANS%" (
    for %%f in ("%QT_TRANS%\qt_*.qm") do (
        echo %%f | findstr /i "qtbase_" >nul
        if errorlevel 1 del "%%f"
    )
    echo  Trimmed Qt translations (kept all qtbase_*.qm, removed other module translations)
)

echo [6/6] Copy plugin-dev-tutorial.md
copy /y "plugin-dev-tutorial.md" "%DEST%\" >nul

echo.
echo Done! Both in: %OUT%\
for /f "tokens=3" %%i in ('powershell -Command "(Get-ChildItem -Recurse '%DEST%' -File | Measure-Object -Property Length -Sum).Sum / 1MB"') do echo Final size: %%i MB
pause
