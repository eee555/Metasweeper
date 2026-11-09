"""录像分块列式存储回归测试。

覆盖：
- evf 边界定位与 split/重拼 bit-exact
- 列式 encode/decode roundtrip（含各类事件、各种尺寸）
- 不支持结构（非 v4 / 损坏）必须抛 UnsupportedReplayError
- 分块封口 / 随机读 / sha256 校验 / tombstone / 回退
- 旧 replay_data 迁移 + finalize 校验
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
    UnsupportedReplayError,
    decode_group,
    encode_group,
    split_evf,
)
from plugins.history.replay_store import (
    BLOCK_SIZE,
    ReplayIntegrityError,
    ensure_tables,
    finalize_migration,
    mark_deleted,
    migrate_from_replay_data,
    read_raw_data,
    restore_deleted,
    seal_staging,
    write_record,
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


def test_write_and_read_before_seal(conn):
    b = make_evf()
    write_record(conn, 1, b)
    conn.commit()
    assert read_raw_data(conn, 1) == b


def test_seal_and_random_read(conn, monkeypatch):
    blobs = [make_evf(row=8, col=8, events=_ALL_EVENTS * (i % 9 + 1))
             for i in range(BLOCK_SIZE)]
    for i, b in enumerate(blobs, 1):
        write_record(conn, i, b)
        # 阻止自动封口，最后手动封
        monkeypatch.setattr("plugins.history.replay_store._maybe_seal",
                            lambda c: None)
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
    restore_deleted(conn, 1)
    conn.commit()
    assert read_raw_data(conn, 1) == b


def test_unsupported_replay_falls_back_to_zlib(conn):
    """非 v4 录像不能列式化，但必须仍能原样读出。"""
    bad = make_evf(version=3)
    write_record(conn, 1, bad)
    conn.commit()
    assert read_raw_data(conn, 1) == bad
    # 强制封口不应把它塞进块
    assert seal_staging(conn) == 0
    assert read_raw_data(conn, 1) == bad


def test_migrate_from_replay_data_and_finalize(conn):
    blobs = [make_evf(row=8, col=8, events=_ALL_EVENTS * (i % 5 + 1))
             for i in range(BLOCK_SIZE + 7)]
    conn.execute("""CREATE TABLE replay_data (
        replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)""")
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


def test_finalize_refuses_when_integrity_broken(conn):
    conn.execute("""CREATE TABLE replay_data (
        replay_id INTEGER PRIMARY KEY, raw_data BLOB, compressed INTEGER)""")
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
