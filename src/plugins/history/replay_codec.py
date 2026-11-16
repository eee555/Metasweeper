"""录像分块列式编解码（零推导风险）。

设计原则：
- 不解析字段含义、不重建头部、不重算 checksum，**不改动任何一个字节**。
- 只按 evf v4 规范定位「头部 / 事件流 / 尾部」边界，把事件流的字节
  按列重排以提高跨记录压缩率；解码时原样拼回，保证 bit-exact。
- 头部与尾部（含 32B 官方 checksum）整段原样保留。
- 任何不认识的 version / 事件类型 / 结构异常，一律抛
  ``UnsupportedReplayError``，由调用方降级为逐条 zlib 原样存储。

块布局（`encode_group` 输出）：
    [10 × 4B 各区长度][heads][tails][etype][dt][dx][dy][other]
    [counts(varint)][head_lens(4B*n)][tail_lens(4B*n)]
其中 heads/tails 为各条原始字节的拼接，其余为事件流按列拆出的字节。

参考：https://github.com/eee555/ms_toollib/blob/main/evf%E6%A0%87%E5%87%86.md
"""

from __future__ import annotations

import struct
from typing import Sequence

__all__ = [
    "UnsupportedReplayError",
    "CODEC_RAW",
    "CODEC_ZLIB",
    "CODEC_LZMA_COLUMNAR",
    "split_evf",
    "encode_group",
    "decode_group",
]

# replay_index.codec 取值
CODEC_RAW = 0               # 未压缩（极旧数据）
CODEC_ZLIB = 1              # 逐条 zlib（现状 / 降级回退）
CODEC_LZMA_COLUMNAR = 3     # 分块列式 + lzma

_U32 = struct.Struct("<I")
_U16 = struct.Struct(">H")

_MOUSE = frozenset(range(1, 13))          # mv/lc/lr/rc/rr/mc/mr/pf/cc/l/r/m
_GAME_STATE = frozenset({81, 82, 83, 99})  # replay/win/fail/error
_BOARD_EVENT = frozenset(range(100, 122)) | frozenset(
    {110, 111, 114, 115, 116, 118, 120, 121}
)
_PAUSE = 255
_INDEX_NUMBER = 200
_INDEX_STRING = 201
_END_MARK = 0

# 事件类型 → 事件总字节数（含 1B 类型字节）。
# 变长字符串指标事件（_INDEX_STRING）不在表中，需按 \0 外推。
_EVENT_SIZES: dict[int, int] = {
    **{t: 6 for t in _MOUSE},          # 1B type + 1B dt + 2B dx + 2B dy
    **{t: 2 for t in _GAME_STATE},     # 1B type + 1B dt
    **{t: 4 for t in _BOARD_EVENT},    # 1B type + 1B dt + 1B row + 1B col
    _PAUSE: 3,                         # 1B type + 2B dt
    _INDEX_NUMBER: 12,                 # 1B type + 1B dt + 2B index + 8B float64
}

# 各区在块头长度表中的顺序
_REGIONS = ("heads", "tails", "etype", "dt", "dx", "dy", "other",
            "counts", "head_lens", "tail_lens")
_REGION_COUNT = len(_REGIONS)


class UnsupportedReplayError(ValueError):
    """录像结构无法安全定位/重排，调用方应降级为逐条 zlib 原样存储。"""


def _scan_events(b: bytes, start: int) -> int:
    """从 start 正向逐事件扫描，返回 ``\\0`` 结束标记的偏移（不含）。"""
    p = start
    size = len(b)
    sizes = _EVENT_SIZES
    while p < size:
        etype = b[p]
        step = sizes.get(etype)
        if step is None:
            if etype == _END_MARK:
                return p
            if etype != _INDEX_STRING:
                raise UnsupportedReplayError(f"未知事件类型 {etype}")
            try:
                end = b.index(0, p + 4)
            except ValueError as exc:
                raise UnsupportedReplayError(
                    f"字符串指标事件缺少 \\0 终止符 @ {p}") from exc
            step = end - p + 1
        p += step
        if p > size:
            raise UnsupportedReplayError(f"事件越过文件末尾 @ {p}")
    raise UnsupportedReplayError("未找到事件结束标记")


def split_evf(b: bytes) -> tuple[bytes, bytes, bytes]:
    """把一条 evf 切成 (head, events, tail)，三者拼接后必须等于原 b。

    head  : 版本号到指标键名表（原样）
    events: 事件流（不含 \\0 结束标记）
    tail  : \\0 结束标记 + 2B 校验码长度 + 校验码（原样）

    Raises:
        UnsupportedReplayError: 非 v4、结构异常或事件类型未知。
    """
    if not b:
        raise UnsupportedReplayError("空录像")
    size = len(b)
    p = 0
    if p + 1 > size:
        raise UnsupportedReplayError("录像过短")
    version = b[p]
    p += 1
    if version != 4:
        # 只支持 v4；v0/v2/v3 与转码录像一律降级
        raise UnsupportedReplayError(f"不支持的 evf 版本 {version}")
    # flags / settings / row / column
    if p + 4 > size:
        raise UnsupportedReplayError("头部截断")
    flags = b[p]
    p += 4
    row = b[p - 2]
    col = b[p - 1]
    # mine_num(2) pix(1) mode(2) bbbv(2) rtime(4) country(2) start(8) end(8)
    p += 2 + 1 + 2 + 2 + 4 + 2 + 8 + 8
    if p > size:
        raise UnsupportedReplayError("定长头部截断")

    def cstr() -> None:
        nonlocal p
        end = b.find(0, p)
        if end < 0:
            raise UnsupportedReplayError("字符串缺少 \\0 终止符")
        p = end + 1

    cstr()                                   # software
    if flags & 0x08:                         # 转码录像：多两个字符串字段
        cstr()                               # 转码软件
        cstr()                               # 编码方式
    cstr()                                   # player_identifier
    cstr()                                   # race_identifier
    cstr()                                   # unique_identifier
    if p + 2 > size:
        raise UnsupportedReplayError("uuid 长度字段截断")
    (uuid_len,) = _U16.unpack_from(b, p)
    p += 2 + uuid_len
    p += (row * col + 7) // 8                # 雷图 bitmap
    if p + 2 > size:
        raise UnsupportedReplayError("指标数量字段截断")
    (metric_count,) = _U16.unpack_from(b, p)
    p += 2
    for _ in range(metric_count):
        cstr()                               # 指标键名
    if p > size:
        raise UnsupportedReplayError("头部越过文件末尾")

    head_end = p
    events_end = _scan_events(b, head_end)
    # 尾部至少要有 \0 + 2B 校验码长度
    if events_end + 3 > size:
        raise UnsupportedReplayError("尾部截断")
    (ck_len,) = _U16.unpack_from(b, events_end + 1)
    if events_end + 3 + ck_len != size:
        raise UnsupportedReplayError(
            f"校验码长度不符: 期望尾部 {3 + ck_len}B, 实际 {size - events_end}B")
    return b[:head_end], b[head_end:events_end], b[events_end:]


def _varint(v: int) -> bytes:
    out = bytearray()
    while v >= 0x80:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v)
    return bytes(out)


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if pos >= len(data):
            raise UnsupportedReplayError("varint 截断")
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value, pos
        shift += 7


def encode_group(triples: list[tuple[bytes, bytes, bytes]]) -> bytes:
    """把一组 (head, events, tail) 编码成列式字节流。

    用 ``bytearray.extend`` 直接搬运切片：每个事件只有常数次 Python 操作，
    字节拷贝由 C 层完成，比逐字节 ``append`` 快约一倍。
    """
    heads = bytearray()
    tails = bytearray()
    etype_col = bytearray()
    dt_col = bytearray()
    dx_col = bytearray()
    dy_col = bytearray()
    other_col = bytearray()
    counts = bytearray()
    head_lens = bytearray()
    tail_lens = bytearray()
    sizes = _EVENT_SIZES

    for head, events, tail in triples:
        heads += head
        tails += tail
        head_lens += _U32.pack(len(head))
        tail_lens += _U32.pack(len(tail))
        p = 0
        count = 0
        size = len(events)
        while p < size:
            etype = events[p]
            step = sizes.get(etype)
            if step is None:
                if etype == _INDEX_STRING:
                    end = events.find(0, p + 4)
                    if end < 0:
                        raise UnsupportedReplayError("字符串指标缺少 \\0")
                    step = end - p + 1
                else:
                    raise UnsupportedReplayError(f"未知事件类型 {etype}")
            if p + step > size:
                raise UnsupportedReplayError("事件流截断")
            etype_col.append(etype)
            if etype in _MOUSE:
                dt_col += events[p + 1:p + 2]
                dx_col += events[p + 2:p + 4]
                dy_col += events[p + 4:p + 6]
            else:
                # etype 已在 etype 列，其余原样搬入 other
                other_col += events[p + 1:p + step]
            p += step
            count += 1
        counts += _varint(count)

    parts = (
        bytes(heads), bytes(tails), bytes(etype_col), bytes(dt_col),
        bytes(dx_col), bytes(dy_col), bytes(other_col), bytes(counts),
        bytes(head_lens), bytes(tail_lens),
    )
    header = b"".join(_U32.pack(len(x)) for x in parts)
    return header + b"".join(parts)


def _unpack_lengths(table: bytes, count: int) -> tuple[int, ...]:
    """一次解出整张 4B 长度表（替代逐条 ``unpack_from``）。"""
    return struct.unpack(f"<{count}I", table)


def _columns(data: bytes, lengths: Sequence[int]) -> list[bytes]:
    """按长度表把连续区切成切片（C 层完成，无逐字节搬运）。"""
    out: list[bytes] = []
    pos = 0
    for length in lengths:
        out.append(data[pos:pos + length])
        pos += length
    return out


def decode_group(blob: bytes, record_count: int) -> list[tuple[bytes, bytes, bytes]]:
    """还原成 [(head, events, tail), ...]，必须与 encode_group 输入完全一致。"""
    head_size = _REGION_COUNT * 4
    if len(blob) < head_size:
        raise UnsupportedReplayError("列式块头截断")
    sizes = [_U32.unpack_from(blob, 4 * i)[0] for i in range(_REGION_COUNT)]
    pos = head_size
    regions: list[bytes] = []
    for size in sizes:
        if pos + size > len(blob):
            raise UnsupportedReplayError("列式块区域截断")
        regions.append(blob[pos:pos + size])
        pos += size
    if pos != len(blob):
        raise UnsupportedReplayError("列式块存在多余字节")
    (heads, tails, etype_col, dt_col, dx_col, dy_col,
     other_col, counts, head_lens, tail_lens) = regions

    if len(head_lens) != record_count * 4 or len(tail_lens) != record_count * 4:
        raise UnsupportedReplayError("长度表条数不符")

    event_counts: list[int] = []
    q = 0
    for _ in range(record_count):
        value, q = _read_varint(counts, q)
        event_counts.append(value)
    if q != len(counts):
        raise UnsupportedReplayError("事件数表存在多余字节")

    # 一次解出整表长度，再按长度切片；避免逐条 unpack 与逐字节 append。
    head_lengths = _unpack_lengths(head_lens, record_count)
    tail_lengths = _unpack_lengths(tail_lens, record_count)
    head_parts = _columns(heads, head_lengths)
    tail_parts = _columns(tails, tail_lengths)

    total_events = len(etype_col)
    if total_events != sum(event_counts):
        raise UnsupportedReplayError("etype 列条数不符")

    sizes = _EVENT_SIZES
    mouse = _MOUSE
    out: list[tuple[bytes, bytes, bytes]] = []
    epos = dp = xp = yp = op = 0
    for i in range(record_count):
        events = bytearray()
        for _ in range(event_counts[i]):
            if epos >= total_events:
                raise UnsupportedReplayError("etype 列截断")
            etype = etype_col[epos]
            epos += 1
            events.append(etype)
            if etype in mouse:
                if dp >= len(dt_col) or xp + 2 > len(dx_col) \
                        or yp + 2 > len(dy_col):
                    raise UnsupportedReplayError("鼠标事件列截断")
                events.append(dt_col[dp])
                dp += 1
                events += dx_col[xp:xp + 2]
                xp += 2
                events += dy_col[yp:yp + 2]
                yp += 2
            else:
                step = sizes.get(etype)
                if step is None:
                    # 变长事件：载荷以 dt(1B)+index(2B) 开头，这三字节可能
                    # 含 \0，必须从字符串起点（op+3）开始找终止符。
                    end = other_col.find(0, op + 3)
                    if end < 0:
                        raise UnsupportedReplayError("字符串指标列缺少 \\0")
                    payload = end - op + 1
                else:
                    payload = step - 1
                if op + payload > len(other_col):
                    raise UnsupportedReplayError("other 列截断")
                events += other_col[op:op + payload]
                op += payload
        out.append((head_parts[i], bytes(events), tail_parts[i]))

    # 所有列必须恰好消费完，防止静默错位
    if (epos != total_events or dp != len(dt_col)
            or xp != len(dx_col) or yp != len(dy_col)
            or op != len(other_col)):
        raise UnsupportedReplayError("列式块存在未消费字节")
    return out
