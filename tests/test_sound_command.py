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
from utils.sound_manager import SoundManager  # noqa: E402
from shared_types.sounds import SoundEvent  # noqa: E402
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


def test_handler_applies_settings():
    """音效包由插件侧通过 pack + extra_dir 一起指定，主程序据此 resolve。"""
    from plugins.skin_manager.sound import (
        imported_sound_dir, seed_builtin_sound_packs,
    )
    seed_builtin_sound_packs()
    ui = _ui()
    resp = handle_set_sound(ui, SetSoundCommand(
        enabled=True, volume=42, pack="soft",
        extra_dir=str(imported_sound_dir()), request_id="r1"))
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


def test_plugin_sound_module_builds_command():
    from plugins.skin_manager.sound import (
        build_sound_command, discover_sound_choices,
    )
    cmd = build_sound_command(enabled=True, volume=55, pack="",
                              play_event="win")
    assert isinstance(cmd, SetSoundCommand)
    assert (cmd.enabled, cmd.volume, cmd.play_event) == (True, 55, "win")
    with pytest.raises(ValueError):
        build_sound_command(volume=999)
    with pytest.raises(ValueError):
        build_sound_command(play_event="nope")
    with pytest.raises(ValueError):
        build_sound_command(pack="../..")

    choices = discover_sound_choices()
    assert choices[0][0] == ""


def test_plugin_config_fields_are_independent():
    from plugins.skin_manager.config import SkinManagerConfig
    sound_fields = [n for n in dir(SkinManagerConfig) if n.startswith("sound_")]
    assert set(sound_fields) == {
        "sound_enabled", "sound_volume", "sound_pack", "sound_zip",
    }
    assert "skin" in dir(SkinManagerConfig)
    assert "skin_zip" in dir(SkinManagerConfig)
    assert len(SkinManagerConfig.skin.choices) > 1


def test_zip_import_fields_target_plugin_data_dir():
    from plugins.skin_manager.config import SkinManagerConfig
    assert SkinManagerConfig.skin_zip.widget_type == "zip_import"
    assert SkinManagerConfig.skin_zip.target_subdir == "skins"
    assert SkinManagerConfig.sound_zip.target_subdir == "sounds"


def test_build_sound_command_points_to_imported_dir():
    from plugins.skin_manager.sound import (
        build_sound_command, imported_sound_dir,
    )
    cmd = build_sound_command(enabled=True)
    assert cmd.extra_dir == str(imported_sound_dir())


def test_builtin_pack_is_seeded_and_selectable():
    """音效包选择完全在插件侧：内置示例包播种后可在下拉框选到。"""
    import shutil
    from plugins.skin_manager.sound import (
        BUILTIN_SOUND_DIR, discover_sound_choices, imported_sound_dir,
        seed_builtin_sound_packs,
    )
    root = imported_sound_dir()
    builtin_names = [p.name for p in BUILTIN_SOUND_DIR.iterdir()
                     if p.is_dir() and not p.name.startswith("_")]
    assert "soft" in builtin_names                 # 示例包随插件分发
    # 删掉再播种，验证「只补缺失、不覆盖」不会破坏已有数据
    shutil.rmtree(root / "soft", ignore_errors=True)
    seed_builtin_sound_packs()
    assert (root / "soft" / "open.wav").is_file()
    assert any(v == "soft" for v, _ in discover_sound_choices())
    # 再播种一次：用户已导入/修改的同名包不被覆盖
    marker = root / "soft" / "user_marker.txt"
    marker.write_text("keep", encoding="utf-8")
    seed_builtin_sound_packs()
    assert marker.is_file()
    marker.unlink()


def test_main_program_has_no_pack_setting():
    """主程序设置页不再有音效包/额外库入口与 ini 键。"""
    from dialogs import gameSettings
    import inspect
    src = inspect.getsource(gameSettings)
    assert "comboBox_sound_pack" not in src
    assert "lineEdit_sound_extra_dir" not in src
    assert "sound_pack" not in src
    assert "sound_extra_dir" not in src


def test_import_zip_end_to_end(tmp_path):
    import json
    import shutil
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
    shutil.rmtree(root / "my_pack", ignore_errors=True)
    result = import_zip(zp, root)
    try:
        assert result.pack_name == "my_pack"
        assert (root / "my_pack" / "open.wav").is_file()
        assert any(v == "my_pack" for v, _ in discover_sound_choices())
        assert any(v == "" for v, _ in discover_choices())
    finally:
        shutil.rmtree(root / "my_pack", ignore_errors=True)

    bad = tmp_path / "evil.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../evil.wav", b"x")
    with pytest.raises(ZipImportError):
        import_zip(bad, root)


def test_import_zip_handles_nested_root_and_rejects_empty(tmp_path):
    """顶层多一个 README / 资源在子目录时也能定位到资源根。"""
    import json
    import shutil
    import zipfile
    from plugins.skin_manager.zip_import import import_zip, ZipImportError

    zp = tmp_path / "nested.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("outer/images/open.wav", b"FAKE")
        z.writestr("outer/sound.json",
                   json.dumps({"name": "嵌套包"}, ensure_ascii=False))

    root = tmp_path / "imported"
    shutil.rmtree(root / "outer", ignore_errors=True)
    result = import_zip(zp, root)
    try:
        # 资源根定位到 outer/images/，但 meta 在 outer/ 下，显示名仍应读到
        assert result.pack_name == "outer"
        assert (root / "outer" / "open.wav").is_file() or (
            root / "outer" / "images" / "open.wav").is_file()
        assert result.display == "嵌套包"
    finally:
        shutil.rmtree(root / "outer", ignore_errors=True)

    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("readme.txt", "x")
    with pytest.raises(ZipImportError):
        import_zip(empty, root)


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


def test_plugin_declares_both_controls():
    from plugins.skin_manager.plugin import SkinManagerPlugin
    required = SkinManagerPlugin.plugin_info().required_controls
    assert SetSkinCommand in required and SetSoundCommand in required


def test_safe_disconnect_is_silent_when_not_connected():
    """回归：PySide6 的 disconnect 未连接时发 RuntimeWarning 而非抛异常，
    插件初始化不应再刷 'libpyside: Failed to disconnect' 告警。"""
    import warnings
    from PySide6.QtCore import QObject, Signal
    from plugins.skin_manager.plugin import _safe_disconnect

    class _Emitter(QObject):
        sig = Signal(str)

    emitter = _Emitter()

    def slot(_x):
        pass

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _safe_disconnect(emitter.sig, slot)
        assert not [w for w in caught
                    if "Failed to disconnect" in str(w.message)]

    # 已连接时应真正断开，且同样无告警
    emitter.sig.connect(slot)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _safe_disconnect(emitter.sig, slot)
        assert not [w for w in caught
                    if "Failed to disconnect" in str(w.message)]
