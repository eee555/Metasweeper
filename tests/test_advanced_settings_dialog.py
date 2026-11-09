"""主程序「高级设置」作弊开关对话框的真实构建测试。

覆盖 ui_Form.__init__ -> _build_allow_ui() 这条真实 UI 路径，防止
QCoreApplication.translate() 返回值被当成 QString 调用 .arg()，以及
Qt %1 占位符未被填充、非作弊命令误生成 checkbox 等回归。
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QWidget

from dialogs.gameAdvancedSettings import ui_Form
from shared_types.commands import (
    COMMAND_TYPES, NON_CHEAT_TAGS, command_label, command_tag,
)
from superGUI import IniConfig


def _make_window(tmp_path):
    config = IniConfig(str(tmp_path / "gameSetting.ini"))
    parent = QWidget()
    return SimpleNamespace(
        game_setting=config, r_path=str(tmp_path), filter_forever=False,
        mainWindow=parent, label=Mock(),
    )


def _checkbox_texts(dialog):
    layout = dialog.verticalLayout_auth_items
    return [layout.itemAt(i).widget().text()
            for i in range(layout.count())]


def test_dialog_builds_and_labels_are_filled(qtbot, tmp_path):
    window = _make_window(tmp_path)
    dialog = ui_Form(window)
    qtbot.addWidget(dialog.Dialog)

    texts = _checkbox_texts(dialog)
    cheat_tags = [command_tag(t) for t in COMMAND_TYPES
                  if command_tag(t) not in NON_CHEAT_TAGS]
    assert len(texts) == len(cheat_tags) + 1  # 额外一个 board_update 事件开关

    # PySide6 的 translate 返回 str：%1 必须用 replace 填充，不能残留字面量。
    assert all("%1" not in text for text in texts)
    for cmd_type in COMMAND_TYPES:
        tag = command_tag(cmd_type)
        label = command_label(cmd_type)
        if tag in NON_CHEAT_TAGS:
            assert not any(label in text for text in texts)
        else:
            assert any(label in text for text in texts)
    assert any("board_update" in text for text in texts)


def test_toggling_persists_only_cheat_tags(qtbot, tmp_path):
    window = _make_window(tmp_path)
    dialog = ui_Form(window)
    qtbot.addWidget(dialog.Dialog)

    layout = dialog.verticalLayout_auth_items
    layout.itemAt(0).widget().setChecked(True)
    dialog.pushButton_yes.click()

    config = IniConfig(window.game_setting.file_path)
    saved = set(filter(None, config.value(
        "DEFAULT/allowed_controls", "", str).split(",")))
    assert saved
    assert not (saved & NON_CHEAT_TAGS)


def test_legacy_ini_drops_non_cheat_tags(qtbot, tmp_path):
    window = _make_window(tmp_path)
    window.game_setting.set_value(
        "DEFAULT/allowed_controls", "mouse_click,new_random_game,set_skin")
    window.game_setting.sync()

    dialog = ui_Form(window)
    qtbot.addWidget(dialog.Dialog)
    assert dialog._allowed_controls == {"mouse_click"}
