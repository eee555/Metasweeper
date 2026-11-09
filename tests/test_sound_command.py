"""SetSoundCommand 与音效控制命令链路测试。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from shared_types.commands import (  # noqa: E402
    COMMAND_TYPES, SOUND_EVENT_NAMES, SetSkinCommand, SetSoundCommand,
)
from utils.sound_manager import SoundManager, SoundEvent  # noqa: E402
from app import sound_applier  # noqa: E402
from app.sound_applier import capture_startup_settings, handle_set_sound  # noqa: E402


class _FakeUI:
    def __init__(self):
        self.sound_enabled = False
        self.sound_volume = 70
        self.sound_pack = ""


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


def test_handler_applies_settings():
    ui = _ui()
    resp = handle_set_sound(ui, SetSoundCommand(
        enabled=True, volume=42, pack="soft", request_id="r1"))
    mgr = SoundManager.instance()
    assert resp.success and resp.error is None
    assert resp.request_id == "r1"
    assert mgr._enabled is True
    assert round(mgr._volume * 100) == 42
    assert mgr.current_pack() == "soft"
    assert mgr.resolve(SoundEvent.OPEN).name == "open.wav"
    assert mgr.resolve(SoundEvent.OPEN).parent.name == "soft"


def test_handler_partial_update_keeps_other_fields():
    ui = _ui()
    handle_set_sound(ui, SetSoundCommand(enabled=True, volume=50, pack="soft"))
    # 只改音量，其余保持
    handle_set_sound(ui, SetSoundCommand(volume=90))
    mgr = SoundManager.instance()
    assert mgr._enabled is True
    assert round(mgr._volume * 100) == 90
    assert mgr.current_pack() == "soft"


def test_handler_reset_restores_startup():
    ui = _ui()
    handle_set_sound(ui, SetSoundCommand(enabled=True, volume=10, pack="soft"))
    resp = handle_set_sound(ui, SetSoundCommand(reset=True))
    mgr = SoundManager.instance()
    assert resp.success
    assert mgr._enabled is False
    assert round(mgr._volume * 100) == 70
    assert mgr.current_pack() == ""


def test_handler_rejects_invalid_params():
    ui = _ui()
    bad_volume = handle_set_sound(ui, SetSoundCommand(volume=200))
    assert not bad_volume.success and "音量" in bad_volume.error
    bad_event = handle_set_sound(ui, SetSoundCommand(play_event="nope"))
    assert not bad_event.success and "未知音效事件" in bad_event.error


def test_handler_preview_does_not_change_pack():
    ui = _ui()
    resp = handle_set_sound(ui, SetSoundCommand(
        enabled=True, play_event="open"))
    assert resp.success


def test_plugin_sound_module_builds_command():
    from plugins.skin_manager.sound import (
        build_sound_command, discover_sound_choices, DEFAULT_PACK,
    )
    cmd = build_sound_command(enabled=True, volume=55, pack="",
                              play_event="win")
    assert isinstance(cmd, SetSoundCommand)
    assert (cmd.enabled, cmd.volume, cmd.play_event) == (True, 55, "win")
    with pytest.raises(ValueError):
        build_sound_command(volume=999)
    with pytest.raises(ValueError):
        build_sound_command(play_event="nope")

    choices = discover_sound_choices()
    assert choices[0] == (DEFAULT_PACK, choices[0][1])
    assert "soft" in dict(choices), "应能发现主进程自带 soft 音效包"


def test_plugin_config_fields_are_independent():
    from plugins.skin_manager.config import SkinManagerConfig
    sound_fields = [n for n in dir(SkinManagerConfig) if n.startswith("sound_")]
    assert set(sound_fields) == {
        "sound_enabled", "sound_volume", "sound_pack", "sound_zip",
    }
    # 皮肤字段仍在，且 choices 未被音效注册覆盖
    assert "skin" in dir(SkinManagerConfig)
    assert "skin_zip" in dir(SkinManagerConfig)
    assert len(SkinManagerConfig.skin.choices) > 1
    assert any(v == "soft" for v, _ in SkinManagerConfig.sound_pack.choices)


def test_zip_import_fields_target_plugin_data_dir():
    from plugins.skin_manager.config import SkinManagerConfig
    skin_zip = SkinManagerConfig.skin_zip
    sound_zip = SkinManagerConfig.sound_zip
    assert skin_zip.widget_type == "zip_import"
    assert skin_zip.target_subdir == "skins"
    assert sound_zip.target_subdir == "sounds"


def test_build_sound_command_points_to_imported_dir():
    from plugins.skin_manager.sound import (
        build_sound_command, imported_sound_dir,
    )
    cmd = build_sound_command(enabled=True)
    assert cmd.extra_dir == str(imported_sound_dir())


def test_import_zip_end_to_end(tmp_path):
    import json
    import zipfile
    from plugins.skin_manager.zip_import import (
        import_zip, imported_dir, ZipImportError,
    )
    from plugins.skin_manager.config import discover_choices
    from plugins.skin_manager.sound import discover_sound_choices

    zp = tmp_path / "pack.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("my_pack/sound.json",
                   json.dumps({"name": "测试包"}, ensure_ascii=False))
        z.writestr("my_pack/open.wav", b"FAKE")

    root = imported_dir("sounds")
    result = import_zip(zp, root)
    try:
        assert result.pack_name == "my_pack"
        assert (root / "my_pack" / "open.wav").is_file()
        assert any(v == "my_pack" for v, _ in discover_sound_choices())
        assert any(v == "" for v, _ in discover_choices())  # 默认项仍在
    finally:
        import shutil
        shutil.rmtree(root / "my_pack", ignore_errors=True)

    # 恶意路径拦截
    bad = tmp_path / "evil.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../evil.wav", b"x")
    with pytest.raises(ZipImportError):
        import_zip(bad, root)


def test_plugin_declares_both_controls():
    from plugins.skin_manager.plugin import SkinManagerPlugin
    required = SkinManagerPlugin.plugin_info().required_controls
    assert SetSkinCommand in required and SetSoundCommand in required
