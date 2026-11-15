"""录像分块存储层（prepare / apply 两阶段）。

在保持 ``history`` 元数据表完全不变的前提下，把录像数据从
「每条一个 zlib BLOB（replay_data）」改造成「每块一个列式 lzma BLOB
（replay_segment）+ 索引（replay_index）+ 增量缓冲（replay_staging）」。

**并发模型（重要）**

数据库只有一个写线程（``DatabaseWriter``）。所有解压、编码、lzma 压缩、
校验等 CPU 工作都必须在写线程之外完成，写线程只执行毫秒级 SQL：

- :func:`prepare_seal` 用**任意只读连接**读取 staging，完成 split /
  列式编码 / lzma 压缩 / roundtrip 自检，返回不可变的
  :class:`PreparedSeal`（纯内存对象，可跨线程传递）。
- :func:`apply_seal` 在**短写事务**内复核 staging 与 index 的每一行都与
  计划完全一致，然后插入块、更新索引、删除 staging。

跨连接的读连接与写连接无法比较 ``PRAGMA data_version``（它是连接本地
计数，跨连接不可比），因此短事务内的正确性由「逐行精确快照比对」保证：
staging 的压缩字节、codec，以及 index 的 seg_id / slot / length /
sha256 / codec / deleted 全部必须与准备阶段捕获的值逐字节相同。任何
差异（并发删除、并发改写、**同长度内容替换**、墓碑、已被他人封口）都
整体放弃本批，不写入任何数据，留待下一轮重试。prepare 与 apply 恰好
使用同一连接时，额外用 ``data_version`` 变化做早期放弃。

安全保证：

- ``history`` 表一列不改，原有 4 个索引、过滤/排序/计算列/自定义 SQL 全部不变。
- 每条录像写入时保存 sha256，读取时校验；任何不一致抛 ``ReplayIntegrityError``，
  由 ``read_raw_data`` 回退到旧的 ``replay_data`` / ``history.raw_data``。
- 结构无法安全定位的录像（非 v4 / 转码 / 未知事件类型）降级为逐条 zlib，
  绝不猜测、绝不重建字节。
- 删除采用 tombstone（块内是绝对偏移，物理删会使后续条目错位）。
- ``write_record`` 只写 staging + index，**绝不同步封口**。

维护 API（供后台 worker 用 ``write=writer.execute(..., background=True)``
把短写回调调度到写线程；读/解压/压缩都在维护线程自己的连接上完成）::

    migrate_from_replay_data(conn, batch_size, *, write=None,
                             progress=None, cancelled=None) -> (migrated, sealed)
    finalize_migration(conn, expected=None, *, batch_size=BLOCK_SIZE,
                       write=None, progress=None, cancelled=None) -> bool
    migrate_board_to_blob(conn, batch_size, *, write=None,
                          progress=None, cancelled=None) -> int  # board_codec
"""

from __future__ import annotations

import hashlib
import logging
import lzma
import sqlite3
import zlib
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence, TypeVar

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
    "SealEntry",
    "PreparedSeal",
    "ensure_tables",
    "write_record",
    "prepare_seal",
    "apply_seal",
    "seal_staging",
    "read_raw_data",
    "mark_deleted",
    "restore_deleted",
    "migrate_from_replay_data",
    "finalize_migration",
    "vacuum",
]

BLOCK_SIZE = 128
_LZMA_PRESET = 6
# 单次操作内保留的解码块数（块约 128 条，数块足够覆盖顺序读与相邻跳转）
_SEGMENT_CACHE_LIMIT = 4
# prepare_seal 扫描 staging 的额外余量：遇到降级/墓碑条目时不至于空转
_STAGING_SCAN_SLACK = 64

T = TypeVar("T")
# writer.execute(callback, background=True) 形态的调度器
WriteDispatch = Callable[[Callable[[sqlite3.Connection], T]], T]
ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


class ReplayIntegrityError(Exception):
    """录像解压/校验失败，调用方应回退到旧存储路径。"""


# ── schema ────────────────────────────────────────────────────

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS replay_index (
        replay_id  INTEGER PRIMARY KEY,
        seg_id     INTEGER,
        slot       INTEGER,
        length     INTEGER,
        sha256     BLOB,
        codec      INTEGER NOT NULL DEFAULT 1,
        deleted    INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_replay_index_seg "
    "ON replay_index (seg_id, slot)",
    "CREATE INDEX IF NOT EXISTS idx_replay_index_deleted "
    "ON replay_index (deleted)",
    "CREATE INDEX IF NOT EXISTS idx_replay_index_codec "
    "ON replay_index (codec, deleted)",
    """
    CREATE TABLE IF NOT EXISTS replay_segment (
        seg_id        INTEGER PRIMARY KEY,
        blob          BLOB NOT NULL,
        codec         INTEGER NOT NULL,
        record_count  INTEGER NOT NULL,
        raw_size      INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS replay_staging (
        replay_id  INTEGER PRIMARY KEY,
        raw_data   BLOB NOT NULL,
        codec      INTEGER NOT NULL DEFAULT 1
    )
    """,
)


def ensure_tables(conn: sqlite3.Connection) -> None:
    """创建三张新表（幂等），不动 history / replay_data 的任何列。

    调用方已有事务时不接管事务（不用 ``executescript``，也不 commit），
    避免在调用方事务里静默提交。
    """
    if conn.in_transaction:
        for statement in _SCHEMA_STATEMENTS:
            conn.execute(statement)
        return
    conn.executescript(";".join(_SCHEMA_STATEMENTS))
    conn.commit()


# ── 短事务辅助 ────────────────────────────────────────────────

def _in_short_write(conn: sqlite3.Connection,
                    fn: Callable[[], T]) -> T:
    """在短写事务中执行 ``fn``；调用方已有事务时用 SAVEPOINT 嵌套。

    绝不在调用方事务中 commit，保证既有调用方的提交边界不被破坏。
    """
    if conn.in_transaction:
        conn.execute("SAVEPOINT replay_store_short_write")
        try:
            result = fn()
        except BaseException:
            conn.execute("ROLLBACK TO SAVEPOINT replay_store_short_write")
            conn.execute("RELEASE SAVEPOINT replay_store_short_write")
            raise
        conn.execute("RELEASE SAVEPOINT replay_store_short_write")
        return result
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = fn()
        conn.commit()
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise
    return result


def _run_short(write: WriteDispatch | None, conn: sqlite3.Connection,
               fn: Callable[[sqlite3.Connection], T]) -> T:
    """把短写回调交给 writer 线程执行；无 ``write`` 时在本连接执行。"""
    if write is not None:
        return write(fn)
    return _in_short_write(conn, lambda: fn(conn))


def _data_version(conn: sqlite3.Connection) -> int | None:
    """连接本地的「其他连接提交」计数（仅同连接比较有意义）。"""
    try:
        row = conn.execute("PRAGMA data_version").fetchone()
    except sqlite3.Error:
        return None
    return int(row[0]) if row else None


def _owner_key(conn: sqlite3.Connection) -> int:
    """连接身份键（用于判断 prepared 能否在本连接比较 data_version）。

    ``sqlite3.Connection`` 不支持弱引用，这里用 ``id``：误判只会导致
    「跳过本次封口」（安全方向，下一轮重试），绝不会造成数据错误。
    """
    return id(conn)


# ── 写入 ──────────────────────────────────────────────────────

def write_record(conn: sqlite3.Connection, replay_id: int,
                 raw_data: bytes | None, *,
                 staged: bytes | None = None) -> None:
    """写入一条录像：只落 staging + replay_index，O(1)。

    **绝不在此同步封口**：封口（split / 编码 / lzma 压缩）是 CPU 密集
    操作，只能由后台维护线程 ``prepare_seal`` / ``apply_seal`` 完成。
    本函数不 commit，由调用方与 history 插入保持同一事务。

    Args:
        staged: 已按 ``zlib.compress(raw_data, 6)`` 压好的字节。调用方若已
            为旧 ``replay_data`` 表压过同一份数据，传进来可省掉一次压缩。
    """
    if raw_data is None:
        return
    cursor = conn.cursor()
    # 逐条 zlib 作为 staging 形态（与旧存储一致，便于回退读取）
    if staged is None:
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


# ── 封口：prepare / apply ─────────────────────────────────────

@dataclass(frozen=True)
class SealEntry:
    """准备阶段捕获的单条录像快照（用于短事务内逐字节复核）。"""

    replay_id: int
    staged_blob: bytes
    staged_codec: int
    length: int
    sha256: bytes


@dataclass(frozen=True)
class PreparedSeal:
    """一个已编码、自检通过、可直接落库的列式块。

    纯内存不可变对象，可安全跨线程从只读连接传给写线程；不持有连接或
    游标。``prepare_owner`` 是连接身份键，仅用于判断 ``data_version``
    能否在 apply 时比较（同一连接才可比）。
    """

    blob: bytes
    raw_size: int
    entries: tuple[SealEntry, ...]
    base_data_version: int | None = None
    prepare_owner: object = field(default=None, repr=False, compare=False)

    @property
    def record_count(self) -> int:
        return len(self.entries)

    def replay_ids(self) -> tuple[int, ...]:
        return tuple(entry.replay_id for entry in self.entries)


@dataclass(frozen=True)
class _Usable:
    """准备阶段的候选记录（含 staging 原始压缩字节，用于复核）。"""

    replay_id: int
    raw: bytes
    staged_blob: bytes
    staged_codec: int
    length: int
    sha256: bytes
    triple: tuple[bytes, bytes, bytes] | None = None


def _build_prepared(
    usable: Iterable[_Usable],
    *,
    limit: int | None = None,
    base_data_version: int | None = None,
    prepare_owner: object = None,
) -> PreparedSeal | None:
    """编码 + lzma 压缩 + roundtrip 自检（纯 CPU，不碰数据库）。"""
    triples: list[tuple[bytes, bytes, bytes]] = []
    entries: list[SealEntry] = []
    for item in usable:
        if limit is not None and len(entries) >= limit:
            break
        triple = item.triple
        if triple is None:
            try:
                triple = split_evf(item.raw)
            except (UnsupportedReplayError, ValueError) as exc:
                logger.warning("录像 %s 结构不支持列式，保留 staging: %s",
                               item.replay_id, exc)
                continue
        triples.append(triple)
        entries.append(SealEntry(
            replay_id=item.replay_id,
            staged_blob=item.staged_blob,
            staged_codec=item.staged_codec,
            length=item.length,
            sha256=item.sha256,
        ))
    if not entries:
        return None
    try:
        payload = encode_group(triples)
        blob = lzma.compress(payload, preset=_LZMA_PRESET)
        # 封口前自检：解回来必须 bit-exact，否则整批放弃
        decoded = decode_group(payload, len(triples))
    except (UnsupportedReplayError, ValueError, lzma.LZMAError) as exc:
        logger.warning("列式封口失败，保留 staging 待下次重试: %s", exc)
        return None
    if decoded != triples:
        logger.warning("列式块 roundtrip 不一致，放弃本批")
        return None
    return PreparedSeal(
        blob=blob,
        raw_size=sum(entry.length for entry in entries),
        entries=tuple(entries),
        base_data_version=base_data_version,
        prepare_owner=prepare_owner,
    )


def prepare_seal(conn: sqlite3.Connection, limit: int = BLOCK_SIZE,
                 force: bool = False) -> PreparedSeal | None:
    """在只读连接上准备一个列式块（CPU 全在这里，写线程只 apply）。

    Args:
        conn: 任意连接（建议维护线程的只读连接，autocommit、不持长事务）。
        limit: 本批最多封入的条数。
        force: ``False``（默认）只在凑满 ``limit`` 条时返回计划，保证块
            大小稳定；``True`` 允许封入不足一整块的尾批。

    Returns:
        :class:`PreparedSeal`；无可用记录、未凑满且 ``force=False``、
        或编码自检失败时返回 ``None``。

    本函数只读，不写库、不开事务。结构异常（非 v4 等）、墓碑、
    staging 与索引不一致的条目会被跳过并继续留在 staging，不影响其余
    记录。
    """
    if limit <= 0:
        return None
    base_version = _data_version(conn)
    scan_budget = max(limit * 2, limit + _STAGING_SCAN_SLACK)
    usable: list[_Usable] = []
    cursor = conn.cursor()
    try:
        rows = cursor.execute(
            "SELECT s.replay_id, s.raw_data, s.codec, "
            "i.seg_id, i.slot, i.length, i.sha256, i.codec, i.deleted "
            "FROM replay_staging AS s "
            "LEFT JOIN replay_index AS i ON i.replay_id = s.replay_id "
            "ORDER BY s.replay_id"
        )
        scanned = 0
        for (replay_id, staged, staged_codec, seg_id, slot,
             length, digest, index_codec, deleted) in rows:
            if scanned >= scan_budget or len(usable) >= scan_budget:
                break
            scanned += 1
            if seg_id is not None or slot is not None:
                # 已封口（staging 残留），跳过
                continue
            if index_codec is None:
                logger.warning("录像 %s 缺少索引条目，暂不封口", replay_id)
                continue
            if deleted:
                # 墓碑：数据保留在 staging，不封口
                continue
            if index_codec != CODEC_ZLIB:
                logger.warning("录像 %s 索引 codec=%s 无法封口",
                               replay_id, index_codec)
                continue
            try:
                if staged_codec not in (CODEC_ZLIB, CODEC_RAW):
                    raise ValueError(f"未知 staging codec={staged_codec}")
                raw = (zlib.decompress(staged) if staged_codec == CODEC_ZLIB
                       else staged)
            except (zlib.error, ValueError, TypeError) as exc:
                logger.warning("录像 %s staging 解压失败，保留: %s",
                               replay_id, exc)
                continue
            if len(raw) != length or hashlib.sha256(raw).digest() != digest:
                # 索引与 staging 不一致：不猜测，留给修复流程
                logger.warning("录像 %s staging/索引不一致，暂不封口", replay_id)
                continue
            try:
                # 结构异常（非 v4 等）的条目不能进块，跳过且不占名额
                triple = split_evf(raw)
            except (UnsupportedReplayError, ValueError) as exc:
                logger.warning("录像 %s 结构不支持列式，保留 staging: %s",
                               replay_id, exc)
                continue
            usable.append(_Usable(
                replay_id=replay_id,
                raw=raw,
                staged_blob=staged,
                staged_codec=staged_codec,
                length=len(raw),
                sha256=digest,
                triple=triple,
            ))
            if len(usable) >= limit:
                # 只需凑满一批，避免无谓解码后续记录
                break
    except sqlite3.OperationalError:
        return None
    finally:
        cursor.close()

    prepared = _build_prepared(
        usable, limit=limit, base_data_version=base_version,
        prepare_owner=_owner_key(conn),
    )
    if prepared is None:
        return None
    if not force and prepared.record_count < limit:
        return None
    return prepared


def _apply_seal_locked(conn: sqlite3.Connection,
                       prepared: PreparedSeal | None) -> int:
    """在**已开启的写事务**内落库；校验不过则整体放弃，返回 0。

    此处只做 SQL 与逐字节比较，不做解压/编码等 CPU 工作。
    """
    if prepared is None or not prepared.entries:
        return 0
    # 只有当 prepare 与 apply 用的是同一个连接时，data_version 才可比：
    # 期间若有其他连接提交（哪怕行数/内容看起来一致），早期放弃。
    owner = prepared.prepare_owner
    if owner is not None and prepared.base_data_version is not None:
        if owner == _owner_key(conn):
            current = _data_version(conn)
            if current is not None and current != prepared.base_data_version:
                logger.info("封口计划已过期（data_version 变化），延迟重试")
                return 0

    cursor = conn.cursor()
    # ① 复核 staging 与 index 的每一行都与准备阶段完全一致
    for entry in prepared.entries:
        srow = cursor.execute(
            "SELECT raw_data, codec FROM replay_staging WHERE replay_id = ?",
            (entry.replay_id,)).fetchone()
        if (srow is None or srow[0] != entry.staged_blob
                or srow[1] != entry.staged_codec):
            logger.info("staging 在准备后被改动，放弃本批: replay_id=%s",
                        entry.replay_id)
            return 0
        irow = cursor.execute(
            "SELECT seg_id, slot, length, sha256, codec, deleted "
            "FROM replay_index WHERE replay_id = ?",
            (entry.replay_id,)).fetchone()
        if (irow is None or irow[0] is not None or irow[1] is not None
                or irow[2] != entry.length or irow[3] != entry.sha256
                or irow[4] != CODEC_ZLIB or irow[5] != 0):
            # 并发删除（墓碑）、重复封口、索引改写等一律放弃，绝不覆盖
            logger.info("index 在准备后被改动，放弃本批: replay_id=%s",
                        entry.replay_id)
            return 0

    # ② 现已持写锁，开始落地
    (seg_id,) = cursor.execute(
        "SELECT COALESCE(MAX(seg_id), -1) + 1 FROM replay_segment").fetchone()
    cursor.execute(
        "INSERT INTO replay_segment "
        "(seg_id, blob, codec, record_count, raw_size) VALUES (?, ?, ?, ?, ?)",
        (seg_id, prepared.blob, CODEC_LZMA_COLUMNAR,
         prepared.record_count, prepared.raw_size),
    )
    for slot, entry in enumerate(prepared.entries):
        cursor.execute(
            "UPDATE replay_index SET seg_id = ?, slot = ?, length = ?, "
            "sha256 = ?, codec = ? WHERE replay_id = ?",
            (seg_id, slot, entry.length, entry.sha256,
             CODEC_LZMA_COLUMNAR, entry.replay_id),
        )
    # 只删成功封口的条目；降级条目留在 staging 供后续单独处理
    cursor.executemany(
        "DELETE FROM replay_staging WHERE replay_id = ?",
        [(entry.replay_id,) for entry in prepared.entries],
    )
    return prepared.record_count


def apply_seal(conn: sqlite3.Connection, prepared: PreparedSeal | None) -> int:
    """在写连接上应用一个预热好的列式块（短事务）。

    Args:
        conn: 写连接（通常由 ``DatabaseWriter`` 提供）。
        prepared: :func:`prepare_seal` 的返回值。

    Returns:
        成功封入块的条数；计划过期、数据在准备后被改动、或数据库繁忙时
        返回 0（安全放弃，留待下一轮重试）。
    """
    if prepared is None or not prepared.entries:
        return 0
    try:
        return _in_short_write(
            conn, lambda: _apply_seal_locked(conn, prepared))
    except sqlite3.OperationalError as exc:
        logger.info("封口延迟（数据库繁忙）: %s", exc)
        return 0


def seal_staging(conn: sqlite3.Connection, limit: int = BLOCK_SIZE) -> int:
    """:func:`prepare_seal` + :func:`apply_seal` 的同步兼容包装。

    新架构下由后台维护线程调用 ``prepare_seal`` / ``apply_seal``；本函数
    仅为旧调用方与测试保留，允许封入不足一整块的尾批。

    Returns:
        成功封入块的条数。
    """
    prepared = prepare_seal(conn, limit=limit, force=True)
    if prepared is None:
        return 0
    return apply_seal(conn, prepared)


# ── 读取 ──────────────────────────────────────────────────────

def _cache_put(segment_cache: dict[int, list], seg_id: int,
               triples: list) -> None:
    """写入有界缓存（OrderedDict 时按 LRU 淘汰，否则按插入顺序）。"""
    segment_cache[seg_id] = triples
    if isinstance(segment_cache, OrderedDict):
        segment_cache.move_to_end(seg_id)
        while len(segment_cache) > _SEGMENT_CACHE_LIMIT:
            segment_cache.popitem(last=False)
    else:
        while len(segment_cache) > _SEGMENT_CACHE_LIMIT:
            segment_cache.pop(next(iter(segment_cache)))


def _decode_segment(
    conn: sqlite3.Connection,
    seg_id: int,
    segment_cache: dict[int, list] | None = None,
) -> list:
    """解码一个列式块，可选跨调用缓存（条数上限有界）。

    ``decode_group`` 的耗时与块内条数成正比，而随机读一条记录也要解码
    整块。连续读取同一块的多条记录时（迁移校验、翻页），缓存能把
    O(条数×块大小) 降为 O(块大小)。
    """
    if segment_cache is not None:
        cached = segment_cache.get(seg_id)
        if cached is not None:
            if isinstance(segment_cache, OrderedDict):
                segment_cache.move_to_end(seg_id)
            return cached
    row = conn.execute(
        "SELECT blob, record_count FROM replay_segment WHERE seg_id = ?",
        (seg_id,),
    ).fetchone()
    if row is None:
        raise ReplayIntegrityError(f"录像块缺失: seg_id={seg_id}")
    try:
        triples = decode_group(lzma.decompress(row[0]), row[1])
    except (lzma.LZMAError, UnsupportedReplayError, ValueError,
            TypeError) as exc:
        raise ReplayIntegrityError(f"块解压失败: {exc}") from exc
    if segment_cache is not None:
        _cache_put(segment_cache, seg_id, triples)
    return triples


def _raw_from_index(
    conn: sqlite3.Connection,
    replay_id: int,
    entry: tuple,
    segment_cache: dict[int, list] | None = None,
) -> bytes:
    """按 ``replay_index`` 条目还原并校验一条录像的原始字节。

    Args:
        entry: ``(seg_id, slot, length, sha256, codec)``。

    Raises:
        ReplayIntegrityError: 数据缺失、损坏或 sha256 不符。
    """
    seg_id, slot, length, digest, codec = entry
    if codec == CODEC_ZLIB:
        # 尚未封口：从 staging 读
        s = conn.execute(
            "SELECT raw_data, codec FROM replay_staging WHERE replay_id = ?",
            (replay_id,),
        ).fetchone()
        if s is None:
            raise ReplayIntegrityError(f"staging 缺失: replay_id={replay_id}")
        try:
            if s[1] not in (CODEC_ZLIB, CODEC_RAW):
                raise ValueError(f"未知 staging codec={s[1]}")
            raw = zlib.decompress(s[0]) if s[1] == CODEC_ZLIB else s[0]
        except (zlib.error, ValueError, TypeError) as exc:
            raise ReplayIntegrityError(f"staging 解压失败: {exc}") from exc
    elif codec == CODEC_LZMA_COLUMNAR:
        triples = _decode_segment(conn, seg_id, segment_cache)
        try:
            if not isinstance(slot, int) or slot < 0:
                raise ValueError(f"无效的块内位置: {slot}")
            head, events, tail = triples[slot]
            raw = head + events + tail
        except (IndexError, TypeError, ValueError) as exc:
            raise ReplayIntegrityError(f"块解压失败: {exc}") from exc
    else:
        raise ReplayIntegrityError(f"未知 codec={codec}")

    try:
        valid = len(raw) == length and hashlib.sha256(raw).digest() == digest
    except (TypeError, ValueError) as exc:
        raise ReplayIntegrityError(f"录像数据无效: replay_id={replay_id}") from exc
    if not valid:
        raise ReplayIntegrityError(f"bit-exact 校验失败: replay_id={replay_id}")
    return raw


def _read_from_segment(
    conn: sqlite3.Connection,
    replay_id: int,
    segment_cache: dict[int, list] | None = None,
) -> bytes | None:
    row = conn.execute(
        "SELECT seg_id, slot, length, sha256, codec, deleted "
        "FROM replay_index WHERE replay_id = ?", (replay_id,),
    ).fetchone()
    if row is None or row[5]:
        return None
    return _raw_from_index(conn, replay_id, row[:5], segment_cache)


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
        index_row = cursor.execute(
            "SELECT deleted FROM replay_index WHERE replay_id = ?", (replay_id,)
        ).fetchone()
        if index_row:
            if index_row[0]:
                return None  # tombstone 必须阻止旧副本复活
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


# ── 维护调度辅助 ──────────────────────────────────────────────

def _ensure_tables_via(write: WriteDispatch | None,
                       conn: sqlite3.Connection) -> None:
    """建表：有 writer 时交给写线程，避免维护连接与写线程争锁。"""
    if write is None:
        ensure_tables(conn)
    else:
        write(ensure_tables)


# ── 迁移：replay_data → staging / segment ────────────────────

def _prepare_staging_batch(
    rows: Sequence[tuple],
) -> tuple[list[_Usable], dict[int, tuple[bytes, bool]]]:
    """把旧表行解压成候选记录（CPU 在准备阶段完成）。"""
    usable: list[_Usable] = []
    snapshots: dict[int, tuple[bytes, bool]] = {}
    for replay_id, data, compressed in rows:
        try:
            raw = zlib.decompress(data) if compressed else data
        except (zlib.error, TypeError) as exc:
            logger.warning("旧录像 %s 解压失败，跳过迁移: %s", replay_id, exc)
            continue
        if not isinstance(raw, (bytes, bytearray)):
            logger.warning("旧录像 %s 数据无效，跳过迁移", replay_id)
            continue
        raw = bytes(raw)
        snapshots[replay_id] = (data, bool(compressed))
        usable.append(_Usable(
            replay_id=replay_id,
            raw=raw,
            staged_blob=zlib.compress(raw, level=6),
            staged_codec=CODEC_ZLIB,
            length=len(raw),
            sha256=hashlib.sha256(raw).digest(),
        ))
    return usable, snapshots


def _apply_staging_batch(
    conn: sqlite3.Connection,
    usable: Sequence[_Usable],
    snapshots: dict[int, tuple[bytes, bool]],
    prepared: PreparedSeal | None,
) -> tuple[int, bool]:
    """写线程短事务：复核旧行未变后插 staging/index，再应用预热块。

    回调内只有 SQL 与逐字节比较，不做任何压缩/编码。

    Returns:
        (插入条数, 是否成功应用预热块)
    """
    inserted = 0
    conflict = False
    for item in usable:
        snapshot = snapshots.get(item.replay_id)
        row = conn.execute(
            "SELECT raw_data, compressed FROM replay_data WHERE replay_id = ?",
            (item.replay_id,)).fetchone()
        if row is None:
            # 老行已被删除：绝不复活
            conflict = True
            continue
        if (snapshot is None or row[0] != snapshot[0]
                or bool(row[1]) != snapshot[1]):
            # 老行在准备后被改写：跳过，下一轮再迁
            conflict = True
            continue
        exists = conn.execute(
            "SELECT 1 FROM replay_index WHERE replay_id = ?",
            (item.replay_id,)).fetchone()
        if exists:
            conflict = True
            continue
        conn.execute(
            "INSERT OR IGNORE INTO replay_staging "
            "(replay_id, raw_data, codec) VALUES (?, ?, ?)",
            (item.replay_id, item.staged_blob, item.staged_codec))
        conn.execute(
            "INSERT OR IGNORE INTO replay_index "
            "(replay_id, seg_id, slot, length, sha256, codec, deleted) "
            "VALUES (?, NULL, NULL, ?, ?, ?, 0)",
            (item.replay_id, item.length, item.sha256, CODEC_ZLIB))
        inserted += 1
    sealed = False
    if prepared is not None and not conflict and inserted == len(usable):
        sealed = _apply_seal_locked(conn, prepared) > 0
    return inserted, sealed


def _apply_prepared(write: WriteDispatch | None, conn: sqlite3.Connection,
                    prepared: PreparedSeal) -> int:
    """把预热块应用回写路径（可跨 writer 线程）。"""
    if write is None:
        return apply_seal(conn, prepared)
    try:
        return write(lambda w: _apply_seal_locked(w, prepared))
    except sqlite3.OperationalError as exc:
        logger.info("封口延迟（数据库繁忙）: %s", exc)
        return 0


def migrate_from_replay_data(
    conn: sqlite3.Connection,
    batch_size: int = BLOCK_SIZE,
    *,
    write: WriteDispatch | None = None,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> tuple[int, int]:
    """把旧 ``replay_data`` 表的数据灌入 staging 并封口（幂等）。

    不删除旧的 ``replay_data`` 行 —— 保留作回退，由
    :func:`finalize_migration` 分小批、逐行复核后清理。

    读/解压/编码全部在 ``conn``（维护线程的只读连接）上完成；
    ``write`` 提供时，只有毫秒级的插入/封口在写线程事务内执行。

    Args:
        batch_size: 每批处理的旧记录数。
        write: ``writer.execute(callback, background=True)`` 形式的调度器；
            ``None`` 时直接在本连接上执行短事务。
        progress: ``(done, total)``，每批结束后回调；``total`` 为开始时
            旧表总行数，``done`` 为已迁移行数。旧表为空时**不会**回调。
        cancelled: 返回 True 时在批间安全停止。

    Returns:
        ``(已迁移条数, 成功封口的块数)``。
    """
    if batch_size <= 0:
        batch_size = BLOCK_SIZE
    _ensure_tables_via(write, conn)
    cursor = conn.cursor()
    try:
        total = cursor.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0]
    except sqlite3.OperationalError:
        return (0, 0)

    migrated = 0
    sealed = 0
    last_id = -1
    while True:
        if cancelled is not None and cancelled():
            break
        try:
            rows = cursor.execute(
                "SELECT d.replay_id, d.raw_data, d.compressed "
                "FROM replay_data AS d "
                "WHERE d.replay_id > ? AND NOT EXISTS ("
                "  SELECT 1 FROM replay_index AS i "
                "  WHERE i.replay_id = d.replay_id) "
                "ORDER BY d.replay_id LIMIT ?",
                (last_id, batch_size),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("读取旧录像表失败，停止迁移: %s", exc)
            break
        if not rows:
            break
        last_id = rows[-1][0]

        # 准备：解压 + 重压 + （可能）编码压缩整块（纯 CPU，写线程不参与）
        usable, snapshots = _prepare_staging_batch(rows)
        prepared = (
            _build_prepared(usable, limit=BLOCK_SIZE,
                            prepare_owner=_owner_key(conn))
            if len(usable) >= BLOCK_SIZE else None)
        try:
            inserted, did_seal = _run_short(
                write, conn,
                lambda w, u=tuple(usable), s=dict(snapshots), p=prepared:
                _apply_staging_batch(w, u, s, p))
        except sqlite3.OperationalError as exc:
            logger.warning("迁移批次写入失败，稍后重试: %s", exc)
            break
        migrated += inserted
        sealed += 1 if did_seal else 0
        if progress is not None and total > 0:
            progress(migrated, total)

    # 收尾：把剩余 staging（含不足一整块的尾批）强制封口
    if cancelled is None or not cancelled():
        while True:
            prepared = prepare_seal(conn, limit=batch_size, force=True)
            if prepared is None:
                break
            if _apply_prepared(write, conn, prepared) <= 0:
                break
            sealed += 1
    return migrated, sealed


# ── 迁移收尾：分小批逐行复核后清理旧表（不自动 VACUUM）──────

def finalize_migration(
    conn: sqlite3.Connection,
    expected: int | None = None,
    *,
    batch_size: int = BLOCK_SIZE,
    write: WriteDispatch | None = None,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
) -> bool:
    """分小批校验并清理旧 ``replay_data`` 表（**不** VACUUM）。

    正确性不依赖行数：每批先只读地捕获「旧行原始字节 + 索引快照 +
    新存储还原结果」，再在短写事务里逐行精确复核（旧行逐字节未变、
    index 快照未变、剩余行数未变）后才删除**已校验的 id**。

    - 并发插入/删除旧行 → 剩余行数复核失败 → 立即放弃（本批不删任何行）。
    - 并发改写旧行内容（行数不变）→ 精确字节复核失败 → 该批保留。
    - 并发删除/墓碑 index → 索引快照不符 → 该批保留。
    - 每批校验通过即提交，中断后可直接重跑；已清理的 id 不会重复处理。

    Args:
        conn: 维护线程的只读连接（不持长事务）。
        expected: 期望的旧表行数；不符则直接返回 False。
        batch_size: 每批处理行数（限制单次写锁持续时间）。
        write: ``writer.execute(callback, background=True)`` 调度器。
        progress: ``(done, total)``，``done`` 为已删除的旧行数。
            旧表为空时**不会**回调。
        cancelled: 返回 True 时在批间停止并返回 False（未完成）。

    Returns:
        旧表是否已全部安全清空。
    """
    # 不接管调用方的事务，也不在调用方事务里做清理。
    if conn.in_transaction:
        logger.warning("迁移收尾需要独立事务，保留旧表")
        return False

    try:
        total = conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0]
    except sqlite3.OperationalError:
        # 没有旧表 = 没有任何需要清理的数据，视为已完成
        return True
    if total == 0:
        return True
    if expected is not None and total != expected:
        logger.warning("迁移条数不符 (%d != %d)，保留旧表", total, expected)
        return False
    if batch_size <= 0:
        batch_size = BLOCK_SIZE

    cache: OrderedDict[int, list] = OrderedDict()
    last_id = -1
    removed = 0
    expected_remaining = total

    while True:
        if cancelled is not None and cancelled():
            return False
        rows = conn.execute(
            "SELECT replay_id, raw_data, compressed FROM replay_data "
            "WHERE replay_id > ? ORDER BY replay_id LIMIT ?",
            (last_id, batch_size),
        ).fetchall()
        if not rows:
            break
        last_id = rows[-1][0]

        # ── 阶段 1：只读校验（不持写锁）──────────────────────
        validated: list[tuple[int, bytes, bool, tuple]] = []
        for replay_id, data, compressed in rows:
            try:
                original = zlib.decompress(data) if compressed else data
            except (zlib.error, TypeError):
                logger.warning("旧录像解压失败 rid=%s，保留旧表", replay_id)
                return False
            try:
                restored = _read_from_segment(conn, replay_id, cache)
            except ReplayIntegrityError:
                restored = None
            if restored is None or restored != original:
                logger.warning("迁移校验失败 rid=%s，保留旧表", replay_id)
                return False
            index_row = conn.execute(
                "SELECT seg_id, slot, length, sha256, codec, deleted "
                "FROM replay_index WHERE replay_id = ?", (replay_id,)).fetchone()
            if index_row is None:
                logger.warning("迁移校验缺少索引 rid=%s，保留旧表", replay_id)
                return False
            validated.append(
                (replay_id, data, bool(compressed), tuple(index_row)))

        # ── 阶段 2：短写事务内精确复核后只删已校验的 id ──────
        def _apply(w: sqlite3.Connection,
                   batch: tuple = tuple(validated),
                   expect: int = expected_remaining) -> int | None:
            remaining = w.execute(
                "SELECT COUNT(*) FROM replay_data").fetchone()[0]
            if remaining != expect:
                # 并发插入/删除：整体放弃本批，不删任何行
                logger.info("旧表行数变化 (%d != %d)，放弃本批",
                            remaining, expect)
                return None
            # 先完整校验本批全部行，任何一行不符就整体放弃（绝不半删）
            for replay_id, data, compressed, index_snapshot in batch:
                row = w.execute(
                    "SELECT raw_data, compressed FROM replay_data "
                    "WHERE replay_id = ?", (replay_id,)).fetchone()
                if (row is None or row[0] != data
                        or bool(row[1]) != compressed):
                    logger.info("旧行在复核前被改写 rid=%s，保留", replay_id)
                    return None
                current_index = w.execute(
                    "SELECT seg_id, slot, length, sha256, codec, deleted "
                    "FROM replay_index WHERE replay_id = ?",
                    (replay_id,)).fetchone()
                if (tuple(current_index) if current_index else None) \
                        != index_snapshot:
                    logger.info("索引在复核前被改写 rid=%s，保留", replay_id)
                    return None
            # 全部校验通过，只删这些已校验的 id
            w.executemany(
                "DELETE FROM replay_data WHERE replay_id = ?",
                [(replay_id,) for replay_id, *_ in batch])
            return len(batch)

        try:
            applied = _run_short(write, conn, _apply)
        except sqlite3.OperationalError as exc:
            logger.warning("清空旧录像表时数据库繁忙，保留旧表: %s", exc)
            return False
        if applied is None:
            return False
        expected_remaining -= applied
        removed += applied
        if progress is not None and total > 0:
            progress(removed, total)

    # 最终复核（只读）
    try:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM replay_data").fetchone()[0]
    except sqlite3.OperationalError:
        return False
    return remaining == 0


def vacuum(conn: sqlite3.Connection) -> None:
    """回收磁盘空间（由维护流程在**确认稳定后**手动调用，非自动）。"""
    conn.execute("VACUUM")
