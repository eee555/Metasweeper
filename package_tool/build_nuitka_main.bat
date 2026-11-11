@echo off
setlocal
chcp 65001 >nul 2>&1

pushd "%~dp0\.."
if errorlevel 1 exit /b 1
set "PYTHON=.venv\Scripts\python.exe"
if not defined NUITKA_JOBS set "NUITKA_JOBS=4"
if not defined NUITKA_CONSOLE_MODE set "NUITKA_CONSOLE_MODE=disable"
if not defined NUITKA_OUTPUT_DIR set "NUITKA_OUTPUT_DIR=dist\metasweeper-nuitka"
if not defined NUITKA_ZIP_NAME set "NUITKA_ZIP_NAME=metasweeper-nuitka.zip"
if not defined NUITKA_INCLUDE_DEBUGPY set "NUITKA_INCLUDE_DEBUGPY=1"
set "EXCLUDE_OPTIONS=--nofollow-import-to=numpy,PIL,setuptools,pkg_resources,pytest,_pytest,zmq.tests,PySide6.QtQuickWidgets,PySide6.QtQuick,PySide6.QtQml,PySide6.QtCharts"
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

"%PYTHON%" -c "import sys; value=sys.argv[1]; sys.exit(0 if value.isascii() and value.isdecimal() and int(value) > 0 else 1)" "%NUITKA_JOBS%"
if errorlevel 1 (
    echo NUITKA_JOBS must be a positive integer.
    popd
    exit /b 1
)

rem dumpbin.exe on PATH does not guarantee the MSVC build environment is set
rem up. Nuitka relies on WindowsSDKVersion/UCRTVersion and friends to detect
rem the Windows SDK; without them it rejects cl.exe and falls back to
rem downloading winlibs MinGW. vcvars64.bat provides those variables.
if defined WindowsSDKVersion goto :msvc_ready
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
    echo MSVC tools not found. Install Visual Studio C++ build tools or use a developer command prompt.
    popd
    exit /b 1
)
call :setup_msvc
if errorlevel 1 (
    echo Failed to initialize the Visual Studio MSVC build environment.
    popd
    exit /b 1
)
if not defined WindowsSDKVersion (
    echo MSVC tools found, but vcvars64.bat did not set WindowsSDKVersion.
    popd
    exit /b 1
)
:msvc_ready

if not exist ".venv\Scripts\pyside6-lrelease.exe" (
    echo Qt translation compiler not found in the project virtual environment.
    popd
    exit /b 1
)
for %%L in (en_US de_DE pl_PL ja_JP) do (
    ".venv\Scripts\pyside6-lrelease.exe" "src\ui\%%L.ts" -qm "src\%%L.qm"
    if errorlevel 1 (
        popd
        exit /b 1
    )
)

rem src\media\cat.ico is gitignored. build.bat generates it before PyInstaller;
rem Nuitka needs the same file both for the exe resource icon and at runtime
rem (superGUI.py and several dialogs load media/cat.ico for the window icon).
if not exist "src\media\cat.ico" (
    if not exist "package_tool\cat.ico" (
        echo Main program icon not found: package_tool\cat.ico
        popd
        exit /b 1
    )
    copy /y "package_tool\cat.ico" "src\media\cat.ico" >nul
    if errorlevel 1 (
        echo Could not copy package_tool\cat.ico to src\media\cat.ico
        popd
        exit /b 1
    )
)
if not exist "src\media\cat.ico" (
    echo Main program icon is missing: src\media\cat.ico
    popd
    exit /b 1
)

if /i "%NUITKA_INCLUDE_DEBUGPY%"=="1" if not exist ".venv\Lib\site-packages\debugpy\__init__.py" (
    echo debugpy is missing from the project virtual environment.
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
    --assume-yes-for-downloads ^
    %EXCLUDE_OPTIONS% ^
    --windows-console-mode=%NUITKA_CONSOLE_MODE% ^
    --output-dir="%MAIN_STAGE%" ^
    --output-filename=metasweeper.exe ^
    --windows-icon-from-ico=src\media\cat.ico ^
    --jobs=%NUITKA_JOBS% ^
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
    --assume-yes-for-downloads ^
    %EXCLUDE_OPTIONS% ^
    --windows-console-mode=%NUITKA_CONSOLE_MODE% ^
    --output-dir="%MANAGER_STAGE%" ^
    --output-filename=plugin_manager.exe ^
    --jobs=%NUITKA_JOBS% ^
    --windows-icon-from-ico=src\media\plugin_manager.ico ^
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
    --include-package=plugin_sdk ^
    --include-package-data=plugin_sdk ^
    --include-package=shared_types ^
    --include-module=config.constants ^
    --include-module=utils.app_logger ^
    --include-package-data=textdistance ^
    --include-module=sqlite3 ^
    --include-module=PySide6.QtSvg ^
    --include-module=code ^
    --include-module=xmlrpc.server ^
    --include-module=xmlrpc.client ^
    --include-module=http.server ^
    --include-module=socketserver ^
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
if /i "%NUITKA_INCLUDE_DEBUGPY%"=="1" (
    xcopy /e /i /y /h ".venv\Lib\site-packages\debugpy\*" "%PACKAGE_DIR%\debugpy\" >nul
    if errorlevel 1 (
        popd
        exit /b 1
    )
    rem pydevd imports its vendored modules by their top-level names.
    for %%M in (_pydev_bundle _pydev_runfiles _pydevd_bundle _pydevd_frame_eval _pydevd_sys_monitoring pydev_ipython pydev_sitecustomize pydevd_attach_to_process pydevd_plugins) do (
        xcopy /e /i /y /h ".venv\Lib\site-packages\debugpy\_vendored\pydevd\%%M\*" "%PACKAGE_DIR%\%%M\" >nul
        if errorlevel 1 (
            popd
            exit /b 1
        )
    )
    copy /y ".venv\Lib\site-packages\debugpy\_vendored\pydevd\*.py" "%PACKAGE_DIR%\" >nul
    if errorlevel 1 (
        popd
        exit /b 1
    )
    rem debugpy/pydevd ship PDB symbols and generated Cython C/C++ sources.
    rem Only the compiled .pyd/.dll/.exe are loaded at runtime, so strip these
    rem ~40 MB of never-used files from the distributable package.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0trim_debug_artifacts.ps1" -PackageDir "%PACKAGE_DIR%"
    if errorlevel 1 (
        echo Failed to strip debugpy symbol/source files.
        popd
        exit /b 1
    )
)
xcopy /e /i /y /h "src\plugins\*" "%PACKAGE_DIR%\internal\plugins\" >nul
if errorlevel 1 (
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
if not exist "%PACKAGE_DIR%\media\cat.ico" (
    echo Main program icon missing from merged package: media\cat.ico
    popd
    exit /b 1
)
rmdir /s /q "%MAIN_STAGE%"
rmdir /s /q "%MANAGER_STAGE%"

set "ZIP_PATH=%NUITKA_OUTPUT_DIR%\%NUITKA_ZIP_NAME%"
if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%"
if exist "%ZIP_PATH%" (
    echo Could not replace existing release zip archive: %ZIP_PATH%
    popd
    exit /b 1
)
for %%I in ("%PACKAGE_DIR%") do set "NUITKA_PACKAGE_DIR=%%~fI"
for %%I in ("%ZIP_PATH%") do set "NUITKA_ZIP_PATH=%%~fI"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0zip_nuitka_package.ps1" -PackageDir "%NUITKA_PACKAGE_DIR%" -ZipPath "%NUITKA_ZIP_PATH%"
if errorlevel 1 (
    echo Failed to create the release zip archive.
    popd
    exit /b 1
)
if not exist "%ZIP_PATH%" (
    echo Release zip archive was not created: %ZIP_PATH%
    popd
    exit /b 1
)

echo.
echo Nuitka package complete:
echo   %PACKAGE_DIR%\metasweeper.exe
echo   %PACKAGE_DIR%\plugin_manager.exe
echo   %ZIP_PATH%
popd
exit /b 0

:setup_msvc
set "VS_INSTALL_DIR="
for /f "usebackq tokens=*" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VS_INSTALL_DIR=%%I"
if not defined VS_INSTALL_DIR exit /b 1
if not exist "%VS_INSTALL_DIR%\VC\Auxiliary\Build\vcvars64.bat" exit /b 1
call "%VS_INSTALL_DIR%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
where dumpbin.exe >nul 2>&1
exit /b %errorlevel%