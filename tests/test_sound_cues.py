"""游戏事件层反馈判定矩阵测试。

用不触发完整 GUI 初始化的假对象直接调
`MineSweeperGUIEvent._emit_feedback()`，验证全盘 diff 到 cue 的映射。
断言的是「哪个 cue 被 play」而不是 `_last_play` 私有字典（后者是
实现细节，此前测试全绿却漏掉 WIN/LOSE 从未接线）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from utils import sound_manager as sm_mod  # noqa: E402
from utils.sound_manager import SoundManager  # noqa: E402
from shared_types.sounds import SoundEvent  # noqa: E402
from mineSweeperGUIEvent import BoardSnapshot, MineSweeperGUIEvent  # noqa: E402
from shared_types.enums import MouseState  # noqa: E402


class _RecordingVoice:
    def __init__(self):
        self.played: list[float] = []

    def set_source(self, path):
        pass

    def play(self, gain):
        self.played.append(gain)

    def stop(self):
        pass

    def cancel_pending(self):
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
    monkeypatch.setattr(sm_mod, "_Voice", _RecordingVoice)
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


def _board(*, opened=0, flags=0):
    return [[0] * opened + [11] * flags + [10] * 3]


def _played_events():
    """返回本次真正触发过 play() 的事件列表."""
    sm = SoundManager.instance()
    return [e for e, v in sm._voices.items() if v.played]


def _clear_played():
    for v in SoundManager.instance()._voices.values():
        v.played.clear()
    SoundManager.instance()._last_play.clear()


def test_open_triggers_open_and_shake():
    obj = _make(_board(opened=3))
    obj._emit_feedback(BoardSnapshot(0, 0, 0))
    assert SoundEvent.OPEN in _played_events()
    assert obj.label.shakes == 1


def test_no_change_is_silent():
    obj = _make(_board(opened=3))
    obj._emit_feedback(BoardSnapshot(3, 0, 0))
    assert _played_events() == []
    assert obj.label.shakes == 0


def test_flag_on_and_off():
    obj = _make(_board(flags=1))
    obj._emit_feedback(BoardSnapshot(0, 0, 0))
    assert SoundEvent.FLAG_ON in _played_events()

    _clear_played()
    obj2 = _make(_board(opened=0))
    obj2._emit_feedback(BoardSnapshot(0, 1, 0))
    assert SoundEvent.FLAG_OFF in _played_events()


def test_flag_and_open_are_both_collected_but_only_highest_plays():
    """一次操作同时开格 + 插旗：只播优先级最高的 OPEN，intensity 取最大。"""
    obj = _make(_board(opened=4, flags=2))
    obj._emit_feedback(BoardSnapshot(0, 0, 0))
    assert _played_events() == [SoundEvent.OPEN]
    gain = SoundManager.instance()._voices[SoundEvent.OPEN].played[-1]
    assert gain > 0.7 * 0.75       # intensity 来自 flags=2


def test_chord_requires_lr_action():
    """rc/rr 级联开格不能因为 old_state 恰为 chording 就误响 CHORD。"""
    for action in ("rc", "rr"):
        obj = _make(_board(opened=8))
        _clear_played()
        obj._emit_feedback(BoardSnapshot(0, 0, 0),
                           old_state=MouseState.DownUpAfterChording,
                           action=action)
        assert SoundEvent.OPEN in _played_events(), action
        assert SoundEvent.CHORD not in _played_events(), action

    obj = _make(_board(opened=8))
    _clear_played()
    obj._emit_feedback(BoardSnapshot(0, 0, 0),
                       old_state=MouseState.DownUpAfterChording,
                       action="lr")
    assert SoundEvent.CHORD in _played_events()
    assert SoundEvent.OPEN not in _played_events()


def test_first_click_only_start():
    obj = _make(_board(opened=5))
    obj._emit_feedback(BoardSnapshot(0, 0, 0), is_start=True)
    assert _played_events() == [SoundEvent.START]
    assert obj.label.shakes == 1


def test_recursive_flag_intensity():
    obj = _make(_board(flags=6))
    obj._emit_feedback(BoardSnapshot(0, 0, 0))
    assert SoundEvent.FLAG_ON in _played_events()
    assert len(SoundManager.instance()._voices[SoundEvent.FLAG_ON].played) == 1


def test_finish_plays_win_and_lose():
    """_finish 是 WIN/LOSE 的唯一接线点，必须真的调 gameWin/gameFailed。"""
    obj = object.__new__(MineSweeperGUIEvent)
    calls = []
    obj.gameWin = lambda: calls.append("win")
    obj.gameFailed = lambda: calls.append("lose")
    SoundManager.instance().configure(enabled=True, volume=70)

    obj._finish(win=True)
    assert calls == ["win"]
    assert SoundEvent.WIN in _played_events()

    _clear_played()
    obj._finish(win=False)
    assert calls == ["win", "lose"]
    assert SoundEvent.LOSE in _played_events()
