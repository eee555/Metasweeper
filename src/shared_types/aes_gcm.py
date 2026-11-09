"""AES-GCM 加解密工具（统一使用 cryptography 后端）。

本模块是主进程与插件管理器进程共用的加密入口，统一收敛此前分散在各
模块中的 AES-GCM 实现。所有持久化密文保持既有字节布局不变::

    nonce(12 字节) + tag(16 字节) + ciphertext

即 stats.dat / 插件存档的 v0 密文格式，保证升级前后文件互相兼容。
"""
from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_LEN = 12
_TAG_LEN = 16


class GCMCipher:
    """持有密钥的 AES-GCM 编解码器，可复用以避免逐条重建上下文。"""

    def __init__(self, key: bytes) -> None:
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        """加密并返回 nonce + tag + ciphertext。"""
        nonce = os.urandom(_NONCE_LEN)
        # AESGCM.encrypt 返回 ciphertext + tag
        sealed = self._aesgcm.encrypt(nonce, plaintext, None)
        ciphertext, tag = sealed[:-_TAG_LEN], sealed[-_TAG_LEN:]
        return nonce + tag + ciphertext

    def decrypt(self, blob: bytes) -> bytes:
        """解密 nonce + tag + ciphertext；校验失败抛 InvalidTag。"""
        nonce = blob[:_NONCE_LEN]
        tag = blob[_NONCE_LEN:_NONCE_LEN + _TAG_LEN]
        ciphertext = blob[_NONCE_LEN + _TAG_LEN:]
        return self._aesgcm.decrypt(nonce, ciphertext + tag, None)


def encrypt_gcm(key: bytes, plaintext: bytes) -> bytes:
    """一次性加密，返回 nonce + tag + ciphertext。"""
    return GCMCipher(key).encrypt(plaintext)


def decrypt_gcm(key: bytes, blob: bytes) -> bytes:
    """一次性解密 nonce + tag + ciphertext。"""
    return GCMCipher(key).decrypt(blob)
