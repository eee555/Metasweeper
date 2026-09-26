@echo off
setlocal
pushd "%~dp0"
pyside6-uic -o ui_gameSettingShortcuts.py ui_gs_shortcuts.ui
if errorlevel 1 goto failed
pyside6-uic -o ui_gameSettings.py ui_gs.ui
if errorlevel 1 goto failed
pyside6-uic -o ui_defined_parameter.py ui_defined_parameter.ui
if errorlevel 1 goto failed
pyside6-uic -o ui_main_board.py main_board.ui
if errorlevel 1 goto failed
pyside6-uic -o ui_mine_num_bar.py ui_mine_num_bar.ui
if errorlevel 1 goto failed
pyside6-uic -o ui_video_control.py ui_video_control.ui
if errorlevel 1 goto failed
pyside6-uic -o ui_score_board.py ui_score_board.ui
if errorlevel 1 goto failed
pyside6-uic -o ui_advanced.py ui_advanced.ui
if errorlevel 1 goto failed
pyside6-uic -o ui_about.py ui_about.ui
if errorlevel 1 goto failed
pyside6-uic -o ui_record_pop.py ui_record_pop.ui
if errorlevel 1 goto failed
pyside6-uic -o ui_import.py ui_import.ui
if errorlevel 1 goto failed

copy /y ui_advanced.py ..\src\ui\ui_advanced.py
copy /y ui_score_board.py ..\src\ui\ui_score_board.py
copy /y ui_gameSettings.py ..\src\ui\ui_gameSettings.py
copy /y ui_main_board.py ..\src\ui\ui_main_board.py
copy /y ui_mine_num_bar.py ..\src\ui\ui_mine_num_bar.py
copy /y ui_defined_parameter.py ..\src\ui\ui_defined_parameter.py
copy /y ui_gameSettingShortcuts.py ..\src\ui\ui_gameSettingShortcuts.py
copy /y ui_record_pop.py ..\src\ui\ui_record_pop.py
copy /y ui_about.py ..\src\ui\ui_about.py
copy /y ui_video_control.py ..\src\ui\ui_video_control.py
copy /y ui_import.py ..\src\ui\ui_import.py

popd
if /i not "%~1"=="--no-pause" pause
exit /b 0

:failed
popd
exit /b 1