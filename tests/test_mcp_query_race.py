from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from plugins.llm_minesweeper_controller.tools import MinesweeperTools
from shared_types.events import BoardUpdateEvent, GameStatusChangeEvent
from shared_types.queries import BoardStateResult, GameContextResult, GameStatusResult


def board_event(cell=10):
    return BoardUpdateEvent(rows=1, cols=1, game_board=[[cell]],
                            mines_remaining=1, game_time=1.0)


def board_result():
    return BoardStateResult(success=True, rows=1, cols=1, cells=[[10]],
                            mines_remaining=1, game_time=1.0,
                            game_status="ready", game_status_code=1)


@pytest.mark.parametrize("name,result", [
    ("get_board_state", board_result()),
    ("get_game_status", GameStatusResult(success=True, game_status="ready", game_status_code=1)),
    ("get_game_context", GameContextResult(success=True, game_status="ready", game_status_code=1)),
])
@pytest.mark.parametrize("change", ["board", "status", "reset"])
def test_query_does_not_replace_newer_events_or_reset(name, result, change):
    started, release = Event(), Event()

    def query(_query, _timeout):
        started.set()
        assert release.wait(5)
        return result

    tools = MinesweeperTools(lambda _: True, lambda *args, **kwargs: None, query)
    tools.update_status(GameStatusChangeEvent(current_status=1))
    tools.update_board(board_event())
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(tools.execute_function, name, {})
        try:
            assert started.wait(5)
            if change == "board":
                tools.update_board(board_event(11))
            elif change == "status":
                tools.update_status(GameStatusChangeEvent(current_status=3))
            else:
                tools.reset()
            expected_board, expected_status = tools.board, tools.status
        finally:
            release.set()
        response = pending.result(timeout=5)
    assert tools.board == expected_board
    assert tools.status == expected_status
    if change != "reset" and name != "get_game_context":
        assert response["source"] == "cache"
    else:
        assert response["success"] is False


def test_refresh_rejects_query_after_board_invalidation():
    started, release = Event(), Event()

    def query(_query, _timeout):
        started.set()
        assert release.wait(5)
        return board_result()

    tools = MinesweeperTools(lambda _: True, lambda *args, **kwargs: None, query)
    tools.update_status(GameStatusChangeEvent(current_status=1))
    tools.update_board(board_event())
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(tools.refresh_state)
        try:
            assert started.wait(5)
            tools.update_board(BoardUpdateEvent(rows=0, cols=0, game_board=[]))
        finally:
            release.set()
        assert pending.result(timeout=5) is False
    assert tools.board is None


def test_query_without_intervening_change_updates_cache():
    tools = MinesweeperTools(lambda _: True, lambda *args, **kwargs: None,
                             lambda *_: board_result())
    response = tools.execute_function("get_board_state", {})
    assert response["source"] == "live"
    assert tools.status == 1
    assert tools.board["cells"] == [[-1]]
