"""SetSoundCommand 与音效控制命令链路测试。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from shared_types.commands import (  # noqa: E402
    COMMAND_TYPES, SOUND_EVENT_NAMES, SetSkinCommand, SetSoundCommand,
)
from utils.sound_manager import SoundManager  # noqa: E402
from shared_types.sounds import SOUND_FILES, SoundEvent  # noqa: E402
from app import sound_applier  # noqa: E402
from app.sound_applier import capture_startup_settings, handle_set_sound  # noqa: E402


class _FakeUI:
    """主程序设置页只有开关/音量；音效包不在这里。"""
    def __init__(self):
        self.sound_enabled = False
        self.sound_volume = 70


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _reset():
    SoundManager._instance = None
    sound_applier._STARTUP_SETTINGS.clear()
    yield
    SoundManager._instance = None


def _ui() -> _FakeUI:
    ui = _FakeUI()
    capture_startup_settings(ui)
    SoundManager.instance().configure(enabled=False, volume=70)
    return ui


def test_command_registered_and_independent_tag():
    assert SetSoundCommand in COMMAND_TYPES
    assert SetSoundCommand.__struct_config__.tag == "set_sound"
    assert SetSoundCommand.__struct_config__.tag != SetSkinCommand.__struct_config__.tag
    assert "open" in SOUND_EVENT_NAMES and "ready" in SOUND_EVENT_NAMES
    assert "question" not in SOUND_EVENT_NAMES


def test_command_roundtrip():
    from lib_zmq_plugins.serializer import Serializer
    s = Serializer()
    s.register_command_types(*COMMAND_TYPES)
    cmd = SetSoundCommand(enabled=True, volume=42, pack="soft",
                          play_event="win", request_id="r1")
    back = s.decode_command(s.encode_command(cmd))
    assert isinstance(back, SetSoundCommand)
    assert (back.enabled, back.volume, back.pack, back.play_event,
            back.request_id) == (True, 42, "soft", "win", "r1")


def test_handler_applies_settings(tmp_path):
    """主程序 handler 应用插件提供的 extra_dir 音效资源。"""
    pack_dir = tmp_path / "soft"
    pack_dir.mkdir()
    for filename in SOUND_FILES.values():
        (pack_dir / filename).write_bytes(b"test wav")
    ui = _ui()
    resp = handle_set_sound(ui, SetSoundCommand(
        enabled=True, volume=42, pack="soft",
        extra_dir=str(tmp_path), request_id="r1"))
    mgr = SoundManager.instance()
    assert resp.success and resp.error is None
    assert resp.request_id == "r1"
    assert mgr.current_enabled() is True
    assert mgr.current_volume() == 42
    assert mgr.current_pack() == "soft"
    assert mgr.resolve(SoundEvent.OPEN).parent.name == "soft"


def test_pack_without_extra_dir_falls_back_to_default():
    """主程序只有默认一组：只给 pack、不给插件落地目录时应回退根目录 wav。"""
    ui = _ui()
    handle_set_sound(ui, SetSoundCommand(enabled=True, pack="soft"))
    assert SoundManager.instance().resolve(SoundEvent.OPEN).parent.name == "sounds"


def test_handler_partial_update_keeps_other_fields():
    ui = _ui()
    handle_set_sound(ui, SetSoundCommand(enabled=True, volume=29, pack="soft"))
    # 只改开关，音量必须精确保持 29（此前会漂移到 28）
    handle_set_sound(ui, SetSoundCommand(enabled=True))
    mgr = SoundManager.instance()
    assert mgr.current_enabled() is True
    assert mgr.current_volume() == 29
    assert mgr.current_pack() == "soft"


def test_partial_update_volume_boundaries_no_drift():
    """29 / 57 / 58 是浮点截断会掉 1 的值。"""
    ui = _ui()
    for v in (29, 57, 58):
        handle_set_sound(ui, SetSoundCommand(volume=v))
        handle_set_sound(ui, SetSoundCommand(enabled=True))
        assert SoundManager.instance().current_volume() == v, v


def test_handler_reset_restores_startup_but_keeps_plugin_pack():
    """reset 只还原主程序职责（开关/音量）；音效包属于插件侧，不被越权清空。"""
    ui = _ui()
    handle_set_sound(ui, SetSoundCommand(enabled=True, volume=10, pack="soft"))
    resp = handle_set_sound(ui, SetSoundCommand(reset=True))
    mgr = SoundManager.instance()
    assert resp.success
    assert mgr.current_enabled() is False
    assert mgr.current_volume() == 70
    assert mgr.current_pack() == "soft"


def test_handler_rejects_invalid_params():
    ui = _ui()
    assert not handle_set_sound(ui, SetSoundCommand(volume=200)).success
    bad_event = handle_set_sound(ui, SetSoundCommand(play_event="nope"))
    assert not bad_event.success and "未知音效事件" in bad_event.error


def test_handler_rejects_unsafe_pack_and_extra_dir():
    ui = _ui()
    for bad in ("../..", "C:/Windows", "a/b"):
        resp = handle_set_sound(ui, SetSoundCommand(pack=bad))
        assert not resp.success and "非法音效包名" in resp.error
    resp = handle_set_sound(ui, SetSoundCommand(extra_dir="../.."))
    assert not resp.success and "非法音效库目录" in resp.error


def test_handler_preview_does_not_change_pack():
    ui = _ui()
    resp = handle_set_sound(ui, SetSoundCommand(
        enabled=True, play_event="open"))
    assert resp.success


def test_main_program_has_no_pack_setting():
    """主程序设置页不再有音效包/额外库入口与 ini 键。"""
    from dialogs import gameSettings
    import inspect
    src = inspect.getsource(gameSettings)
    assert "comboBox_sound_pack" not in src
    assert "lineEdit_sound_extra_dir" not in src
    assert "sound_pack" not in src
    assert "sound_extra_dir" not in src


def test_set_skin_command_reaches_host_handler(monkeypatch):
    """迁出插件后，主进程仍注册并处理 SetSkinCommand。"""
    from lib_zmq_plugins.shared.base import CommandResponse
    from app import plugin_commands

    captured = {}

    class _Bridge:
        def register_handler(self, cmd_type, handler):
            captured[cmd_type] = handler

    monkeypatch.setattr(plugin_commands, "_is_non_cheat_authorized", lambda _tag: True)
    monkeypatch.setattr(
        plugin_commands, "handle_set_skin",
        lambda _ui, cmd: CommandResponse(request_id=cmd.request_id, success=True))
    plugin_commands.register_plugin_commands(_Bridge(), object())
    response = captured[SetSkinCommand](SetSkinCommand(request_id="skin-host"))
    assert response.success
    assert response.request_id == "skin-host"


def test_end_to_end_command_to_handler():
    """序列化 → 解码 → handler 分派 → configure 全链路。"""
    from lib_zmq_plugins.serializer import Serializer
    from app import plugin_commands

    s = Serializer()
    s.register_command_types(*COMMAND_TYPES)
    cmd = SetSoundCommand(enabled=True, volume=29, pack="soft",
                          request_id="e2e")
    wire = s.encode_command(cmd)
    decoded = s.decode_command(wire)

    ui = _ui()
    ui._allowed_controls = set()
    captured = {}

    class _Bridge:
        def register_handler(self, cmd_type, handler):
            captured[cmd_type.__struct_config__.tag] = handler

    plugin_commands.register_plugin_commands(_Bridge(), ui)
    handler = captured["set_sound"]
    resp = handler(decoded)
    assert resp.success
    assert SoundManager.instance().current_volume() == 29
    assert SoundManager.instance().current_pack() == "soft"
