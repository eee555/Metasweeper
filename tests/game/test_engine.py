from __future__ import annotations

import pytest
from app.game_engine import GameEngine
from config.constants import (
    READY, PLAYING, WIN, FAIL, MODE_STANDARD,
    MIN_PIX_SIZE, MAX_PIX_SIZE,
)


class TestGameEngine:
    def test_initial_state(self):
        e = GameEngine()
        assert e.game_state == READY
        assert e.gameMode == MODE_STANDARD
        assert e.row == 16
        assert e.column == 30
        assert e.minenum == 99
        assert e.pixSize == 20

    def test_state_transition(self):
        e = GameEngine()
        e.game_state = PLAYING
        assert e.game_state == PLAYING
        e.game_state = WIN
        assert e.game_state == WIN

    def test_pixSize_bounds(self):
        e = GameEngine()
        e.pixSize = 1
        assert e.pixSize >= MIN_PIX_SIZE
        e.pixSize = 999
        assert e.pixSize <= MAX_PIX_SIZE

    def test_cell_is_in_board(self):
        e = GameEngine()
        e.row = 8
        e.column = 8
        assert e.cell_is_in_board(0, 0) is True
        assert e.cell_is_in_board(7, 7) is True
        assert e.cell_is_in_board(-1, 0) is False
        assert e.cell_is_in_board(0, 8) is False
        assert e.cell_is_in_board(8, 0) is False


class TestAssistedGameFinishEvent:
    """启用任何控制权限后对局进入 joking 形态，结束时仍必须广播 GameFinishedEvent"""

    @staticmethod
    def _stub(state: str, finished: list):
        class Stub:
            _game_state = state

            def onGameFinished(self, new_state: str) -> None:
                finished.append(new_state)

            def unlimit_cursor(self) -> None:
                pass

            def _send_board_update_event(self) -> None:
                pass

        Stub.timer_10ms = type("Timer", (), {"stop": lambda self: None})()
        return Stub()

    @pytest.mark.parametrize("target", ["jowin", "jofail", "ready", "study"])
    def test_joking_to_terminal_calls_on_game_finished(self, target):
        from mineSweeperGUI import MineSweeperGUI

        finished: list[str] = []
        stub = self._stub("joking", finished)
        MineSweeperGUI.game_state.fset(stub, target)
        assert finished == [target]
        assert stub._game_state == target

    @pytest.mark.parametrize("target", ["show", "joking", "playing"])
    def test_joking_internal_transitions_do_not_finish(self, target):
        from mineSweeperGUI import MineSweeperGUI

        finished: list[str] = []
        stub = self._stub("joking", finished)
        MineSweeperGUI.game_state.fset(stub, target)
        assert finished == []

    def test_playing_to_terminal_still_calls_on_game_finished(self):
        from mineSweeperGUI import MineSweeperGUI

        finished: list[str] = []
        stub = self._stub("playing", finished)
        MineSweeperGUI.game_state.fset(stub, "win")
        assert finished == ["win"]


class TestEngineMisc:
    def test_mineNumWheel(self):
        e = GameEngine()
        e.game_state = READY
        old = e.minenum
        e.mineNumWheel(1)
        assert e.minenum == old + 1
        e.mineNumWheel(-1)
        assert e.minenum == old

    def test_mineNumWheel_lower_bound(self):
        e = GameEngine()
        e.game_state = READY
        e.minenum = 1
        e.mineNumWheel(-1)
        assert e.minenum == 1

    def test_mineNumWheel_upper_bound(self):
        e = GameEngine()
        e.game_state = READY
        e.minenum = e.row * e.column - 1
        e.mineNumWheel(1)
        assert e.minenum == e.row * e.column - 1

    def test_official_fair_no_board(self):
        e = GameEngine()
        assert e.is_official() is False
        assert e.is_fair() is False

    def test_checksum_module(self):
        assert isinstance(GameEngine.checksum_module_ok(), bool)
