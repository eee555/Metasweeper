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
                             progress=None, cancelled=None,
                             prepare=None, stats=None) -> (migrated, sealed)
    finalize_migration(conn, expected=None, *, batch_size=BLOCK_SIZE,
                       write=None, progress=None, cancelled=None) -> bool
    migrate_board_to_ascii(conn, batch_size, *, write=None,
                          progress=None, cancelled=None) -> int  # board_codec
    fill_incomplete_segments(conn, *, write=None, batch_size=BLOCK_SIZE,
                             after_id=0) -> int
    compact_tombstone_segments(conn, *, write=None, cancelled=None) -> int
    cleanup_low_value_replays(conn, min_solved_percent, *, write=None,
                              progress=None, cancelled=None,
                              prepare=None, stats=None) -> int

``prepare`` 是 :class:`parallel_prepare.PreparePool`：迁移按批次、清理按
``seg_id`` 在池里并行完成解压/编码/压缩，协调线程仍按顺序把短事务交给
写线程。``stats`` 收集冲突、失败与剩余数量，便于判断是否真正完成。
"""

from __future__ import annotations

import hashlib
import logging
import lzma
import sqlite3
import zlib
from collections import OrderedDict, deque
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence, TypeVar

from .parallel_prepare import PreparePool
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
    "count_sealable_staging",
    "batch_sealable_staging_max_id",
    "has_incomplete_segments",
    "fill_incomplete_segments",
    "tombstone_segment_ids",
    "compact_tombstone_segments",
    "read_raw_data",
    "mark_deleted",
    "cleanup_low_value_replays",
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
    "CREATE INDEX IF NOT EXISTS idx_replay_index_seg_deleted "
    "ON replay_index (seg_id, deleted)",
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


def _completed_future(value: T) -> Future[T]:
    """把同步准备结果包装成已完成 Future，供流水线统一按序消费。"""
    future: Future[T] = Future()
    future.set_result(value)
    return future


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


def count_sealable_staging(conn: sqlite3.Connection, *,
                           after_id: int = 0) -> int:
    """统计可进入列式块的 staging 条数（不解压、不写库）。

    ``after_id`` 仅统计 replay_id 更大的候选，供批量补齐的“新一批”
    水位判断使用；默认统计全部。
    """
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM replay_staging s "
            "JOIN replay_index i ON i.replay_id = s.replay_id "
            "WHERE s.replay_id > ? AND i.seg_id IS NULL AND i.slot IS NULL "
            "AND i.deleted = 0 AND i.codec = ?",
            (after_id, CODEC_ZLIB)).fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def batch_sealable_staging_max_id(conn: sqlite3.Connection,
                                  batch_size: int = BLOCK_SIZE, *,
                                  after_id: int = 0) -> int:
    """``after_id`` 之后的一批最多 ``batch_size`` 条 staging 的最大 id。"""
    try:
        row = conn.execute(
            "SELECT MAX(replay_id) FROM ("
            "SELECT s.replay_id FROM replay_staging s "
            "JOIN replay_index i ON i.replay_id = s.replay_id "
            "WHERE s.replay_id > ? AND i.seg_id IS NULL AND i.slot IS NULL "
            "AND i.deleted = 0 AND i.codec = ? "
            "ORDER BY s.replay_id LIMIT ?)",
            (after_id, CODEC_ZLIB, batch_size)).fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0]) if row and row[0] is not None else 0


def has_incomplete_segments(conn: sqlite3.Connection,
                            batch_size: int = BLOCK_SIZE) -> bool:
    """是否存在可继续补齐的未满列式块。"""
    try:
        return conn.execute(
            "SELECT 1 FROM replay_segment WHERE codec = ? "
            "AND record_count < ? LIMIT 1",
            (CODEC_LZMA_COLUMNAR, batch_size)).fetchone() is not None
    except sqlite3.OperationalError:
        return False


def fill_incomplete_segments(
    conn: sqlite3.Connection,
    *,
    write: WriteDispatch | None = None,
    batch_size: int = BLOCK_SIZE,
    after_id: int = 0,
) -> int:
    """用 ``after_id`` 之后的一批 staging 录像补齐未满列式块。

    只处理当前快照里 ``record_count < batch_size`` 且 codec 为列式 LZMA
    的分块；补齐后剩余 staging 留在原地，不强制新建小块。返回成功并入
    旧块的条数。
    """
    if batch_size <= 0:
        batch_size = BLOCK_SIZE
    if conn.in_transaction:
        return 0
    cursor = conn.cursor()
    try:
        staging = cursor.execute(
            "SELECT s.replay_id, s.raw_data, s.codec, i.length, i.sha256, "
            "i.codec, i.deleted FROM replay_staging s "
            "JOIN replay_index i ON i.replay_id = s.replay_id "
            "WHERE s.replay_id > ? AND i.seg_id IS NULL AND i.slot IS NULL "
            "AND i.deleted = 0 AND i.codec = ? "
            "ORDER BY s.replay_id LIMIT ?",
            (after_id, CODEC_ZLIB, batch_size)).fetchall()
        segments = cursor.execute(
            "SELECT seg_id, blob, record_count FROM replay_segment "
            "WHERE codec = ? AND record_count < ? ORDER BY seg_id",
            (CODEC_LZMA_COLUMNAR, batch_size)).fetchall()
    except sqlite3.OperationalError:
        return 0
    if not staging or not segments:
        return 0

    candidates: list[tuple[SealEntry, object]] = []
    for replay_id, staged_blob, staged_codec, length, digest, index_codec, deleted in staging:
        try:
            if index_codec != CODEC_ZLIB or deleted or staged_codec not in (CODEC_ZLIB, CODEC_RAW):
                continue
            raw = (zlib.decompress(staged_blob) if staged_codec == CODEC_ZLIB
                   else staged_blob)
            if len(raw) != length or hashlib.sha256(raw).digest() != digest:
                continue
            triple = split_evf(raw)
        except (zlib.error, ValueError, TypeError, UnsupportedReplayError):
            continue
        candidates.append((SealEntry(
            replay_id=replay_id, staged_blob=staged_blob,
            staged_codec=staged_codec, length=length, sha256=digest), triple))
    if not candidates:
        return 0

    queued = list(candidates)
    filled = 0
    for seg_id, blob, record_count in segments:
        if not queued:
            break
        try:
            old_triples = decode_group(lzma.decompress(blob), record_count)
        except (lzma.LZMAError, UnsupportedReplayError, ValueError, TypeError):
            continue
        capacity = batch_size - len(old_triples)
        if capacity <= 0:
            continue
        take = queued[:capacity]
        all_triples = old_triples + [triple for _, triple in take]
        try:
            packed = lzma.compress(encode_group(all_triples), preset=_LZMA_PRESET)
            decoded = decode_group(lzma.decompress(packed), len(all_triples))
        except (lzma.LZMAError, UnsupportedReplayError, ValueError, TypeError):
            continue
        if decoded != all_triples:
            continue
        old_indexes = tuple(tuple(row) for row in cursor.execute(
            "SELECT replay_id, slot, length, sha256, codec, deleted "
            "FROM replay_index WHERE seg_id = ? ORDER BY slot", (seg_id,)).fetchall())
        old_slots = [(row[0], row[1]) for row in old_indexes]

        def apply(target, sid=seg_id, old_blob=blob, snapshots=old_indexes,
                  slots=tuple(old_slots), entries=tuple(entry for entry, _ in take),
                  packed_blob=packed, triples=tuple(all_triples)):
            current_blob = target.execute(
                "SELECT blob FROM replay_segment WHERE seg_id = ?", (sid,)).fetchone()
            if current_blob is None or current_blob[0] != old_blob:
                return False
            current_indexes = tuple(tuple(row) for row in target.execute(
                "SELECT replay_id, slot, length, sha256, codec, deleted "
                "FROM replay_index WHERE seg_id = ? ORDER BY slot", (sid,)))
            if current_indexes != snapshots:
                return False
            for entry in entries:
                srow = target.execute(
                    "SELECT raw_data, codec FROM replay_staging WHERE replay_id = ?",
                    (entry.replay_id,)).fetchone()
                irow = target.execute(
                    "SELECT seg_id, slot, length, sha256, codec, deleted "
                    "FROM replay_index WHERE replay_id = ?",
                    (entry.replay_id,)).fetchone()
                if (srow != (entry.staged_blob, entry.staged_codec)
                        or irow != (None, None, entry.length, entry.sha256,
                                    CODEC_ZLIB, 0)):
                    return False
            target.execute(
                "UPDATE replay_segment SET blob = ?, record_count = ?, "
                "raw_size = ? WHERE seg_id = ?",
                (packed_blob, len(triples), sum(
                    len(h + e + t) for h, e, t in triples), sid))
            for slot, entry in enumerate(entries, len(slots)):
                target.execute(
                    "UPDATE replay_index SET seg_id = ?, slot = ?, codec = ? "
                    "WHERE replay_id = ?",
                    (sid, slot, CODEC_LZMA_COLUMNAR, entry.replay_id))
                target.execute(
                    "DELETE FROM replay_staging WHERE replay_id = ?",
                    (entry.replay_id,))
            return True

        if _run_short(write, conn, apply):
            queued = queued[len(take):]
            filled += len(take)
    return filled


def tombstone_segment_ids(conn: sqlite3.Connection) -> list[int]:
    """返回仍指向分块、但已被 tombstone 的槽位所在 seg_id。"""
    try:
        rows = conn.execute(
            "SELECT DISTINCT seg_id FROM replay_index "
            "WHERE deleted = 1 AND seg_id IS NOT NULL "
            "ORDER BY seg_id").fetchall()
    except sqlite3.OperationalError:
        return []
    return [int(row[0]) for row in rows if row[0] is not None]


def compact_tombstone_segments(
    conn: sqlite3.Connection,
    *,
    write: WriteDispatch | None = None,
    cancelled: CancelCallback | None = None,
) -> int:
    """重建含 tombstone 的分块，移除死槽位并保留活跃录像。"""
    if conn.in_transaction:
        return 0
    compacted = 0
    for seg_id in tombstone_segment_ids(conn):
        if cancelled is not None and cancelled():
            break
        try:
            segment = conn.execute(
                "SELECT blob, codec, record_count FROM replay_segment "
                "WHERE seg_id = ?", (seg_id,)).fetchone()
            if segment is None or segment[1] != CODEC_LZMA_COLUMNAR:
                continue
            blob, codec, count = segment
            triples = decode_group(lzma.decompress(blob), count)
            indexes = conn.execute(
                "SELECT replay_id, slot, length, sha256, codec, deleted "
                "FROM replay_index WHERE seg_id = ? ORDER BY slot",
                (seg_id,)).fetchall()
            snapshots = tuple(tuple(row) for row in indexes)
            removed_rows = tuple(row for row in indexes if row[5])
            kept_rows = tuple(
                row for row in indexes
                if not row[5] and row[1] is not None
                and row[1] >= 0 and row[1] < len(triples))
            if (not removed_rows or len(indexes) != count
                    or any(row[1] != slot for slot, row in enumerate(indexes))
                    or any(row[4] != CODEC_LZMA_COLUMNAR for row in kept_rows)):
                continue
            kept_triples = [triples[row[1]] for row in kept_rows]
            packed = (lzma.compress(encode_group(kept_triples),
                                    preset=_LZMA_PRESET)
                      if kept_triples else None)
            if packed is not None:
                decoded = decode_group(lzma.decompress(packed),
                                       len(kept_triples))
                if decoded != kept_triples:
                    continue
            raw_size = sum(int(row[2] or 0) for row in kept_rows)

            def apply(target, sid=seg_id, old_segment=(blob, codec, count),
                      old_indexes=snapshots, removed=removed_rows,
                      kept=kept_rows, packed_blob=packed, size=raw_size):
                if not target.in_transaction:
                    target.execute("BEGIN IMMEDIATE")
                current_segment = target.execute(
                    "SELECT blob, codec, record_count FROM replay_segment "
                    "WHERE seg_id = ?", (sid,)).fetchone()
                if (current_segment is None
                        or tuple(current_segment) != old_segment):
                    return False
                current_indexes = tuple(tuple(row) for row in target.execute(
                    "SELECT replay_id, slot, length, sha256, codec, deleted "
                    "FROM replay_index WHERE seg_id = ? ORDER BY slot", (sid,)))
                if current_indexes != old_indexes:
                    return False
                for rid, old_slot, *_ in removed:
                    cur = target.execute(
                        "UPDATE replay_index SET seg_id = NULL, slot = NULL "
                        "WHERE replay_id = ? AND deleted = 1 "
                        "AND seg_id = ? AND slot = ?",
                        (rid, sid, old_slot))
                    if cur.rowcount != 1:
                        raise ReplayIntegrityError("墓碑槽位复核失败")
                if packed_blob is None:
                    target.execute(
                        "DELETE FROM replay_segment WHERE seg_id = ?", (sid,))
                else:
                    for slot, row in enumerate(kept):
                        rid, old_slot = row[0], row[1]
                        cur = target.execute(
                            "UPDATE replay_index SET slot = ? "
                            "WHERE replay_id = ? AND deleted = 0 "
                            "AND seg_id = ? AND slot = ?",
                            (slot, rid, sid, old_slot))
                        if cur.rowcount != 1:
                            raise ReplayIntegrityError("活跃槽位复核失败")
                    target.execute(
                        "UPDATE replay_segment SET blob = ?, "
                        "record_count = ?, raw_size = ? WHERE seg_id = ?",
                        (packed_blob, len(kept), size, sid))
                return True

            try:
                applied = _run_short(write, conn, apply)
            except (sqlite3.OperationalError, ReplayIntegrityError) as exc:
                logger.info("分块回收暂缓: %s", exc)
                continue
            compacted += int(applied)
        except (lzma.LZMAError, UnsupportedReplayError, ValueError,
                TypeError, IndexError) as exc:
            logger.warning("分块 %s 损坏，暂不回收: %s", seg_id, exc)
            continue
    return compacted


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
    """标记录像已删除；块内数据由后台整理回收，暂存数据由调用方删除。"""
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


@dataclass(frozen=True)
class _MigrationBatch:
    """一批旧表的 CPU 准备结果（可在准备线程里生成）。"""

    usable: tuple[_Usable, ...]
    snapshots: dict[int, tuple[bytes, bool]]
    prepared: PreparedSeal | None


def _prepare_migration_batch(rows: Sequence[tuple],
                             block_size: int,
                             prepare_owner: object) -> _MigrationBatch:
    """纯 CPU：解压旧行、重压 staging、编码预热块（不碰数据库）。"""
    usable, snapshots = _prepare_staging_batch(rows)
    prepared = (
        _build_prepared(usable, limit=block_size,
                        prepare_owner=prepare_owner)
        if len(usable) >= block_size else None)
    return _MigrationBatch(usable=tuple(usable), snapshots=snapshots,
                           prepared=prepared)


def migrate_from_replay_data(
    conn: sqlite3.Connection,
    batch_size: int = BLOCK_SIZE,
    *,
    write: WriteDispatch | None = None,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
    prepare: PreparePool | None = None,
    stats: dict[str, int] | None = None,
) -> tuple[int, int]:
    """把旧 ``replay_data`` 表的数据灌入 staging 并封口（幂等）。

    不删除旧的 ``replay_data`` 行 —— 保留作回退，由
    :func:`finalize_migration` 分小批、逐行复核后清理。

    读/解压/编码全部在 ``conn``（维护线程的只读连接）上完成；``write``
    提供时，只有毫秒级的插入/封口在写线程事务内执行。``prepare`` 提供时，
    批次的解压/编码/压缩在有界线程池中并行完成，提交仍按顺序进行。

    Args:
        batch_size: 每批处理的旧记录数。
        write: ``writer.execute(callback, background=True)`` 形式的调度器；
            ``None`` 时直接在本连接上执行短事务。
        progress: ``(done, total)``，每批结束后回调；``total`` 为开始时
            旧表总行数，``done`` 为已迁移行数。旧表为空时**不会**回调。
        cancelled: 返回 True 时在批间安全停止。
        prepare: 有界并行准备池；``None`` 时串行准备。
        stats: 可选统计字典，累加 ``migrated`` / ``sealed`` /
            ``conflicts`` / ``failed_batches`` / ``abandoned_records``。
            冲突记录会在流水线排空后重扫一次，仍失败才计入
            ``abandoned_records`` 并留给下次启动。

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
    owner = _owner_key(conn)
    depth = prepare.max_in_flight if prepare is not None else 1
    pending: deque[Future[_MigrationBatch]] = deque()
    # 因并发改动被跳过的 id：流水线排空后统一重扫一次
    skipped: set[int] = set()

    def _submit_next() -> bool:
        """读一批旧行并提交准备任务；无可读行时返回 False。"""
        nonlocal last_id
        if cancelled is not None and cancelled():
            return False
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
            return False
        if not rows:
            return False
        last_id = rows[-1][0]
        if prepare is not None:
            try:
                pending.append(prepare.submit(
                    _prepare_migration_batch, rows, BLOCK_SIZE, owner))
            except RuntimeError as exc:
                # 准备池在关闭过程中：已读到的批次留待下次重试
                logger.info("准备池已关闭，停止派发迁移批次: %s", exc)
                return False
        else:
            pending.append(_completed_future(
                _prepare_migration_batch(rows, BLOCK_SIZE, owner)))
        return True

    while True:
        if cancelled is not None and cancelled():
            break
        # 有界流水线：先尽量填满在途批次，再按提交顺序应用最早的一批。
        while len(pending) < depth and _submit_next():
            pass
        if not pending:
            break
        future = pending.popleft()
        try:
            batch = future.result()
        except BaseException as exc:  # 准备失败只影响本批，源数据保持不变
            logger.warning("迁移准备失败，停止本批之后的重试: %s", exc)
            if stats is not None:
                stats["failed_batches"] = stats.get("failed_batches", 0) + 1
            break

        try:
            inserted, did_seal = _run_short(
                write, conn,
                lambda w, b=batch: _apply_staging_batch(
                    w, b.usable, b.snapshots, b.prepared))
        except sqlite3.OperationalError as exc:
            logger.warning("迁移批次写入失败，稍后重试: %s", exc)
            if stats is not None:
                stats["failed_batches"] = stats.get("failed_batches", 0) + 1
            break
        if stats is not None:
            stats["conflicts"] = stats.get("conflicts", 0) + max(
                0, len(batch.usable) - inserted)
        migrated += inserted
        sealed += 1 if did_seal else 0
        if inserted < len(batch.usable):
            # 记录被并发改动跳过的 id：等流水线排空后统一重扫一次即可，
            # 不在仍有在途批次时回头扫，避免重复派发。
            for item in batch.usable:
                exists = conn.execute(
                    "SELECT 1 FROM replay_index WHERE replay_id = ?",
                    (item.replay_id,)).fetchone()
                if exists is None:
                    skipped.add(item.replay_id)
        if progress is not None and total > 0:
            progress(migrated, total)

    # 重试一次：只重扫曾因并发改动被跳过的 id，仍冲突则留给下次启动
    if skipped and (cancelled is None or not cancelled()):
        ids = sorted(skipped)
        for start in range(0, len(ids), batch_size):
            if cancelled is not None and cancelled():
                break
            chunk = ids[start:start + batch_size]
            placeholders = ",".join("?" * len(chunk))
            try:
                rows = cursor.execute(
                    "SELECT d.replay_id, d.raw_data, d.compressed "
                    "FROM replay_data AS d "
                    f"WHERE d.replay_id IN ({placeholders}) "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM replay_index AS i "
                    "  WHERE i.replay_id = d.replay_id) "
                    "ORDER BY d.replay_id",
                    chunk).fetchall()
            except sqlite3.OperationalError:
                break
            if not rows:
                continue
            batch = _prepare_migration_batch(rows, BLOCK_SIZE, owner)
            try:
                inserted, did_seal = _run_short(
                    write, conn,
                    lambda w, b=batch: _apply_staging_batch(
                        w, b.usable, b.snapshots, b.prepared))
            except sqlite3.OperationalError:
                break
            migrated += inserted
            sealed += 1 if did_seal else 0
            if inserted and progress is not None and total > 0:
                progress(migrated, total)
        if stats is not None:
            remaining = 0
            for rid in ids:
                still_legacy = conn.execute(
                    "SELECT 1 FROM replay_data WHERE replay_id = ?",
                    (rid,)).fetchone()
                if still_legacy is None:
                    continue
                if conn.execute(
                        "SELECT 1 FROM replay_index WHERE replay_id = ?",
                        (rid,)).fetchone() is None:
                    remaining += 1
            if remaining:
                stats["abandoned_records"] = remaining

    # 收尾：把剩余 staging（含不足一整块的尾批）强制封口
    if cancelled is None or not cancelled():
        while True:
            prepared = prepare_seal(conn, limit=batch_size, force=True)
            if prepared is None:
                break
            if _apply_prepared(write, conn, prepared) <= 0:
                break
            sealed += 1
    if stats is not None:
        stats["migrated"] = stats.get("migrated", 0) + migrated
        stats["sealed"] = stats.get("sealed", 0) + sealed
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


@dataclass(frozen=True)
class _CleanupPlan:
    """一个分块的清理计划（纯 CPU 准备结果，可跨线程传递）。"""

    seg_id: int
    old_blob: bytes
    old_indexes: tuple[tuple, ...]
    removed_rows: tuple[tuple, ...]
    kept_rows: tuple[tuple, ...]
    packed: bytes | None
    raw_size: int

    @property
    def removable(self) -> int:
        return sum(1 for row in self.removed_rows if row[5] == 0)


def _plan_segment_cleanup(
    seg_id: int,
    blob: bytes,
    count: int,
    indexes: Sequence[tuple],
    low_ids: frozenset[int] | set[int],
) -> _CleanupPlan | None:
    """解压分块、筛掉低完成率槽位并重新压缩（纯 CPU，不碰数据库）。"""
    try:
        triples = decode_group(lzma.decompress(blob), count)
        snapshots = tuple(tuple(row) for row in indexes)
        if len(snapshots) != count:
            return None
        removed_rows = tuple(row for row in snapshots
                             if row[5] or row[0] in low_ids)
        kept_rows = tuple(row for row in snapshots
                          if not row[5] and row[0] not in low_ids)
        kept_triples = [triples[row[1]] for row in kept_rows]
        if kept_triples:
            packed = lzma.compress(encode_group(kept_triples),
                                  preset=_LZMA_PRESET)
            if decode_group(lzma.decompress(packed),
                            len(kept_triples)) != kept_triples:
                logger.warning("分块 %s 清理后自检失败，保留原数据", seg_id)
                return None
        else:
            packed = None
    except (lzma.LZMAError, UnsupportedReplayError, ValueError,
            TypeError, IndexError) as exc:
        logger.warning("分块 %s 清理准备失败，保留原数据: %s", seg_id, exc)
        return None
    return _CleanupPlan(
        seg_id=seg_id,
        old_blob=blob,
        old_indexes=snapshots,
        removed_rows=removed_rows,
        kept_rows=kept_rows,
        packed=packed,
        raw_size=sum(int(row[2] or 0) for row in kept_rows),
    )


def _apply_cleanup_plan(write: WriteDispatch | None,
                        conn: sqlite3.Connection,
                        plan: _CleanupPlan) -> bool:
    """短写事务内复核快照并落地一个分块的清理结果。"""
    def apply(target, p=plan):
        current = target.execute(
            "SELECT blob FROM replay_segment WHERE seg_id = ?",
            (p.seg_id,)).fetchone()
        if current is None or current[0] != p.old_blob:
            return False
        current_indexes = tuple(tuple(row) for row in target.execute(
            "SELECT replay_id, slot, length, sha256, codec, deleted "
            "FROM replay_index WHERE seg_id = ? ORDER BY slot",
            (p.seg_id,)))
        if current_indexes != p.old_indexes:
            return False
        for rid, *_ in p.removed_rows:
            target.execute(
                "UPDATE replay_index SET deleted=1, seg_id=NULL, slot=NULL "
                "WHERE replay_id=?", (rid,))
            try:
                target.execute("DELETE FROM replay_data WHERE replay_id=?",
                               (rid,))
            except sqlite3.OperationalError:
                pass
        if p.packed is None:
            target.execute("DELETE FROM replay_segment WHERE seg_id=?",
                           (p.seg_id,))
        else:
            (new_id,) = target.execute(
                "SELECT COALESCE(MAX(seg_id), -1) + 1 FROM replay_segment"
            ).fetchone()
            target.execute(
                "INSERT INTO replay_segment"
                "(seg_id,blob,codec,record_count,raw_size) "
                "VALUES(?,?,?,?,?)",
                (new_id, p.packed, CODEC_LZMA_COLUMNAR,
                 len(p.kept_rows), p.raw_size))
            for slot, row in enumerate(p.kept_rows):
                target.execute(
                    "UPDATE replay_index SET seg_id=?, slot=? "
                    "WHERE replay_id=?", (new_id, slot, row[0]))
            target.execute("DELETE FROM replay_segment WHERE seg_id=?",
                           (p.seg_id,))
        return True

    return bool(_run_short(write, conn, apply))


def cleanup_low_value_replays(
    conn: sqlite3.Connection,
    min_solved_percent: int,
    *,
    write: WriteDispatch | None = None,
    progress: ProgressCallback | None = None,
    cancelled: CancelCallback | None = None,
    prepare: PreparePool | None = None,
    stats: dict[str, int] | None = None,
) -> int:
    """清理低 3BV 完成率录像并紧凑受影响分块；保留 history 元数据。

    不同分块的解压与重新压缩在 ``prepare`` 线程池里并行完成；每个分块的
    提交仍由协调线程按序交由写线程执行。进度只累计**实际删除成功**的
    录像数，扫描到的候选数不等于完成数。

    Args:
        min_solved_percent: 完成率阈值（0-100）；0 表示不清理。
        write: 短写事务调度器；``None`` 时在本连接执行。
        progress: ``(done, total)``，``done`` 为已实际删除的录像数。
        cancelled: 返回 True 时在分块间停止。
        prepare: 有界并行准备池；``None`` 时串行准备。
        stats: 可选统计字典，累加 ``removed`` / ``conflict_segments`` /
            ``failed_segments`` / ``pending_segments``。

    Returns:
        实际删除的录像数。
    """
    threshold = max(0, min(100, int(min_solved_percent)))
    if threshold == 0 or conn.in_transaction:
        return 0
    low_ids = {row[0] for row in conn.execute(
        "SELECT i.replay_id FROM replay_index i "
        "JOIN history h ON h.replay_id = i.replay_id "
        "WHERE i.deleted = 0 AND h.bbbv > 0 AND h.bbbv_solved IS NOT NULL "
        "AND h.bbbv_solved * 100 < ? * h.bbbv", (threshold,))}
    total = len(low_ids)
    if progress is not None and total:
        progress(0, total)
    if not low_ids:
        return 0

    # 先对尚未封口的录像做软删除，避免封口线程重新纳入它们。
    staged = conn.execute(
        "SELECT s.replay_id, s.raw_data, s.codec, i.seg_id, i.slot, i.length, "
        "i.sha256, i.codec, i.deleted FROM replay_staging s "
        "JOIN replay_index i ON i.replay_id=s.replay_id "
        "JOIN history h ON h.replay_id=i.replay_id "
        "WHERE i.deleted=0 AND h.bbbv>0 AND h.bbbv_solved IS NOT NULL "
        "AND h.bbbv_solved * 100 < ? * h.bbbv", (threshold,)).fetchall()
    def remove_staged(target, snapshots=tuple(tuple(row) for row in staged)):
        removed_ids = []
        for snapshot in snapshots:
            rid = snapshot[0]
            current = target.execute(
                "SELECT s.raw_data, s.codec, i.seg_id, i.slot, i.length, i.sha256, "
                "i.codec, i.deleted FROM replay_staging s JOIN replay_index i "
                "ON i.replay_id=s.replay_id WHERE s.replay_id=?", (rid,)).fetchone()
            if current is None or tuple(current) != snapshot[1:]:
                continue
            target.execute(
                "UPDATE replay_index SET deleted=1 WHERE replay_id=? AND deleted=0",
                (rid,))
            target.execute("DELETE FROM replay_staging WHERE replay_id=?", (rid,))
            try:
                target.execute("DELETE FROM replay_data WHERE replay_id=?", (rid,))
            except sqlite3.OperationalError:
                pass
            removed_ids.append(rid)
        return removed_ids
    removed_staged = _run_short(write, conn, remove_staged) if staged else []
    if removed_staged:
        low_ids -= set(removed_staged)

    segments = conn.execute(
        "SELECT DISTINCT i.seg_id FROM replay_index i "
        "JOIN history h ON h.replay_id = i.replay_id "
        "WHERE i.deleted = 0 AND i.seg_id IS NOT NULL AND h.bbbv > 0 "
        "AND h.bbbv_solved IS NOT NULL AND h.bbbv_solved * 100 < ? * h.bbbv",
        (threshold,)).fetchall()
    removed = len(removed_staged)
    if progress is not None and total:
        progress(min(removed, total), total)

    cancelled_now = (lambda: cancelled is not None and cancelled())
    depth = prepare.max_in_flight if prepare is not None else 1
    queue: deque[int] = deque(int(row[0]) for row in segments)
    frozen_ids = frozenset(low_ids)
    pending: deque[tuple[int, Future[_CleanupPlan | None]]] = deque()
    retries: dict[int, int] = {}
    max_retries = 1

    def _submit_next() -> bool:
        if not queue or cancelled_now():
            return False
        seg_id = queue.popleft()
        row = conn.execute(
            "SELECT blob, record_count FROM replay_segment WHERE seg_id = ?",
            (seg_id,)).fetchone()
        if row is None:
            return True
        blob, count = row
        indexes = conn.execute(
            "SELECT replay_id, slot, length, sha256, codec, deleted "
            "FROM replay_index WHERE seg_id = ? ORDER BY slot",
            (seg_id,)).fetchall()
        if prepare is not None:
            try:
                future = prepare.submit(
                    _plan_segment_cleanup, seg_id, blob, count, indexes,
                    frozen_ids)
            except RuntimeError as exc:
                logger.info("准备池已关闭，停止派发清理分块: %s", exc)
                queue.appendleft(seg_id)
                return False
        else:
            future = _completed_future(
                _plan_segment_cleanup(seg_id, blob, count, indexes, frozen_ids))
        pending.append((seg_id, future))
        return True

    while True:
        if cancelled_now():
            break
        while len(pending) < depth and queue and _submit_next():
            pass
        if not pending:
            break
        seg_id, future = pending.popleft()
        try:
            plan = future.result()
        except BaseException as exc:
            logger.warning("分块 %s 清理准备失败，保留原数据: %s", seg_id, exc)
            if stats is not None:
                stats["failed_segments"] = stats.get("failed_segments", 0) + 1
            continue
        if plan is None:
            if stats is not None:
                stats["failed_segments"] = stats.get("failed_segments", 0) + 1
            continue
        try:
            applied = _apply_cleanup_plan(write, conn, plan)
        except sqlite3.OperationalError as exc:
            logger.warning("分块 %s 清理提交失败，保留原数据: %s", seg_id, exc)
            applied = False
        if applied:
            removed += plan.removable
            if progress is not None and total:
                progress(min(removed, total), total)
        else:
            # 快照冲突：重新读取该分块再试一次，之后放弃并保留原数据
            used = retries.get(seg_id, 0)
            if used < max_retries and not cancelled_now():
                retries[seg_id] = used + 1
                queue.append(seg_id)
            elif stats is not None:
                stats["conflict_segments"] = stats.get(
                    "conflict_segments", 0) + 1

    if (stats is not None and (queue or pending)):
        stats["pending_segments"] = stats.get("pending_segments", 0) + \
            len(queue) + len(pending)
    if (progress is not None and total and removed >= total
            and not queue and not pending):
        progress(total, total)
    if stats is not None:
        stats["removed"] = stats.get("removed", 0) + removed
    return removed


def vacuum(conn: sqlite3.Connection) -> None:
    """回收磁盘空间（由维护流程在**确认稳定后**手动调用，非自动）。"""
    conn.execute("VACUUM")
