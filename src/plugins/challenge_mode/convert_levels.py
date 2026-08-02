"""
将 levels.json 转换为加密的 levels.dat（AES-256-GCM）。
运行方式：python convert_levels.py
"""
from __future__ import annotations

import json
import base64
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

LEVELS_KEY = b"Ch4ll3ng3M0deK3y!2026SecureKey!!"


def convert():
    src = Path(__file__).parent.parent.parent / "levels.json"
    dst = Path(__file__).parent / "levels.dat"

    data = json.loads(src.read_text(encoding="utf-8"))

    all_levels = []
    for diff_str in sorted(data.keys(), key=lambda x: int(x)):
        all_levels.extend(data[diff_str])

    plaintext = json.dumps(all_levels, ensure_ascii=False).encode("utf-8")

    nonce = get_random_bytes(12)
    cipher = AES.new(LEVELS_KEY, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)

    dst.write_bytes(base64.b64encode(nonce + tag + ciphertext))
    print(f"已生成 {dst}，共 {len(all_levels)} 关，明文 {len(plaintext)} 字节")


if __name__ == "__main__":
    convert()
