"""局面板（board）紧凑存储与 SQLite 自定义函数。

``history.board`` 物理列从「带数字的完成局面 JSON 文本」改为「雷图 BLOB」：
数字格可由雷图通过 ``ms_toollib.cal_board_numbers`` 无损推导，无需落盘。

BLOB 布局（小端）：
    [2B row][2B col][ceil(row*col/8) B 雷图位图]
位序：第 ``i*col+j`` 个格子对应 ``bits[i//8]`` 的 ``7 - i%8`` 位。

读取约定（**重要**）：
- ``SELECT * FROM history`` 拿到的 ``board`` 是 **雷图 BLOB**，不是 JSON 文本。
- 需要 JSON 文本时，用 SQLite 自定义函数 ``py_board_json(board)`` 展开，
  例如 ``SELECT replay_id, py_board_json(board) AS board FROM history``。
- 对 board 做 LIKE / 字符串比较时，必须写成
  ``py_board_json(board) LIKE ?``，直接对 ``board`` 做 LIKE 无意义。
- 写入时用 ``py_board_blob(json_text)`` 把 JSON 转成 BLOB；插件自身的
  ``_on_video_save`` 已自动处理，第三方插件不要直接写 history 表。

``db_connection`` 会在每个连接上注册这三个函数，因此
``HistoryService.raw_query`` 也可直接使用它们。

兼容性：若某条记录的 board 仍是旧 JSON 文本（未迁移的历史数据），
``py_board_json`` 会原样返回，保证平滑过渡。

迁移并发模型：``migrate_board_to_blob`` 把 JSON→BLOB 的解析与校验放在
维护线程自己的连接上完成（CPU 密集），只把**短小**的条件 UPDATE 交给
``write=writer.execute(...)``。每个 UPDATE 都带 ``WHERE replay_id = ? AND
board = ?``（旧值精确匹配），因此并发改写/删除的行不会被覆盖，也不会
被错误计入迁移数量。函数不自动 commit 调用方事务，也不自动 VACUUM。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import struct
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

__all__ = [
    "board_json_to_blob",
    "board_blob_to_json",
    "register_board_functions",
    "is_board_blob",
    "migrate_board_to_blob",
    "BOARD_JSON_SQL",
]

_U16 = struct.Struct("<HH")

T = TypeVar("T")
# writer.execute(callback, background=True) 形态的调度器
WriteDispatch = Callable[[Callable[[sqlite3.Connection], T]], T]
ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]

# 在 SQL 里把 board 列展开成 JSON 文本的标准表达式，供各查询处复用
BOARD_JSON_SQL = 'py_board_json("board") AS "board"'

# board 迁移每批行数
_BOARD_BATCH = 200


def board_json_to_blob(text: str | bytes | None) -> bytes | None:
    """把带数字的完成局面 JSON 文本转成雷图 BLOB。

    解析失败返回 None（调用方应保留原值，不静默丢弃数据）。
    """
    if text is None:
        return None
    if isinstance(text, bytes):
        # 已是紧凑 BLOB，直接返回（幂等）
        return text
    try:
        matrix = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(matrix, list) or not matrix or not isinstance(matrix[0], list):
        return None
    row = len(matrix)
    col = len(matrix[0])
    if row == 0 or col == 0 or row > 255 or col > 255:
        return None
    for line in matrix:
        if not isinstance(line, list) or len(line) != col:
            return None
    bits = bytearray((row * col + 7) // 8)
    for i in range(row):
        for j in range(col):
            if matrix[i][j] == -1:
                pos = i * col + j
                bits[pos // 8] |= 1 << (7 - pos % 8)
    return _U16.pack(row, col) + bytes(bits)


def board_blob_to_json(blob: bytes | str | None) -> str | None:
    """把雷图 BLOB 展开回带数字的完成局面 JSON 文本。

    兼容旧数据：传入 str（旧 JSON 文本）时原样返回。
    """
    if blob is None:
        return None
    if isinstance(blob, str):
        return blob
    try:
        if len(blob) < 4:
            return None
        row, col = _U16.unpack_from(blob, 0)
        bits = blob[4:]
        if row == 0 or col == 0 or row > 255 or col > 255:
            return None
        expected = (row * col + 7) // 8
        if len(bits) != expected:
            return None
        matrix: list[list[int]] = []
        for i in range(row):
            line: list[int] = []
            for j in range(col):
                pos = i * col + j
                is_mine = (bits[pos // 8] >> (7 - pos % 8)) & 1
                line.append(-1 if is_mine else 0)
            matrix.append(line)
        import ms_toollib as ms
        solved = ms.cal_board_numbers(matrix)
        return json.dumps(solved, separators=(",", ":"))
    except Exception as exc:  # 解析/推导失败一律返回 None，不抛给 SQLite
        logger.warning("board 雷图展开失败: %s", exc)
        return None


def is_board_blob(value: object) -> bool:
    """判断值是否为紧凑雷图 BLOB（用于迁移时的幂等判断）。"""
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
    """SQLite UDF：board → JSON 文本。"""
    return board_blob_to_json(value)


def _py_board_blob(value):
    """SQLite UDF：JSON 文本 → 雷图 BLOB。"""
    result = board_json_to_blob(value)
    return result if result is not None else value


def _py_board_is_blob(value):
    """SQLite UDF：判断 board 是否已是紧凑 BLOB（迁移用）。"""
    return 1 if is_board_blob(value) else 0


def register_board_functions(conn) -> None:
    """在 SQLite 连接上注册 board 相关自定义函数（幂等）。"""
    conn.create_function("py_board_json", 1, _py_board_json)
    conn.create_function("py_board_blob", 1, _py_board_blob)
    conn.create_function("py_board_is_blob", 1, _py_board_is_blob)


# ── 迁移 ──────────────────────────────────────────────────────

def _board_columns(conn: sqlite3.Connection) -> set[str]:
    try:
        return {r[1] for r in conn.execute("PRAGMA table_info(history)")}
    except sqlite3.Error:
        return set()


def _convert_batch(
    rows: list[tuple[int, object]],
) -> tuple[list[tuple[bytes, int, object]], int]:
    """纯 CPU：解析 + 压缩 + 反向校验一批旧 JSON 文本。

    Returns:
        (``[(blob, replay_id, 原值), ...]``, 本批中**待迁移**的行数)。
        无法压缩的异常数据保留原值、不计入待迁移，不阻断迁移。
    """
    pending: list[tuple[bytes, int, object]] = []
    needed = 0
    for replay_id, value in rows:
        if is_board_blob(value):
            continue
        needed += 1
        text = value.decode("utf-8") if isinstance(value, bytes) else value
        if not isinstance(text, str):
            continue
        blob = board_json_to_blob(text)
        if blob is None:
            continue
        if board_blob_to_json(blob) != text:
            raise ValueError(
                f"board 迁移校验失败 replay_id={replay_id}: "
                "展开结果与原 JSON 不一致")
        pending.append((blob, replay_id, value))
    return pending, needed


def migrate_board_to_blob(
    conn: sqlite3.Connection,
    batch_size: int = _BOARD_BATCH,
    *,
    write: WriteDispatch | None = None,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> int:
    """把 ``history.board`` 中残留的 JSON 文本转成雷图 BLOB（幂等）。

    解析/压缩/反向校验（CPU）在 ``conn``（维护线程连接）上完成；写线程
    只执行带旧值精确匹配的短 ``UPDATE .. WHERE replay_id=? AND board=?``，
    每条 UPDATE 独立条件判断，因此：

    - 并发改写 board 的行不会被覆盖（条件不匹配 → 不计入转换数）。
    - 并发删除的行自然跳过。
    - 不 commit 调用方事务；``write`` 提供时由 writer 事务边界负责。

    Args:
        conn: 维护线程连接（读数据）。
        batch_size: 每批读取行数。
        write: ``writer.execute(callback, background=True)`` 调度器；
            ``None`` 时直接在本连接执行短事务。
        progress: ``(done, total)``，每批结束后回调；没有待迁移数据时
            **不会**回调。
        cancelled: 返回 True 时在批间停止，返回已转换行数。

    Returns:
        本函数实际转换的行数。
    """
    if batch_size <= 0:
        batch_size = _BOARD_BATCH
    if "board" not in _board_columns(conn):
        return 0
    # 只统计「仍是旧 JSON 文本」的行；已是 BLOB 的行不算待办，
    # 因此没有待迁移数据时 total=0，progress 完全不回调。
    total = -1
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM history "
            "WHERE board IS NOT NULL AND py_board_is_blob(board) = 0"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        # 连接未注册 UDF：本地注册（幂等，只影响本连接）
        try:
            register_board_functions(conn)
            total = conn.execute(
                "SELECT COUNT(*) FROM history "
                "WHERE board IS NOT NULL AND py_board_is_blob(board) = 0"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            return 0
    if total <= 0:
        return 0

    converted = 0
    processed = 0
    done_needed = 0
    last_id = -1
    while True:
        if cancelled is not None and cancelled():
            break
        rows = conn.execute(
            "SELECT replay_id, board FROM history "
            "WHERE replay_id > ? AND board IS NOT NULL "
            "ORDER BY replay_id LIMIT ?",
            (last_id, batch_size),
        ).fetchall()
        if not rows:
            break
        last_id = rows[-1][0]
        processed += len(rows)
        try:
            pending, needed = _convert_batch(rows)
        except ValueError as exc:
            logger.warning("board 迁移中断: %s", exc)
            break
        done_needed += needed

        if pending:
            def _apply(w: sqlite3.Connection,
                       batch: tuple = tuple(pending)) -> int:
                # 回调内只有 SQL，无解析/编码
                done = 0
                for blob, replay_id, original in batch:
                    cur = w.execute(
                        "UPDATE history SET board = ? "
                        "WHERE replay_id = ? AND board = ?",
                        (blob, replay_id, original))
                    done += cur.rowcount
                return done

            if write is not None:
                try:
                    converted += write(_apply)
                except sqlite3.OperationalError as exc:
                    logger.warning("board 迁移写入失败，稍后重试: %s", exc)
                    break
            else:
                # 无 writer：用短事务；调用方已有事务时不接管其提交边界
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
