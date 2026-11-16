"""列式编解码的正确性与性能约束回归测试。

性能断言只做宽松的数量级检查（相对同一进程内的简单基线），用于捕捉
「又退回逐字节 append」这类退化，不作为精确基准。
"""
from __future__ import annotations

import random
import struct
import time

import pytest

from plugins.history.replay_codec import (
    UnsupportedReplayError,
    decode_group,
    encode_group,
    split_evf,
)

from tests.replay.test_replay_store import make_evf


def _varied_events(seed: int, count: int = 600) -> bytes:
    rnd = random.Random(seed)
    out = bytearray()
    for _ in range(count):
        etype = rnd.choice([1, 2, 3, 9, 81, 100, 255])
        out.append(etype)
        if etype in (1, 2, 3, 9):
            out += bytes(rnd.randrange(256) for _ in range(5))
        elif etype == 255:
            out += bytes(rnd.randrange(256) for _ in range(2))
        elif etype == 81:
            out += bytes([rnd.randrange(256)])
        else:
            out += bytes([rnd.randrange(256), rnd.randrange(16),
                          rnd.randrange(30)])
    return bytes(out)


def _varied_triples(count: int = 128) -> list[tuple[bytes, bytes, bytes]]:
    return [
        split_evf(make_evf(row=16, col=30, events=_varied_events(i)))
        for i in range(count)
    ]


def test_roundtrip_with_varied_events_is_bit_exact():
    triples = _varied_triples()
    payload = encode_group(triples)
    restored = decode_group(payload, len(triples))
    assert restored == triples
    assert [h + e + t for h, e, t in restored] == \
        [h + e + t for h, e, t in triples]


def test_roundtrip_mixed_sizes_and_event_kinds():
    triples = [
        split_evf(make_evf(row=r, col=c, events=_varied_events(i, 40)))
        for i, (r, c) in enumerate(
            ((8, 8), (16, 16), (16, 30), (9, 11), (24, 30)))
    ]
    payload = encode_group(triples)
    assert decode_group(payload, len(triples)) == triples


def test_roundtrip_without_mouse_events():
    """没有鼠标事件时 dt/dx/dy 列为空，解码不得误判为错位。"""
    events = b"\x51\x05" + b"\x64\x07\x03\x04" + b"\xff\x01\x2c"
    triples = [split_evf(make_evf(events=events)) for _ in range(4)]
    payload = encode_group(triples)
    assert decode_group(payload, len(triples)) == triples


def test_roundtrip_with_index_events():
    """200/201 指标事件：定长与变长载荷混排。"""
    number = b"\xc8" + bytes([1]) + struct.pack(">H", 7) + \
        struct.pack("<d", 3.14)
    text = b"\xc9" + bytes([2]) + struct.pack(">H", 8) + b"flag\x00"
    events = b"\x01\x01\x00\x01\x00\x02" + number + text
    triples = [split_evf(make_evf(events=events)) for _ in range(3)]
    payload = encode_group(triples)
    assert decode_group(payload, len(triples)) == triples


def test_decode_rejects_truncated_columns():
    triples = _varied_triples(8)
    payload = encode_group(triples)
    with pytest.raises(UnsupportedReplayError):
        decode_group(payload[:len(payload) - 4], len(triples))


def test_encode_rejects_unknown_event_type():
    bad = make_evf(events=b"\x7f\x01\x02\x03")
    triple = (bad[:10], b"\x7f\x01\x02\x03", bad[-35:])
    with pytest.raises(UnsupportedReplayError):
        encode_group([triple])


def test_encode_rejects_early_end_marker():
    triple = (b"head", b"\x01\x01\x00\x01\x00\x02\x00", b"tail")
    with pytest.raises(UnsupportedReplayError):
        encode_group([triple])


def test_event_size_table_covers_all_known_events():
    """事件尺寸表必须覆盖所有已知定长事件，且不含变长事件。"""
    from plugins.history import replay_codec

    # 与 evf 规范一致的显式期望值，避免实现内部自证
    expected = {
        1: 6, 2: 6, 3: 6, 4: 6, 5: 6, 6: 6, 7: 6,
        8: 6, 9: 6, 10: 6, 11: 6, 12: 6,
        81: 2, 82: 2, 83: 2, 99: 2,
        100: 4, 101: 4, 102: 4, 103: 4, 104: 4, 105: 4, 106: 4,
        107: 4, 108: 4, 110: 4, 111: 4, 114: 4, 115: 4, 116: 4,
        118: 4, 120: 4, 121: 4,
        200: 12,
        255: 3,
    }
    assert replay_codec._EVENT_SIZES == expected
    # 变长字符串指标不得进入定长表
    assert replay_codec._INDEX_STRING not in replay_codec._EVENT_SIZES
    # 保留编号不参与新编码，但旧列式块仍由单独的兼容路径解码。
    assert replay_codec._LEGACY_RESERVED_BOARD_EVENTS == {
        109, 112, 113, 117, 119,
    }
    # 结束标记不是事件
    assert replay_codec._END_MARK not in replay_codec._EVENT_SIZES


def test_reserved_board_events_are_rejected_for_new_encoding():
    from plugins.history import replay_codec

    for etype in replay_codec._LEGACY_RESERVED_BOARD_EVENTS:
        event = bytes((etype, 1, 2, 3))
        bad = make_evf(events=event)
        with pytest.raises(UnsupportedReplayError):
            split_evf(bad)
        with pytest.raises(UnsupportedReplayError):
            encode_group([(b"head", event, b"tail")])


def test_decode_keeps_compatibility_with_legacy_reserved_events(monkeypatch):
    from plugins.history import replay_codec

    triple = (b"legacy head", bytes((109, 1, 2, 3)), b"legacy tail")
    current_sizes = replay_codec._EVENT_SIZES
    legacy_sizes = {**current_sizes, **{code: 4 for code in
                                        replay_codec._LEGACY_RESERVED_BOARD_EVENTS}}
    with monkeypatch.context() as patcher:
        patcher.setattr(replay_codec, "_EVENT_SIZES", legacy_sizes)
        old_payload = encode_group([triple])

    assert replay_codec._EVENT_SIZES is current_sizes
    assert decode_group(old_payload, 1) == [triple]


def test_encode_is_not_quadratic_in_event_count():
    """宽松性能护栏：编码/解码应远快于逐字节 reinterpret 的实现。

    旧实现（逐字节 append）在同一负载下约 100ms/批；这里给出 5 倍余量，
    只用于捕捉明显退化（例如换回 Python 层逐条拼接）。
    """
    triples = _varied_triples(64)
    start = time.perf_counter()
    payload = encode_group(triples)
    encode_cost = time.perf_counter() - start

    start = time.perf_counter()
    decode_group(payload, len(triples))
    decode_cost = time.perf_counter() - start

    total_bytes = sum(len(h) + len(e) + len(t) for h, e, t in triples)
    # 每 MB 数据不超过 150ms（实测约 20-40ms/MB）
    assert encode_cost < max(0.5, total_bytes / 1_000_000 * 0.150)
    assert decode_cost < max(0.5, total_bytes / 1_000_000 * 0.150)
