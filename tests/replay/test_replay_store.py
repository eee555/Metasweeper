"""录像分块列式存储回归测试。

覆盖：
- evf 边界定位与 split/重拼 bit-exact
- 列式 encode/decode roundtrip（含各类事件、各种尺寸）
- 不支持结构（非 v4 / 损坏）必须抛 UnsupportedReplayError
- ``write_record`` 只 stage、绝不自动封口（含 ``staged=`` 兼容）
- prepare/apply 分离（跨线程 / 只读连接 prepare、写连接 apply）
- 并发：同条数内容替换、删除竞态、重复封口
- 分块读 / sha256 校验 / tombstone / 旧路径回退
- 旧 replay_data 分批迁移 + finalize 逐行复核清理
- board JSON → 雷图 BLOB 分批条件迁移
- 后台维护 progress/cancelled 语义（无旧数据时不回调）
"""
from __future__ import annotations

import hashlib
import lzma
import sqlite3
import struct
import zlib

import pytest

from plugins.history.replay_codec import (
    CODEC_LZMA_COLUMNAR,
    CODEC_ZLIB,
    UnsupportedReplayError,
    decode_group,
    encode_group,
    split_evf,
)
from plugins.history.replay_store import (
    BLOCK_SIZE,
    PreparedSeal,
    ReplayIntegrityError,
    apply_seal,
    cleanup_low_value_replays,
    compact_tombstone_segments,
    count_sealable_staging,
    ensure_tables,
    fill_incomplete_segments,
    finalize_migration,
    mark_deleted,
    migrate_from_replay_data,
    prepare_seal,
    read_raw_data,
    seal_staging,
    write_record,
    batch_sealable_staging_max_id,
    tombstone_segment_ids,
)


# ── 构造合法的 evf v4 字节 ────────────────────────────────────

def make_evf(row: int = 8, col: int = 8, *, flags: int = 0xF0,
             version: int = 4, events: bytes | None = None,
             checksum: bytes = b"\xAA" * 32, software: bytes = b"test\0"):
    head = bytearray()
    head.append(version)
    head.append(flags)
    head.append(0)                       # settings
    head.append(row)
    head.append(col)
    head += struct.pack(">H", 10)        # mine_num
    head.append(24)                      # pix_size
    head += struct.pack(">H", 0)         # mode
    head += struct.pack(">H", 20)        # bbbv
    head += struct.pack(">I", 5000)      # rtime_ms
    head += b"XX"                        # country
    head += struct.pack(">Q", 1000000)   # start_us
    head += struct.pack(">Q", 1005000)   # end_us
    head += software                     # software (已含 \0)
    # 转码录像标志位 bit3
    if flags & 0x08:
        head += b"transcoder\0utf-8\0"
    head += b"player\0race\0unique\0"
    head += struct.pack(">H", 4) + b"uuid"
    head += b"\x00" * ((row * col + 7) // 8)   # 雷图
    head += struct.pack(">H", 0)         # 指标数量
    if events is None:
        # mv(2): dt=3, dx=1, dy=2 ; lr(3) ; pause(255)
        events = (b"\x02\x03\x00\x01\x00\x02"
                  b"\x03\x05\x00\x02\x00\x03"
                  b"\xff\x01\x2c")
    tail = b"\x00" + struct.pack(">H", len(checksum)) + checksum
    return bytes(head) + events + tail


# 各种事件类型覆盖
_ALL_EVENTS = (
    b"\x01\x01\x00\x01\x00\x02"              # mv
    b"\x02\x02\xff\xff\xff\xfe"              # lc (负 dx/dy)
    b"\x03\x03\x00\x00\x00\x00"              # lr
    b"\x09\x04\x00\x05\x00\x06"              # cc
    b"\x51\x05"                              # replay (81)
    b"\x63\x06"                              # board event 99? 不是 -> 用 100
    b"\x64\x07\x03\x04"                      # board event 100
    b"\xff\x01\xf4"                          # pause 500ms
)


def test_split_evf_bit_exact():
    b = make_evf()
    head, events, tail = split_evf(b)
    assert head + events + tail == b
    assert tail[0] == 0
    assert struct.unpack_from(">H", tail, 1)[0] == 32
    assert len(tail) == 35


def test_split_evf_various_sizes_and_flags():
    for row, col in ((8, 8), (16, 16), (16, 30), (9, 11)):
        for flags in (0xF0, 0x30, 0x20, 0xE0, 0xF8):
            b = make_evf(row, col, flags=flags)
            head, events, tail = split_evf(b)
            assert head + events + tail == b


def test_split_evf_transcode_has_extra_fields():
    b = make_evf(flags=0xF8)   # bit3 置位 → 转码录像
    head, events, tail = split_evf(b)
    assert head + events + tail == b


def test_split_evf_rejects_non_v4():
    with pytest.raises(UnsupportedReplayError):
        split_evf(make_evf(version=3))


def test_split_evf_rejects_truncated():
    b = make_evf()
    with pytest.raises(UnsupportedReplayError):
        split_evf(b[:20])
    with pytest.raises(UnsupportedReplayError):
        split_evf(b[:-10])


def test_split_evf_rejects_wrong_checksum_len():
    b = bytearray(make_evf())
    struct.pack_into(">H", b, len(b) - 34 + 1, 16)   # 谎报长度
    with pytest.raises(UnsupportedReplayError):
        split_evf(bytes(b))


def test_split_evf_rejects_unknown_event():
    bad = b"\x7f\x01\x02\x03"    # 未知事件类型 127
    b = make_evf(events=bad)
    with pytest.raises(UnsupportedReplayError):
        split_evf(b)


def test_columnar_roundtrip_bit_exact():
    blobs = [make_evf(row=r, col=c, events=_ALL_EVENTS)
             for r, c in ((8, 8), (16, 16), (16, 30), (9, 11), (8, 8))]
    triples = [split_evf(b) for b in blobs]
    payload = encode_group(triples)
    decoded = decode_group(payload, len(triples))
    assert decoded == triples
    assert [h + e + t for h, e, t in decoded] == blobs


def test_columnar_roundtrip_many_records():
    blobs = [make_evf(row=8 + i % 3, col=8 + i % 5,
                      events=_ALL_EVENTS * (i % 7 + 1))
             for i in range(37)]
    triples = [split_evf(b) for b in blobs]
    payload = encode_group(triples)
    assert decode_group(payload, len(triples)) == triples


def test_columnar_compresses():
    blobs = [make_evf(events=_ALL_EVENTS * 30) for _ in range(64)]
    triples = [split_evf(b) for b in blobs]
    payload = encode_group(triples)
    assert len(lzma.compress(payload, preset=6)) < sum(len(b) for b in blobs)


def test_decode_group_rejects_corrupt():
    triples = [split_evf(make_evf()) for _ in range(3)]
    payload = encode_group(triples)
    with pytest.raises(UnsupportedReplayError):
        decode_group(payload[:10], 3)
    # 篡改一个区长度
    bad = bytearray(payload)
    struct.pack_into("<I", bad, 0, 10**6)
    with pytest.raises(UnsupportedReplayError):
        decode_group(bytes(bad), 3)
    with pytest.raises(UnsupportedReplayError):
        decode_group(payload, 99)


# ── 存储层 ────────────────────────────────────────────────────

@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_tables(c)
    yield c
    c.close()


@pytest.fixture
def legacy_replay_data(conn):
    """建立旧 replay_data 子表（与生产 schema 一致）。"""
    conn.execute("""CREATE TABLE replay_data (
        replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)""")
    conn.commit()
    return conn


def test_write_and_read_before_seal(conn):
    b = make_evf()
    write_record(conn, 1, b)
    conn.commit()
    assert read_raw_data(conn, 1) == b


def test_cleanup_compacts_segment_and_preserves_history_metadata(tmp_path):
    from plugins.history.db import db_connection
    path = tmp_path / "history.db"
    with db_connection(path) as conn:
        conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY, bbbv INTEGER, bbbv_solved INTEGER)")
        ensure_tables(conn)
        raws = [make_evf(checksum=bytes([i]) * 32) for i in (1, 2, 3)]
        for rid, raw, solved in zip((1, 2, 3), raws, (10, 30, 100)):
            conn.execute("INSERT INTO history VALUES (?, 100, ?)", (rid, solved))
            write_record(conn, rid, raw)
        conn.commit()
        assert seal_staging(conn, limit=3) == 3
        progress = []
        assert cleanup_low_value_replays(
            conn, 30, progress=lambda done, total: progress.append((done, total))) == 1
        assert progress[0] == (0, 1)
        assert progress[-1] == (1, 1)
        assert read_raw_data(conn, 1) is None
        assert read_raw_data(conn, 2) == raws[1]
        assert read_raw_data(conn, 3) == raws[2]
        assert conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 3
        assert conn.execute("SELECT record_count FROM replay_segment").fetchone()[0] == 2
        assert cleanup_low_value_replays(conn, 30) == 0



def test_compact_tombstone_segments_removes_dead_slots(conn):
    raws = {rid: make_evf(checksum=bytes([rid]) * 32) for rid in range(1, 6)}
    for rid, raw in raws.items():
        write_record(conn, rid, raw)
    conn.commit()
    assert seal_staging(conn, limit=5) == 5
    (seg_id,) = conn.execute("SELECT seg_id FROM replay_segment").fetchone()
    mark_deleted(conn, 2)
    mark_deleted(conn, 4)
    conn.commit()

    assert tombstone_segment_ids(conn) == [seg_id]
    assert compact_tombstone_segments(conn) == 1
    assert conn.execute(
        "SELECT record_count FROM replay_segment WHERE seg_id = ?",
        (seg_id,)).fetchone()[0] == 3
    for rid in (1, 3, 5):
        assert read_raw_data(conn, rid) == raws[rid]
    for rid in (2, 4):
        assert read_raw_data(conn, rid) is None
    assert tombstone_segment_ids(conn) == []
    assert compact_tombstone_segments(conn) == 0


def test_compact_tombstone_segments_rechecks_snapshot(conn):
    raws = {rid: make_evf(checksum=bytes([rid]) * 32) for rid in range(1, 4)}
    for rid, raw in raws.items():
        write_record(conn, rid, raw)
    conn.commit()
    assert seal_staging(conn, limit=3) == 3
    (seg_id,) = conn.execute("SELECT seg_id FROM replay_segment").fetchone()
    mark_deleted(conn, 2)
    conn.commit()
    original_blob = conn.execute(
        "SELECT blob FROM replay_segment WHERE seg_id = ?",
        (seg_id,)).fetchone()[0]
    changed = []

    def write(operation):
        conn.execute(
            "UPDATE replay_segment SET blob = ? WHERE seg_id = ?",
            (b"changed", seg_id))
        conn.commit()
        changed.append(True)
        try:
            return operation(conn)
        finally:
            conn.execute(
                "UPDATE replay_segment SET blob = ? WHERE seg_id = ?",
                (original_blob, seg_id))
            conn.commit()

    assert compact_tombstone_segments(conn, write=write) == 0
    assert changed == [True]
    for rid, raw in raws.items():
        if rid != 2:
            assert read_raw_data(conn, rid) == raw


def test_batch_sealable_staging_max_id_limits_watermark(conn):
    for rid in range(1, 6):
        write_record(conn, rid, make_evf(checksum=bytes([rid]) * 32))
    conn.commit()
    assert batch_sealable_staging_max_id(conn, 3) == 3
    assert batch_sealable_staging_max_id(conn, 10) == 5

def test_fill_incomplete_segments_keeps_remaining_staging(conn):
    raw = make_evf()
    for rid in range(1, 4):
        write_record(conn, rid, make_evf(checksum=bytes([rid]) * 32))
    conn.commit()
    assert seal_staging(conn, limit=3) == 3
    (seg_id,) = conn.execute("SELECT seg_id FROM replay_segment").fetchone()
    for rid in range(4, 8):
        write_record(conn, rid, make_evf(checksum=bytes([rid]) * 32))
    conn.commit()
    assert count_sealable_staging(conn) == 4
    assert fill_incomplete_segments(conn, batch_size=4) == 1
    assert conn.execute(
        "SELECT record_count FROM replay_segment WHERE seg_id = ?",
        (seg_id,)).fetchone()[0] == 4
    assert count_sealable_staging(conn) == 3
    assert conn.execute("SELECT COUNT(*) FROM replay_segment").fetchone()[0] == 1
    for rid in range(1, 5):
        assert read_raw_data(conn, rid) == make_evf(checksum=bytes([rid]) * 32)
    for rid in range(5, 8):
        assert read_raw_data(conn, rid) == make_evf(checksum=bytes([rid]) * 32)


def test_write_record_never_seals(conn):
    """单次 staging 写入不得触发同步封口（CPU 必须留给后台线程）。"""
    import plugins.history.replay_store as rs

    def _boom(*_a, **_k):
        raise AssertionError("write_record 不得同步封口")

    orig_prepare, orig_seal = rs.prepare_seal, rs.seal_staging
    rs.prepare_seal = _boom        # type: ignore[assignment]
    try:
        for i in range(BLOCK_SIZE * 2):
            write_record(conn, i + 1, make_evf())
        conn.commit()
    finally:
        rs.prepare_seal = orig_prepare  # type: ignore[assignment]

    assert conn.execute(
        "SELECT COUNT(*) FROM replay_staging").fetchone()[0] == BLOCK_SIZE * 2
    assert conn.execute(
        "SELECT COUNT(*) FROM replay_segment").fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM replay_index WHERE seg_id IS NOT NULL"
    ).fetchone()[0] == 0
    assert rs.seal_staging is orig_seal
    # 仍然可以正常读到 staging 数据
    assert read_raw_data(conn, BLOCK_SIZE * 2) == make_evf()


def test_prepare_requires_full_block_unless_forced(conn):
    for i in range(BLOCK_SIZE - 1):
        write_record(conn, i + 1, make_evf())
    conn.commit()
    assert prepare_seal(conn) is None                 # 未凑满，不封口
    prepared = prepare_seal(conn, force=True)
    assert isinstance(prepared, PreparedSeal)
    assert prepared.record_count == BLOCK_SIZE - 1
    assert apply_seal(conn, prepared) == BLOCK_SIZE - 1


def test_prepare_seal_is_read_only(conn):
    for i in range(BLOCK_SIZE):
        write_record(conn, i + 1, make_evf())
    conn.commit()
    before = (conn.execute("SELECT COUNT(*) FROM replay_staging").fetchone()[0],
              conn.execute("SELECT COUNT(*) FROM replay_segment").fetchone()[0])
    prepared = prepare_seal(conn)
    assert prepared is not None
    after = (conn.execute("SELECT COUNT(*) FROM replay_staging").fetchone()[0],
             conn.execute("SELECT COUNT(*) FROM replay_segment").fetchone()[0])
    assert before == after
    assert not conn.in_transaction


def test_read_snapshot_survives_concurrent_seal(tmp_path, monkeypatch):
    """索引读完后另一连接封口并删除 staging，读取仍使用原快照。"""
    from plugins.history import replay_store

    path = tmp_path / "history.db"
    reader = sqlite3.connect(path)
    writer = sqlite3.connect(path)
    try:
        reader.execute("PRAGMA journal_mode=WAL")
        ensure_tables(reader)
        raw = make_evf()
        write_record(writer, 1, raw)
        writer.commit()
        prepared = prepare_seal(writer, force=True)
        assert prepared is not None
        original = replay_store._raw_from_index
        sealed = []

        def seal_after_index(conn, replay_id, entry, segment_cache=None):
            assert entry[4] == CODEC_ZLIB
            sealed.append(apply_seal(writer, prepared))
            assert writer.execute(
                "SELECT 1 FROM replay_staging WHERE replay_id=1").fetchone() is None
            return original(conn, replay_id, entry, segment_cache)

        monkeypatch.setattr(replay_store, "_raw_from_index", seal_after_index)
        assert read_raw_data(reader, 1) == raw
        assert sealed == [1]
        assert not reader.in_transaction
    finally:
        reader.close()
        writer.close()


def test_read_snapshot_preserves_caller_transaction(conn):
    raw = make_evf()
    write_record(conn, 1, raw)
    assert conn.in_transaction
    assert read_raw_data(conn, 1) == raw
    assert conn.in_transaction
    conn.rollback()
    assert read_raw_data(conn, 1) is None


def test_read_snapshot_released_after_integrity_failure(conn):
    write_record(conn, 1, make_evf())
    conn.execute("DELETE FROM replay_staging WHERE replay_id=1")
    conn.commit()
    assert read_raw_data(conn, 1) is None
    assert not conn.in_transaction


def test_prepare_then_apply_separate_connections(tmp_path):
    """维护线程 prepare、写线程 apply（真实跨连接模型）。"""
    path = tmp_path / "history.db"
    reader = sqlite3.connect(path)
    writer = sqlite3.connect(path)
    try:
        ensure_tables(reader)
        blobs = [make_evf(events=_ALL_EVENTS * (i % 9 + 1))
                 for i in range(BLOCK_SIZE + 5)]
        for i, b in enumerate(blobs, 1):
            write_record(writer, i, b)
        writer.commit()

        sealed_total = 0
        while True:
            prepared = prepare_seal(reader)      # 只读连接，CPU 在这里
            if prepared is None:
                break
            sealed_total += apply_seal(writer, prepared)  # 短写事务
        # 尾批用 force
        prepared = prepare_seal(reader, force=True)
        if prepared is not None:
            sealed_total += apply_seal(writer, prepared)
        assert sealed_total == len(blobs)
        for i, b in enumerate(blobs, 1):
            assert read_raw_data(reader, i) == b
        assert reader.execute(
            "SELECT COUNT(*) FROM replay_staging").fetchone()[0] == 0
    finally:
        reader.close()
        writer.close()


def test_prepare_and_apply_in_worker_thread(tmp_path):
    """prepare 在另一个线程执行，apply 回到原（写）连接。"""
    import threading

    path = tmp_path / "history.db"
    conn = sqlite3.connect(path, check_same_thread=False)
    try:
        ensure_tables(conn)
        blobs = [make_evf(events=_ALL_EVENTS * 3) for _ in range(BLOCK_SIZE)]
        for i, b in enumerate(blobs, 1):
            write_record(conn, i, b)
        conn.commit()

        box: dict[str, object] = {}

        def worker() -> None:
            own = sqlite3.connect(path)
            try:
                box["prepared"] = prepare_seal(own)
            finally:
                own.close()

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        prepared = box["prepared"]
        assert isinstance(prepared, PreparedSeal)
        # 跨线程 apply 到写连接
        assert apply_seal(conn, prepared) == BLOCK_SIZE
        assert read_raw_data(conn, 1) == blobs[0]
    finally:
        conn.close()


def test_apply_rejects_same_count_content_replacement(conn):
    """同条数、同长度的内容替换必须被逐字节快照比对拦下。"""
    blobs = [make_evf(events=_ALL_EVENTS * 1) for _ in range(BLOCK_SIZE)]
    for i, b in enumerate(blobs, 1):
        write_record(conn, i, b)
    conn.commit()
    prepared = prepare_seal(conn)
    assert prepared is not None
    assert prepared.record_count == BLOCK_SIZE

    # 同长度替换：条数不变、长度不变，仅内容不同
    replacement = make_evf(events=_ALL_EVENTS * 1 + b"\xff\x01\xf4")
    assert len(replacement) != len(blobs[0]) or replacement != blobs[0]
    conn.execute(
        "UPDATE replay_staging SET raw_data = ? WHERE replay_id = 1",
        (zlib.compress(replacement, 6),))
    # 同步改索引，保持「看起来一致」
    conn.execute(
        "UPDATE replay_index SET length = ?, sha256 = ? WHERE replay_id = 1",
        (len(replacement), hashlib.sha256(replacement).digest()))
    conn.commit()

    assert apply_seal(conn, prepared) == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM replay_segment").fetchone()[0] == 0
    # 数据未丢：仍在 staging，且读得到新内容
    assert read_raw_data(conn, 1) == replacement
    assert conn.execute(
        "SELECT COUNT(*) FROM replay_staging").fetchone()[0] == BLOCK_SIZE


def test_apply_rejects_same_length_sha_preserved_replacement(conn):
    """在 prepare 之后仅改 staging 字节（索引不动）也必须放弃。"""
    for i in range(BLOCK_SIZE):
        write_record(conn, i + 1, make_evf())
    conn.commit()
    prepared = prepare_seal(conn)
    assert prepared is not None

    tampered = zlib.compress(make_evf(events=b"\xff\x01\x2c"), 6)
    conn.execute(
        "UPDATE replay_staging SET raw_data = ? WHERE replay_id = 5",
        (tampered,))
    conn.commit()
    assert apply_seal(conn, prepared) == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM replay_segment").fetchone()[0] == 0


def test_apply_rejects_concurrent_deletion(tmp_path):
    """prepare 后并发删除（墓碑）必须放弃本批，其余记录仍可读。"""
    path = tmp_path / "history.db"
    reader = sqlite3.connect(path)
    writer = sqlite3.connect(path)
    try:
        ensure_tables(reader)
        blobs = [make_evf(events=_ALL_EVENTS * 2) for _ in range(BLOCK_SIZE)]
        for i, b in enumerate(blobs, 1):
            write_record(writer, i, b)
        writer.commit()
        prepared = prepare_seal(reader)
        assert prepared is not None

        # 并发删除其中一条
        writer.execute("DELETE FROM replay_staging WHERE replay_id = 7")
        writer.execute(
            "UPDATE replay_index SET deleted = 1 WHERE replay_id = 7")
        writer.commit()

        assert apply_seal(writer, prepared) == 0
        assert writer.execute(
            "SELECT COUNT(*) FROM replay_segment").fetchone()[0] == 0
        assert read_raw_data(writer, 7) is None
        assert read_raw_data(writer, 8) == blobs[7]
    finally:
        reader.close()
        writer.close()


def test_apply_rejects_double_seal(conn):
    """同一批数据不能被封口两次（防止重复块覆盖索引）。"""
    for i in range(BLOCK_SIZE):
        write_record(conn, i + 1, make_evf())
    conn.commit()
    prepared = prepare_seal(conn)
    assert prepared is not None
    assert apply_seal(conn, prepared) == BLOCK_SIZE
    assert apply_seal(conn, prepared) == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM replay_segment").fetchone()[0] == 1


def test_apply_ignores_plan_when_data_version_changed(conn):
    """同一连接：prepare 后其他连接提交过 → 直接放弃，不做无谓写入。"""
    import tempfile, os
    path = os.path.join(tempfile.mkdtemp(), "h.db")
    reader = sqlite3.connect(path)
    other = sqlite3.connect(path)
    try:
        ensure_tables(reader)
        for i in range(BLOCK_SIZE):
            write_record(reader, i + 1, make_evf())
        reader.commit()
        prepared = prepare_seal(reader)
        assert prepared is not None
        other.execute("INSERT INTO replay_staging VALUES (9999, ?, 1)",
                      (zlib.compress(make_evf(), 6),))
        other.commit()
        # 同连接 prepare/apply：data_version 变化 → 放弃
        assert apply_seal(reader, prepared) == 0
        assert reader.execute(
            "SELECT COUNT(*) FROM replay_segment").fetchone()[0] == 0
        # 重新准备（用其自身连接）后可正常封口
        again = prepare_seal(reader)
        assert again is not None
        assert apply_seal(reader, again) == BLOCK_SIZE
    finally:
        reader.close()
        other.close()


def test_seal_and_random_read(conn):
    blobs = [make_evf(row=8, col=8, events=_ALL_EVENTS * (i % 9 + 1))
             for i in range(BLOCK_SIZE)]
    for i, b in enumerate(blobs, 1):
        write_record(conn, i, b)
    conn.commit()
    sealed = seal_staging(conn)
    conn.commit()
    assert sealed == BLOCK_SIZE
    for i, b in enumerate(blobs, 1):
        assert read_raw_data(conn, i) == b
    (seg_count,) = conn.execute(
        "SELECT COUNT(*) FROM replay_segment").fetchone()
    assert seg_count == 1
    (codec,) = conn.execute(
        "SELECT codec FROM replay_index WHERE replay_id = 1").fetchone()
    assert codec == CODEC_LZMA_COLUMNAR


def test_integrity_check_catches_corruption(conn):
    b = make_evf()
    write_record(conn, 1, b)
    conn.commit()
    # 篡改 sha256
    conn.execute("UPDATE replay_index SET sha256 = ? WHERE replay_id = 1",
                 (hashlib.sha256(b"wrong").digest(),))
    conn.commit()
    with pytest.raises(ReplayIntegrityError):
        from plugins.history.replay_store import _read_from_segment
        _read_from_segment(conn, 1)
    # read_raw_data 应回退（旧表无数据 → None）
    assert read_raw_data(conn, 1) is None


def test_tombstone_delete(conn):
    b = make_evf()
    write_record(conn, 1, b)
    conn.commit()
    assert read_raw_data(conn, 1) == b
    mark_deleted(conn, 1)
    conn.commit()
    assert read_raw_data(conn, 1) is None


def test_tombstoned_entry_not_sealed(conn):
    """墓碑条目不得被封口。"""
    for i in range(BLOCK_SIZE):
        write_record(conn, i + 1, make_evf())
    mark_deleted(conn, 3)
    conn.commit()
    prepared = prepare_seal(conn, force=True)
    assert prepared is not None
    assert 3 not in prepared.replay_ids()
    assert apply_seal(conn, prepared) == BLOCK_SIZE - 1
    assert conn.execute(
        "SELECT codec FROM replay_index WHERE replay_id = 3").fetchone()[0] \
        == CODEC_ZLIB
    assert read_raw_data(conn, 3) is None


def test_unsupported_replay_falls_back_to_zlib(conn):
    """非 v4 录像不能列式化，但必须仍能原样读出。"""
    bad = make_evf(version=3)
    write_record(conn, 1, bad)
    conn.commit()
    assert read_raw_data(conn, 1) == bad
    # 强制封口不应把它塞进块
    assert seal_staging(conn) == 0
    assert read_raw_data(conn, 1) == bad


def test_migrate_from_replay_data_and_finalize(legacy_replay_data):
    conn = legacy_replay_data
    blobs = [make_evf(row=8, col=8, events=_ALL_EVENTS * (i % 5 + 1))
             for i in range(BLOCK_SIZE + 7)]
    for i, b in enumerate(blobs, 1):
        conn.execute("INSERT INTO replay_data VALUES (?, ?, ?)",
                     (i, zlib.compress(b, 6), 1))
    conn.commit()

    migrated, sealed = migrate_from_replay_data(conn)
    assert migrated == len(blobs)
    assert sealed >= 1
    for i, b in enumerate(blobs, 1):
        assert read_raw_data(conn, i) == b
    # finalize 前旧表还在
    assert conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == len(blobs)
    assert finalize_migration(conn) is True
    assert conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == 0
    # 清空旧表后仍全部可读
    for i, b in enumerate(blobs, 1):
        assert read_raw_data(conn, i) == b


def test_finalize_refuses_when_integrity_broken(legacy_replay_data):
    conn = legacy_replay_data
    b = make_evf()
    conn.execute("INSERT INTO replay_data VALUES (?, ?, ?)",
                 (1, zlib.compress(b, 6), 1))
    write_record(conn, 1, b)
    conn.commit()
    # 破坏新存储的索引
    conn.execute("UPDATE replay_index SET sha256 = ? WHERE replay_id = 1",
                 (hashlib.sha256(b"x").digest(),))
    conn.commit()
    assert finalize_migration(conn) is False
    assert conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == 1


def test_unencodable_staging_does_not_block_later_records(conn):
    bad = make_evf(version=3)
    for rid in range(1, 4):
        write_record(conn, rid, bad)
    good = make_evf()
    for rid in range(4, 7):
        write_record(conn, rid, good)
    conn.commit()
    assert seal_staging(conn, limit=2) == 2
    assert seal_staging(conn, limit=2) == 1
    assert seal_staging(conn, limit=2) == 0
    assert [read_raw_data(conn, rid) for rid in range(1, 7)] == [bad] * 3 + [good] * 3
    assert conn.execute("SELECT COUNT(*) FROM replay_staging").fetchone()[0] == 3


def test_prepare_progresses_past_unsupported_records(conn):
    """被降级的记录不能占满扫描名额，后续合法记录仍应被封装。"""
    for rid in range(1, BLOCK_SIZE + 1):
        write_record(conn, rid, make_evf(version=3))
    conn.commit()
    raw = make_evf()
    write_record(conn, BLOCK_SIZE + 1, raw)
    conn.commit()
    assert seal_staging(conn, limit=BLOCK_SIZE) == 1
    assert conn.execute("SELECT codec FROM replay_index WHERE replay_id = ?",
                        (BLOCK_SIZE + 1,)).fetchone()[0] == CODEC_LZMA_COLUMNAR
    assert read_raw_data(conn, BLOCK_SIZE + 1) == raw
    assert read_raw_data(conn, 1) == make_evf(version=3)


@pytest.mark.parametrize("damage", ["bad_zlib", "missing_staging", "bad_codec",
                                    "missing_segment", "bad_segment", "bad_slot"])
@pytest.mark.parametrize("legacy", ["replay_data", "history"])
def test_damaged_new_storage_falls_back(conn, damage, legacy):
    raw = make_evf()
    conn.execute(f"CREATE TABLE {legacy} (replay_id INTEGER PRIMARY KEY, "
                 "raw_data BLOB, compressed INTEGER)")
    conn.execute(f"INSERT INTO {legacy} VALUES (?, ?, ?)", (1, zlib.compress(raw), 1))
    write_record(conn, 1, raw)
    conn.commit()
    if damage in ("missing_segment", "bad_segment", "bad_slot"):
        assert seal_staging(conn) == 1
        if damage == "missing_segment":
            conn.execute("DELETE FROM replay_segment")
        elif damage == "bad_segment":
            conn.execute("UPDATE replay_segment SET blob = ?", (b"broken",))
        else:
            conn.execute("UPDATE replay_index SET slot = -1")
    elif damage == "bad_zlib":
        conn.execute("UPDATE replay_staging SET raw_data = ?", (b"broken",))
    elif damage == "bad_codec":
        conn.execute("UPDATE replay_staging SET codec = 99")
    else:
        conn.execute("DELETE FROM replay_staging")
    assert read_raw_data(conn, 1) == raw


def test_tombstone_never_falls_back_to_old_history(conn):
    raw = make_evf()
    conn.execute("CREATE TABLE history (replay_id INTEGER PRIMARY KEY, raw_data BLOB)")
    conn.execute("INSERT INTO history VALUES (?, ?)", (1, raw))
    write_record(conn, 1, raw)
    mark_deleted(conn, 1)
    conn.execute("DELETE FROM replay_staging WHERE replay_id = 1")
    assert read_raw_data(conn, 1) is None


def test_finalize_preserves_caller_transaction(conn):
    conn.execute("CREATE TABLE replay_data (replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)")
    raw = make_evf()
    conn.execute("INSERT INTO replay_data VALUES (?, ?, 0)", (1, raw))
    write_record(conn, 1, raw)
    assert finalize_migration(conn) is False
    assert conn.in_transaction
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == 0


def test_write_record_reuses_precompressed_staging(conn):
    """调用方已压好的字节应直接复用，同一份数据只压一次。"""
    import zlib as _zlib

    from plugins.history import replay_store

    raw = make_evf()
    staged = _zlib.compress(raw, 6)
    calls = []
    original = replay_store.zlib.compress

    def counting_compress(data, *args, **kwargs):
        calls.append(len(data))
        return original(data, *args, **kwargs)

    import unittest.mock as mock
    with mock.patch.object(replay_store.zlib, "compress", counting_compress):
        write_record(conn, 1, raw, staged=staged)
    assert calls == []
    assert read_raw_data(conn, 1) == raw
    assert conn.execute(
        "SELECT raw_data FROM replay_staging WHERE replay_id = 1"
    ).fetchone()[0] == staged


def test_write_record_compresses_when_staging_not_given(conn):
    """未传 staged 时保持原有行为：内部自行压缩。"""
    raw = make_evf()
    write_record(conn, 1, raw)
    assert read_raw_data(conn, 1) == raw


# ── finalize：并发保护 / 分批 / 进度 ─────────────────────────

def _seed_legacy(conn, raws, *, also_new=True, seal=True):
    for i, raw in enumerate(raws, 1):
        conn.execute("INSERT INTO replay_data VALUES (?, ?, 0)", (i, raw))
        if also_new:
            write_record(conn, i, raw)
    conn.commit()
    if also_new and seal:
        while seal_staging(conn) > 0:
            pass
        conn.commit()


def test_finalize_does_not_block_competing_writer_during_validation(
        tmp_path):
    """校验阶段不得持有写锁：期间其他连接写入必须成功。"""
    import plugins.history.replay_store as replay_store

    path = tmp_path / "history.db"
    with sqlite3.connect(path) as primary, sqlite3.connect(path, timeout=0) as other:
        ensure_tables(primary)
        primary.execute("CREATE TABLE replay_data (replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)")
        raw = make_evf()
        _seed_legacy(primary, [raw])
        original_read = replay_store._read_from_segment
        attempted = []

        def competing_read(conn, replay_id, segment_cache=None):
            # 校验期间另一连接写入必须立即成功，而不是 database is locked
            other.execute("UPDATE replay_index SET deleted = 0 WHERE replay_id = 1")
            other.commit()
            attempted.append(True)
            return original_read(conn, replay_id, segment_cache)

        import unittest.mock as mock
        with mock.patch.object(replay_store, "_read_from_segment", competing_read):
            assert finalize_migration(primary) is True
        assert attempted == [True]
        assert primary.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == 0
        assert original_read(primary, 1) == raw


def test_finalize_aborts_when_old_rows_change_after_validation(tmp_path):
    """校验通过后旧表被改动，复核失败必须保留旧表而不是盲删。"""
    import plugins.history.replay_store as replay_store

    path = tmp_path / "history.db"
    with sqlite3.connect(path) as primary, sqlite3.connect(path, timeout=0) as other:
        ensure_tables(primary)
        primary.execute("CREATE TABLE replay_data (replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)")
        raws = [make_evf(events=_ALL_EVENTS * i) for i in (1, 2)]
        _seed_legacy(primary, raws)
        original_read = replay_store._read_from_segment
        inserted = []

        def racing_read(conn, replay_id, segment_cache=None):
            result = original_read(conn, replay_id, segment_cache)
            # 读完后并发插入一条旧表记录，复核应发现行数变化
            if not inserted:
                other.execute("INSERT INTO replay_data VALUES (?, ?, 0)",
                              (99, raws[0]))
                other.commit()
                inserted.append(True)
            return result

        import unittest.mock as mock
        with mock.patch.object(replay_store, "_read_from_segment", racing_read):
            assert finalize_migration(primary) is False
        assert not primary.in_transaction
        assert primary.execute(
            "SELECT COUNT(*) FROM replay_data").fetchone()[0] == 3


def test_finalize_aborts_on_same_count_row_mutation(tmp_path):
    """同条数、同长度但内容被替换的旧行不得被删除（逐字节复核）。"""
    import plugins.history.replay_store as replay_store

    path = tmp_path / "history.db"
    with sqlite3.connect(path) as primary, sqlite3.connect(path, timeout=0) as other:
        ensure_tables(primary)
        primary.execute("CREATE TABLE replay_data (replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)")
        raw_a = make_evf(events=_ALL_EVENTS * 1)
        raw_b = make_evf(events=_ALL_EVENTS * 1)
        assert raw_a == raw_b
        replacement = raw_a[:-3] + b"\x00" + raw_a[-2:]   # 等长不同内容
        assert len(replacement) == len(raw_a)
        _seed_legacy(primary, [raw_a, raw_a])
        # 让 index 快照仍与旧行匹配（模拟别的连接只改旧表字节）
        original_read = replay_store._read_from_segment
        mutated = []

        def racing_read(conn, replay_id, segment_cache=None):
            result = original_read(conn, replay_id, segment_cache)
            if not mutated:
                other.execute(
                    "UPDATE replay_data SET raw_data = ? WHERE replay_id = 2",
                    (replacement,))
                other.commit()
                mutated.append(True)
            return result

        import unittest.mock as mock
        with mock.patch.object(replay_store, "_read_from_segment", racing_read):
            assert finalize_migration(primary) is False
        assert primary.execute(
            "SELECT COUNT(*) FROM replay_data").fetchone()[0] == 2


def test_finalize_deletes_only_validated_ids_in_batches(conn):
    """分批：只删已校验的 id，tombstone 记录阻止清理。"""
    conn.execute("CREATE TABLE replay_data (replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)")
    raws = [make_evf(events=_ALL_EVENTS * (i % 3 + 1))
            for i in range(BLOCK_SIZE + 5)]
    _seed_legacy(conn, raws)

    assert finalize_migration(conn, batch_size=17) is True
    assert conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == 0
    for i, raw in enumerate(raws, 1):
        assert read_raw_data(conn, i) == raw


def test_finalize_reuses_decoded_segments(conn):
    """同一块的记录只解码一次，避免 O(条数 × 块大小)。"""
    import plugins.history.replay_store as replay_store

    conn.execute("CREATE TABLE replay_data (replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)")
    raws = [make_evf(events=_ALL_EVENTS * (i % 3 + 1))
            for i in range(1, BLOCK_SIZE + 1)]
    _seed_legacy(conn, raws)
    assert conn.execute(
        "SELECT COUNT(DISTINCT seg_id) FROM replay_index").fetchone()[0] == 1

    calls = []
    original = replay_store.decode_group

    def counting_decode(payload, count):
        calls.append(count)
        return original(payload, count)

    import unittest.mock as mock
    with mock.patch.object(replay_store, "decode_group", counting_decode):
        assert finalize_migration(conn) is True
    assert len(calls) == 1


def test_finalize_rejects_tombstone_and_releases_lock(conn):
    conn.execute("CREATE TABLE replay_data (replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)")
    raw = make_evf()
    _seed_legacy(conn, [raw])
    conn.execute("UPDATE replay_index SET deleted = 1 WHERE replay_id = 1")
    conn.commit()
    assert finalize_migration(conn) is False
    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == 1


def test_finalize_no_legacy_table_is_noop(conn):
    assert finalize_migration(conn) is True
    calls = []
    migrate_from_replay_data(conn, progress=lambda d, t: calls.append((d, t)))
    assert calls == []          # 无旧表 → 不回调（UI 不会显示迁移中）


def test_progress_not_called_when_no_legacy_rows(legacy_replay_data):
    """只有 metadata、没有旧录像数据时，后台回调必须完全不触发。"""
    conn = legacy_replay_data
    replay_events, board_events = [], []
    assert migrate_from_replay_data(
        conn, progress=lambda d, t: replay_events.append((d, t))) == (0, 0)
    assert finalize_migration(conn, progress=lambda d, t: board_events.append((d, t))) is True
    assert replay_events == []
    assert board_events == []


def test_migrate_reports_progress_and_honours_cancel(legacy_replay_data):
    conn = legacy_replay_data
    raws = [make_evf(events=_ALL_EVENTS * 2) for _ in range(BLOCK_SIZE * 2 + 3)]
    for i, raw in enumerate(raws, 1):
        conn.execute("INSERT INTO replay_data VALUES (?, ?, 0)", (i, raw))
    conn.commit()

    seen: list[tuple[int, int]] = []
    migrated, sealed = migrate_from_replay_data(
        conn, batch_size=BLOCK_SIZE,
        progress=lambda d, t: seen.append((d, t)))
    assert migrated == len(raws)
    assert seen and seen[-1][0] == len(raws) and seen[-1][1] == len(raws)
    # 允许中途取消：至少不抛异常、不破坏数据
    cancelled = {"n": 0}

    def cancel() -> bool:
        cancelled["n"] += 1
        return cancelled["n"] > 1

    another = [make_evf(events=_ALL_EVENTS * 2) for _ in range(BLOCK_SIZE * 2)]
    for i, raw in enumerate(another, len(raws) + 1):
        conn.execute("INSERT INTO replay_data VALUES (?, ?, 0)", (i, raw))
    conn.commit()
    migrate_from_replay_data(conn, batch_size=BLOCK_SIZE, cancelled=cancel)
    assert conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] > 0


def test_migrate_uses_read_conn_and_short_writer_batches(tmp_path):
    """read 在维护连接，写只走 write()；回调内不做 CPU 压缩。"""
    import plugins.history.replay_store as replay_store

    path = tmp_path / "history.db"
    reader = sqlite3.connect(path)
    writer = sqlite3.connect(path)
    try:
        ensure_tables(reader)
        reader.execute(
            "CREATE TABLE replay_data (replay_id INTEGER PRIMARY KEY, "
            "raw_data BLOB, compressed INTEGER)")
        reader.commit()
        raws = [make_evf(events=_ALL_EVENTS * 2) for _ in range(BLOCK_SIZE + 2)]
        for i, raw in enumerate(raws, 1):
            reader.execute("INSERT INTO replay_data VALUES (?, ?, 0)", (i, raw))
        reader.commit()

        def dispatch(callback):
            # 记录回调期间是否发生 zlib 压缩（CPU 不得在写线程里做）
            calls = []
            orig_compress = zlib.compress

            def tracking(data, *a, **k):
                calls.append(len(data))
                return orig_compress(data, *a, **k)

            import unittest.mock as mock
            with mock.patch.object(replay_store.zlib, "compress", tracking):
                result = callback(writer)
            writer.commit()
            assert calls == [], "写线程回调内不得压缩"
            return result

        migrated, sealed = migrate_from_replay_data(reader, write=dispatch)
        assert migrated == len(raws)
        assert sealed >= 1
        for i, raw in enumerate(raws, 1):
            assert read_raw_data(reader, i) == raw
    finally:
        reader.close()
        writer.close()


def test_finalize_uses_write_dispatch_and_preserves_caller_tx(tmp_path):
    path = tmp_path / "history.db"
    reader = sqlite3.connect(path)
    writer = sqlite3.connect(path)
    try:
        ensure_tables(reader)
        reader.execute(
            "CREATE TABLE replay_data (replay_id INTEGER PRIMARY KEY, "
            "raw_data BLOB, compressed INTEGER)")
        raws = [make_evf(events=_ALL_EVENTS * i) for i in (1, 2)]
        _seed_legacy(reader, raws)

        calls = []

        def dispatch(callback):
            calls.append(True)
            out = callback(writer)
            writer.commit()
            return out

        assert finalize_migration(reader, write=dispatch) is True
        assert calls
        assert reader.execute(
            "SELECT COUNT(*) FROM replay_data").fetchone()[0] == 0
    finally:
        reader.close()
        writer.close()


def test_vacuum_is_not_automatic(conn):
    """finalize 不得自动 VACUUM（会长时间独占写锁）。"""
    import plugins.history.replay_store as replay_store
    import unittest.mock as mock

    conn.execute("CREATE TABLE replay_data (replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)")
    _seed_legacy(conn, [make_evf()])
    with mock.patch.object(replay_store, "vacuum",
                           side_effect=AssertionError("不得自动 VACUUM")) as m:
        assert finalize_migration(conn) is True
    assert not m.called


# ── 有界并行准备（迁移 / 清理）────────────────────────────────

def _legacy_data(conn, raws):
    """只建旧表数据，不写新存储，供迁移测试使用。"""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS replay_data ("
        "replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)")
    for i, raw in enumerate(raws, 1):
        conn.execute("INSERT INTO replay_data VALUES (?, ?, 0)", (i, raw))
    conn.commit()


def test_migrate_with_prepare_pool_keeps_bit_exact_data(legacy_replay_data):
    """并行准备多个批次后按序提交，数据仍需逐字节一致。"""
    from plugins.history.parallel_prepare import PreparePool

    conn = legacy_replay_data
    raws = [make_evf(events=_ALL_EVENTS * (i % 4 + 1))
            for i in range(BLOCK_SIZE * 3 + 5)]
    _legacy_data(conn, raws)

    stats: dict[str, int] = {}
    seen: list[tuple[int, int]] = []
    with PreparePool(workers=2, max_in_flight=3) as pool:
        migrated, sealed = migrate_from_replay_data(
            conn, progress=lambda d, t: seen.append((d, t)),
            prepare=pool, stats=stats)

    assert migrated == len(raws)
    assert sealed >= 1
    assert seen[-1] == (len(raws), len(raws))
    assert stats.get("conflicts", 0) == 0
    assert stats.get("failed_batches", 0) == 0
    assert finalize_migration(conn) is True
    assert conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == 0
    # 清空旧表后，逐字节读取验证的是新存储路径。
    for i, raw in enumerate(raws, 1):
        assert read_raw_data(conn, i) == raw


def test_migrate_prepare_failure_keeps_legacy_rows(legacy_replay_data,
                                                   monkeypatch):
    """准备阶段抛异常时停止提交，旧表数据原样保留。"""
    from plugins.history import replay_store
    from plugins.history.parallel_prepare import PreparePool

    conn = legacy_replay_data
    raws = [make_evf() for _ in range(BLOCK_SIZE * 2)]
    _legacy_data(conn, raws)

    def boom(*_args, **_kwargs):
        raise RuntimeError("prepare failed")

    monkeypatch.setattr(replay_store, "_prepare_migration_batch", boom)
    stats: dict[str, int] = {}
    with PreparePool(workers=2) as pool:
        migrated, _sealed = migrate_from_replay_data(
            conn, prepare=pool, stats=stats)

    assert migrated == 0
    assert stats.get("failed_batches") == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM replay_data").fetchone()[0] == len(raws)


def test_cleanup_with_prepare_pool_removes_only_low_value(tmp_path):
    """并行清理多个分块只删除低完成率录像，其余可原样读出。"""
    from plugins.history.db import db_connection
    from plugins.history.parallel_prepare import PreparePool

    path = tmp_path / "history.db"
    with db_connection(path) as conn:
        conn.execute(
            "CREATE TABLE history ("
            "replay_id INTEGER PRIMARY KEY, bbbv INTEGER, bbbv_solved INTEGER)")
        ensure_tables(conn)
        raws = {rid: make_evf(checksum=bytes([rid]) * 32)
                for rid in range(1, 9)}
        solved = {1: 5, 2: 100, 3: 10, 4: 100, 5: 100, 6: 1, 7: 100, 8: 100}
        for rid, raw in raws.items():
            conn.execute("INSERT INTO history VALUES (?, 100, ?)",
                         (rid, solved[rid]))
            write_record(conn, rid, raw)
        conn.commit()
        # 每块 2 条 → 4 个分块，便于并行准备
        while seal_staging(conn, limit=2) > 0:
            conn.commit()
        total = len(conn.execute(
            "SELECT seg_id FROM replay_segment").fetchall())
        assert total >= 2

        progress: list[tuple[int, int]] = []
        stats: dict[str, int] = {}
        with PreparePool(workers=2, max_in_flight=3) as pool:
            removed = cleanup_low_value_replays(
                conn, 30, progress=lambda d, t: progress.append((d, t)),
                prepare=pool, stats=stats)

        assert removed == 3
        assert stats.get("conflict_segments", 0) == 0
        assert progress[-1] == (3, 3)
        for rid, raw in raws.items():
            if rid in (1, 3, 6):
                assert read_raw_data(conn, rid) is None
            else:
                assert read_raw_data(conn, rid) == raw
        assert conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 8


def test_cleanup_reports_progress_only_for_actual_removals(
        tmp_path, monkeypatch):
    """提交被拒时不得把候选计数当成已删除数上报。"""
    from plugins.history import replay_store
    from plugins.history.db import db_connection
    from plugins.history.parallel_prepare import PreparePool

    path = tmp_path / "history.db"
    with db_connection(path) as conn:
        conn.execute(
            "CREATE TABLE history ("
            "replay_id INTEGER PRIMARY KEY, bbbv INTEGER, bbbv_solved INTEGER)")
        ensure_tables(conn)
        for rid, solved in ((1, 1), (2, 100), (3, 1)):
            conn.execute("INSERT INTO history VALUES (?, 100, ?)", (rid, solved))
            write_record(conn, rid, make_evf(checksum=bytes([rid]) * 32))
        conn.commit()
        while seal_staging(conn, limit=3) > 0:
            conn.commit()

        # 模拟写事务内的快照复核失败：计划不得被计为已删除
        monkeypatch.setattr(
            replay_store, "_apply_cleanup_plan",
            lambda *args, **kwargs: False)

        progress: list[tuple[int, int]] = []
        stats: dict[str, int] = {}
        with PreparePool(workers=2) as pool:
            removed = cleanup_low_value_replays(
                conn, 30, progress=lambda d, t: progress.append((d, t)),
                prepare=pool, stats=stats)

        assert removed == 0
        assert stats.get("conflict_segments", 0) >= 1
        assert all(done == 0 for done, _total in progress)
        assert read_raw_data(conn, 1) is not None


def test_migration_retries_records_skipped_by_concurrent_change(
        legacy_replay_data, monkeypatch):
    """批次内被并发改动跳过的录像，应在流水线排空后重扫补齐。"""
    from plugins.history import replay_store
    from plugins.history.parallel_prepare import PreparePool

    conn = legacy_replay_data
    raws = [make_evf(checksum=bytes([i]) * 32) for i in range(1, 10)]
    _legacy_data(conn, raws)

    original = replay_store._apply_staging_batch
    state = {"first": True}

    def partial(target, usable, snapshots, prepared):
        if state["first"] and len(usable) > 1:
            state["first"] = False
            # 模拟其中一条在准备后被改写：只插入其余记录
            return original(target, usable[:-2], snapshots, prepared)
        return original(target, usable, snapshots, prepared)

    monkeypatch.setattr(replay_store, "_apply_staging_batch", partial)
    stats: dict[str, int] = {}
    with PreparePool(workers=2) as pool:
        migrated, _sealed = migrate_from_replay_data(
            conn, prepare=pool, stats=stats)

    assert stats.get("conflicts", 0) == 2
    assert "abandoned_records" not in stats
    assert migrated == len(raws)
    assert conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == len(raws)
    assert finalize_migration(conn) is True
    assert conn.execute("SELECT COUNT(*) FROM replay_data").fetchone()[0] == 0
    # 旧表已清空，读取只能从迁移后的新存储成功。
    for i, raw in enumerate(raws, 1):
        assert read_raw_data(conn, i) == raw
