@echo off
pyuic5 -o ui_gameSettingShortcuts.py ui_gs_shortcuts.ui
pyuic5 -o ui_gameSettings.py ui_gs.ui
pyuic5 -o ui_defined_parameter.py ui_defined_parameter.ui
pyuic5 -o ui_main_board.py main_board.ui
pyuic5 -o ui_mine_num_bar.py ui_mine_num_bar.ui
pyuic5 -o ui_video_control.py ui_video_control.ui
pyuic5 -o ui_score_board.py ui_score_board.ui
pyuic5 -o ui_about.py ui_about.ui
pyuic5 -o ui_record_pop.py ui_record_pop.ui
copy /y ui_score_board.py ..\src\ui\ui_score_board.py
copy /y ui_gameSettings.py ..\src\ui\ui_gameSettings.py
copy /y ui_main_board.py ..\src\ui\ui_main_board.py
copy /y ui_mine_num_bar.py ..\src\ui\ui_mine_num_bar.py
copy /y ui_defined_parameter.py ..\src\ui\ui_defined_parameter.py
copy /y ui_gameSettingShortcuts.py ..\src\ui\ui_gameSettingShortcuts.py
copy /y ui_record_pop.py ..\src\ui\ui_record_pop.py
copy /y ui_about.py ..\src\ui\ui_about.py
copy /y ui_video_control.py ..\src\ui\ui_video_control.py
pause