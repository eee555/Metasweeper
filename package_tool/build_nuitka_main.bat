@echo off
setlocal
chcp 65001 >nul 2>&1

pushd "%~dp0\.."
set "PYTHON=.venv\Scripts\python.exe"
if not defined NUITKA_CONSOLE_MODE set "NUITKA_CONSOLE_MODE=disable"
if not defined NUITKA_OUTPUT_DIR set "NUITKA_OUTPUT_DIR=dist\metasweeper-nuitka"
set "EXCLUDE_OPTIONS=--nofollow-import-to=numpy,PIL,setuptools,pkg_resources,pytest,_pytest,zmq.tests"
set "QML_EXCLUDE_OPTIONS="
for %%M in (QtQuick3D Qt3D QtGraphs QtDataVisualization QtLocation QtMultimedia QtPositioning QtTest QtTextToSpeech QtSensors QtRemoteObjects QtScxml QtWebEngine QtWebChannel QtWebSockets QtWebView) do call set "QML_EXCLUDE_OPTIONS=%%QML_EXCLUDE_OPTIONS%% --noinclude-data-files=PySide6/qml/%%M/* --noinclude-dlls=PySide6/qml/%%M/*"
set "MANAGER_DEBUGPY_OPTION=--nofollow-import-to=debugpy"
if /i "%NUITKA_INCLUDE_DEBUGPY%"=="1" set "MANAGER_DEBUGPY_OPTION=--include-package=debugpy"
if defined PYTHONPATH (
    set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%CD%\src"
)
set "MAIN_STAGE=%NUITKA_OUTPUT_DIR%\_build_main"
set "MANAGER_STAGE=%NUITKA_OUTPUT_DIR%\_build_plugin_manager"
set "PACKAGE_DIR=%NUITKA_OUTPUT_DIR%\package"

if not exist "%PYTHON%" (
    echo Project virtual environment not found: %PYTHON%
    popd
    exit /b 1
)

"%PYTHON%" -c "import nuitka" >nul 2>&1
if errorlevel 1 (
    echo Nuitka is not installed in the project virtual environment.
    echo Install it with: .venv\Scripts\python.exe -m pip install Nuitka
    popd
    exit /b 1
)

if exist "%MAIN_STAGE%" rmdir /s /q "%MAIN_STAGE%"
if exist "%MAIN_STAGE%" (
    echo Could not clear main build staging directory: %MAIN_STAGE%
    popd
    exit /b 1
)
if exist "%MANAGER_STAGE%" rmdir /s /q "%MANAGER_STAGE%"
if exist "%MANAGER_STAGE%" (
    echo Could not clear plugin manager staging directory: %MANAGER_STAGE%
    popd
    exit /b 1
)

"%PYTHON%" -m nuitka ^
    --mode=standalone ^
    --enable-plugin=pyside6 ^
    %EXCLUDE_OPTIONS% ^
    --windows-console-mode=%NUITKA_CONSOLE_MODE% ^
    --output-dir="%MAIN_STAGE%" ^
    --output-filename=metasweeper.exe ^
    --include-data-files=AI_AGENT_POLICY.md=AI_AGENT_POLICY.md ^
    --include-data-files=README.md=README.md ^
    --include-data-dir=src\media=media ^
    --include-data-files=src\en_US.qm=en_US.qm ^
    --include-data-files=src\de_DE.qm=de_DE.qm ^
    --include-data-files=src\pl_PL.qm=pl_PL.qm ^
    --include-data-files=src\ja_JP.qm=ja_JP.qm ^
    --include-package=textdistance ^
    --include-package-data=textdistance ^
    --include-module=ms_toollib ^
    --include-module=win32api ^
    --include-module=win32event ^
    --include-module=winerror ^
    --include-module=pythoncom ^
    --include-module=pywintypes ^
    src\main.py
if errorlevel 1 (
    popd
    exit /b 1
)

"%PYTHON%" -m nuitka ^
    --mode=standalone ^
    --enable-plugin=pyside6 ^
    --include-qt-plugins=qml ^
    %EXCLUDE_OPTIONS% ^
    %QML_EXCLUDE_OPTIONS% ^
    --windows-console-mode=%NUITKA_CONSOLE_MODE% ^
    --output-dir="%MANAGER_STAGE%" ^
    --output-filename=plugin_manager.exe ^
    --include-data-dir=src\media=media ^
    --include-data-dir=src\plugins=internal/plugins ^
    --include-data-files=src\en_US.qm=en_US.qm ^
    --include-data-files=src\de_DE.qm=de_DE.qm ^
    --include-data-files=src\pl_PL.qm=pl_PL.qm ^
    --include-data-files=src\ja_JP.qm=ja_JP.qm ^
    --include-package=msgspec ^
    --include-package=zmq ^
    --include-package=loguru ^
    %MANAGER_DEBUGPY_OPTION% ^
    --include-package=requests ^
    --include-package=textdistance ^
    --include-package=cryptography ^
    --include-package=PyMCUlib ^
    --include-package=ms_toollib ^
    --include-package-data=textdistance ^
    --include-module=sqlite3 ^
    --include-module=code ^
    --include-module=xmlrpc.server ^
    --include-module=xmlrpc.client ^
    --include-module=http.server ^
    --include-module=socketserver ^
    --include-module=PySide6.QtQuickWidgets ^
    --include-module=PySide6.QtQuick ^
    --include-module=PySide6.QtQml ^
    --include-module=PySide6.QtCharts ^
    --include-module=win32api ^
    --include-module=win32event ^
    --include-module=winerror ^
    --include-module=pythoncom ^
    --include-module=pywintypes ^
    src\plugin_manager_nuitka.py
if errorlevel 1 (
    popd
    exit /b 1
)

set "MAIN_DIST="
for /d %%D in ("%MAIN_STAGE%\*.dist") do set "MAIN_DIST=%%~fD"
set "MANAGER_DIST="
for /d %%D in ("%MANAGER_STAGE%\*.dist") do set "MANAGER_DIST=%%~fD"

if not exist "%MAIN_DIST%\metasweeper.exe" (
    echo Main executable was not found in %MAIN_DIST%
    popd
    exit /b 1
)
if not exist "%MANAGER_DIST%\plugin_manager.exe" (
    echo Plugin manager executable was not found in %MANAGER_DIST%
    popd
    exit /b 1
)

if exist "%PACKAGE_DIR%" rmdir /s /q "%PACKAGE_DIR%"
if exist "%PACKAGE_DIR%" (
    echo Could not replace package directory. Close running app processes and retry:
    echo   %PACKAGE_DIR%
    popd
    exit /b 1
)
mkdir "%PACKAGE_DIR%"
if errorlevel 1 (
    popd
    exit /b 1
)
xcopy /e /i /y /h "%MAIN_DIST%\*" "%PACKAGE_DIR%\" >nul
if errorlevel 1 (
    popd
    exit /b 1
)
xcopy /e /i /y /h "%MANAGER_DIST%\*" "%PACKAGE_DIR%\" >nul
if errorlevel 1 (
    popd
    exit /b 1
)
xcopy /e /i /y /h "src\plugins\*" "%PACKAGE_DIR%\internal\plugins\" >nul
if errorlevel 1 (
    popd
    exit /b 1
)
for %%F in (qt6webenginecore.dll qt6webenginequick.dll qt6webenginequickdelegatesqml.dll qt6webchannel.dll qt6webchannelquick.dll qt6websockets.dll qt6webview.dll qt6webviewquick.dll) do (
    if exist "%PACKAGE_DIR%\%%F" del /q "%PACKAGE_DIR%\%%F"
)
for /d %%D in ("%PACKAGE_DIR%\PySide6\qml\QtWebEngine*" "%PACKAGE_DIR%\PySide6\qml\QtWebChannel" "%PACKAGE_DIR%\PySide6\qml\QtWebSockets" "%PACKAGE_DIR%\PySide6\qml\QtWebView") do (
    if exist "%%~fD" rmdir /s /q "%%~fD"
)
if exist "%PACKAGE_DIR%\qt6webenginecore.dll" (
    echo Could not remove unused Qt WebEngine runtime from package.
    popd
    exit /b 1
)
if exist "%PACKAGE_DIR%\PySide6\qml\QtWebEngine" (
    echo Could not remove unused Qt WebEngine QML module from package.
    popd
    exit /b 1
)
if not exist "%PACKAGE_DIR%\internal\plugins\history\plugin.py" (
    echo Built-in plugin source files were not copied to the package.
    popd
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0trim_qt_runtime.ps1" -PackageDir "%PACKAGE_DIR%" -Apply
if errorlevel 1 (
    popd
    exit /b 1
)
mkdir "%PACKAGE_DIR%\plugins" >nul 2>&1
mkdir "%PACKAGE_DIR%\user_plugins" >nul 2>&1
if not exist "%PACKAGE_DIR%\metasweeper.exe" (
    echo Main executable missing from merged package.
    popd
    exit /b 1
)
if not exist "%PACKAGE_DIR%\plugin_manager.exe" (
    echo Plugin manager executable missing from merged package.
    popd
    exit /b 1
)
if not exist "%PACKAGE_DIR%\internal\plugins\history\plugin.py" (
    echo Built-in HistoryPlugin source missing from merged package.
    popd
    exit /b 1
)
rmdir /s /q "%MAIN_STAGE%"
rmdir /s /q "%MANAGER_STAGE%"

echo.
echo Nuitka package complete:
echo   %PACKAGE_DIR%\metasweeper.exe
echo   %PACKAGE_DIR%\plugin_manager.exe
popd
exit /b 0