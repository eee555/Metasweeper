from pathlib import Path
from threading import Event

import pytest
from PySide6.QtCore import QPoint, QThread

import plugin_manager.main_window as mw
from plugin_manager.dependency_scan import DependencyDiagnostic, PluginDependencyStatus
from tests.plugin_manager.test_cov_pm_e_helpers import _offscreen, make_plugin, shell  # noqa: F401
from tests.plugin_manager.test_cov_pm_e_list import _capture_menu, _install


def test_failed_plugin_shows_dependency_detail(qtbot, monkeypatch, tmp_path):
    w = shell(qtbot)
    manager, _ = _install(w, qtbot, {})
    status = PluginDependencyStatus(
        "broken", tmp_path / "broken" / "__init__.py",
        tmp_path / "broken" / "requirements.txt", "missing",
        (DependencyDiagnostic(1, "missing-package>=2", "missing"),),
        "failed", "ModuleNotFoundError: missing_package")
    manager.module_dependency_statuses = {"broken": status}
    manager.get_module_dependency_status = lambda name: status
    w._refresh_plugin_list()
    item = w._list.item(0)
    assert "加载失败" in item.text()
    assert "missing-package>=2" in item.toolTip()
    menus = _capture_menu(monkeypatch)
    monkeypatch.setattr(w._list, "itemAt", lambda pos: item)
    shown = []
    monkeypatch.setattr("plugin_manager.main_window.QDialog.exec",
                        lambda dialog: shown.append(dialog))
    w._on_list_context_menu(QPoint(1, 1))
    menus[0].items[0].trigger()
    assert shown
    assert shown[0].windowTitle().endswith("broken")
    assert any("ModuleNotFoundError" in label.text()
               for label in shown[0].findChildren(mw.QLabel))


def test_dependency_details_show_each_installed_and_missing_package(qtbot, tmp_path):
    w = shell(qtbot)
    status = PluginDependencyStatus(
        "demo", tmp_path / "__init__.py", tmp_path / "requirements.txt", "missing",
        (
            DependencyDiagnostic(1, "present>=1", "satisfied", "1.2"),
            DependencyDiagnostic(2, "absent>=2", "missing"),
        ),
        "loaded")
    text = w._dependency_text(status)
    assert "present>=1: 已安装 (已安装版本 1.2)" in text
    assert "absent>=2: 未安装" in text


def test_dependency_dialog_uses_table_for_installed_and_missing(qtbot, monkeypatch, tmp_path):
    w = shell(qtbot)
    manager, _ = _install(w, qtbot, {})
    status = PluginDependencyStatus(
        "demo", tmp_path / "__init__.py", tmp_path / "requirements.txt", "missing",
        (
            DependencyDiagnostic(1, "present>=1", "satisfied", "1.2"),
            DependencyDiagnostic(2, "absent>=2", "missing"),
        ),
        "loaded")
    w._manager.get_module_dependency_status = lambda name: status
    dialogs = []
    monkeypatch.setattr("plugin_manager.main_window.QDialog.exec",
                        lambda dialog: dialogs.append(dialog))
    w._show_dependency_details("demo")
    table = dialogs[0].findChild(mw.QTableWidget)
    assert table.rowCount() == 2
    assert [table.item(0, col).text() for col in range(3)] == [
        "present>=1", "1.2", "已安装"]
    assert [table.item(1, col).text() for col in range(3)] == [
        "absent>=2", "—", "未安装"]


def test_dependency_install_requires_explicit_button_click(
        qtbot, monkeypatch, tmp_path):
    w = shell(qtbot)
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("humanize>=4,<5\n", encoding="utf-8")
    status = PluginDependencyStatus(
        "demo", tmp_path / "__init__.py", requirements, "missing",
        (DependencyDiagnostic(1, "humanize>=4,<5", "missing"),), "loaded")
    manager, _ = _install(w, qtbot, {})
    manager.get_module_dependency_status = lambda name: status
    dialogs = []
    monkeypatch.setattr("plugin_manager.main_window.QDialog.exec",
                        lambda dialog: dialogs.append(dialog))
    installs = []
    monkeypatch.setattr(mw, "install_plugin_requirements",
                        lambda data_dir, path, *, output_callback: installs.append((data_dir, path)))

    w._show_dependency_details("demo")
    assert installs == []
    button = next(
        btn for btn in dialogs[0].findChildren(mw.QPushButton)
        if "手动安装" in btn.text())
    button.click()

    qtbot.waitUntil(lambda: not w._install_progress._active)
    assert installs == [(mw.get_data_dir(), requirements)]
    assert "重启插件管理器" in w._install_progress._status.text()
    w._install_progress.close()


def test_loaded_plugin_does_not_annotate_satisfied_dependencies(qtbot):
    w = shell(qtbot)
    plugin = make_plugin(qtbot, "demo", widget=None)
    manager, _ = _install(w, qtbot, {"demo": plugin})
    status = PluginDependencyStatus(
        "demo_module", Path("demo/__init__.py"), Path("demo/requirements.txt"),
        "satisfied", (DependencyDiagnostic(1, "example>=2", "satisfied", "2.1"),),
        "loaded")
    manager.get_plugin_dependency_status = lambda name: status
    manager.module_dependency_statuses = {"demo_module": status}
    w._refresh_plugin_list()
    assert w._list.item(0).text() == "demo"
    assert w._list.item(0).toolTip() == ""


def test_loaded_plugin_displays_conflicting_dependency(qtbot, tmp_path):
    w = shell(qtbot)
    plugin = make_plugin(qtbot, "demo", widget=None)
    manager, _ = _install(w, qtbot, {"demo": plugin})
    status = PluginDependencyStatus(
        "demo_module", Path("demo/__init__.py"), Path("demo/requirements.txt"),
        "conflict", (DependencyDiagnostic(1, "example>=2", "conflict", "1"),), "loaded")
    manager.get_plugin_dependency_status = lambda name: status
    manager.module_dependency_statuses = {"demo_module": status}
    w._refresh_plugin_list()
    assert "依赖版本冲突" in w._list.item(0).text()
    assert w._list.item(0).toolTip() == ""


@pytest.mark.parametrize("raises", [False, True])
def test_install_progress_streams_without_blocking_and_handles_failure(
        qtbot, tmp_path, raises):
    w = shell(qtbot)
    release = Event()
    calls = []

    def installer(data_dir, *, output_callback):
        calls.append((data_dir, QThread.currentThread() == w.thread()))
        output_callback("first\n")
        if not release.wait(5):
            return "test timeout"
        output_callback("second\n")
        if raises:
            raise RuntimeError("installer exception")
        return "installation error"

    progress = w._start_installation("test", installer, (tmp_path,))
    try:
        progress.start()
        qtbot.waitUntil(lambda: progress._output.toPlainText() == "first\n")
        assert calls[0][0] == tmp_path
        assert calls[0][1] is False
        assert progress._active and not progress._close_button.isEnabled()
        progress.reject()
        assert progress.isVisible()
        progress.close()
        assert progress.isVisible()
        assert w._start_installation("duplicate", installer, (tmp_path,)) is None
        release.set()
        qtbot.waitUntil(lambda: not progress._active)
        assert progress._output.toPlainText() == "first\nsecond\n"
        assert "安装失败" in progress._status.text()
        assert ("installer exception" if raises else "installation error") in progress._status.text()
        assert progress._close_button.isEnabled()
        progress.close()
    finally:
        release.set()
        if progress._active:
            qtbot.waitUntil(lambda: not progress._active)
