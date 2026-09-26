from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QCoreApplication

from .core import (
    ReplayEvent,
    ReplayEventContext,
    ReplayEventManager,
    is_mouse_event,
    register_replay_event_manager,
    unwrap_mouse_event,
)
from .format import format_number


Cell = Tuple[int, int]
_translate = QCoreApplication.translate


@dataclass
class FlagContribution:
    event_index: int
    time: float
    row: int
    column: int
    dce: float = 0.0
    bbbv_solved: float = 0.0
    dce_cells: Tuple[Cell, ...] = ()


class FlagEvent(ReplayEvent):
    def __init__(self, flag: FlagContribution):
        self.dce = flag.dce
        self.bbbv_solved = flag.bbbv_solved
        self.dce_cells = flag.dce_cells
        super().__init__(
            event_index=flag.event_index,
            time=flag.time,
            coordinate=(flag.row, flag.column),
        )

    def type_text(self) -> str:
        return _translate("ReplayAnalysis", "标雷")

    def detail_text(self) -> str:
        text = _translate("ReplayAnalysis", "双击{dce}次，解决{bbbv}bv")
        return (
            text
            .replace("{dce}", format_number(self.dce))
            .replace("{bbbv}", format_number(self.bbbv_solved))
        )

    def severity(self) -> str:
        if self.bbbv_solved == 0:
            return "error"
        if self.bbbv_solved > self.dce + 1:
            return "success"
        if self.bbbv_solved < self.dce + 1:
            return "warning"
        return "info"

    def highlight_cells(self) -> Tuple[Tuple[int, int], ...]:
        if self.coordinate is None:
            return self.dce_cells
        return (self.coordinate, *self.dce_cells)


class FlagCancelEvent(ReplayEvent):
    def type_text(self) -> str:
        return _translate("ReplayAnalysis", "标雷")

    def detail_text(self) -> str:
        return _translate("ReplayAnalysis", "取消标雷")

    def severity(self) -> str:
        return "error"

    def highlight_cells(self) -> Tuple[Tuple[int, int], ...]:
        if self.coordinate is None:
            return ()
        return (self.coordinate,)


@register_replay_event_manager
class FlagEventManager(ReplayEventManager):
    def reset(self, context: ReplayEventContext) -> None:
        self.flags_by_index: Dict[int, FlagContribution] = {}
        self.flags_by_cell: Dict[Cell, FlagContribution] = {}
        self.previous_mouse_record: Optional[Any] = context.record

    def handle(self, context: ReplayEventContext) -> Tuple[ReplayEvent, ...]:
        mouse_event = _mouse_event_record(context, context.index)
        if mouse_event is None:
            return ()

        emitted: Tuple[ReplayEvent, ...] = ()
        _mouse_name, row, column = mouse_event
        cell = (row, column)
        flag_delta = _counter_delta(
            self.previous_mouse_record, context.record, "flag")
        if flag_delta > 0:
            flag = self.flags_by_cell.get(cell)
            if flag is None:
                flag = FlagContribution(
                    event_index=context.index,
                    time=context.time,
                    row=row,
                    column=column,
                )
                self.flags_by_index[context.index] = flag
                self.flags_by_cell[cell] = flag
        elif flag_delta < 0:
            emitted = (
                FlagCancelEvent(
                    event_index=context.index,
                    time=context.time,
                    coordinate=cell,
                ),
            )

        dce_delta = _counter_delta(
            self.previous_mouse_record, context.record, "dce")
        if dce_delta > 0:
            bbbv_delta = _counter_delta(
                self.previous_mouse_record, context.record, "bbbv_solved")
            nearby_flags = [
                flag
                for flag_cell, flag in self.flags_by_cell.items()
                if _is_nearby(flag_cell, cell)
            ]
            if nearby_flags:
                dce_share = dce_delta / len(nearby_flags)
                bbbv_share = bbbv_delta / len(nearby_flags)
                for flag in nearby_flags:
                    flag.dce += dce_share
                    flag.bbbv_solved += bbbv_share
                    flag.dce_cells = _append_unique_cell(
                        flag.dce_cells, (row, column))

        self.previous_mouse_record = context.record
        return emitted

    def finish(self) -> Tuple[ReplayEvent, ...]:
        return tuple(
            FlagEvent(flag)
            for _, flag in sorted(self.flags_by_index.items())
        )


def _mouse_event_record(
    context: ReplayEventContext,
    index: int,
) -> Optional[Tuple[str, int, int]]:
    record = context.records[index]
    event = getattr(record, "event", None)
    if not is_mouse_event(event):
        return None
    mouse = unwrap_mouse_event(event, context.pix_size)
    if mouse.mouse in {"mv", "mc", "mr"}:
        return None
    return mouse.mouse, mouse.row, mouse.column


def _counter_delta(
    previous_record: Optional[Any],
    current_record: Any,
    *counter_names: str,
) -> int:
    for counter_name in counter_names:
        previous_value = _record_counter(previous_record, counter_name)
        current_value = _record_counter(current_record, counter_name)
        return current_value - previous_value
    return 0


def _record_counter(record: Optional[Any], counter_name: str) -> int:
    if record is None:
        return 0
    return getattr(record.key_dynamic_params, counter_name)


def _is_nearby(left: Cell, right: Cell) -> bool:
    return abs(left[0] - right[0]) <= 1 and abs(left[1] - right[1]) <= 1


def _append_unique_cell(cells: Tuple[Cell, ...], cell: Cell) -> Tuple[Cell, ...]:
    if cell in cells:
        return cells
    return (*cells, cell)
