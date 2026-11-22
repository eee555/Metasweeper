"""执行主入口启动路径：插件子进程启动时即可取得实际语言。"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_main_seeds_language_and_registers_handlers_before_spawning_manager(monkeypatch):
    calls = []
    window = SimpleNamespace(show=lambda: None)
    ui = SimpleNamespace(language="de_DE", mainWindow=window)
    bridge = SimpleNamespace(
        start=lambda: calls.append("server-start"),
        send_event=lambda event: calls.append(("language", event.language)),
    )
    application = SimpleNamespace(
        setStyle=lambda style: None,
        aboutToQuit=SimpleNamespace(connect=lambda fn: None),
        exec=lambda: 0,
    )

    def spawn(actual_ui, actual_window, disabled):
        assert actual_ui is ui and actual_window is window and not disabled
        assert calls == ["server-start", ("language", "de_DE"), "commands", "queries"]
        calls.append("spawn")
        return object()

    modules = {
        "policy_guard": SimpleNamespace(enforce_policy_integrity=lambda: None),
        "mainWindowGUI": SimpleNamespace(MainWindow=lambda: window),
        "mineSweeperGUI": SimpleNamespace(MineSweeperGUI=lambda *args: ui),
        "plugin_sdk": SimpleNamespace(GameServerBridge=SimpleNamespace(instance=lambda: bridge)),
        "app.startup_platform": SimpleNamespace(
            on_new_connection=lambda *args: None,
            configure_capture_guard=lambda value: None,
        ),
        "app.cli_check": SimpleNamespace(cli_check_file=lambda value: 0),
        "app.plugin_process": SimpleNamespace(
            start_plugin_process=spawn,
            cleanup_plugin_process=lambda value: None,
            install_restart_action=lambda *args: None,
        ),
        "app.plugin_commands": SimpleNamespace(register_plugin_commands=lambda *args: calls.append("commands")),
        "app.plugin_queries": SimpleNamespace(register_plugin_queries=lambda *args: calls.append("queries")),
    }
    for name, value in modules.items():
        monkeypatch.setitem(sys.modules, name, value)

    from PySide6 import QtNetwork, QtWidgets
    real_application = QtWidgets.QApplication

    class StartupApplication:
        def __new__(cls, args):
            return application

        instance = staticmethod(real_application.instance)

    monkeypatch.setattr(QtWidgets, "QApplication", StartupApplication)
    monkeypatch.setattr(QtNetwork, "QLocalSocket", lambda: SimpleNamespace(
        connectToServer=lambda name: None,
        waitForConnected=lambda timeout: False,
    ))
    monkeypatch.setattr(QtNetwork, "QLocalServer", lambda: SimpleNamespace(
        listen=lambda name: None,
        newConnection=SimpleNamespace(connect=lambda callback: None),
    ))
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setenv("QT_FONT_DPI", "96")
    entry = Path(__file__).parents[2] / "src" / "main.py"
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(entry), run_name="__main__")
    assert exit_info.value.code == 0
    assert calls[-1] == "spawn"
