"""局面板（board）紧凑 ASCII 存储与 SQLite 兼容函数。

``history.board`` 存储「每格一个 ASCII 字符」的完成局面：
``0`` ~ ``8`` 分别表示空白格/周围雷数，``*`` 表示雷。字符串按行优先
排列，没有分隔符；行列数由同一行的 ``history.row`` / ``history.column``
给出，因此字符串长度应为 ``row * column``。

示例：``[[-1,-1,-1],[2,3,2],[0,0,0]]`` 存为 ``"***232000"``。

读取约定：
- SELECT ``board`` 拿到的就是实际存储字符串，可直接 LIKE / 子串过滤。
- 悬浮预览按同一记录的 row/column 把字符串切成二维整数列表；
  ``*`` 转为 -1，数字字符转为对应整数。
- 旧 JSON 文本和旧雷图 BLOB 会在后台迁移为 ASCII；迁移前仍可读，
  但不能按新格式的子串语义查询。

兼容性 UDF：
- ``py_board_json(board)``：把旧 BLOB/JSON 转成旧 JSON 文本；ASCII 字符串
  按 row/column 无法在此函数中恢复二维结构，仅作过渡兼容。
- ``py_board_is_blob(board)`` / ``py_board_is_ascii(board)``：格式判断。
- ``py_board_ascii(board, row, col)``：把 JSON/雷图 BLOB/ASCII 统一转为 ASCII。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import struct
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

__all__ = [
    "board_json_to_ascii",
    "board_blob_to_ascii",
    "board_to_ascii",
    "board_ascii_to_matrix",
    "is_board_ascii",
    "is_board_blob",
    "board_blob_to_json",
    "board_json_to_blob",
    "register_board_functions",
    "migrate_board_to_ascii",
]

_U16 = struct.Struct("<HH")

T = TypeVar("T")
# writer.execute(callback, background=True) 形态的调度器
WriteDispatch = Callable[[Callable[[sqlite3.Connection], T]], T]
ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]

# board 迁移每批行数
_BOARD_BATCH = 200


def _matrix_from_blob(blob: bytes) -> list[list[int]]:
    row, col = _U16.unpack_from(blob, 0)
    bits = blob[4:]
    if row == 0 or col == 0 or len(bits) != (row * col + 7) // 8:
        raise ValueError("invalid board bitmap")
    matrix: list[list[int]] = []
    for i in range(row):
        line: list[int] = []
        for j in range(col):
            pos = i * col + j
            mine = (bits[pos // 8] >> (7 - pos % 8)) & 1
            line.append(-1 if mine else 0)
        matrix.append(line)
    import ms_toollib as ms
    return ms.cal_board_numbers(matrix)


def board_json_to_blob(text: str | bytes | None) -> bytes | None:
    """兼容旧 API：把 JSON 文本转成旧雷图 BLOB。"""
    if text is None:
        return None
    if isinstance(text, bytes) and is_board_blob(text):
        return text
    matrix = _matrix_from_json(text)
    if matrix is None:
        return None
    return _blob_from_matrix(matrix)


def _matrix_from_json(text: object) -> list[list[int]] | None:
    try:
        data = json.loads(text) if isinstance(text, str) else text
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, (list, tuple)) or not data or not isinstance(data[0], (list, tuple)):
        return None
    col = len(data[0])
    if col == 0:
        return None
    matrix: list[list[int]] = []
    for line in data:
        if not isinstance(line, (list, tuple)) or len(line) != col:
            return None
        values: list[int] = []
        for cell in line:
            if isinstance(cell, bool) or not isinstance(cell, int):
                return None
            if cell not in (-1, *range(0, 9)):
                return None
            values.append(cell)
        matrix.append(values)
    return matrix


def _blob_from_matrix(matrix: list[list[int]]) -> bytes:
    row, col = len(matrix), len(matrix[0])
    bits = bytearray((row * col + 7) // 8)
    for i, line in enumerate(matrix):
        for j, cell in enumerate(line):
            if cell == -1:
                pos = i * col + j
                bits[pos // 8] |= 1 << (7 - pos % 8)
    return _U16.pack(row, col) + bytes(bits)


def board_json_to_ascii(text: str | bytes | None) -> str | None:
    """把带数字的完成局面 JSON 文本转成每格一个字符的字符串。"""
    matrix = _matrix_from_json(text)
    if matrix is None:
        return None
    return "".join("*" if cell == -1 else str(cell)
                   for line in matrix for cell in line)


def board_blob_to_ascii(blob: bytes | str | None) -> str | None:
    """把旧雷图 BLOB 转成每格一个字符的字符串。"""
    if isinstance(blob, str):
        return board_json_to_ascii(blob)
    if blob is None or not is_board_blob(blob):
        return None
    try:
        matrix = _matrix_from_blob(blob)
    except Exception:
        return None
    return "".join("*" if cell == -1 else str(cell)
                   for line in matrix for cell in line)


def board_ascii_to_matrix(text: object, row: int, col: int) -> list[list[int]] | None:
    """按 row/column 把 ASCII 字符串切成二维整数列表。"""
    if not isinstance(text, str) or row <= 0 or col <= 0:
        return None
    if len(text) != row * col:
        return None
    board: list[list[int]] = []
    for i in range(row):
        line: list[int] = []
        for ch in text[i * col:(i + 1) * col]:
            if ch == "*":
                line.append(-1)
            elif "0" <= ch <= "8":
                line.append(ord(ch) - ord("0"))
            else:
                return None
        board.append(line)
    return board


def is_board_ascii(value: object) -> bool:
    """判断值是否为每格一个字符的 ASCII 局面。"""
    return (isinstance(value, str) and value != ""
            and all(ch == "*" or "0" <= ch <= "8" for ch in value))


def board_to_ascii(value: object, row: int = 0, col: int = 0) -> str | None:
    """把 JSON 文本 / 旧雷图 BLOB / ASCII 统一转成 ASCII。"""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        if is_board_blob(raw):
            return board_blob_to_ascii(raw)
        try:
            return board_json_to_ascii(raw.decode("utf-8"))
        except UnicodeDecodeError:
            return None
    if is_board_ascii(value):
        return value
    return board_json_to_ascii(value)


def board_blob_to_json(blob: bytes | str | None) -> str | None:
    """兼容旧 API：把旧雷图 BLOB 展开回 JSON 文本。"""
    if blob is None:
        return None
    if isinstance(blob, str):
        return blob
    if not is_board_blob(blob):
        return None
    try:
        return json.dumps(_matrix_from_blob(blob), separators=(",", ":"))
    except Exception as exc:
        logger.warning("board 雷图展开失败: %s", exc)
        return None


def is_board_blob(value: object) -> bool:
    """判断值是否为旧雷图 BLOB（供迁移兼容）。"""
    if not isinstance(value, (bytes, bytearray, memoryview)):
        return False
    try:
        if len(value) < 4:
            return False
        row, col = _U16.unpack_from(value, 0)
        return (row > 0 and col > 0
                and len(value) == 4 + (row * col + 7) // 8)
    except (struct.error, TypeError):
        return False


def _py_board_json(value):
    return board_blob_to_json(value)


def _py_board_blob(value):
    result = board_json_to_blob(value)
    return result if result is not None else value


def _py_board_ascii(value, row, col):
    return board_to_ascii(value, row, col)


def _py_board_is_blob(value):
    return 1 if is_board_blob(value) else 0


def _py_board_is_ascii(value):
    return 1 if is_board_ascii(value) else 0


def register_board_functions(conn) -> None:
    """在 SQLite 连接上注册兼容 UDF（幂等）。"""
    conn.create_function("py_board_json", 1, _py_board_json)
    conn.create_function("py_board_blob", 1, _py_board_blob)
    conn.create_function("py_board_ascii", 3, _py_board_ascii)
    conn.create_function("py_board_is_blob", 1, _py_board_is_blob)
    conn.create_function("py_board_is_ascii", 1, _py_board_is_ascii)


def _board_columns(conn: sqlite3.Connection) -> set[str]:
    try:
        return {r[1] for r in conn.execute("PRAGMA table_info(history)")}
    except sqlite3.Error:
        return set()


def _convert_batch(
    rows: list[tuple[int, object, int, int]],
) -> tuple[list[tuple[str, int, object]], int]:
    """准备一批待迁移行：JSON/旧雷图 BLOB → ASCII 字符串。"""
    pending: list[tuple[str, int, object]] = []
    needed = 0
    for replay_id, value, row, col in rows:
        if is_board_ascii(value):
            continue
        needed += 1
        ascii_board = board_to_ascii(value, row, col)
        if ascii_board is None or int(row) <= 0 or int(col) <= 0 \
                or len(ascii_board) != int(row) * int(col):
            logger.warning("board %s 无法安全转成 ASCII，保留原值", replay_id)
            continue
        pending.append((ascii_board, replay_id, value))
    return pending, needed


def migrate_board_to_ascii(
    conn: sqlite3.Connection,
    batch_size: int = _BOARD_BATCH,
    *,
    write: WriteDispatch | None = None,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> int:
    """把旧 JSON/雷图 BLOB 迁移为每格一个字符的 ASCII 字符串（幂等）。"""
    if batch_size <= 0:
        batch_size = _BOARD_BATCH
    cols = _board_columns(conn)
    if "board" not in cols or "row" not in cols or "column" not in cols:
        return 0
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM history WHERE board IS NOT NULL "
            "AND py_board_is_ascii(board) = 0").fetchone()[0]
    except sqlite3.OperationalError:
        register_board_functions(conn)
        total = conn.execute(
            "SELECT COUNT(*) FROM history WHERE board IS NOT NULL "
            "AND py_board_is_ascii(board) = 0").fetchone()[0]
    if total <= 0:
        return 0

    converted = 0
    done_needed = 0
    last_id = -1
    while True:
        if cancelled is not None and cancelled():
            break
        rows = conn.execute(
            'SELECT replay_id, board, "row", "column" FROM history '
            "WHERE replay_id > ? AND board IS NOT NULL "
            "ORDER BY replay_id LIMIT ?",
            (last_id, batch_size)).fetchall()
        if not rows:
            break
        last_id = rows[-1][0]
        pending, needed = _convert_batch(rows)
        done_needed += needed
        if pending:
            def _apply(w: sqlite3.Connection,
                       batch: tuple = tuple(pending)) -> int:
                done = 0
                for ascii_board, replay_id, original in batch:
                    cur = w.execute(
                        "UPDATE history SET board = ? "
                        "WHERE replay_id = ? AND board = ?",
                        (ascii_board, replay_id, original))
                    done += cur.rowcount
                return done

            if write is not None:
                try:
                    converted += write(_apply)
                except sqlite3.OperationalError as exc:
                    logger.warning("board 迁移写入失败，稍后重试: %s", exc)
                    break
            else:
                owned = not conn.in_transaction
                if owned:
                    conn.execute("BEGIN IMMEDIATE")
                try:
                    converted += _apply(conn)
                except BaseException:
                    if owned and conn.in_transaction:
                        conn.rollback()
                    raise
                else:
                    if owned:
                        conn.commit()
        if progress is not None and total > 0:
            progress(min(done_needed, total), total)
    return converted
