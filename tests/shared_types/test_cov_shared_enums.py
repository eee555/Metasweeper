"""shared_types.enums 覆盖率补测：基类方法、各枚举值与 LABELS 映射。

Qt 翻译依赖 QCoreApplication，这里用 QApplication（offscreen）保证
QCoreApplication.translate 在无 .ts 时返回源文本，从而可断言中文标签。
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from shared_types.enums import (
    BaseDiaPlayEnum,
    ButtonEventType,
    GameBoardState,
    GameLevel,
    GameMode,
    MouseState,
)


@pytest.fixture(scope="module")
def app():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


class _Bare(BaseDiaPlayEnum):
    """继承基类但不重写 display_name，覆盖基类默认实现。"""

    ALPHA = 1
    BETA = 2


def _pseudo_member(cls, value=42):
    """构造一个 value 不在定义中的伪成员，用于覆盖 match 的兜底分支。

    不修改任何真实枚举成员，也不写入类的 _value2member_map_。
    """
    fake = object.__new__(cls)
    fake._value_ = value
    fake._name_ = "Pseudo"
    return fake


def test_base_display_name_default_returns_member_name(app):
    assert _Bare.ALPHA.display_name == "ALPHA"
    assert _Bare.BETA.display_name == "BETA"


def test_base_from_display_name_roundtrip_and_error(app):
    assert _Bare.from_display_name("ALPHA") is _Bare.ALPHA
    assert _Bare.from_display_name("BETA") is _Bare.BETA
    with pytest.raises(ValueError, match="Invalid display name: MISSING"):
        _Bare.from_display_name("MISSING")


def test_base_display_names_lists_all_members(app):
    assert _Bare.display_names() == ["ALPHA", "BETA"]


def test_base_try_create_valid_and_invalid(app):
    assert _Bare.try_create(1) is _Bare.ALPHA
    assert _Bare.try_create(2) is _Bare.BETA
    # 非法值返回原始 int，而不是抛异常
    assert _Bare.try_create(99) == 99
    assert GameLevel.try_create(6) is GameLevel.CUSTOM
    assert GameLevel.try_create(999) == 999


def test_game_board_state_values_and_labels(app):
    expected = {
        GameBoardState.Ready: (0, "准备"),
        GameBoardState.Study: (1, "研究模式"),
        GameBoardState.Show: (2, "显示概率"),
        GameBoardState.Playing: (3, "游戏中"),
        GameBoardState.Joking: (4, "作弊中"),
        GameBoardState.Fail: (5, "失败"),
        GameBoardState.Win: (6, "胜利"),
        GameBoardState.Jofail: (7, "作弊且失败"),
        GameBoardState.Jowin: (8, "作弊且成功"),
        GameBoardState.Display: (9, "播放录像中"),
        GameBoardState.ShowDisplay: (10, "播放录像时显示概率"),
    }
    for member, (value, label) in expected.items():
        assert member.value == value
        assert member.display_name == label
    assert len(GameBoardState.display_names()) == 11
    assert GameBoardState.from_display_name("胜利") is GameBoardState.Win
    with pytest.raises(ValueError, match="Invalid display name: 不存在的状态"):
        GameBoardState.from_display_name("不存在的状态")


def test_mouse_state_values_and_labels(app):
    expected = {
        MouseState.UpUp: (1, "双键抬起"),
        MouseState.UpDown: (2, "右键按下且标过雷"),
        MouseState.UpDownNotFlag: (3, "右键按下且没有标过雷"),
        MouseState.DownUp: (4, "左键按下"),
        MouseState.Chording: (5, "双键按下"),
        MouseState.ChordingNotFlag: (6, "双键按下且先按下右键且没有标雷"),
        MouseState.DownUpAfterChording: (7, "双击后先弹起右键左键还没有弹起"),
        MouseState.Undefined: (8, "未初始化"),
    }
    for member, (value, label) in expected.items():
        assert member.value == value
        assert member.display_name == label
    assert len(MouseState.display_names()) == 8
    assert MouseState.from_display_name("双键按下") is MouseState.Chording


def test_game_mode_all_values_and_labels(app):
    expected = {
        GameMode.Standard: (0, "标准"),
        GameMode.UPK: (1, "UPK"),
        GameMode.Win7: (4, "win7"),
        GameMode.ClassicNoGuess: (5, "经典无猜"),
        GameMode.StrictNoGuess: (6, "强无猜"),
        GameMode.WeakNoGuess: (7, "弱无猜"),
        GameMode.BlessingMode: (8, "准无猜"),
        GameMode.GuessableNoGuess: (9, "强可猜"),
        GameMode.LuckyMode: (10, "弱可猜"),
        GameMode.ChordRecursive: (11, "双击递归"),
        GameMode.FlagRecursive: (12, "标雷递归"),
        GameMode.ChordFlagRecursive: (13, "双击标雷递归"),
        GameMode.NoGuessChordRecursive: (14, "无猜双击递归"),
        GameMode.NoGuessFlagRecursive: (15, "无猜标雷递归"),
        GameMode.NoGuessChordFlagRecursive: (16, "无猜双击标雷递归"),
    }
    for member, (value, label) in expected.items():
        assert member.value == value
        assert member.display_name == label
    assert len(GameMode.display_names()) == 15
    assert GameMode.from_display_name("标准") is GameMode.Standard


def test_game_level_values_and_labels(app):
    expected = {
        GameLevel.BEGINNER: (3, "初级"),
        GameLevel.INTERMEDIATE: (4, "中级"),
        GameLevel.EXPERT: (5, "高级"),
        GameLevel.CUSTOM: (6, "自定义"),
    }
    for member, (value, label) in expected.items():
        assert member.value == value
        assert member.display_name == label
    assert GameLevel.display_names() == ["初级", "中级", "高级", "自定义"]
    assert GameLevel.from_display_name("自定义") is GameLevel.CUSTOM


def test_button_event_type_values_and_display_names(app):
    expected = {
        "MV": 1, "LC": 2, "LR": 3, "RC": 4, "RR": 5, "MC": 6,
        "MR": 7, "PF": 8, "CC": 9, "L": 10, "R": 11, "M": 12,
    }
    for name, value in expected.items():
        member = ButtonEventType[name]
        assert member.value == value
        assert member.display_name == name.lower()
    assert ButtonEventType.display_names() == [n.lower() for n in expected]
    assert ButtonEventType.from_display_name("mv") is ButtonEventType.MV
    with pytest.raises(ValueError, match="Invalid display name: zz"):
        ButtonEventType.from_display_name("zz")


def test_display_name_fallback_for_unknown_value(app):
    """四个 match 的 case _ 兜底：未知 value 时返回 str(value)。"""
    for cls in (GameBoardState, MouseState, GameMode, GameLevel):
        assert _pseudo_member(cls, 42).display_name == "42"
    # 真实成员未被污染
    assert GameBoardState.Ready.display_name == "准备"
