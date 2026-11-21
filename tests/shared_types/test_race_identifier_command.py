"""比赛标识命令：协议、独立授权、持久化及对局状态边界。"""
from types import SimpleNamespace
from unittest.mock import Mock

import msgspec
import pytest

from app import plugin_commands
from lib_zmq_plugins.serializer import Serializer
from plugin_sdk.control_auth import ControlAuthorizationManager
from shared_types import SetRaceIdentifierCommand
from shared_types.commands import COMMAND_TYPES, NON_CHEAT_TAGS
from superGUI import IniConfig


@pytest.fixture
def host(tmp_path, monkeypatch):
    # 本命令不依赖主进程授权文件，也不受 allowed_controls 开关约束。
    def unexpected_auth_check(tag):
        pytest.fail(f"不应进行主进程授权复查: {tag}")

    monkeypatch.setattr(plugin_commands, "_is_non_cheat_authorized",
                        unexpected_auth_check)
    settings = IniConfig(tmp_path / "gameSetting.ini")
    settings.set_value("DEFAULT/race_identifier", "old-race")
    settings.set_value("DEFAULT/player_identifier", "unchanged-player")
    settings.sync()
    board = SimpleNamespace(race_identifier="old-board-race", raw_data=b"saved")
    ui = SimpleNamespace(
        race_identifier="old-race", game_setting=settings,
        game_state="ready", _allowed_controls=set(),
        label=SimpleNamespace(ms_board=board),
        score_board_manager=SimpleNamespace(with_namespace=Mock(), show=Mock()),
        gameRestart=Mock(),
    )
    handlers = {}
    plugin_commands.register_plugin_commands(
        SimpleNamespace(register_handler=handlers.__setitem__), ui)
    return ui, handlers[SetRaceIdentifierCommand]


@pytest.mark.parametrize("identifier, expected", [
    ("  G1234  ", "G1234"),
    ("  周赛 2026  ", "周赛 2026"),
    ("", ""),
    (" \t\r\n", ""),
    ("old-race", "old-race"),
])
def test_command_roundtrip_and_host_persists_identifier(host, identifier, expected):
    ui, handler = host
    serializer = Serializer()
    serializer.register_command_types(*COMMAND_TYPES)
    command = SetRaceIdentifierCommand(
        request_id="race-request", race_identifier=identifier)
    decoded = serializer.decode_command(serializer.encode_command(command))

    assert isinstance(decoded, SetRaceIdentifierCommand)
    response = handler(decoded)

    assert response.success and response.request_id == "race-request"
    assert ui.race_identifier == expected
    reloaded = IniConfig(ui.game_setting.file_path)
    assert reloaded.value("DEFAULT/race_identifier") == expected
    assert reloaded.value("DEFAULT/player_identifier") == "unchanged-player"
    ui.score_board_manager.with_namespace.assert_called_once_with(
        {"race_identifier": expected})
    ui.score_board_manager.show.assert_called_once_with(ui.label.ms_board, index_type=1)
    assert ui.label.ms_board.race_identifier == "old-board-race"
    assert ui.label.ms_board.raw_data == b"saved"
    assert ui._allowed_controls == set() and ui.game_state == "ready"
    ui.gameRestart.assert_not_called()


@pytest.mark.parametrize("state", [
    "playing", "joking", "show", "win", "fail", "jowin", "jofail",
    "display", "showdisplay", "study", "modify",
])
def test_rejects_changes_outside_ready_without_side_effects(host, state):
    ui, handler = host
    ui.game_state = state
    before = ui.game_setting.file_path.read_bytes()

    response = handler(SetRaceIdentifierCommand(
        request_id="busy", race_identifier="new-race"))

    assert not response.success and response.request_id == "busy"
    assert "ready" in response.error
    assert ui.race_identifier == "old-race" and ui.game_state == state
    assert ui.game_setting.file_path.read_bytes() == before
    assert ui.game_setting.value("DEFAULT/race_identifier") == "old-race"
    ui.score_board_manager.with_namespace.assert_not_called()
    ui.score_board_manager.show.assert_not_called()
    ui.gameRestart.assert_not_called()


@pytest.mark.parametrize("identifier", [None, 123, True, b"G1234", []])
def test_invalid_identifier_is_rejected_on_wire_and_in_process(host, identifier):
    ui, handler = host
    before = ui.game_setting.file_path.read_bytes()
    payload = msgspec.msgpack.encode({
        "type": "set_race_identifier", "race_identifier": identifier,
    })
    serializer = Serializer()
    serializer.register_command_types(*COMMAND_TYPES)
    with pytest.raises(msgspec.ValidationError):
        serializer.decode_command(payload)

    response = handler(SetRaceIdentifierCommand(race_identifier=identifier))

    assert not response.success and "字符串" in response.error
    assert ui.race_identifier == "old-race"
    assert ui.game_setting.file_path.read_bytes() == before
    ui.score_board_manager.with_namespace.assert_not_called()


def test_persistence_failure_does_not_change_runtime_or_cached_setting(host, monkeypatch):
    ui, handler = host
    before = ui.game_setting.file_path.read_bytes()

    def fail_sync():
        raise OSError("read only")

    monkeypatch.setattr(ui.game_setting, "sync", fail_sync)
    response = handler(SetRaceIdentifierCommand(
        request_id="save-error", race_identifier="new-race"))

    assert not response.success and response.request_id == "save-error"
    assert "read only" in response.error
    assert ui.race_identifier == "old-race"
    assert ui.game_setting.value("DEFAULT/race_identifier") == "old-race"
    assert ui.game_setting.file_path.read_bytes() == before
    ui.score_board_manager.with_namespace.assert_not_called()
    ui.score_board_manager.show.assert_not_called()


def test_independent_plugin_authorization_and_non_cheat_classification(tmp_path, monkeypatch):
    monkeypatch.setattr(ControlAuthorizationManager, "_instance", None)
    manager = ControlAuthorizationManager(tmp_path)

    assert SetRaceIdentifierCommand in manager.get_all_control_types()
    assert "set_race_identifier" in NON_CHEAT_TAGS
    assert not manager.is_authorized(SetRaceIdentifierCommand, "race-plugin")
    manager.authorize(SetRaceIdentifierCommand, "race-plugin")
    assert manager.is_authorized(SetRaceIdentifierCommand, "race-plugin")
    assert not manager.is_authorized(SetRaceIdentifierCommand, "other-plugin")
    manager.revoke(SetRaceIdentifierCommand)
    assert not manager.is_authorized(SetRaceIdentifierCommand, "race-plugin")
