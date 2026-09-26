from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from PySide6.QtCore import QCoreApplication

from .core import (
    ReplayEvent,
    ReplayEventContext,
    ReplayEventManager,
    register_replay_event_manager,
)
from .format import format_interval_ms


_translate = QCoreApplication.translate


@dataclass(frozen=True)
class ComboClick:
    event_index: int
    time: float
    row: int
    column: int


class ComboClickEvent(ReplayEvent):
    def __init__(self, clicks: List[ComboClick]):
        self.clicks = tuple(clicks)
        super().__init__(
            event_index=clicks[0].event_index,
            time=clicks[0].time,
            coordinate=(clicks[0].row, clicks[0].column),
        )

    def type_text(self) -> str:
        return _translate("ReplayAnalysis", "连击")

    def detail_text(self) -> str:
        text = _translate(
            "ReplayAnalysis",
            "长度{length}，间隔最大{max_interval}，最小{min_interval}，平均{average_interval}",
        )
        return (
            text
            .replace("{length}", str(len(self.clicks)))
            .replace("{max_interval}", format_interval_ms(max(self.intervals())))
            .replace("{min_interval}", format_interval_ms(min(self.intervals())))
            .replace("{average_interval}", format_interval_ms(self.average_interval()))
        )

    def average_interval(self) -> float:
        return (self.clicks[-1].time - self.clicks[0].time) / (len(self.clicks) - 1)

    def intervals(self) -> Tuple[float, ...]:
        return tuple(
            self.clicks[index].time - self.clicks[index - 1].time
            for index in range(1, len(self.clicks))
        )

    def highlight_cells(self) -> Tuple[Tuple[int, int], ...]:
        return tuple((click.row, click.column) for click in self.clicks)


@register_replay_event_manager
class ComboClickEventManager(ReplayEventManager):
    def reset(self, context: ReplayEventContext) -> None:
        self.sequence: List[ComboClick] = []
        self.lce = context.key_dynamic_params.lce
        self.rdce = context.key_dynamic_params.rce + context.key_dynamic_params.dce

    def handle(self, context: ReplayEventContext) -> Tuple[ReplayEvent, ...]:
        if context.mouse is None or context.mouse.is_mouse("mv", "mc", "mr"):
            return ()

        emitted: Tuple[ReplayEvent, ...] = ()
        params = context.key_dynamic_params
        if params.lce > self.lce:
            self.lce = params.lce
            emitted = self._handle_click(ComboClick(
                event_index=context.index,
                time=context.time,
                row=context.mouse.row,
                column=context.mouse.column,
            ))
        elif (rdce := params.rce + params.dce) > self.rdce:
            self.rdce = rdce
            emitted = self._flush_sequence()
        return emitted

    def finish(self) -> Tuple[ReplayEvent, ...]:
        return self._flush_sequence()

    def _handle_click(self, click: ComboClick) -> Tuple[ReplayEvent, ...]:
        if not self.sequence:
            self.sequence = [click]
            return ()
        if _is_adjacent_cell(self.sequence[-1], click):
            self.sequence.append(click)
            return ()
        emitted = self._flush_sequence()
        self.sequence = [click]
        return emitted

    def _flush_sequence(self) -> Tuple[ReplayEvent, ...]:
        if len(self.sequence) < 3:
            self.sequence = []
            return ()
        event = ComboClickEvent(self.sequence)
        self.sequence = []
        return (event,)


def _is_adjacent_cell(left: ComboClick, right: ComboClick) -> bool:
    row_delta = abs(left.row - right.row)
    column_delta = abs(left.column - right.column)
    return row_delta + column_delta == 1
