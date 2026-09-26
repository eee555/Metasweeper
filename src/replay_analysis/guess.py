from __future__ import annotations

import math
from typing import Iterable, Iterator, Tuple

from PySide6.QtCore import QCoreApplication

from config.constants import CELL_UNOPENED

from .core import (
    Board,
    ReplayEvent,
    ReplayEventContext,
    ReplayEventManager,
    board_size,
    cell_at,
    register_replay_event_manager,
    neighbours,
)
from .format import format_pluck, format_probability_percent


_PLUCK_DELTA_EPSILON = 1e-12
_translate = QCoreApplication.translate


class GuessEvent(ReplayEvent):
    def __init__(
        self,
        event_index: int,
        time: float,
        pluck_delta: float,
        global_min_probability: float,
        non_frontier_probability: float,
        row: int,
        column: int,
        current_pluck: float,
    ):
        self.pluck_delta = pluck_delta
        self.global_min_probability = global_min_probability
        self.non_frontier_probability = non_frontier_probability
        self.current_pluck = current_pluck
        super().__init__(
            event_index=event_index,
            time=time,
            coordinate=(row, column),
        )

    def type_text(self) -> str:
        return _translate("ReplayAnalysis", "猜雷")

    def detail_text(self) -> str:
        text = _translate(
            "ReplayAnalysis",
            "pluck={pluck}(+{pluck_diff})，雷{mine}，最小{minimum}，密度{density}",
        )
        return (
            text
            .replace("{pluck}", format_pluck(self.current_pluck))
            .replace("{pluck_diff}", format_pluck(self.pluck_delta))
            .replace("{mine}", format_probability_percent(1 - 10 ** (-self.pluck_delta)))
            .replace("{minimum}", format_probability_percent(self.global_min_probability))
            .replace("{density}", format_probability_percent(self.non_frontier_probability))
        )

    def severity(self) -> str:
        mine_probability = 1 - 10 ** (-self.pluck_delta)
        if math.isclose(mine_probability, self.global_min_probability):
            return "success"
        if mine_probability > self.non_frontier_probability:
            return "warning"
        if math.isclose(self.global_min_probability, 0.0):
            return "warning"
        return "info"

    def highlight_cells(self) -> Tuple[Tuple[int, int], ...]:
        return (self.coordinate,)


@register_replay_event_manager
class GuessEventManager(ReplayEventManager):
    def reset(self, context: ReplayEventContext) -> None:
        context.video.analyse_for_features(["pluck"])
        self._set_current_event(context)
        self.pluck = context.video.pluck

    def handle(self, context: ReplayEventContext) -> Iterable[ReplayEvent]:
        if context.mouse is None or context.mouse.is_mouse("mv", "mc", "mr"):
            return ()

        self._set_current_event(context)
        current_pluck = context.video.pluck
        previous_pluck = self.pluck
        self.pluck = current_pluck
        pluck_delta = current_pluck - previous_pluck
        if pluck_delta <= _PLUCK_DELTA_EPSILON:
            return ()

        prior_game_board = context.record.prior_game_board
        game_board = prior_game_board.game_board
        possibility_board = prior_game_board.poss
        global_min_probability = _global_min_probability(
            game_board,
            possibility_board,
        )
        non_frontier_probability = _non_frontier_probability(
            game_board,
            possibility_board,
        )

        return (
            GuessEvent(
                event_index=context.index,
                time=context.time,
                pluck_delta=pluck_delta,
                global_min_probability=global_min_probability,
                non_frontier_probability=non_frontier_probability,
                row=context.mouse.row,
                column=context.mouse.column,
                current_pluck=current_pluck,
            ),
        )

    def _set_current_event(self, context: ReplayEventContext) -> None:
        context.video.current_event_id = context.index


def _global_min_probability(game_board: Board, possibility_board: Board) -> float:
    ret = 1.0
    row_count, column_count = board_size(game_board)
    for row in range(row_count):
        for column in range(column_count):
            if cell_at(game_board, row, column) == CELL_UNOPENED:
                ret = min(ret, possibility_board[row][column])
    return ret


def _non_frontier_probability(
    game_board: Board,
    possibility_board: Board,
) -> float:
    row_count, column_count = board_size(game_board)
    for row in range(row_count):
        for column in range(column_count):
            if cell_at(game_board, row, column) == CELL_UNOPENED and not _touches_number_cell(game_board, row, column, row_count, column_count):
                return possibility_board[row][column]
    return math.nan


def _touches_number_cell(
    game_board: Board,
    row: int, column: int,
    row_count: int, column_count: int,
) -> bool:
    return any(
        _is_number_cell(cell_at(game_board, next_row, next_column))
        for next_row, next_column in neighbours(row, column, row_count, column_count)
    )


def _is_number_cell(value: int) -> bool:
    return 1 <= value <= 8
