"""插件管理器菜单布局、动作绑定和运行时翻译。"""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from PySide6.QtCore import QEvent, QTranslator
from PySide6.QtWidgets import QApplication

from plugin_manager.main_window import PluginManagerWindow
from tests.plugin_manager.test_cov_pm_e_helpers import real_window


def find_lrelease() -> Path:
    """定位 pyside6-lrelease（兼容 venv 单目录与 setup-python 的 Scripts 布局）。"""
    name = "pyside6-lrelease.exe" if sys.platform == "win32" else "pyside6-lrelease"
    python_dir = Path(sys.executable).parent
    candidates = [python_dir / name, python_dir / "Scripts" / name]
    which = shutil.which(name)
    if which:
        candidates.append(Path(which))
    return next(path for path in candidates if path.is_file())


def test_menu_structure_and_actions(qtbot, monkeypatch, tmp_path):
    calls = []
    handlers = {
        "_open_plugin_market": "market",
        "_open_download_plugin": "download",
        "_open_basic_settings_dialog": "settings",
        "_open_plugin_environment_dialog": "environment",
        "_open_control_auth_dialog": "authorization",
        "_open_log_viewer": "logs",
        "_clear_all_logs": "clear",
        "_start_debug": "debug",
        "_open_dev_guide": "guide",
    }
    for method, name in handlers.items():
        monkeypatch.setattr(PluginManagerWindow, method,
                            lambda self, *args, name=name: calls.append(name))
    w = real_window(qtbot, monkeypatch, tmp_path, tray=False)
    assert [action.menu() for action in w.menuBar().actions()] == [
        w._menu_plugins, w._menu_settings, w._menu_tools, w._menu_help,
    ]
    # Qt 菜单栏遇到带图标的顶层菜单项会绘制图标而非标题。
    assert [action.text() for action in w.menuBar().actions()] == [
        "插件", "设置", "工具", "帮助",
    ]
    assert all(action.icon().isNull() for action in w.menuBar().actions())
    plugin_actions = w._menu_plugins.actions()
    assert plugin_actions[0] == w._act_plugin_market
    assert plugin_actions[1].isSeparator()
    assert plugin_actions[2:] == [w._act_download_plugin]
    assert w._menu_settings.actions() == [
        w._act_basic_settings, w._act_plugin_environment, w._act_control_auth,
    ]
    tools = w._menu_tools.actions()
    assert tools[:2] == [w._act_log_viewer, w._act_clear_logs]
    assert tools[2].isSeparator()
    assert tools[3:] == [w._debug_act]
    assert w._menu_help.actions() == [w._act_dev_guide]
    for action in (w._act_plugin_market, w._act_download_plugin,
                   w._act_basic_settings,
                   w._act_plugin_environment, w._act_control_auth,
                   w._act_log_viewer, w._act_clear_logs, w._debug_act,
                   w._act_dev_guide):
        action.trigger()
    w._control_auth_btn.click()
    assert calls == ["market", "download", "settings", "environment",
                     "authorization", "logs", "clear", "debug", "guide",
                     "authorization"]


@pytest.mark.parametrize("locale,titles,log_text", [
    ("en_US", ["Plugins", "Settings", "Tools", "Help"], "View logs"),
    ("de_DE", ["Plugins", "Einstellungen", "Werkzeuge", "Hilfe"], "Protokolle anzeigen"),
    ("ja_JP", ["プラグイン", "設定", "ツール", "ヘルプ"], "ログを表示"),
    ("pl_PL", ["Wtyczki", "Ustawienia", "Narzędzia", "Pomoc"], "Wyświetl dzienniki"),
])
def test_menu_runtime_language_change_during_debug_install(
        qtbot, monkeypatch, tmp_path, locale, titles, log_text):
    monkeypatch.setattr(PluginManagerWindow, "_debug_active", False)
    w = real_window(qtbot, monkeypatch, tmp_path, tray=False)
    w._debug_act.setEnabled(False)  # 安装调试依赖时暂时禁用
    translator = QTranslator()
    ts = Path(__file__).resolve().parents[2] / "src" / "ui" / f"{locale}.ts"
    qm = tmp_path / f"{locale}.qm"
    subprocess.run([str(find_lrelease()), str(ts), "-qm", str(qm)], check=True,
                   capture_output=True, text=True)
    assert translator.load(str(qm))
    app = QApplication.instance()
    app.installTranslator(translator)
    try:
        QApplication.sendEvent(w, QEvent(QEvent.Type.LanguageChange))
        assert [action.text() for action in w.menuBar().actions()] == titles
        assert all(action.icon().isNull() for action in w.menuBar().actions())
        assert w._act_log_viewer.text() == log_text
        for action, source in (
            (w._act_plugin_market, "插件市场..."),
            (w._act_download_plugin, "从仓库 URL 安装..."),
            (w._act_basic_settings, "基础设置..."),
            (w._act_plugin_environment, "插件依赖环境..."),
            (w._act_control_auth, "控制授权..."),
            (w._act_clear_logs, "清理全部日志..."),
            (w._act_dev_guide, "插件开发指南"),
        ):
            translated = translator.translate("PluginManagerWindow", source)
            assert translated and translated != source
            assert action.text() == translated
        assert w._debug_act.text() == translator.translate(
            "PluginManagerWindow", "启动调试")
        assert not w._debug_act.isEnabled()
        w._on_debug_install_finished("installation failed")
        assert w._debug_act.isEnabled()
        assert w._debug_act.text() == translator.translate(
            "PluginManagerWindow", "启动调试")
        w._debug_act.setEnabled(False)
        monkeypatch.setattr(PluginManagerWindow, "_debug_active", True)
        QApplication.sendEvent(w, QEvent(QEvent.Type.LanguageChange))
        assert w._debug_act.text() == translator.translate(
            "PluginManagerWindow", "调试已启动")
    finally:
        app.removeTranslator(translator)
        QApplication.sendEvent(w, QEvent(QEvent.Type.LanguageChange))
    assert [action.text() for action in w.menuBar().actions()] == [
        "插件", "设置", "工具", "帮助",
    ]
    assert all(action.icon().isNull() for action in w.menuBar().actions())


@pytest.mark.parametrize("locale,titles", [
    ("en_US", ["Plugins", "Settings", "Tools", "Help"]),
    ("de_DE", ["Plugins", "Einstellungen", "Werkzeuge", "Hilfe"]),
    ("ja_JP", ["プラグイン", "設定", "ツール", "ヘルプ"]),
    ("pl_PL", ["Wtyczki", "Ustawienia", "Narzędzia", "Pomoc"]),
])
def test_menu_initial_language(qtbot, monkeypatch, tmp_path, locale, titles):
    ts = Path(__file__).resolve().parents[2] / "src" / "ui" / f"{locale}.ts"
    qm = tmp_path / f"{locale}.qm"
    subprocess.run([str(find_lrelease()), str(ts), "-qm", str(qm)], check=True,
                   capture_output=True, text=True)
    translator = QTranslator()
    assert translator.load(str(qm))
    app = QApplication.instance()
    app.installTranslator(translator)
    try:
        w = real_window(qtbot, monkeypatch, tmp_path, tray=False)
        assert [action.text() for action in w.menuBar().actions()] == titles
        assert all(action.icon().isNull() for action in w.menuBar().actions())
        assert not w._act_basic_settings.icon().isNull()
    finally:
        app.removeTranslator(translator)
