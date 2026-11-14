"""Coverage for the log viewer dialog."""
from __future__ import annotations

from unittest.mock import Mock

import loguru
import pytest
from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from plugin_manager.main_window import LogViewerDialog
import plugin_manager.main_window as mw


@pytest.fixture(autouse=True)
def offscreen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(mw, "action_icon",
                        lambda _name: QIcon(QPixmap(16, 16)))
    monkeypatch.setattr(mw, "set_action_icon", lambda _target, _name: None)
    monkeypatch.setattr(mw, "set_button_box_icons", lambda _box: None)


@pytest.fixture
def viewer(qtbot):
    dlg = LogViewerDialog(
        ["alpha", "beta"], initial_log="main", initial_level="INFO",
        auto_scroll=False, show_source=True,
    )
    qtbot.addWidget(dlg)
    return dlg


def test_init_attaches_sink_and_builds_controls(viewer):
    assert viewer._sink_id is not None
    assert viewer._current_log == "main"
    assert viewer._current_level == "INFO"
    assert [viewer._log_combo.itemData(i)
            for i in range(viewer._log_combo.count())] == ["main", "alpha", "beta"]
    assert viewer._level_combo.currentText() == "INFO"
    assert viewer._auto_scroll_cb.isChecked() is False
    assert viewer._show_source_cb.isChecked() is True
    assert viewer._log_view.isReadOnly()
    assert viewer._log_view.maximumBlockCount() == 5000
    assert not viewer.windowIcon().isNull()


def test_append_line_formats_source_and_color_levels(viewer):
    viewer._append_log_line("12:00", "INFO", "mod:fn:1", "hello")
    viewer._append_log_line("12:01", "ERROR", "mod:fn:2", "bad")
    viewer._append_log_line("12:02", "CRITICAL", "mod:fn:3", "worse")
    viewer._append_log_line("12:03", "WARNING", "mod:fn:4", "careful")
    viewer._append_log_line("12:04", "DEBUG", "mod:fn:5", "detail")
    viewer._append_log_line("12:05", "TRACE", "mod:fn:6", "trace")
    viewer._append_log_line("12:06", "SUCCESS", "mod:fn:7", "other")

    text = viewer._log_view.toPlainText()
    assert "INFO    " not in text
    assert "12:00 | INFO | mod:fn:1 | hello" in text
    assert "worse" in text and "other" in text
    assert text.count("\n") == 6


def test_append_line_without_source_and_auto_scroll(viewer):
    viewer._show_source_cb.setChecked(False)
    viewer._auto_scroll_cb.setChecked(True)
    viewer._append_log_line("12:00", "INFO", "mod:fn:1", "hello")
    assert viewer._log_view.toPlainText() == "12:00 | INFO | hello"


def test_append_signal_from_real_sink_is_rendered(viewer):
    viewer._log_view.clear()
    logger = loguru.logger.bind(plugin="alpha")
    logger.info("from alpha")
    QApplication.processEvents()
    assert "from alpha" in viewer._log_view.toPlainText()


def test_attach_sink_removes_previous_and_filters(viewer):
    old_id = viewer._sink_id
    viewer._attach_sink("alpha")
    assert viewer._current_log == "alpha"
    assert viewer._sink_id is not None and viewer._sink_id != old_id
    assert viewer._log_view.toPlainText() == ""

    viewer._log_view.clear()
    loguru.logger.bind(plugin="beta").warning("wrong plugin")
    loguru.logger.bind(plugin="alpha").warning("right plugin")
    QApplication.processEvents()
    text = viewer._log_view.toPlainText()
    assert "right plugin" in text
    assert "wrong plugin" not in text


def test_attach_sink_handles_invalid_removed_sink(viewer, monkeypatch):
    def remove(_sink_id):
        raise ValueError("already gone")

    monkeypatch.setattr(loguru.logger, "remove", remove)
    viewer._attach_sink("main")
    assert viewer._current_log == "main"


def test_on_log_changed_and_on_level_changed(viewer):
    viewer._on_log_changed(2)
    assert viewer._current_log == "beta"

    viewer._on_level_changed(viewer._level_combo.findText("TRACE"))
    viewer._level_combo.setCurrentText("ERROR")
    viewer._on_level_changed(viewer._level_combo.currentIndex())
    assert viewer._current_level == "ERROR"


def test_clear_log_and_show_log_adds_missing_source(viewer):
    viewer._append_log_line("t", "INFO", "src", "line")
    viewer._clear_log()
    assert viewer._log_view.toPlainText() == ""

    viewer.show_log("main")
    assert viewer._current_log == "main"
    viewer.show_log("gamma")
    assert viewer._current_log == "gamma"
    assert viewer._log_combo.findData("gamma") >= 0
    assert viewer._log_combo.currentData() == "gamma"

    viewer.show_log("main")
    assert viewer._current_log == "main"


def test_show_log_missing_main_does_not_add_duplicate(viewer):
    count = viewer._log_combo.count()
    viewer.show_log("main")
    assert viewer._log_combo.count() == count

    viewer._log_combo.removeItem(0)
    viewer._log_combo.insertItem(0, "主进程", "main")
    viewer.show_log("main")
    assert viewer._log_combo.count() == count


def test_update_settings_changes_all_toggles_and_level(viewer):
    old_sink = viewer._sink_id
    viewer.update_settings("CRITICAL", True, False)
    assert viewer._current_level == "CRITICAL"
    assert viewer._level_combo.currentText() == "CRITICAL"
    assert viewer._sink_id != old_sink
    assert viewer._auto_scroll_cb.isChecked() is True
    assert viewer._show_source_cb.isChecked() is False

    same_sink = viewer._sink_id
    viewer.update_settings("CRITICAL", False, True)
    assert viewer._sink_id == same_sink
    assert viewer._auto_scroll_cb.isChecked() is False
    assert viewer._show_source_cb.isChecked() is True


def test_close_event_removes_sink(viewer):
    assert viewer._sink_id is not None
    viewer.close()
    assert viewer._sink_id is None


def test_close_event_handles_invalid_removed_sink(viewer, monkeypatch):
    monkeypatch.setattr(loguru.logger, "remove",
                        Mock(side_effect=ValueError("gone")))
    viewer.close()
    assert viewer._sink_id is None


def test_close_event_without_sink_is_safe(viewer):
    viewer._sink_id = None
    viewer.close()
    assert viewer._sink_id is None


def test_log_signal_emission_and_button_box_close(qtbot):
    dlg = LogViewerDialog([], initial_level="DEBUG")
    qtbot.addWidget(dlg)
    dlg._show_source_cb.setChecked(False)
    dlg._log_signal.emit("t", "INFO", "src", "via signal")
    QApplication.processEvents()
    assert "t | INFO | via signal" in dlg._log_view.toPlainText()

    boxes = dlg.findChildren(QDialogButtonBox)
    assert boxes
    dlg.close()
    assert dlg._sink_id is None
