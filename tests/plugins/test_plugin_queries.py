from types import SimpleNamespace

import pytest

from app import plugin_queries
from shared_types.queries import (
    GetBoardStateQuery, GetGameStatusQuery, GetGameContextQuery,
)


class LiveBoard:
    level = 0
    time = 12.5
    bbbv = 8
    game_board = [[0, 1], [10, 11]]

    @property
    def rtime(self):
        raise AssertionError("live rtime must not be read")

    @property
    def bbbv_solved(self):
        raise AssertionError("live bbbv_solved must not be read")


@pytest.fixture
def setup_queries():
    handlers = {}
    ui = SimpleNamespace(
        _allowed_controls=set(), label=SimpleNamespace(ms_board=LiveBoard()),
        _game_state="playing", gameMode=0, mineUnFlagedNum=3,
        row=9, column=9, minenum=10,
    )
    plugin_queries.register_plugin_queries(
        SimpleNamespace(register_query_handler=handlers.__setitem__), ui)
    return ui, handlers


def test_permissions_and_live_board_safety(setup_queries):
    ui, handlers = setup_queries
    assert set(handlers) == {GetBoardStateQuery,
                             GetGameStatusQuery, GetGameContextQuery}
    # 只有含棋盘格子的 board_state 受 board_update 开关约束；
    # game_status / game_context 只返回可见信息与统计元数据。
    board = handlers[GetBoardStateQuery](
        GetBoardStateQuery(request_id="denied"))
    assert not board.success
    assert board.request_id == "denied"
    assert "board_update permission disabled" in board.error
    for query_type in (GetGameStatusQuery, GetGameContextQuery):
        result = handlers[query_type](query_type(request_id="open"))
        assert result.success, query_type

    ui._allowed_controls.add("mouse_click")
    context = handlers[GetGameContextQuery](
        GetGameContextQuery(request_id="context"))
    assert context.success and context.request_id == "context"
    assert context.rtime == 0 and context.bbbv_solved == 0 and context.progress is None
    assert context.permissions.allowed_controls == ["mouse_click"]
    assert context.permissions.mouse_click and not context.permissions.board_update
    assert not hasattr(context.permissions, "new_random_game"), \
        "重开新局不再是作弊开关"


def test_visible_snapshot_and_invalid_dimensions(setup_queries):
    ui, handlers = setup_queries
    ui._allowed_controls.add("board_update")
    result = handlers[GetBoardStateQuery](
        GetBoardStateQuery(request_id="board"))
    assert result.success and result.request_id == "board"
    assert (result.rows, result.cols, result.cells) == (
        2, 2, [[0, 1], [10, 11]])
    ui.label.ms_board.game_board[0][0] = 8
    assert result.cells[0][0] == 0
    status = handlers[GetGameStatusQuery](
        GetGameStatusQuery(request_id="status"))
    assert status.success and (
        status.rows, status.cols, status.rtime) == (9, 9, 0)
    ui.label.ms_board.game_board = [[0], [1, 2]]
    result = handlers[GetBoardStateQuery](GetBoardStateQuery(request_id="bad"))
    assert not result.success and result.request_id == "bad"
    assert result.error == "board state unavailable: inconsistent board dimensions"


def test_parsed_video_statistics(setup_queries, monkeypatch):
    ui, handlers = setup_queries

    class ParsedVideo:
        level = 0
        time = 2.0
        rtime = 3.5
        bbbv = 8
        bbbv_solved = 3

    monkeypatch.setattr(plugin_queries.ms, "EvfVideo", ParsedVideo)
    ui.label.ms_board = ParsedVideo()
    result = handlers[GetGameContextQuery](
        GetGameContextQuery(request_id="video"))
    assert result.success
    assert (result.rtime, result.bbbv, result.bbbv_solved,
            result.progress) == (3.5, 8, 3, 3 / 8)
