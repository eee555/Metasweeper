"""原子 JSON 写入工具。

先写入同目录临时文件并 fsync，再用 ``os.replace`` 原子替换目标文件，
避免进程中断或写入失败时留下半截 JSON。
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

__all__ = ["atomic_write_json"]


def atomic_write_json(
    path: str | Path,
    data: Any,
    *,
    ensure_ascii: bool = False,
    keep_backup: bool = False,
    trailing_newline: bool = True,
) -> None:
    """把 ``data`` 以 JSON 形式原子写入 ``path``。

    Args:
        path: 目标文件路径，父目录不存在时自动创建。
        data: 可 JSON 序列化的对象。
        ensure_ascii: 是否转义非 ASCII 字符（默认保留原文）。
        keep_backup: 覆盖前是否把旧文件复制为 ``<name>.bak``。
        trailing_newline: 是否在文件末尾追加换行（保持各调用方原有格式）。

    Raises:
        OSError: 写入或替换失败；临时文件会被清理，目标文件保持原样。
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=ensure_ascii, indent=2)
    if trailing_newline:
        payload += "\n"

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
        # 内容仍走 Path.write_text，保持与旧实现一致的编码/换行行为。
        tmp_path.write_text(payload, encoding="utf-8")
        with open(tmp_path, "r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        if keep_backup and target.exists():
            shutil.copy2(target, target.with_name(target.name + ".bak"))
        os.replace(tmp_path, target)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
