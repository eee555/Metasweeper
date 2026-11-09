"""board 列紧凑存储（雷图 BLOB）回归测试。"""
from __future__ import annotations

import json
import sqlite3

import pytest

from plugins.history.board_codec import (
    BOARD_JSON_SQL,
    board_blob_to_json,
    board_json_to_blob,
    is_board_blob,
    migrate_board_to_blob,
    register_board_functions,
)
from plugins.history.computed_column import ComputedColumn
from plugins.history.db import db_connection
from plugins.history.query_builder import build_order_by, build_where


def _board(row=3, col=4):
    """一个带数字的合法完成局面。"""
    import ms_toollib as ms
    m = [[0] * col for _ in range(row)]
    m[0][0] = -1
    m[1][2] = -1
    m[2][col - 1] = -1
    return ms.cal_board_numbers(m)


@pytest.fixture
def board_json():
    return json.dumps(_board(), separators=(",", ":"))


# ── 编解码 ────────────────────────────────────────────────────

def test_roundtrip_bit_exact(board_json):
    blob = board_json_to_blob(board_json)
    assert blob is not None
    assert is_board_blob(blob)
    assert board_blob_to_json(blob) == board_json


@pytest.mark.parametrize("row,col", [(1, 1), (8, 8), (16, 16), (16, 30),
                                     (9, 11), (99, 99)])
def test_roundtrip_various_sizes(row, col):
    import ms_toollib as ms
    m = [[0] * col for _ in range(row)]
    for i in range(0, row, 2):
        for j in range(0, col, 3):
            m[i][j] = -1
    text = json.dumps(ms.cal_board_numbers(m), separators=(",", ":"))
    blob = board_json_to_blob(text)
    assert blob is not None
    assert board_blob_to_json(blob) == text


def test_blob_is_much_smaller(board_json):
    assert len(board_json_to_blob(board_json)) < len(board_json) / 4


def test_board_json_to_blob_rejects_invalid():
    assert board_json_to_blob(None) is None
    assert board_json_to_blob("not json") is None
    assert board_json_to_blob("[]") is None
    assert board_json_to_blob("[[1,2],[3]]") is None      # 非矩形
    assert board_json_to_blob(json.dumps([[0]])) is not None


def test_board_json_to_blob_is_idempotent(board_json):
    blob = board_json_to_blob(board_json)
    assert board_json_to_blob(blob) == blob


def test_board_blob_to_json_accepts_legacy_text(board_json):
    """兼容未迁移的旧 JSON 文本：原样返回。"""
    assert board_blob_to_json(board_json) == board_json
    assert board_blob_to_json(None) is None
    assert board_blob_to_json(b"\x00\x01") is None       # 损坏 BLOB


def test_is_board_blob_rejects_text(board_json):
    assert not is_board_blob(board_json)
    assert not is_board_blob(b"[[0,1],[1,-1]]")
    assert not is_board_blob(None)


# ── UDF ───────────────────────────────────────────────────────

def test_udf_registered_on_db_connection(tmp_path, board_json):
    db = tmp_path / "h.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY, board)")
    conn.execute("INSERT INTO history VALUES (1, ?)",
                 (board_json_to_blob(board_json),))
    conn.commit()
    conn.close()

    with db_connection(db) as c:
        (value,) = c.execute(
            "SELECT py_board_json(board) FROM history WHERE replay_id=1"
        ).fetchone()
        assert value == board_json
        (flag,) = c.execute(
            "SELECT py_board_is_blob(board) FROM history WHERE replay_id=1"
        ).fetchone()
        assert flag == 1
        (blob,) = c.execute(
            "SELECT py_board_blob(?)", (board_json,)).fetchone()
        assert board_blob_to_json(blob) == board_json


def test_udf_available_even_with_custom_functions_disabled(tmp_path, board_json):
    """register_custom_functions=False 时 board UDF 仍必须可用。"""
    db = tmp_path / "h.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY, board)")
    conn.commit(); conn.close()
    with db_connection(db, register_custom_functions=False) as c:
        (value,) = c.execute("SELECT py_board_json(?)",
                             (board_json_to_blob(board_json),)).fetchone()
        assert value == board_json


def test_board_like_requires_udf(tmp_path, board_json):
    db = tmp_path / "h.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY, board)")
    conn.execute("INSERT INTO history VALUES (1, ?)",
                 (board_json_to_blob(board_json),))
    conn.commit(); conn.close()
    with db_connection(db) as c:
        # 展开后 LIKE 才能匹配 JSON 文本（用 board_json 的真实前缀）
        n = c.execute("SELECT COUNT(*) FROM history "
                      "WHERE py_board_json(board) LIKE ?",
                      (board_json[:12].replace("%", "\\%") + "%",)).fetchone()[0]
        assert n == 1
        # 不展开时直接对 BLOB 做 LIKE 匹配不到 JSON 文本
        n_raw = c.execute("SELECT COUNT(*) FROM history "
                          "WHERE board LIKE ?", ("%[%",)).fetchone()[0]
        assert n_raw == 0


# ── 迁移 ──────────────────────────────────────────────────────

def test_migrate_board_to_blob(tmp_path, board_json):
    db = tmp_path / "h.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY, board)")
    conn.executemany("INSERT INTO history VALUES (?, ?)",
                     [(1, board_json), (2, board_json),
                      (3, board_json_to_blob(board_json))])  # 已压缩
    conn.commit(); conn.close()

    with db_connection(db) as c:
        converted = migrate_board_to_blob(c)
        c.commit()
        assert converted == 2                       # 跳过已压缩的
        rows = c.execute("SELECT replay_id, board FROM history "
                         "ORDER BY replay_id").fetchall()
        assert all(is_board_blob(r[1]) for r in rows)
        for _, blob in rows:
            assert board_blob_to_json(blob) == board_json
        # 幂等
        assert migrate_board_to_blob(c) == 0


def test_migrate_keeps_legacy_text_readable(tmp_path, board_json):
    """迁移前后用 UDF 读到的 JSON 必须一致。"""
    db = tmp_path / "h.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY, board)")
    conn.execute("INSERT INTO history VALUES (1, ?)", (board_json,))
    conn.commit(); conn.close()

    with db_connection(db) as c:
        before = c.execute(
            "SELECT py_board_json(board) FROM history").fetchone()[0]
        assert before == board_json                 # 旧文本原样返回
        migrate_board_to_blob(c); c.commit()
        after = c.execute(
            "SELECT py_board_json(board) FROM history").fetchone()[0]
        assert after == before


# ── 查询构建器：board 字段必须展开 ────────────────────────────

from plugins.history.models import CompareSymbol, LogicSymbol  # noqa: E402

_EQUAL = CompareSymbol.display_names()[0]
_LIKE = CompareSymbol.display_names()[8]
_AND = LogicSymbol.display_names()[0]


def _filter_row(field: str, compare: str, value: str) -> dict:
    return {
        "left_bracket": "", "field": field, "compare": compare,
        "value": value, "right_bracket": "", "logic": _AND,
    }


def test_build_where_expands_board_for_like():
    rows = [_filter_row("board", _LIKE, "[[0")]
    sql, params = build_where(rows, {"board"}, {"board": ""})
    assert 'py_board_json("board")' in sql
    assert params


def test_build_where_expands_board_for_equality():
    rows = [_filter_row("board", _EQUAL, "x")]
    sql, params = build_where(rows, {"board"}, {"board": ""})
    assert 'py_board_json("board") = ?' in sql


def test_build_where_does_not_touch_other_fields():
    rows = [_filter_row("level", _EQUAL, "3")]
    sql, params = build_where(rows, {"level"}, {"level": 0})
    assert "level" in sql
    assert "py_board_json" not in sql


def test_build_order_by_expands_board():
    sql = build_order_by(
        [{"field": "board", "order": "升序"}], {"board"})
    assert 'py_board_json("board")' in sql


def test_computed_column_subquery_expands_board():
    col = ComputedColumn(name="bbbvs",
                         expression="bbbv_solved*1.0/rtime",
                         result_type="float")
    sql = ComputedColumn.build_subquery_sql([col])
    assert sql is not None
    assert 'py_board_json("board") AS "board"' in sql
    assert 'SELECT *' not in sql               # 不能带出原始 BLOB
    assert '"bbbvs"' in sql


def test_board_json_sql_constant():
    assert BOARD_JSON_SQL == 'py_board_json("board") AS "board"'
