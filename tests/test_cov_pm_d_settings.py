"""Coverage for plugin settings and basic settings dialogs."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QWidget

from plugin_manager.main_window import BasicSettingsDialog, PluginSettingsDialog
from plugin_manager.plugin_state import PluginState
from plugin_manager.settings_manager import SettingsManager
from plugin_sdk.config_types import IntConfig, OtherInfoBase, TextConfig
from plugin_sdk.plugin_base import LogLevel, WindowMode
import plugin_manager.main_window as mw


@pytest.fixture(autouse=True)
def offscreen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(mw, "action_icon",
                        lambda _name: QIcon(QPixmap(16, 16)))
    monkeypatch.setattr(mw, "set_button_box_icons", lambda _box: None)


class _OtherInfo(OtherInfoBase):
    upload_token = TextConfig("", "令牌", description="上传令牌")
    count = IntConfig(1, "数量", min_value=0, max_value=10)

    @classmethod
    def settings_extra_hints(cls, config_path: Path) -> list[str]:
        return [f"配置路径 {config_path.name}", "请备份令牌"]


class _OtherInfoNoHints(OtherInfoBase):
    count = IntConfig(2, "数量")


def _dialog(qtbot, **kwargs):
    dlg = PluginSettingsDialog("demo", **kwargs)
    qtbot.addWidget(dlg)
    return dlg


def test_plugin_settings_defaults_without_other_info_or_plugin(qtbot):
    dlg = _dialog(qtbot, state=PluginState())
    assert "demo" in dlg.windowTitle()
    assert dlg._config_widget is None
    assert dlg._chk_enabled.isChecked() is True
    assert dlg._chk_show.isChecked() is True
    assert dlg._combo_mode.currentData() == "tab"
    assert dlg._combo_loglevel.currentData() == "DEBUG"

    accepted = []
    dlg.accepted.connect(lambda: accepted.append(True))
    dlg._on_ok_clicked()
    assert accepted == [True]
    dlg.apply_config()


def test_plugin_settings_invalid_log_and_window_modes_fall_back(qtbot):
    state = PluginState(enabled=False, show_window=False,
                        window_mode="bogus", log_level="weird")
    dlg = _dialog(qtbot, state=state)
    assert dlg._chk_enabled.isChecked() is False
    assert dlg._chk_show.isChecked() is False
    assert dlg._combo_mode.currentIndex() == 0
    assert dlg._combo_loglevel.currentIndex() == 1
    assert dlg._combo_loglevel.currentData() == "DEBUG"


def test_plugin_settings_result_state_reflects_all_controls(qtbot):
    dlg = _dialog(qtbot, state=PluginState())
    dlg._chk_enabled.setChecked(False)
    dlg._chk_show.setChecked(False)
    dlg._combo_mode.setCurrentIndex(dlg._combo_mode.findData("detached"))
    dlg._combo_loglevel.setCurrentIndex(dlg._combo_loglevel.findData("ERROR"))

    result = dlg.result_state
    assert result == PluginState(
        enabled=False, show_window=False,
        window_mode=WindowMode.DETACHED, log_level=LogLevel.ERROR,
    )


def test_plugin_settings_with_plugin_icon(qtbot):
    icon = QIcon(QPixmap(20, 20))
    dlg = _dialog(
        qtbot, state=PluginState(),
        plugin=SimpleNamespace(plugin_icon=icon, other_info=None),
    )
    assert dlg.windowIcon().cacheKey() == icon.cacheKey()


def test_plugin_settings_custom_config_with_plugin_and_hints(qtbot, tmp_path):
    other = _OtherInfo()
    config_path = tmp_path / "config.json"
    plugin = SimpleNamespace(
        plugin_icon=QIcon(), other_info=other,
        config_file_path=config_path, info=SimpleNamespace(name="demo"),
    )
    dlg = _dialog(qtbot, state=PluginState(), other_info=other, plugin=plugin)
    assert dlg._config_widget is not None
    assert isinstance(dlg.layout().itemAt(dlg.layout().count() - 3).widget(), QWidget)
    labels = [w.text() for w in dlg.findChildren(QLabel)
              if "配置路径" in w.text() or "请备份令牌" in w.text()]
    assert any("config.json" in text for text in labels)
    assert "请备份令牌" in labels
    tooltip = dlg._config_widget._inner_widget._widgets["upload_token"].toolTip()
    assert "config.json" in tooltip


def test_plugin_settings_custom_config_without_plugin(qtbot):
    other = _OtherInfo()
    dlg = _dialog(qtbot, state=PluginState(), other_info=other)
    assert dlg._config_widget is not None
    labels = [w.text() for w in dlg.findChildren(QLabel)]
    assert not any("配置路径" in text for text in labels)


def test_plugin_settings_custom_config_with_no_hints(qtbot):
    other = _OtherInfoNoHints()
    plugin = SimpleNamespace(
        plugin_icon=QIcon(), other_info=other, config_file_path=None,
        info=SimpleNamespace(name="demo"),
    )
    dlg = _dialog(qtbot, state=PluginState(), other_info=other, plugin=plugin)
    assert dlg._config_widget is not None


def test_plugin_settings_ok_without_errors_applies_and_accepts(qtbot, monkeypatch):
    other = _OtherInfo()
    dlg = _dialog(qtbot, state=PluginState(), other_info=other,
                  plugin=SimpleNamespace(plugin_icon=QIcon(), other_info=other))
    monkeypatch.setattr(dlg._config_widget, "validate_pending",
                        Mock(return_value={}))
    monkeypatch.setattr(dlg._config_widget, "clear_highlights", Mock())
    monkeypatch.setattr(dlg._config_widget, "apply_to_config", Mock())
    accepted = []
    dlg.accepted.connect(lambda: accepted.append(True))

    dlg._on_ok_clicked()
    assert accepted == [True]
    dlg._config_widget.clear_highlights.assert_called_once()
    dlg.apply_config()
    dlg._config_widget.apply_to_config.assert_called_once()


def test_plugin_settings_ok_reports_validation_errors(qtbot, monkeypatch):
    other = _OtherInfo()
    dlg = _dialog(qtbot, state=PluginState(), other_info=other,
                  plugin=SimpleNamespace(plugin_icon=QIcon(), other_info=other))
    monkeypatch.setattr(dlg._config_widget, "validate_pending",
                        Mock(return_value={"count": "太小", "_plugin": "失败"}))
    monkeypatch.setattr(dlg._config_widget, "highlight_errors", Mock())
    monkeypatch.setattr(dlg._config_widget, "clear_highlights", Mock())
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *args: warnings.append(args))
    accepted = []
    dlg.accepted.connect(lambda: accepted.append(True))

    dlg._on_ok_clicked()

    assert accepted == []
    dlg._config_widget.highlight_errors.assert_called_once_with(
        {"count": "太小", "_plugin": "失败"})
    dlg._config_widget.clear_highlights.assert_not_called()
    assert len(warnings) == 1
    assert "太小" in warnings[0][2] and "失败" in warnings[0][2]


def test_plugin_settings_ok_handles_validator_exception(qtbot, monkeypatch):
    other = _OtherInfo()
    dlg = _dialog(qtbot, state=PluginState(), other_info=other)

    def boom(_plugin):
        raise RuntimeError("validator crashed")

    monkeypatch.setattr(dlg._config_widget, "validate_pending",
                        Mock(side_effect=boom))
    monkeypatch.setattr(dlg._config_widget, "highlight_errors", Mock())
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *args: warnings.append(args))

    dlg._on_ok_clicked()

    assert "validator crashed" in warnings[0][2]
    assert dlg._config_widget.highlight_errors.call_args[0][0] == {
        "_plugin": "validator crashed"}


def test_plugin_settings_apply_config_noop_without_widget(qtbot):
    dlg = _dialog(qtbot, state=PluginState())
    dlg.apply_config()
    assert dlg._config_widget is None


def test_basic_settings_initializes_from_manager(qtbot, tmp_path):
    manager = SettingsManager(tmp_path)
    manager.set_file_log_level("WARNING")
    manager.set_viewer_log_level("ERROR")
    manager.set_viewer_auto_scroll(False)
    manager.set_viewer_show_source(True)
    dlg = BasicSettingsDialog(manager)
    qtbot.addWidget(dlg)

    assert dlg._file_log_level_combo.currentText() == "WARNING"
    assert dlg._viewer_log_level_combo.currentText() == "ERROR"
    assert dlg._auto_scroll_cb.isChecked() is False
    assert dlg._show_source_cb.isChecked() is True
    assert dlg._settings_manager is manager


def test_basic_settings_accepts_without_changes(qtbot, tmp_path):
    manager = SettingsManager(tmp_path)
    dlg = BasicSettingsDialog(manager)
    qtbot.addWidget(dlg)
    seen = []
    dlg.settings_changed.connect(lambda: seen.append(True))
    accepted = []
    dlg.accepted.connect(lambda: accepted.append(True))

    dlg._on_accept()

    assert seen == []
    assert accepted == [True]


def test_basic_settings_persists_every_changed_control(qtbot, tmp_path):
    manager = SettingsManager(tmp_path)
    dlg = BasicSettingsDialog(manager)
    qtbot.addWidget(dlg)
    seen = []
    dlg.settings_changed.connect(lambda: seen.append(True))

    dlg._file_log_level_combo.setCurrentText("CRITICAL")
    dlg._viewer_log_level_combo.setCurrentText("TRACE")
    dlg._auto_scroll_cb.setChecked(False)
    dlg._show_source_cb.setChecked(True)
    dlg._on_accept()

    assert manager.settings.file_log_level == "CRITICAL"
    assert manager.settings.viewer_log_level == "TRACE"
    assert manager.settings.viewer_auto_scroll is False
    assert manager.settings.viewer_show_source is True
    assert seen == [True]
    reloaded = SettingsManager(tmp_path)
    assert reloaded.settings == manager.settings


def test_basic_settings_unknown_initial_values_use_first_item(qtbot, tmp_path):
    manager = SettingsManager(tmp_path)
    manager._settings.file_log_level = "UNKNOWN"  # type: ignore[assignment]
    manager._settings.viewer_log_level = "UNKNOWN"  # type: ignore[assignment]
    dlg = BasicSettingsDialog(manager)
    qtbot.addWidget(dlg)
    assert dlg._file_log_level_combo.currentIndex() == 0
    assert dlg._viewer_log_level_combo.currentIndex() == 0
