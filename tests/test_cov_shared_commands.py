"""shared_types.commands 覆盖率补测：i18n 哑函数、tag/label/hint 兜底与正路径。

哑函数 _i18n_command_strings 只影响覆盖率，但断言其调用次数与上下文/源文本
可验证 lupdate 抽取词条与两张 dict 保持同步，属于有实际意义的校验。
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from shared_types import commands as mod
from shared_types.commands import (
    COMMAND_HINTS,
    COMMAND_LABELS,
    COMMAND_TYPES,
    COMMANDS_I18N_CONTEXT,
    InitOpenCommand,
    MouseClickCommand,
    NewGameCommand,
    NewPresetGameCommand,
    NON_CHEAT_TAGS,
    SetSkinCommand,
    SetSoundCommand,
    SKIN_CELL_KEYS,
    SKIN_COLOR_KEYS,
    SKIN_FACE_KEYS,
    SKIN_LED_KEYS,
    command_hint,
    command_label,
    command_tag,
)


@pytest.fixture(scope="module")
def app():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


class _NoTag:
    """无 __struct_config__ 的普通类，用于兜底分支。"""
    __name__ = "_NoTag"


class _EmptyTag:
    __name__ = "_EmptyTag"
    __struct_config__ = SimpleNamespace(tag=None)


class _Documented:
    """这是文档字符串首行。

    第二行不应被返回。
    """


class _Bare:
    """无 tag、无 docstring（用 __doc__ = None 强制），回退类名。"""
    pass


def test_command_types_and_tags_are_unique(app):
    assert len(COMMAND_TYPES) == 6
    tags = [command_tag(t) for t in COMMAND_TYPES]
    assert tags == [
        "new_random_game", "new_preset_game", "mouse_click",
        "init_open", "set_skin", "set_sound",
    ]
    assert len(set(tags)) == len(tags), "tag 必须全局唯一"
    assert set(tags) == set(COMMAND_LABELS) == set(COMMAND_HINTS)


def test_command_tag_fallbacks(app):
    assert command_tag(_NoTag) == "_NoTag"
    assert command_tag(_EmptyTag) == "_EmptyTag"


def test_command_label_known_and_fallback(app):
    for cmd_type in COMMAND_TYPES:
        # 无 .ts 时 QCoreApplication.translate 返回中文源文本
        assert command_label(cmd_type) == COMMAND_LABELS[command_tag(cmd_type)]
    assert command_label(_NoTag) == "_NoTag"


def test_command_hint_known_and_fallbacks(app):
    for cmd_type in COMMAND_TYPES:
        assert command_hint(cmd_type) == COMMAND_HINTS[command_tag(cmd_type)]
    assert command_hint(_Documented) == "这是文档字符串首行。"
    _Bare.__doc__ = None
    assert command_hint(_Bare) == "_Bare"


def test_i18n_dummy_function_covers_all_source_strings(app):
    """哑函数必须为两张 dict 的每条源文本各调用一次 translate。"""
    expected_context = COMMANDS_I18N_CONTEXT
    assert expected_context == "Commands"
    with patch.object(mod, "_translate") as tr:
        assert mod._i18n_command_strings() is None
    assert tr.call_count == len(COMMAND_LABELS) + len(COMMAND_HINTS) == 12
    seen = [(c.args[0], c.args[1]) for c in tr.call_args_list]
    assert all(ctx == "Commands" for ctx, _ in seen)
    assert {src for _, src in seen} == set(COMMAND_LABELS.values()) | set(
        COMMAND_HINTS.values())


def test_non_cheat_tags_are_declared(app):
    assert NON_CHEAT_TAGS == frozenset(
        {"set_skin", "set_sound", "new_random_game"})
    assert NON_CHEAT_TAGS <= set(COMMAND_LABELS)


def test_skin_key_constants(app):
    assert len(SKIN_CELL_KEYS) == 16
    assert SKIN_LED_KEYS == tuple(range(10))
    assert SKIN_FACE_KEYS == (14, 15, 16, 17, 18)
    assert "window" in SKIN_COLOR_KEYS and len(SKIN_COLOR_KEYS) == 10


def test_command_defaults_roundtrip_via_msgspec(app):
    """所有命令都能用 msgspec 编码/解码且字段默认值符合协议约定。"""
    import msgspec
    from lib_zmq_plugins.shared.base import BaseCommand

    cases = [
        (NewGameCommand(), {"level": 5, "mode": 0}),
        # 显式提供合法 board：默认值 None 与声明类型 List[List[int]] 冲突，
        # 详见 test_new_preset_game_default_board_does_not_roundtrip。
        (NewPresetGameCommand(board=[[0, 1], [1, -1]]),
         {"board": [[0, 1], [1, -1]], "mode": 0}),
        (MouseClickCommand(), {"row": 0, "col": 0, "button": 0, "modifiers": 0}),
        (InitOpenCommand(), {"row": 0, "col": 0}),
        (SetSkinCommand(), {"reset": False, "frame_svg": None}),
        (SetSoundCommand(), {"enabled": None, "volume": None, "reset": False}),
    ]
    for cmd, fields in cases:
        assert isinstance(cmd, BaseCommand)
        blob = msgspec.msgpack.encode(cmd)
        restored = msgspec.msgpack.decode(blob, type=type(cmd))
        for name, value in fields.items():
            assert getattr(restored, name) == value


def test_set_skin_and_set_sound_dict_defaults_are_independent(app):
    """msgspec.field(default_factory=dict) 不能在不同实例间共享可变默认值。"""
    a, b = SetSkinCommand(), SetSkinCommand()
    a.cells[0] = b"x"
    assert b.cells == {}
    assert b.leds == {} and b.faces == {} and b.colors == {}


def test_new_preset_game_default_board_does_not_roundtrip():
    """记录源码现状：board 默认 None 与 List[List[int]] 类型注解不一致。

    commands.py:51 声明 `board: List[List[int]] = None`，默认实例可被构造
    但 encode→decode 会抛 ValidationError（Expected `array`, got `None`）。
    这是源码缺陷，不是测试期望；按约束不改源码，仅在最终报告中说明。
    """
    import msgspec
    cmd = NewPresetGameCommand()
    assert cmd.board is None
    blob = msgspec.msgpack.encode(cmd)
    with pytest.raises(msgspec.ValidationError, match="Expected `array`, got `None`"):
        msgspec.msgpack.decode(blob, type=NewPresetGameCommand)
