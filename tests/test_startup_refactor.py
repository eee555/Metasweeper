import json
import subprocess
from types import SimpleNamespace

from app import cli_check, plugin_commands, plugin_process
from shared_types.commands import (
    COMMAND_TYPES, NON_CHEAT_TAGS, MouseClickCommand, NewGameCommand,
    command_tag,
)


def test_non_cheat_classification_contract():
    # 非作弊命令不得出现在高级设置的作弊开关里；含格子读取/代操作的命令仍在。
    cheat_tags = {command_tag(t) for t in COMMAND_TYPES} - NON_CHEAT_TAGS
    assert cheat_tags == {"new_preset_game", "mouse_click", "init_open"}
    assert "new_random_game" not in cheat_tags


def test_cli_missing_file_writes_next_to_main(monkeypatch, tmp_path):
    module_file = tmp_path / "src" / "app" / "cli_check.py"
    module_file.parent.mkdir(parents=True)
    monkeypatch.setattr(cli_check, "__file__", str(module_file))
    monkeypatch.setattr(cli_check.sys, "platform", "win32")

    assert cli_check.cli_check_file(str(tmp_path / "missing.evf")) == 0
    result = json.loads(
        (tmp_path / "src" / "out.json").read_text(encoding="utf-8"))
    assert result == {"error": "file not found", "data": []}


def test_cli_frozen_macos_writes_to_current_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(cli_check.sys, "platform", "darwin")
    monkeypatch.setattr(cli_check.sys, "frozen", True, raising=False)
    monkeypatch.chdir(tmp_path)

    assert cli_check.cli_check_file("missing.evf") == 0
    assert json.loads(
        (tmp_path / "out.json").read_text(encoding="utf-8"))["error"] == "file not found"


def test_cleanup_stops_bridge_before_terminating_and_kills_on_timeout(monkeypatch):
    calls = []

    class Process:
        def poll(self):
            calls.append("poll")
            return None

        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout):
            calls.append(("wait", timeout))
            if calls.count(("wait", timeout)) == 1:
                raise subprocess.TimeoutExpired("plugin_manager", timeout)

        def kill(self):
            calls.append("kill")

    bridge = SimpleNamespace(stop=lambda: calls.append("stop"))
    monkeypatch.setattr(plugin_process.GameServerBridge,
                        "instance", lambda: bridge)

    plugin_process.cleanup_plugin_process(Process())
    assert calls == ["stop", "poll", "terminate",
                     ("wait", 5), "kill", ("wait", 5)]


def test_plugin_commands_deny_controls_before_touching_game(monkeypatch):
    touched = []
    handlers = {}
    bridge = SimpleNamespace(register_handler=handlers.__setitem__)
    ui = SimpleNamespace(_allowed_controls=set(), gameMode=0,
                         setBoard_and_start=lambda *a: touched.append(a))
    plugin_commands.register_plugin_commands(bridge, ui)
    command = SimpleNamespace(request_id="test", level=5, mode=0)

    # mouse_click 属于作弊开关，开关为空时必须拒绝。
    assert not handlers[MouseClickCommand](command).success
    assert touched == []

    # new_random_game 等价于按 F2，不属于作弊开关：能否执行只由独立授权决定，
    # 与 _allowed_controls 无关。
    monkeypatch.setattr(plugin_commands, "_is_non_cheat_authorized",
                        lambda tag: False)
    assert not handlers[NewGameCommand](command).success
    assert touched == []
    monkeypatch.setattr(plugin_commands, "_is_non_cheat_authorized",
                        lambda tag: True)
    assert handlers[NewGameCommand](command).success
    assert len(touched) == 1
