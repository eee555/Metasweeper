@REM 翻译源文件维护脚本：pyside6-lupdate 扫描以下全部源文件，更新四个 .ts
@REM 注意：扫描清单必须覆盖所有含 _translate()/self.tr() 的源文件，
@REM 否则 -noobsolete 会把清单外文件对应的翻译词条误删！
@REM 新增含翻译字符串的源文件时，请同步加入下方清单。
@REM 清单与 git grep -l -E "_translate\(|self\.tr\(|QCoreApplication\.translate" -- "src/*.py" 保持一致。

@REM ---------- 界面文件（.ui，生成 src/ui/ui_*.py 的源头） ----------
set UI_FILES=../../uiFiles/ui_gs.ui ../../uiFiles/main_board.ui ../../uiFiles/ui_about.ui ../../uiFiles/ui_defined_parameter.ui ../../uiFiles/ui_gs_shortcuts.ui ../../uiFiles/ui_score_board.ui ../../uiFiles/ui_record_pop.ui ../../uiFiles/ui_advanced.ui ../../uiFiles/ui_video_control.ui ../../uiFiles/ui_import.ui ../../uiFiles/ui_mine_num_bar.ui

@REM ---------- 主程序 ----------
set MAIN=../main.py ../mainWindowGUIImportExport.py ../mine_num_bar.py ../mineSweeperGUI.py ../mineSweeperGUIEvent.py ../mineSweeperVideoPlayer.py

@REM ---------- 对话框 ----------
set DIALOGS=../dialogs/CheckUpdateGui.py ../dialogs/gameAdvancedSettings.py ../dialogs/gameScores.py ../dialogs/videoControl.py

@REM ---------- 复盘分析 ----------
set REPLAY_ANALYSIS=../replay_analysis/combo_click.py ../replay_analysis/flag.py ../replay_analysis/guess.py ../replay_analysis/one_point_five_click.py

@REM ---------- 公共类型与工具 ----------
set SHARED=../shared_types/enums.py ../shared_types/widgets/confirm_dialog.py ../utils/csv_export.py ../utils/helpers.py

@REM ---------- 插件 SDK 与插件管理器 ----------
set PLUGIN_SDK=../plugin_sdk/config_types/base_config.py ../plugin_sdk/config_types/file_config.py ../plugin_sdk/config_types/path_config.py ../plugin_sdk/config_types/text_config.py
set PLUGIN_MANAGER=../plugin_manager/config_widget.py ../plugin_manager/main_window.py ../plugin_manager/plugin_download.py ../plugin_manager/plugin_download_dialog.py ../plugin_manager/plugin_info_dialog.py ../plugin_manager/plugin_repositories.py

@REM ---------- 插件 ----------
set HISTORY_PLUGIN=../plugins/history/columns_dialog.py ../plugins/history/computed_columns_dialog.py ../plugins/history/filter_dialog.py ../plugins/history/history_table.py ../plugins/history/main_widget.py ../plugins/history/models.py ../plugins/history/plugin.py ../plugins/history/query_builder.py ../plugins/history/sort_dialog.py ../plugins/history/table_views.py
set LLM_PLUGIN=../plugins/llm_minesweeper_controller/config.py ../plugins/llm_minesweeper_controller/widgets.py ../plugins/llm_minesweeper_controller/plugin.py
set XIANNI_PLUGIN=../plugins/XianNiUpgrade/config.py ../plugins/XianNiUpgrade/models.py ../plugins/XianNiUpgrade/plugin.py ../plugins/XianNiUpgrade/widgets.py
set CHALLENGE_PLUGIN=../plugins/challenge_mode/plugin.py ../plugins/challenge_mode/widgets.py
set CLIPBOARD_PLUGIN=../plugins/clipboard_replay/widgets.py
set SAOLEI_PLUGIN=../plugins/SaoleiWebsite/config.py
set STATS_PLUGIN=../plugins/stats/plugin.py

set ALL_SOURCES=%UI_FILES% %MAIN% %DIALOGS% %REPLAY_ANALYSIS% %SHARED% %PLUGIN_SDK% %PLUGIN_MANAGER% %HISTORY_PLUGIN% %LLM_PLUGIN% %XIANNI_PLUGIN% %CHALLENGE_PLUGIN% %CLIPBOARD_PLUGIN% %SAOLEI_PLUGIN% %STATS_PLUGIN%

pyside6-lupdate %ALL_SOURCES% -ts en_US.ts -noobsolete -tr-function-alias translate+=_translate

pyside6-lupdate %ALL_SOURCES% -ts pl_PL.ts -noobsolete -tr-function-alias translate+=_translate

pyside6-lupdate %ALL_SOURCES% -ts de_DE.ts -noobsolete -tr-function-alias translate+=_translate

pyside6-lupdate %ALL_SOURCES% -ts ja_JP.ts -noobsolete -tr-function-alias translate+=_translate

@REM 编译 .qm（与 build.bat 保持一致）：
@REM pyside6-lrelease en_US.ts -qm ../en_US.qm
@REM pyside6-lrelease de_DE.ts -qm ../de_DE.qm
@REM pyside6-lrelease pl_PL.ts -qm ../pl_PL.qm
@REM pyside6-lrelease ja_JP.ts -qm ../ja_JP.qm
