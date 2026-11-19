"""__init__, UI construction, tray, language events, menus and dialogs."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication, QListWidget, QMessageBox, QPushButton, QSystemTrayIcon, QWidget,
)

import plugin_manager.main_window as mw
import plugin_manager.logging_setup as logging_setup
import plugin_manager.app_paths as app_paths
from plugin_manager.main_window import ConnectionStatusWidget, PluginManagerWindow
from plugin_sdk.plugin_base import PluginLifecycle
from tests.plugin_manager.test_cov_pm_e_helpers import (  # noqa: F401
    _offscreen, make_manager, make_plugin, real_window, shell,
)


class _FakeDialog:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.exec_calls = 0
        self.deleted = False

    def exec(self):
        self.exec_calls += 1
        return QMessageBox.StandardButton.Yes

    def deleteLater(self):
        self.deleted = True


def test_full_init_builds_ui_signals_and_tray(qtbot, monkeypatch, tmp_path):
    plugin = make_plugin(qtbot, "alpha", widget=None)
    plugin.info.required_controls = []
    w = real_window(qtbot, monkeypatch, tmp_path, {"alpha": plugin})
    try:

        assert w._menu_plugins.title() == w.tr("插件")
        assert w._act_plugin_market.isEnabled()
        assert w._act_plugin_environment in w._menu_settings.actions()
        assert w._list.count() == 1
        assert w._list.item(0).text() == "alpha"
        assert w._conn_status is not None
        assert isinstance(w._conn_status, ConnectionStatusWidget)
        assert w._tray_icon.isVisible()
        assert w._tray_act_show in w._tray_menu.actions()
        assert w._tray_act_quit in w._tray_menu.actions()
        assert w._timer.isActive()
        assert callable(plugin.ready)
        w.retranslateUi()
        assert w._tray_act_show.text() == w.tr("显示主窗口")
        w._debug_act.setEnabled(False)
        monkeypatch.setattr(PluginManagerWindow, "_debug_active", False)
        w.retranslateUi()
        assert w._debug_act.text() == w.tr("启动调试")
        monkeypatch.setattr(PluginManagerWindow, "_debug_active", True)
        w.retranslateUi()
        assert w._debug_act.text() == w.tr("调试已启动")
    finally:
        w._timer.stop()
        w._tray_icon.hide()


def test_full_init_without_tray_and_language_change(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable",
                        staticmethod(lambda: False))
    w = real_window(qtbot, monkeypatch, tmp_path, tray=False)
    try:
        # 无托盘时属性存在但为 None，retranslateUi 不应抛 AttributeError
        assert w._tray_icon is None
        w.retranslateUi()
        assert w._status_bar_msg == w.tr("已连接到主进程")
        w.changeEvent(QEvent(QEvent.Type.LanguageChange))
        w.changeEvent(QEvent(QEvent.Type.Paint))
        assert w.windowTitle() == w.tr("插件管理器")
    finally:
        w._timer.stop()


def test_setup_tray_icon_unavailable(qtbot, monkeypatch, tmp_path):
    w = shell(qtbot)
    w._tray_icon = None
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable",
                        staticmethod(lambda: False))
    w._setup_tray_icon()
    assert w._tray_icon is None


def test_show_and_raise_and_tray_activation(qtbot, monkeypatch):
    w = shell(qtbot)
    calls = []
    monkeypatch.setattr(w, "show_and_raise", lambda: calls.append("show"))
    w._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
    w._on_tray_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
    assert calls == ["show"]

    original = PluginManagerWindow.show_and_raise
    w.show_and_raise = lambda: original(w)
    w.show()
    assert w.isVisible()
    w.showMinimized()
    w.show_and_raise()
    assert not w.isMinimized()
    w.hide()
    w.show_and_raise()
    assert w.isVisible()


def test_really_quit_and_global_settings(qtbot, monkeypatch):
    w = shell(qtbot)
    calls = []
    w._tray_icon = SimpleNamespace(hide=lambda: calls.append("hide"))
    w._state_mgr = SimpleNamespace(save=lambda: calls.append("save"))
    w._manager = SimpleNamespace(stop=lambda: calls.append("stop"))
    monkeypatch.setattr(mw, "QApplication", SimpleNamespace(
        instance=lambda: SimpleNamespace(quit=lambda: calls.append("quit"))))
    w._really_quit()
    assert calls == ["hide", "save", "stop", "quit"]

    monkeypatch.setattr(w, "_open_control_auth_dialog",
                        lambda: calls.append("auth"))
    w._open_global_settings()
    assert calls[-1] == "auth"


def test_really_quit_without_tray_does_not_raise(qtbot, monkeypatch):
    """无系统托盘时 _tray_icon 为 None，退出流程仍须完成。"""
    w = shell(qtbot)
    calls = []
    w._tray_icon = None
    w._state_mgr = SimpleNamespace(save=lambda: calls.append("save"))
    w._manager = SimpleNamespace(stop=lambda: calls.append("stop"))
    monkeypatch.setattr(mw, "QApplication", SimpleNamespace(
        instance=lambda: SimpleNamespace(quit=lambda: calls.append("quit"))))
    w._really_quit()
    assert calls == ["save", "stop", "quit"]


def test_open_dev_guide_missing_read_error_and_success(qtbot, monkeypatch, tmp_path):
    w = shell(qtbot)
    warnings = []
    monkeypatch.setattr(mw.QMessageBox, "warning",
                        lambda *args: warnings.append(args))
    monkeypatch.setattr(app_paths, "get_executable_dir", lambda: tmp_path)
    w._open_dev_guide()
    assert len(warnings) == 1 and "未找到" in warnings[0][2]

    guide = tmp_path / "plugin-dev-tutorial.md"
    guide.write_text("# Guide", encoding="utf-8")
    original_read = Path.read_text

    def broken_read(self, *args, **kwargs):
        if self == guide:
            raise OSError("nope")
        return original_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", broken_read)
    w._open_dev_guide()
    assert "无法读取文档" in warnings[1][2]

    monkeypatch.setattr(Path, "read_text", original_read)
    made = []

    class Readme:
        def __init__(self, name, content, parent=None, base_dir=None, title=None):
            made.append((name, content, parent, base_dir, title))

        def resize(self, *args):
            made.append(("resize", args))

        def exec(self):
            made.append("exec")

    monkeypatch.setattr(mw, "_PluginReadmeDialog", Readme)
    w._open_dev_guide()
    assert made[0][0] == "plugin-dev-tutorial"
    assert made[0][1] == "# Guide"
    assert made[0][3] == tmp_path
    assert ("resize", (900, 700)) in made and "exec" in made


def test_connect_signals_wires_controls(qtbot, monkeypatch):
    w = shell(qtbot)
    w._refresh_btn = QPushButton("refresh")
    qtbot.addWidget(w._refresh_btn)
    w._control_auth_btn = QPushButton("auth")
    qtbot.addWidget(w._control_auth_btn)
    w._list = QListWidget()
    qtbot.addWidget(w._list)
    calls = []
    monkeypatch.setattr(w, "_refresh_plugin_list",
                        lambda: calls.append("refresh"))
    monkeypatch.setattr(w, "_on_list_double_clicked",
                        lambda item: calls.append(("double", item)))
    monkeypatch.setattr(w, "_on_list_context_menu",
                        lambda pos: calls.append(("menu", pos)))
    monkeypatch.setattr(w, "_on_conn_changed",
                        lambda ok: calls.append(("conn", ok)))
    monkeypatch.setattr(w, "_open_control_auth_dialog",
                        lambda: calls.append("auth"))
    w._connect_signals()
    w._refresh_btn.click()
    w._control_auth_btn.click()
    w.set_connected(False)
    assert calls == ["refresh", "auth", ("conn", False)]
    # itemDoubleClicked / customContextMenuRequested connections exist.
    w._list.itemDoubleClicked.emit(None)
    w._list.customContextMenuRequested.emit(w._list.viewport().pos())
    assert calls[-2:] == [("double", None), ("menu", w._list.viewport().pos())]


def test_basic_settings_dialog_wires_callback(qtbot, monkeypatch):
    w = shell(qtbot)
    w._settings_mgr = SimpleNamespace(file_log_level="INFO")
    seen = []
    monkeypatch.setattr(logging_setup, "set_console_log_level",
                        lambda level: seen.append(level))
    monkeypatch.setattr(w, "_on_settings_changed", lambda: seen.append("changed"))

    class Dialog:
        settings_changed = SimpleNamespace(connect=lambda cb: seen.append(cb))

        def __init__(self, settings, parent):
            seen.append((settings, parent))

        def exec(self):
            seen.append("exec")

    monkeypatch.setattr(mw, "BasicSettingsDialog", Dialog)
    w._open_basic_settings_dialog()
    assert seen[0] == (w._settings_mgr, w)
    assert "exec" in seen
    callback = next(item for item in seen if callable(item))
    callback()
    assert seen[-1] == "changed"


def test_environment_dialog_wires_callback(qtbot, monkeypatch):
    w = shell(qtbot)
    w._settings_mgr = SimpleNamespace()
    seen = []
    monkeypatch.setattr(w, "_on_plugin_environment_changed", lambda: seen.append("changed"))

    class Dialog:
        settings_changed = SimpleNamespace(connect=lambda cb: seen.append(cb))

        def __init__(self, settings, parent):
            assert settings is w._settings_mgr and parent is w

        def exec(self):
            seen.append("exec")

    monkeypatch.setattr(mw, "PluginEnvironmentDialog", Dialog)
    w._open_plugin_environment_dialog()
    next(item for item in seen if callable(item))()
    assert seen[-2:] == ["exec", "changed"]


def test_on_settings_changed_applies_level_and_status(qtbot, monkeypatch):
    w = shell(qtbot)
    w._settings_mgr = SimpleNamespace(file_log_level="WARNING", plugin_lib_dir="")
    seen = []
    monkeypatch.setattr(logging_setup, "set_console_log_level",
                        lambda level: seen.append(level))
    monkeypatch.setattr(w, "tr", lambda text: (
        "settings-saved" if text == "设置已保存" else text))
    w._on_settings_changed()
    assert seen == ["WARNING"]
    assert w.statusBar().currentMessage() == "settings-saved"


def test_on_environment_changed_hints_restart_for_lib_dir(qtbot, monkeypatch):
    w = shell(qtbot)
    monkeypatch.setattr(w, "tr", lambda text: text)
    w._on_plugin_environment_changed()
    assert "重启" in w.statusBar().currentMessage()


def test_clear_all_logs_confirms_and_truncates(qtbot, monkeypatch, tmp_path):
    w = shell(qtbot)
    log_dir = tmp_path / "logs"
    (log_dir / "plugins").mkdir(parents=True)
    (log_dir / "main.log").write_text("main", encoding="utf-8")
    (log_dir / "plugins" / "alpha.log").write_text("alpha", encoding="utf-8")
    monkeypatch.setattr(app_paths, "get_data_dir", lambda: tmp_path)
    asked = []

    def fake_question(*args, **kwargs):
        asked.append(args)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(mw.QMessageBox, "question", fake_question)
    warnings = []
    monkeypatch.setattr(mw.QMessageBox, "warning",
                        lambda *a, **k: warnings.append(a))
    cleared_viewer = []
    w._log_viewer_dlg = SimpleNamespace(
        clear_display=lambda: cleared_viewer.append(True))

    w._clear_all_logs()

    assert asked and "logs" in asked[0][2]
    assert (log_dir / "main.log").read_text(encoding="utf-8") == ""
    assert (log_dir / "plugins" / "alpha.log").read_text(encoding="utf-8") == ""
    assert cleared_viewer == [True]
    assert not warnings
    assert w.statusBar().currentMessage() == w.tr("已清理 {n} 个日志文件").format(n=2)


def test_clear_all_logs_cancelled_changes_nothing(qtbot, monkeypatch, tmp_path):
    w = shell(qtbot)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    target = log_dir / "main.log"
    target.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(app_paths, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(mw.QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.No)
    cleared_viewer = []
    w._log_viewer_dlg = SimpleNamespace(
        clear_display=lambda: cleared_viewer.append(True))

    w._clear_all_logs()

    assert target.read_text(encoding="utf-8") == "keep"
    assert cleared_viewer == []


def test_clear_all_logs_reports_failures(qtbot, monkeypatch, tmp_path):
    w = shell(qtbot)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "main.log").write_text("main", encoding="utf-8")
    monkeypatch.setattr(app_paths, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(mw.QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(
        "plugin_manager.logging_setup.clear_all_logs",
        lambda _dir: (1, ["C:/logs/locked.log"]))
    warnings = []
    monkeypatch.setattr(mw.QMessageBox, "warning",
                        lambda *a, **k: warnings.append(a))

    w._clear_all_logs()

    assert warnings
    assert "1" in warnings[0][2]


def test_open_log_viewer_creates_then_reuses(qtbot, monkeypatch):
    w = shell(qtbot)
    w._settings_mgr = SimpleNamespace(
        viewer_log_level="INFO", viewer_auto_scroll=True,
        viewer_show_source=False)
    w._manager = SimpleNamespace(plugins={"a": object(), "b": object()})

    class Viewer:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.calls = []

        def update_display_names(self, names):
            self.calls.append(("display_names", names))

        def update_settings(self, *args):
            self.calls.append(("update", args))

        def show_log(self, name):
            self.calls.append(("log", name))

        def show(self):
            self.calls.append("show")

        def raise_(self):
            self.calls.append("raise")

        def activateWindow(self):
            self.calls.append("activate")

    monkeypatch.setattr(mw, "LogViewerDialog", Viewer)
    w._open_log_viewer()
    dlg = w._log_viewer_dlg
    assert dlg.args[0] == ["a", "b"] and dlg.args[1] == "main"
    assert dlg.args[-1] is w
    assert dlg.calls == ["show", "raise", "activate"]

    w._open_log_viewer(initial_log="b")
    assert w._log_viewer_dlg is dlg
    assert dlg.calls[-5:] == [
        ("update", ("INFO", True, False)), ("log", "b"),
        "show", "raise", "activate",
    ]


def test_open_control_auth_dialog_collects_ready_required(qtbot, monkeypatch):
    w = shell(qtbot)
    required = [object]
    ready = make_plugin(qtbot, "ready", info=SimpleNamespace(required_controls=required))
    not_ready = make_plugin(qtbot, "initializing", PluginLifecycle.INITIALIZING,
                            info=SimpleNamespace(required_controls=required))
    empty = make_plugin(qtbot, "empty")
    w._manager = SimpleNamespace(plugins={
        "ready": ready, "initializing": not_ready, "empty": empty})
    seen = []

    class Dialog:
        def __init__(self, controls, parent, display_names=None):
            seen.append((controls, parent))

        def deleteLater(self):
            seen.append("deleteLater")

        def exec(self):
            seen.append("exec")

    monkeypatch.setattr(mw, "ControlAuthorizationDialog", Dialog)
    w._open_control_auth_dialog()
    assert seen[0] == ({"ready": required}, w) and seen[1] == "exec"


def test_connection_status_branches_and_poll_exception(qtbot):
    w = shell(qtbot)
    calls = []
    w._conn_status = SimpleNamespace(
        set_status=lambda ok, rc: calls.append(("status", ok, rc)))
    w._manager = SimpleNamespace(reconnect_count=0)
    w.connection_changed.connect(w._on_conn_changed)
    w.set_connected(True)
    assert w.statusBar().currentMessage() == w.tr("已连接到主进程")

    w._manager.reconnect_count = 0
    w.set_connected(False)
    assert w.tr("未连接到主进程") in w.statusBar().currentMessage()

    w._manager.reconnect_count = 3
    w.set_connected(False)
    assert "3" in w.statusBar().currentMessage()

    w._manager.reconnect_count = 1
    w._manager.is_connected = False
    w._poll_connection_status()
    assert calls[-1] == ("status", False, 1)

    class Broken:
        @property
        def is_connected(self):
            raise RuntimeError("offline")

        reconnect_count = 9

    w._manager = Broken()
    w._poll_connection_status()
    assert calls[-1] == ("status", False, 1)


def test_start_debug_success_and_failure_branches(qtbot, monkeypatch):
    w = shell(qtbot)
    w._debug_act = QAction("调试")
    warnings = []
    monkeypatch.setattr(mw.QMessageBox, "warning",
                        lambda *args: warnings.append(args))
    monkeypatch.setattr(PluginManagerWindow, "_debug_active", False)
    listens = []
    monkeypatch.setitem(sys.modules, "debugpy", SimpleNamespace(
        listen=lambda *args, **kwargs: listens.append((args, kwargs))))
    w._start_debug()
    assert listens and listens[0][1] == {"in_process_debug_adapter": True}
    assert listens[0][0][0] == ("0.0.0.0", 5678)
    assert PluginManagerWindow._debug_active is True
    assert not w._debug_act.isEnabled()
    assert "5678" in w.statusBar().currentMessage()

    monkeypatch.setitem(sys.modules, "debugpy", SimpleNamespace(
        listen=lambda *a, **k: (_ for _ in ()).throw(ImportError("missing"))))
    w._start_debug()
    assert "启动调试服务失败" in warnings[-1][2]

    monkeypatch.setitem(sys.modules, "debugpy", SimpleNamespace(
        listen=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("port"))))
    w._start_debug()
    assert "port" in warnings[-1][2]


def test_start_debug_installs_missing_debugpy_only_after_confirmation(
        qtbot, monkeypatch):
    w = shell(qtbot)
    w._debug_act = QAction("调试")
    monkeypatch.setattr(PluginManagerWindow, "_debug_active", False)
    monkeypatch.setitem(sys.modules, "debugpy", None)
    asked = []
    monkeypatch.setattr(
        mw.QMessageBox, "question",
        lambda *args: asked.append(args) or mw.QMessageBox.StandardButton.Yes)
    installed = []
    listens = []

    def install(data_dir, *, output_callback):
        installed.append(data_dir)
        monkeypatch.setitem(sys.modules, "debugpy", SimpleNamespace(
            listen=lambda *args, **kwargs: listens.append((args, kwargs))))
        return None

    monkeypatch.setattr(mw, "install_debugpy", install)
    w._start_debug()
    qtbot.waitUntil(lambda: not w._install_progress._active)

    assert asked and installed
    assert listens and listens[0][0][0] == ("0.0.0.0", 5678)
    w._install_progress.close()
    assert PluginManagerWindow._debug_active is True


def test_plugin_ready_and_stopped_refresh(qtbot, monkeypatch):
    w = shell(qtbot)
    seen = []
    monkeypatch.setattr(w, "_refresh_plugin_list", lambda: seen.append("refresh"))
    p = SimpleNamespace(name="demo")
    w._on_plugin_ready(p)
    assert w.tr("插件 {name} 就绪").format(name="demo") in w.statusBar().currentMessage()
    w._on_plugin_stopped(p)
    assert seen == ["refresh", "refresh"]


def test_close_event_tray_and_confirmation_branches(qtbot, monkeypatch):
    w = shell(qtbot)
    original = PluginManagerWindow.closeEvent
    w.closeEvent = lambda event: original(w, event)
    try:
        calls = []
        w._state_mgr = SimpleNamespace(save=lambda: calls.append("save"))
        w._manager = SimpleNamespace(stop=lambda: calls.append("stop"))
        for supports in (True, False):
            w._tray_icon = SimpleNamespace(
                isVisible=lambda: True,
                supportsMessages=lambda: supports,
                showMessage=lambda *args: calls.append("message"))
            event = QCloseEvent()
            w.closeEvent(event)
            assert not event.isAccepted()
            assert not w.isVisible()
            assert ("message" in calls) is supports
            calls.clear()

        w._tray_icon = SimpleNamespace(isVisible=lambda: False)
        monkeypatch.setattr(mw.QMessageBox, "question",
                            lambda *args: QMessageBox.StandardButton.Yes)
        accepted = QCloseEvent()
        w.closeEvent(accepted)
        assert accepted.isAccepted() and calls == ["save", "stop"]

        calls.clear()
        monkeypatch.setattr(mw.QMessageBox, "question",
                            lambda *args: QMessageBox.StandardButton.No)
        ignored = QCloseEvent()
        w.closeEvent(ignored)
        assert not ignored.isAccepted() and calls == []
    finally:
        w.closeEvent = lambda event: event.accept()
