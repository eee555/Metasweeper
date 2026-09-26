from __future__ import annotations

from typing import Any, Optional, Tuple

from PySide6.QtCore import QCoreApplication

from .core import (
    ReplayEvent,
    ReplayEventContext,
    ReplayEventManager,
    is_mouse_event,
    register_replay_event_manager,
    unwrap_mouse_event,
)
from .format import format_interval_ms


_translate = QCoreApplication.translate
MouseAction = Tuple[int, Any, str, float, int, int]


class OnePointFiveClickEvent(ReplayEvent):
    def __init__(
        self,
        event_index: int,
        time: float,
        right_left_interval: float,
        flag_double_interval: float,
        right_cell: Tuple[int, int],
        double_cell: Tuple[int, int],
    ):
        self.right_left_interval = right_left_interval
        self.flag_double_interval = flag_double_interval
        self.right_cell = right_cell
        super().__init__(
            event_index=event_index,
            time=time,
            coordinate=double_cell,
        )

    def type_text(self) -> str:
        return "1.5click"

    def detail_text(self) -> str:
        text = _translate(
            "ReplayAnalysis",
            "右左间隔{right_left}，标双间隔{flag_double}",
        )
        return (
            text
            .replace("{right_left}", format_interval_ms(self.right_left_interval))
            .replace("{flag_double}", format_interval_ms(self.flag_double_interval))
        )

    def highlight_cells(self) -> Tuple[Tuple[int, int], ...]:
        return _unique_cells(self.right_cell, self.coordinate)


@register_replay_event_manager
class OnePointFiveClickEventManager(ReplayEventManager):
    def reset(self, _context: ReplayEventContext) -> None:
        self.actions: list[MouseAction] = []

    def handle(self, context: ReplayEventContext) -> Tuple[ReplayEvent, ...]:
        action = _mouse_action_record(context, context.index)
        if action is None:
            return ()

        event = self._event_from_action(context, action)
        self.actions.append(action)
        return (event,) if event is not None else ()

    def _event_from_action(
        self,
        context: ReplayEventContext,
        action: MouseAction,
    ) -> Optional[ReplayEvent]:
        index, record, mouse_name, event_time, row, column = action
        if mouse_name not in {"lr", "rr", "l", "r"}:
            return None
        if len(self.actions) < 2:
            return None

        left_press = self.actions[-1]
        if left_press[2] not in {"lc", "cc"}:
            return None
        if not _counter_increased(left_press[1], record, "dce"):
            return None

        right_press = self.actions[-2]
        if right_press[2] != "rc":
            return None
        previous_record_before_right = self.actions[-3][1] if len(
            self.actions) >= 3 else None
        if not _counter_increased(previous_record_before_right, right_press[1], "rce"):
            return None

        return OnePointFiveClickEvent(
            event_index=index,
            time=event_time,
            right_left_interval=left_press[3] - right_press[3],
            flag_double_interval=event_time - right_press[3],
            right_cell=(right_press[4], right_press[5]),
            double_cell=(row, column),
        )


def _mouse_action_record(
    context: ReplayEventContext,
    index: int,
) -> Optional[MouseAction]:
    record = context.records[index]
    event = getattr(record, "event", None)
    if not is_mouse_event(event):
        return None
    mouse = unwrap_mouse_event(event, context.pix_size)
    if mouse.mouse in {"mv", "mc", "mr"}:
        return None
    return index, record, mouse.mouse, _record_time(record), mouse.row, mouse.column


def _unique_cells(*cells: Tuple[int, int]) -> Tuple[Tuple[int, int], ...]:
    result = []
    seen = set()
    for cell in cells:
        if cell in seen:
            continue
        result.append(cell)
        seen.add(cell)
    return tuple(result)


def _counter_increased(
    previous_record: Optional[Any],
    current_record: Any,
    *counter_names: str,
) -> bool:
    for counter_name in counter_names:
        previous_value = _record_counter(previous_record, counter_name)
        current_value = _record_counter(current_record, counter_name)
        if current_value - previous_value == 1:
            return True
    return False


def _record_counter(record: Optional[Any], counter_name: str) -> int:
    if record is None:
        return 0
    return getattr(record.key_dynamic_params, counter_name)


def _record_time(record: Any) -> float:
    return record.time
