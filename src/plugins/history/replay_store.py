"""录像分块存储层。

在保持 ``history`` 元数据表完全不变的前提下，把录像数据从
「每条一个 zlib BLOB（replay_data）」改造成「每块一个列式 lzma BLOB
（replay_segment）+ 索引（replay_index）+ 增量缓冲（replay_staging）」。

安全保证：
- ``history`` 表一列不改，原有 4 个索引、过滤/排序/计算列/自定义 SQL 全部不变。
- 每条录像写入时保存 sha256，读取时校验；任何不一致抛 ``ReplayIntegrityError``，
  由 ``read_raw_data`` 回退到旧的 ``replay_data`` / ``history.raw_data``。
- 结构无法安全定位的录像（非 v4 / 转码 / 未知事件类型）降级为逐条 zlib，
  绝不猜测、绝不重建字节。
- 删除采用 tombstone（块内是绝对偏移，物理删会使后续条目错位）。
"""

from __future__ import annotations

import hashlib
import logging
import lzma
import sqlite3
import zlib
from pathlib import Path
from typing import Iterable

from .replay_codec import (
    CODEC_LZMA_COLUMNAR,
    CODEC_RAW,
    CODEC_ZLIB,
    UnsupportedReplayError,
    decode_group,
    encode_group,
    split_evf,
)

logger = logging.getLogger(__name__)

__all__ = [
    "BLOCK_SIZE",
    "ReplayIntegrityError",
    "ensure_tables",
    "write_record",
    "read_raw_data",
    "mark_deleted",
    "restore_deleted",
    "seal_staging",
    "migrate_from_replay_data",
    "finalize_migration",
]

BLOCK_SIZE = 128
_LZMA_PRESET = 6


class ReplayIntegrityError(Exception):
    """录像解压/校验失败，调用方应回退到旧存储路径。"""


# ── schema ────────────────────────────────────────────────────

def ensure_tables(conn: sqlite3.Connection) -> None:
    """创建三张新表（幂等），不动 history / replay_data 的任何列。"""
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS replay_index (
            replay_id  INTEGER PRIMARY KEY,
            seg_id     INTEGER,
            slot       INTEGER,
            length     INTEGER,
            sha256     BLOB,
            codec      INTEGER NOT NULL DEFAULT 1,
            deleted    INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_replay_index_seg
            ON replay_index (seg_id, slot);
        CREATE INDEX IF NOT EXISTS idx_replay_index_deleted
            ON replay_index (deleted);
        CREATE INDEX IF NOT EXISTS idx_replay_index_codec
            ON replay_index (codec, deleted);

        CREATE TABLE IF NOT EXISTS replay_segment (
            seg_id        INTEGER PRIMARY KEY,
            blob          BLOB NOT NULL,
            codec         INTEGER NOT NULL,
            record_count  INTEGER NOT NULL,
            raw_size      INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS replay_staging (
            replay_id  INTEGER PRIMARY KEY,
            raw_data   BLOB NOT NULL,
            codec      INTEGER NOT NULL DEFAULT 1
        );
    """)
    conn.commit()


# ── 写入 ──────────────────────────────────────────────────────

def write_record(conn: sqlite3.Connection, replay_id: int,
                 raw_data: bytes | None) -> None:
    """写入一条录像：先落到 staging + replay_index，O(1)，不触发重压。

    由 ``seal_staging`` 在攒够一个块后统一封口。
    """
    if raw_data is None:
        return
    cursor = conn.cursor()
    # 逐条 zlib 作为 staging 形态（与现状一致，热路径开销不变）
    staged = zlib.compress(raw_data, level=6)
    cursor.execute(
        "INSERT OR REPLACE INTO replay_staging (replay_id, raw_data, codec) "
        "VALUES (?, ?, ?)",
        (replay_id, staged, CODEC_ZLIB),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO replay_index "
        "(replay_id, seg_id, slot, length, sha256, codec, deleted) "
        "VALUES (?, NULL, NULL, ?, ?, ?, 0)",
        (replay_id, len(raw_data), hashlib.sha256(raw_data).digest(),
         CODEC_ZLIB),
    )
    # 不 commit，由调用方与 history 插入保持同一事务
    _maybe_seal(conn)


def _maybe_seal(conn: sqlite3.Connection) -> None:
    """staging 达到 BLOCK_SIZE 时封口一批（由写路径顺带触发）。"""
    cursor = conn.cursor()
    (count,) = cursor.execute(
        "SELECT COUNT(*) FROM replay_staging").fetchone()
    if count >= BLOCK_SIZE:
        seal_staging(conn, limit=BLOCK_SIZE)


def seal_staging(conn: sqlite3.Connection, limit: int = BLOCK_SIZE) -> int:
    """把 staging 中最多 limit 条封成一个列式块。

    结构异常的单条会降级为逐条 zlib 并继续留在库里（codec=1），
    不影响其余条目。

    Returns:
        成功封入块的条数。
    """
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT replay_id, raw_data, codec FROM replay_staging "
        "ORDER BY replay_id LIMIT ?", (limit,),
    ).fetchall()
    if not rows:
        return 0

    # 解压成原始字节；结构异常者单独降级，不参与本块
    usable: list[tuple[int, bytes]] = []
    for replay_id, staged, codec in rows:
        try:
            raw = zlib.decompress(staged) if codec == CODEC_ZLIB else staged
            split_evf(raw)              # 只验证可安全定位，不修改字节
            usable.append((replay_id, raw))
        except (zlib.error, UnsupportedReplayError, ValueError):
            logger.warning("录像 %s 结构不支持列式，降级为逐条 zlib", replay_id)
            continue
    if not usable:
        return 0

    try:
        triples = [split_evf(raw) for _, raw in usable]
        payload = encode_group(triples)
        blob = lzma.compress(payload, preset=_LZMA_PRESET)
        # 封口前自检：解回来必须 bit-exact，否则整批放弃
        decoded = decode_group(payload, len(triples))
        if any(a != b for a, b in zip(triples, decoded)):
            raise ReplayIntegrityError("列式块 roundtrip 不一致")
    except (UnsupportedReplayError, ReplayIntegrityError, ValueError) as exc:
        logger.warning("列式封口失败，保留 staging 待下次重试: %s", exc)
        return 0

    (seg_id,) = cursor.execute(
        "SELECT COALESCE(MAX(seg_id), -1) + 1 FROM replay_segment").fetchone()
    raw_size = sum(len(raw) for _, raw in usable)
    cursor.execute(
        "INSERT INTO replay_segment "
        "(seg_id, blob, codec, record_count, raw_size) VALUES (?, ?, ?, ?, ?)",
        (seg_id, blob, CODEC_LZMA_COLUMNAR, len(usable), raw_size),
    )
    for slot, (replay_id, raw) in enumerate(usable):
        cursor.execute(
            "UPDATE replay_index SET seg_id = ?, slot = ?, length = ?, "
            "sha256 = ?, codec = ? WHERE replay_id = ?",
            (seg_id, slot, len(raw), hashlib.sha256(raw).digest(),
             CODEC_LZMA_COLUMNAR, replay_id),
        )
    # 只删成功封口的条目；降级条目留在 staging 供后续单独处理
    cursor.executemany(
        "DELETE FROM replay_staging WHERE replay_id = ?",
        [(rid,) for rid, _ in usable],
    )
    # 不 commit，由调用方控制事务边界
    return len(usable)


# ── 读取 ──────────────────────────────────────────────────────

def _read_from_segment(conn: sqlite3.Connection, replay_id: int) -> bytes | None:
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT seg_id, slot, length, sha256, codec, deleted "
        "FROM replay_index WHERE replay_id = ?", (replay_id,),
    ).fetchone()
    if row is None or row[5]:
        return None
    seg_id, slot, length, digest, codec, _ = row
    if codec == CODEC_ZLIB:
        # 尚未封口：从 staging 读
        s = cursor.execute(
            "SELECT raw_data, codec FROM replay_staging WHERE replay_id = ?",
            (replay_id,),
        ).fetchone()
        if s is None:
            return None
        raw = zlib.decompress(s[0]) if s[1] == CODEC_ZLIB else s[0]
    elif codec == CODEC_LZMA_COLUMNAR:
        seg = cursor.execute(
            "SELECT blob, record_count FROM replay_segment WHERE seg_id = ?",
            (seg_id,),
        ).fetchone()
        if seg is None:
            return None
        try:
            payload = lzma.decompress(seg[0])
            triples = decode_group(payload, seg[1])
            head, events, tail = triples[slot]
            raw = head + events + tail
        except (lzma.LZMAError, UnsupportedReplayError, ValueError,
                IndexError) as exc:
            raise ReplayIntegrityError(f"块解压失败: {exc}") from exc
    else:
        raise ReplayIntegrityError(f"未知 codec={codec}")

    if len(raw) != length or hashlib.sha256(raw).digest() != digest:
        raise ReplayIntegrityError(f"bit-exact 校验失败: replay_id={replay_id}")
    return raw


def read_raw_data(conn: sqlite3.Connection, replay_id: int) -> bytes | None:
    """读取录像原始数据，优先新存储，失败自动回退到旧路径。

    兼容形态（与 history_table._read_raw_data 原有逻辑一致）：
    a) replay_index / replay_segment / replay_staging（新）
    b) replay_data 子表（现状，逐条 zlib）
    c) history.raw_data（极旧库，可能有 compressed 列）
    """
    cursor = conn.cursor()
    # a) 新存储
    try:
        if cursor.execute(
            "SELECT 1 FROM replay_index WHERE replay_id = ?", (replay_id,)
        ).fetchone():
            try:
                return _read_from_segment(conn, replay_id)
            except ReplayIntegrityError as exc:
                logger.warning("新存储读取失败，回退旧路径: %s", exc)
    except sqlite3.OperationalError:
        pass  # 新表不存在

    # b) replay_data 子表
    try:
        row = cursor.execute(
            "SELECT raw_data, compressed FROM replay_data WHERE replay_id = ?",
            (replay_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row and row[0] is not None:
        return zlib.decompress(row[0]) if row[1] else row[0]

    # c) 极旧库：history.raw_data
    try:
        cursor.execute(
            "SELECT raw_data, compressed FROM history WHERE replay_id = ?",
            (replay_id,),
        )
        row = cursor.fetchone()
        flag = bool(row[1]) if row and row[1] is not None else None
    except sqlite3.OperationalError:
        try:
            cursor.execute(
                "SELECT raw_data FROM history WHERE replay_id = ?",
                (replay_id,))
            row = cursor.fetchone()
            flag = None
        except sqlite3.OperationalError:
            return None
    if row and row[0] is not None:
        return zlib.decompress(row[0]) if flag else row[0]
    return None


# ── 删除 ──────────────────────────────────────────────────────

def mark_deleted(conn: sqlite3.Connection, replay_id: int) -> None:
    """tombstone 删除：不物理删块，避免块内偏移错位。

    注意：未封口的条目数据只存在于 staging，删除时不能清掉它，
    否则 restore_deleted 后该条录像就永久丢失。已封口的条目数据
    在 segment 里，由后台 compaction 回收，这里一律不物理删。
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE replay_index SET deleted = 1 WHERE replay_id = ?",
            (replay_id,))
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute(
            "DELETE FROM replay_data WHERE replay_id = ?", (replay_id,))
    except sqlite3.OperationalError:
        pass


def restore_deleted(conn: sqlite3.Connection, replay_id: int) -> None:
    """撤销 tombstone（供撤销/测试用）。"""
    try:
        conn.execute(
            "UPDATE replay_index SET deleted = 0 WHERE replay_id = ?",
            (replay_id,))
    except sqlite3.OperationalError:
        pass


# ── 迁移 ──────────────────────────────────────────────────────

def migrate_from_replay_data(conn: sqlite3.Connection,
                             batch_size: int = BLOCK_SIZE) -> tuple[int, int]:
    """把旧 ``replay_data`` 表的数据灌入 staging 并封口（幂等）。

    不删除旧的 ``replay_data`` 行 —— 保留作回退，待确认稳定后由
    单独的清理流程 + VACUUM 回收。

    Returns:
        (迁移条数, 已封口块数)
    """
    ensure_tables(conn)
    cursor = conn.cursor()
    migrated = 0
    sealed = 0
    while True:
        rows = cursor.execute(
            "SELECT replay_id, raw_data, compressed FROM replay_data "
            "WHERE replay_id NOT IN (SELECT replay_id FROM replay_index) "
            "ORDER BY replay_id LIMIT ?", (batch_size,),
        ).fetchall()
        if not rows:
            break
        for replay_id, data, compressed in rows:
            raw = zlib.decompress(data) if compressed else data
            staged = zlib.compress(raw, level=6)
            cursor.execute(
                "INSERT OR IGNORE INTO replay_staging "
                "(replay_id, raw_data, codec) VALUES (?, ?, ?)",
                (replay_id, staged, CODEC_ZLIB),
            )
            cursor.execute(
                "INSERT OR IGNORE INTO replay_index "
                "(replay_id, length, sha256, codec, deleted) "
                "VALUES (?, ?, ?, ?, 0)",
                (replay_id, len(raw), hashlib.sha256(raw).digest(),
                 CODEC_ZLIB),
            )
            migrated += 1
        conn.commit()
        while seal_staging(conn, limit=batch_size) > 0:
            sealed += 1
            conn.commit()
    conn.commit()
    return migrated, sealed


def finalize_migration(conn: sqlite3.Connection,
                       expected: int | None = None) -> bool:
    """校验迁移完整性后，清空旧 ``replay_data`` 表并回收磁盘空间。

    只有「每一条旧录像都能从新存储 bit-exact 读回」时才允许清空；
    任一失败则原样保留旧表，调用方可安全回退。

    Args:
        expected: 旧表行数；None 时自动统计。

    Returns:
        是否成功清空（False 表示校验未通过，旧表保持不动）。
    """
    cursor = conn.cursor()
    try:
        rows = cursor.execute(
            "SELECT replay_id, raw_data, compressed FROM replay_data"
        ).fetchall()
    except sqlite3.OperationalError:
        return False
    if not rows:
        return False
    if expected is not None and len(rows) != expected:
        logger.warning("迁移条数不符 (%d != %d)，保留旧表", len(rows), expected)
        return False

    # 逐条校验新存储可读且与原字节完全一致
    for replay_id, data, compressed in rows:
        original = zlib.decompress(data) if compressed else data
        try:
            restored = _read_from_segment(conn, replay_id)
        except ReplayIntegrityError:
            restored = None
        if restored != original:
            logger.warning("迁移校验失败 rid=%s，保留旧表", replay_id)
            return False

    cursor.execute("DELETE FROM replay_data")
    conn.commit()
    conn.execute("VACUUM")
    return True


def vacuum(conn: sqlite3.Connection) -> None:
    """回收磁盘空间（清理旧 replay_data 行之后调用）。"""
    conn.execute("VACUUM")
