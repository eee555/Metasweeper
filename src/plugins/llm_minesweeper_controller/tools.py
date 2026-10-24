from __future__ import annotations

import copy
import math
import threading
from typing import Callable

import msgspec

from config.constants import GAME_EVENT_STATE_MAP
from lib_zmq_plugins.shared.base import BaseCommand, BaseQuery, BaseQueryResult, CommandResponse
from shared_types.commands import MouseClickCommand, NewGameCommand
from shared_types.events import BoardUpdateEvent, GameStatusChangeEvent
from shared_types.queries import (
    BoardStateResult, GameContextResult, GameStatusResult,
    GetBoardStateQuery, GetGameContextQuery, GetGameStatusQuery,
)

from .mcp_server import failure

STATUS_NAMES: dict[int, str] = {}
for state_name, state_number in GAME_EVENT_STATE_MAP.items():
    STATUS_NAMES.setdefault(state_number, state_name)

# 只读查询：工具名 → 查询类（不进入控制授权）
READ_ONLY_QUERIES: dict[str, type[BaseQuery]] = {
    "get_board_state": GetBoardStateQuery,
    "get_game_status": GetGameStatusQuery,
    "get_game_context": GetGameContextQuery,
}

# 会产生实际游戏动作的工具
CONTROL_TOOLS = frozenset({"click_cell", "start_new_game"})

MAX_BATCH_CLICKS = 128
CLICK_PROPERTIES = {
    "row": {"type": "integer", "minimum": 0},
    "col": {"type": "integer", "minimum": 0},
    "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
}

TOOLS = [
    {"name": "get_board_state", "description": "Actively request the current visible board snapshot. Falls back to the last official event with source=cache when the live request fails.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "get_game_status", "description": "Actively request the current game status, timer, remaining mines and board parameters. Falls back to the last official event with source=cache when the live request fails.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "get_game_context", "description": "Actively request the game context: status, board parameters, 3BV progress, official/fair flags and currently enabled control permissions.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "click_cell", "description": "Click one cell (row, col, button) or submit clicks for an ordered batch. Validate all inputs before any click; refresh the visible board and check SDK permission for each action. Stop on the first failure, unknown confirmation or unavailable/finished/changed board. Never retry automatically; inspect completed, results and stopped_index before continuing.",
     "inputSchema": {"type": "object", "properties": {
         **CLICK_PROPERTIES,
         "clicks": {"type": "array", "minItems": 1, "maxItems": MAX_BATCH_CLICKS,
                    "items": {"type": "object", "properties": CLICK_PROPERTIES,
                              "required": ["row", "col"], "additionalProperties": False}}},
         "oneOf": [{"required": ["row", "col"], "not": {"required": ["clicks"]}},
                   {"required": ["clicks"], "not": {"anyOf": [
                       {"required": [field]} for field in CLICK_PROPERTIES]}}],
         "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False,
                     "openWorldHint": False}},
    {"name": "start_new_game", "description": "Start a game only when no game is in progress; default difficulty medium.",
     "inputSchema": {"type": "object", "properties": {
         "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"], "default": "medium"}},
         "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False,
                     "openWorldHint": False}},
]


class MinesweeperTools:
    def __init__(self, has_auth: Callable[[type], bool], request: Callable,
                 query: Callable[[BaseQuery, float], BaseQueryResult] | None = None):
        self.has_auth = has_auth
        self.request = request
        self.query = query
        self.report_progress: Callable[[dict], None] | None = None
        self.lock = threading.RLock()
        self.board: dict | None = None
        self.status: int | None = None
        self.revision = 0
        self.board_epoch = 0

    def reset(self) -> None:
        with self.lock:
            self.board = None
            self.status = None
            self.revision += 1
            self.board_epoch += 1

    def update_board(self, event: BoardUpdateEvent) -> None:
        with self.lock:
            self.revision += 1
            self.board = None
            rows, cols = event.rows, event.cols
            if (type(rows) is not int or type(cols) is not int or rows <= 0 or cols <= 0
                    or rows * cols > 65536 or not isinstance(event.game_board, list)
                    or len(event.game_board) != rows):
                self.board_epoch += 1
                return
            cells = self._normalize_cells(event.game_board, rows, cols)
            if cells is None:
                self.board_epoch += 1
                return
            if (type(event.mines_remaining) is not int
                    or type(event.game_time) not in (int, float) or not math.isfinite(event.game_time)):
                self.board_epoch += 1
                return
            self.board = {"rows": rows, "cols": cols, "cells": cells,
                          "mines_remaining": event.mines_remaining, "game_time": event.game_time}

    @staticmethod
    def _normalize_cells(game_board: object, rows: int, cols: int) -> list[list] | None:
        if not isinstance(game_board, list) or len(game_board) != rows:
            return None
        mapping = {10: -1, 11: "F", 14: "X", 15: "M", 16: "m"}
        cells = []
        for row in game_board:
            if not isinstance(row, list) or len(row) != cols:
                return None
            if any(type(cell) is not int for cell in row):
                return None
            cells.append(
                [cell if 0 <= cell <= 8 else mapping.get(cell, -1) for cell in row])
        return cells

    def update_status(self, event: GameStatusChangeEvent) -> None:
        with self.lock:
            self.revision += 1
            previous = self.status
            self.status = event.current_status if type(
                event.current_status) is int else None
            if self.status not in (1, 2, 3, 4) or (self.status == 1 and previous not in (None, 1)):
                self.board = None
                self.board_epoch += 1

    def _prepare(self, name: str, arguments: dict) -> BaseQuery | BaseCommand | dict:
        if not isinstance(arguments, dict):
            return failure("Arguments must be an object")
        query_type = READ_ONLY_QUERIES.get(name)
        if query_type is not None:
            if arguments:
                return failure(f"{name} accepts no arguments")
            return query_type()
        if name == "click_cell":
            if set(arguments) - {"row", "col", "button"} or not {"row", "col"} <= arguments.keys():
                return failure("Expected row, col, and optional button only")
            row, col, button = arguments["row"], arguments["col"], arguments.get(
                "button", "left")
            if type(row) is not int or type(col) is not int:
                return failure("Coordinates must be integers, not booleans or strings")
            if not isinstance(button, str) or button not in ("left", "right", "middle"):
                return failure("Unknown button; use left, right, or middle")
            if self.board is None or self.status not in (1, 2):
                return failure("No actionable visible board; wait for SDK events")
            if not (0 <= row < self.board["rows"] and 0 <= col < self.board["cols"]):
                return failure("Coordinates out of bounds")
            return MouseClickCommand(row=row, col=col, button={"left": 0, "middle": 1, "right": 2}[button])
        if name == "start_new_game":
            if set(arguments) - {"difficulty"}:
                return failure("Expected optional difficulty only")
            difficulty = arguments.get("difficulty", "medium")
            if not isinstance(difficulty, str) or difficulty not in ("easy", "medium", "hard"):
                return failure("Unknown difficulty; use easy, medium, or hard")
            if self.status not in (1, 3, 4) or self.board is None:
                return failure("Cannot replace a playing, unknown, or unavailable game")
            return NewGameCommand(level={"easy": 3, "medium": 4, "hard": 5}[difficulty])
        return failure("Unknown tool")

    def _live_snapshot(self, name: str, result: BaseQueryResult) -> dict | None:
        """校验强类型查询结果；不合法时返回 None"""
        if name == "get_board_state":
            if not isinstance(result, BoardStateResult):
                return None
            rows, cols = result.rows, result.cols
            if (type(rows) is not int or type(cols) is not int
                    or rows <= 0 or cols <= 0 or rows * cols > 65536):
                return None
            cells = self._normalize_cells(result.cells, rows, cols)
            if cells is None:
                return None
            if (type(result.mines_remaining) is not int
                    or type(result.game_time) not in (int, float)
                    or not math.isfinite(result.game_time)
                    or not isinstance(result.game_status, str)
                    or result.game_status not in GAME_EVENT_STATE_MAP
                    or type(result.game_status_code) is not int
                    or GAME_EVENT_STATE_MAP[result.game_status] != result.game_status_code):
                return None
            result.cells = cells
        elif not isinstance(result, (GameStatusResult, GameContextResult)):
            return None
        elif result.game_status not in GAME_EVENT_STATE_MAP:
            # 使用状态名集合（含 joking/jowin/jofail），而非去重后的数值映射
            return None
        payload = msgspec.to_builtins(result)
        if not isinstance(payload, dict):
            return None
        payload["success"] = True
        payload["source"] = "live"
        return payload

    def _cached_snapshot(self, name: str) -> dict | None:
        """主动查询失败时的回退结果"""
        with self.lock:
            if name == "get_board_state" and self.board is not None and self.status in STATUS_NAMES:
                return {"success": True, "source": "cache",
                        **copy.deepcopy(self.board), "game_status": STATUS_NAMES[self.status]}
            if (name == "get_game_status" and self.status in STATUS_NAMES
                    and self.board is not None):
                board = copy.deepcopy(self.board)
                return {"success": True, "source": "cache",
                        "game_status": STATUS_NAMES[self.status],
                        "game_status_code": self.status,
                        "game_time": board["game_time"],
                        "mines_remaining": board["mines_remaining"],
                        "rows": board["rows"], "cols": board["cols"]}
        return None

    def _run_query(self, name: str, query: BaseQuery) -> dict:
        """执行只读查询，失败时回退到最近一次官方事件"""
        try:
            result = self.query(query, 3.0) if self.query is not None else None
        except Exception:
            result = None
        if (not isinstance(result, BaseQueryResult)
                or type(result.success) is not bool
                or not result.success):
            cached = self._cached_snapshot(name)
            if cached is not None:
                return cached
            error = getattr(result, "error", None) or \
                "No valid snapshot from the main process; wait for SDK events"
            return failure(error, "unknown")
        snapshot = self._live_snapshot(name, result)
        if snapshot is None:
            cached = self._cached_snapshot(name)
            if cached is not None:
                return cached
            return failure("Main process returned an invalid snapshot; wait for SDK events", "unknown")
        code = getattr(result, "game_status_code", None)
        with self.lock:
            if name == "get_board_state":
                self.revision += 1
                self.board = {"rows": snapshot["rows"], "cols": snapshot["cols"],
                              "cells": snapshot["cells"],
                              "mines_remaining": snapshot["mines_remaining"],
                              "game_time": snapshot["game_time"]}
            # 同步状态：插件可能晚于对局启动，收不到 GameStatusChangeEvent
            if type(code) is int and code in STATUS_NAMES:
                self.status = code
        return snapshot

    def refresh_state(self) -> bool:
        """主动刷新一次可见局面与状态；成功时返回 True"""
        if self.query is None:
            return False
        snapshot = self._run_query("get_board_state", GetBoardStateQuery())
        return bool(snapshot.get("success")) and snapshot.get("source") == "live"

    @staticmethod
    def _batch_result(clicks: list[dict], results: list[dict]) -> dict:
        completed = sum(result["success"] for result in results)
        success = bool(clicks) and completed == len(clicks)
        failed = bool(results) and not results[-1]["success"]
        result = {"success": success, "outcome": "confirmed" if success else (
            "unknown" if failed and results[-1]["outcome"] == "unknown" else
            "partial" if completed else "not_executed"),
            "requested": len(clicks), "completed": completed,
            "results": copy.deepcopy(results),
            "stopped_index": None if success else len(results) - int(failed),
            "unattempted": len(clicks) - len(results)}
        if not success:
            result["error"] = results[-1]["error"] if failed else "Batch stopped before the next click"
        return result

    def _publish_batch_progress(self, clicks: list[dict], results: list[dict]) -> None:
        if self.report_progress is not None:
            self.report_progress(self._batch_result(clicks, results))

    def _execute_click_batch(self, arguments: dict) -> dict:
        clicks = arguments["clicks"]
        if (set(arguments) != {"clicks"} or not isinstance(clicks, list)
                or not 1 <= len(clicks) <= MAX_BATCH_CLICKS):
            return {**self._batch_result(clicks if isinstance(clicks, list) else [], []),
                **failure(f"Expected clicks only: an array of 1..{MAX_BATCH_CLICKS} cell objects")}
        clicks = copy.deepcopy(clicks)
        for index, click in enumerate(clicks):
            if (not isinstance(click, dict) or set(click) - {"row", "col", "button"}
                    or not {"row", "col"} <= click.keys()
                    or type(click["row"]) is not int or type(click["col"]) is not int
                    or click["row"] < 0 or click["col"] < 0
                    or not isinstance(click.get("button", "left"), str)
                    or click.get("button", "left") not in ("left", "right", "middle")):
                return {**self._batch_result(clicks, []),
                        **failure(f"Invalid click at index {index}; no clicks executed"),
                        "invalid_index": index}
        results = []
        self._publish_batch_progress(clicks, results)
        if not self.refresh_state():
            return {**self._batch_result(clicks, results),
                    "error": "Batch requires a fresh live visible board; no clicks executed"}
        with self.lock:
            if self.board is None:
                return {**self._batch_result(clicks, results),
                        "error": "No actionable visible board; no clicks executed"}
            for index, click in enumerate(clicks):
                prepared = self._prepare("click_cell", click)
                if isinstance(prepared, dict):
                    return {**self._batch_result(clicks, results), **prepared,
                            "invalid_index": index}
            shape = (self.board["rows"], self.board["cols"])
            epoch, game_time = self.board_epoch, self.board["game_time"]
            left_ready = self.status != 1
        for index, click in enumerate(clicks):
            blocked = None
            if index:
                fresh = self.refresh_state()
                with self.lock:
                    if not fresh:
                        blocked = failure("Fresh live board unavailable; batch stopped")
                    elif (self.board is None or self.board_epoch != epoch
                          or shape != (self.board["rows"], self.board["cols"])
                          or self.board["game_time"] < game_time):
                        blocked = failure("Board changed or invalidated; batch stopped")
                    elif self.status == 1 and left_ready:
                        blocked = failure("Game returned to ready state; batch stopped")
                    if blocked is None and self.board is not None:
                        game_time = self.board["game_time"]
                        left_ready = left_ready or self.status != 1
            result = blocked if blocked is not None else self.execute_function("click_cell", click)
            results.append({"index": index, **click, "button": click.get("button", "left"), **result})
            self._publish_batch_progress(clicks, results)
            if not result["success"]:
                break
        return self._batch_result(clicks, results)

    def execute_function(self, name: str, arguments: dict) -> dict:
        if name == "click_cell" and isinstance(arguments, dict) and "clicks" in arguments:
            return self._execute_click_batch(arguments)
        if name in CONTROL_TOOLS:
            with self.lock:
                stale = self.status is None or self.board is None
            # 缓存未知时先主动取值，不依赖事件是否已经到达
            if stale:
                self.refresh_state()
        with self.lock:
            command = self._prepare(name, arguments)
            if isinstance(command, dict):
                return command
            if isinstance(command, BaseQuery):
                pass  # 只读查询不检查控制授权
            elif not self.has_auth(type(command)):
                return failure("Official SDK control permission not granted to this plugin; reauthorize it")
            previous_board, previous_status = self.board, self.status
            revision = self.revision
            if not isinstance(command, BaseQuery):
                self.board = None
                if name == "start_new_game":
                    self.status = None
        if isinstance(command, BaseQuery):
            return self._run_query(name, command)
        try:
            response = self.request(command, timeout=3.0)
        except Exception as error:
            response = (CommandResponse(request_id=command.request_id, success=False, error=str(error))
                        if getattr(error, "send_state", None) == "not_sent" else None)
        if not isinstance(response, CommandResponse) or type(response.success) is not bool:
            with self.lock:
                if self.revision == revision:
                    self.board = None
                    self.status = None
                    self.revision += 1
            return failure("No valid command confirmation; result unknown; do not retry automatically", "unknown")
        if not response.success:
            with self.lock:
                if self.revision == revision:
                    self.board, self.status = previous_board, previous_status
            return failure(response.error or "Main process rejected command; check its control switches")
        return {"success": True, "outcome": "confirmed", "request_id": response.request_id,
                "message": "Main process confirmed; use fresh board events for the next action"}
