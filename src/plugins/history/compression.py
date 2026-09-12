"""录像数据压缩/解压工具

使用 zlib 压缩 raw_data (BLOB)，优先按 compressed 列标志判断是否已压缩，
无标志时回退到 magic byte 前缀检测。
"""

from __future__ import annotations

import zlib

# zlib 压缩数据以 0x78 开头 (level 6 = 0x78 0x9C)
_ZLIB_MAGIC = b'\x78'


def compress(data: bytes | None) -> bytes | None:
    """压缩数据，返回压缩后的 bytes。None 输入返回 None。"""
    if data is None:
        return None
    return zlib.compress(data, level=6)


def decompress(
    data: bytes | None,
    compressed: bool | None = None,
) -> bytes | None:
    """
    解压数据。优先按 compressed 标志判断：
    - None 输入 → None
    - compressed=True → 已压缩，直接解压
    - compressed=False → 未压缩，原样返回
    - compressed=None → 无标志，回退 magic byte 检测（兼容极旧数据）
    """
    if data is None:
        return None
    if compressed is None:
        # 兜底：按 magic byte 检测
        if data[:1] == _ZLIB_MAGIC:
            return zlib.decompress(data)
        return data
    if compressed:
        return zlib.decompress(data)
    return data


def is_compressed(data: bytes | None) -> bool:
    """判断数据是否已压缩"""
    if data is None or len(data) == 0:
        return False
    return data[:1] == _ZLIB_MAGIC
