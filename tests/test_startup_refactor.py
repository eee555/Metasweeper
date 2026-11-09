import json
import subprocess
from types import SimpleNamespace

from app import cli_check, plugin_commands, plugin_process
from shared_types.commands import MouseClickCommand, NewGameCommand


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


def test_plugin_commands_deny_controls_before_touching_game():
    handlers = {}
    bridge = SimpleNamespace(register_handler=handlers.__setitem__)
    ui = SimpleNamespace(_allowed_controls=set())
    plugin_commands.register_plugin_commands(bridge, ui)
    command = SimpleNamespace(request_id="test")

    assert not handlers[NewGameCommand](command).success
    assert not handlers[MouseClickCommand](command).success
