"""board 列 ASCII 存储回归测试。"""
from __future__ import annotations

import json
import sqlite3

import pytest

from plugins.history.board_codec import (
    board_ascii_to_matrix,
    board_blob_to_ascii,
    board_json_to_ascii,
    board_to_ascii,
    is_board_ascii,
    migrate_board_to_ascii,
    register_board_functions,
)
from plugins.history.computed_column import ComputedColumn
from plugins.history.db import db_connection
from plugins.history.query_builder import build_order_by, build_where


def _matrix():
    import ms_toollib as ms
    m = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    m[0][0] = -1
    m[1][2] = -1
    m[2][3] = -1
    return ms.cal_board_numbers(m)


@pytest.fixture
def board_json():
    return json.dumps(_matrix(), separators=(",", ":"))


@pytest.fixture
def board_ascii(board_json):
    return board_json_to_ascii(board_json)


def test_json_to_ascii_and_matrix_roundtrip(board_json, board_ascii):
    assert board_ascii is not None
    assert is_board_ascii(board_ascii)
    assert len(board_ascii) == 3 * 4
    assert board_ascii_to_matrix(board_ascii, 3, 4) == _matrix()


def test_to_ascii_accepts_legacy_json_blob_and_ascii(board_json, board_ascii):
    from plugins.history.board_codec import board_json_to_blob
    blob = board_json_to_blob(board_json)
    assert board_to_ascii(board_json, 3, 4) == board_ascii
    assert board_to_ascii(blob, 3, 4) == board_ascii
    assert board_to_ascii(board_ascii, 3, 4) == board_ascii
    assert board_blob_to_ascii(blob) == board_ascii


def test_preview_parses_ascii_and_legacy_json(board_json, board_ascii):
    from plugins.history.board_preview import parse_board

    assert parse_board(board_ascii, 3, 4) == _matrix()
    assert parse_board(board_json, 3, 4) == _matrix()
    assert parse_board("000000000009", 3, 4) is None


def test_invalid_ascii_is_rejected():
    assert not is_board_ascii("[[0,1]]")
    assert not is_board_ascii("019")
    assert board_ascii_to_matrix("00000000000", 3, 4) is None


def test_migrate_board_converts_json_and_blob(tmp_path, board_json, board_ascii):
    from plugins.history.board_codec import board_json_to_blob
    db = tmp_path / "h.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY, row INTEGER, column INTEGER, board)")
    conn.executemany(
        "INSERT INTO history VALUES (?, 3, 4, ?)",
        [(1, board_json), (2, board_json_to_blob(board_json)), (3, board_ascii)])
    conn.commit(); conn.close()
    with db_connection(db) as c:
        assert migrate_board_to_ascii(c) == 2
        rows = c.execute("SELECT board FROM history ORDER BY replay_id").fetchall()
        assert [r[0] for r in rows] == [board_ascii] * 3
        assert migrate_board_to_ascii(c) == 0


def test_migrate_board_progress_write_and_cancel(tmp_path, board_json, board_ascii):
    db = tmp_path / "h.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY, row INTEGER, column INTEGER, board)")
    conn.executemany(
        "INSERT INTO history VALUES (?, 3, 4, ?)",
        [(i, board_json) for i in range(1, 6)])
    conn.commit(); conn.close()
    with db_connection(db) as c:
        seen = []
        dispatch = lambda cb: cb(c)
        assert migrate_board_to_ascii(
            c, batch_size=2, write=dispatch,
            progress=lambda d, t: seen.append((d, t))) == 5
        assert seen and seen[-1][1] == 5
        assert all(r[0] == board_ascii for r in c.execute("SELECT board FROM history"))


def test_board_udfs_registered(tmp_path, board_json, board_ascii):
    db = tmp_path / "h.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY, board)")
    conn.execute("INSERT INTO history VALUES (1, ?)", (board_ascii,))
    conn.commit(); conn.close()
    with db_connection(db) as c:
        assert c.execute("SELECT py_board_is_ascii(board) FROM history").fetchone()[0] == 1
        assert c.execute("SELECT py_board_ascii(?, 3, 4)", (board_json,)).fetchone()[0] == board_ascii
        assert c.execute(
            "SELECT COUNT(*) FROM history WHERE board LIKE ?",
            ("%2%",)).fetchone()[0] == 1


from plugins.history.models import CompareSymbol, LogicSymbol  # noqa: E402

_EQUAL = CompareSymbol.display_names()[0]
_LIKE = CompareSymbol.display_names()[8]
_AND = LogicSymbol.display_names()[0]


def _filter_row(field: str, compare: str, value: str) -> dict:
    return {"left_bracket": "", "field": field, "compare": compare,
            "value": value, "right_bracket": "", "logic": _AND}


def test_build_where_uses_raw_board_string():
    sql, params = build_where([_filter_row("board", _LIKE, "3")], {"board"}, {"board": ""})
    assert '"board"' in sql
    assert "py_board_json" not in sql
    assert params


def test_build_where_does_not_touch_other_fields():
    sql, _ = build_where([_filter_row("level", _EQUAL, "3")], {"level"}, {"level": 0})
    assert "level" in sql
    assert "py_board_json" not in sql


def test_build_order_by_uses_raw_board_string():
    sql = build_order_by([{"field": "board", "order": "升序"}], {"board"})
    assert '"board"' in sql
    assert "py_board_json" not in sql


def test_computed_column_subquery_keeps_raw_board_string():
    col = ComputedColumn(name="bbbvs", expression="bbbv_solved*1.0/rtime", result_type="float")
    sql = ComputedColumn.build_subquery_sql([col])
    assert sql is not None
    assert '"board"' in sql
    assert "py_board_json" not in sql
    assert "SELECT *" not in sql
