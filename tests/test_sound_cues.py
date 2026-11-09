"""游戏事件层反馈判定矩阵测试。

用一个不触发完整 GUI 初始化的假对象直接调用
`MineSweeperGUIEvent._emit_feedback()`，验证全盘 diff 到 cue 的映射，
以及「第一击只响 START」「同一操作只播最高优先级 cue」「SHOW/回放不发声」。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from utils import sound_manager as sm_mod  # noqa: E402
from utils.sound_manager import SoundEvent, SoundManager  # noqa: E402
from mineSweeperGUIEvent import BoardSnapshot, MineSweeperGUIEvent  # noqa: E402
from shared_types.enums import MouseState  # noqa: E402


class _FakeSignal:
    def connect(self, *a, **kw):
        pass


class _FakeVoice:
    def __init__(self):
        self.played: list[tuple] = []
        self.effect = type("E", (), {
            "setSource": lambda *a: None,
            "stop": lambda *a: None,
            "setVolume": lambda *a: None,
            "play": lambda *a: None,
            "statusChanged": _FakeSignal(),
            "status": lambda *a: "Ready",
        })()

    def set_source(self, path):
        pass

    def play(self, gain):
        self.played.append(gain)

    def stop(self):
        pass


class _FakeLabel:
    def __init__(self):
        self.shakes = 0

    def start_shake(self, *, strong=False):
        self.shakes += 1


class _FakeBoardHolder:
    def __init__(self, board):
        self.ms_board = type("B", (), {"game_board": board})()


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(sm_mod, "_Voice", _FakeVoice)
    SoundManager._instance = None
    yield
    SoundManager._instance = None


def _make(board):
    """构造一个只带 _snapshot / _emit_feedback 所需属性的假 GUI 对象。"""
    obj = object.__new__(MineSweeperGUIEvent)
    obj.label = _FakeLabel()
    obj.label.ms_board = _FakeBoardHolder(board).ms_board
    SoundManager.instance().configure(enabled=True, volume=70)
    return obj


def _board(*, opened=0, flags=0, questions=0):
    return [[0] * opened + [11] * flags + [17] * questions + [10] * 3]


def _played(obj):
    """取出本次 _emit_feedback 实际播出的 cue（按 _last_play 变化判断）。"""
    return list(SoundManager.instance()._last_play.keys())


def test_open_triggers_open_and_shake():
    board = _board(opened=3)
    obj = _make(board)
    before = BoardSnapshot(0, 0, 0)
    obj._emit_feedback(before)
    assert SoundEvent.OPEN in SoundManager.instance()._last_play
    assert obj.label.shakes == 1


def test_no_change_is_silent():
    board = _board(opened=3)
    obj = _make(board)
    before = BoardSnapshot(3, 0, 0)
    obj._emit_feedback(before)
    assert SoundManager.instance()._last_play == {}
    assert obj.label.shakes == 0


def test_flag_on_and_off():
    # 插旗：flags 0 -> 1
    board = _board(flags=1)
    obj = _make(board)
    SoundManager.instance()._last_play.clear()
    obj._emit_feedback(BoardSnapshot(0, 0, 0))
    assert SoundEvent.FLAG_ON in SoundManager.instance()._last_play

    # 拔旗：flags 1 -> 0
    board2 = _board(opened=0)
    obj2 = _make(board2)
    SoundManager.instance()._last_play.clear()
    obj2._emit_feedback(BoardSnapshot(0, 1, 0))
    assert SoundEvent.FLAG_OFF in SoundManager.instance()._last_play


def test_question_is_not_flag_off():
    # 启用问号时 11 -> 17：应归 QUESTION，不归 FLAG_OFF
    board = _board(questions=1)
    obj = _make(board)
    SoundManager.instance()._last_play.clear()
    obj._emit_feedback(BoardSnapshot(0, 1, 0))
    assert SoundEvent.QUESTION in SoundManager.instance()._last_play
    assert SoundEvent.FLAG_OFF not in SoundManager.instance()._last_play


def test_chord_detected_by_old_mouse_state():
    board = _board(opened=8)
    obj = _make(board)
    SoundManager.instance()._last_play.clear()
    obj._emit_feedback(BoardSnapshot(0, 0, 0),
                       old_state=MouseState.DownUpAfterChording)
    assert SoundEvent.CHORD in SoundManager.instance()._last_play
    assert SoundEvent.OPEN not in SoundManager.instance()._last_play


def test_first_click_only_start():
    board = _board(opened=5)
    obj = _make(board)
    SoundManager.instance()._last_play.clear()
    obj._emit_feedback(BoardSnapshot(0, 0, 0), is_start=True)
    played = SoundManager.instance()._last_play
    assert list(played.keys()) == [SoundEvent.START]
    # 抖动仍然保留（原有手感）
    assert obj.label.shakes == 1


def test_same_operation_only_highest_priority_cue():
    # 一次 rc 同时开格 + 插旗：只播优先级更高的 OPEN，但 intensity 取最大值
    board = _board(opened=4, flags=2)
    obj = _make(board)
    sm = SoundManager.instance()
    sm._last_play.clear()
    obj._emit_feedback(BoardSnapshot(0, 0, 0))
    assert list(sm._last_play.keys()) == [SoundEvent.OPEN]
    # OPEN 的 gain 应反映 flags 的 intensity（>= 2 而非 1）
    assert sm._voices[SoundEvent.OPEN].played[-1] > 0.7 * 0.55


def test_recursive_flag_intensity():
    board = _board(flags=6)
    obj = _make(board)
    sm = SoundManager.instance()
    sm._last_play.clear()
    obj._emit_feedback(BoardSnapshot(0, 0, 0))
    assert SoundEvent.FLAG_ON in sm._last_play
    assert len(sm._voices[SoundEvent.FLAG_ON].played) == 1
