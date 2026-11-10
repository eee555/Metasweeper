"""协议层补测：aes_gcm、sounds、shared/base、serializer。

全部为纯函数/纯数据测试，不开端口、不启线程、不需要真实 QApplication
（只有 sounds.default_*_label 会调用 QCoreApplication.translate，用
QApplication offscreen 满足）。
"""
from __future__ import annotations

import enum
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import msgspec
import pytest
from PySide6.QtWidgets import QApplication
from cryptography.exceptions import InvalidTag

from lib_zmq_plugins.serializer import Serializer, _dec_hook, _enc_hook, _make_union
from lib_zmq_plugins.shared.base import (
    BaseCommand,
    BaseEvent,
    BaseQuery,
    BaseQueryResult,
    CommandResponse,
    SyncCommand,
    get_event_tag,
    get_struct_tag,
    peek_struct_tag,
)
from shared_types.aes_gcm import GCMCipher, decrypt_gcm, encrypt_gcm
from shared_types import sounds


@pytest.fixture(scope="module")
def app():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


# ── aes_gcm ────────────────────────────────────────────────────────

def test_gcm_cipher_roundtrip_and_blob_layout():
    key = b"0" * 32
    cipher = GCMCipher(key)
    plaintext = b"\x00\x01secret\xff payload"
    blob = cipher.encrypt(plaintext)
    # nonce(12) + tag(16) + ciphertext
    assert len(blob) == 12 + 16 + len(plaintext)
    assert cipher.decrypt(blob) == plaintext
    assert encrypt_gcm(key, b"same plaintext but different nonce") != \
        encrypt_gcm(key, b"same plaintext but different nonce"), "nonce 必须随机"


def test_gcm_decrypt_tamper_raises_invalid_tag():
    key = b"1" * 32
    blob = bytearray(encrypt_gcm(key, b"hello"))
    blob[-1] ^= 0x01
    with pytest.raises(InvalidTag):
        GCMCipher(key).decrypt(bytes(blob))


def test_gcm_wrong_key_raises_invalid_tag():
    blob = encrypt_gcm(b"2" * 32, b"hello")
    with pytest.raises(InvalidTag):
        decrypt_gcm(b"3" * 32, blob)


def test_module_level_encrypt_decrypt_helpers():
    """覆盖 decrypt_gcm 的一次性入口（基线中唯一缺失行 49）。"""
    key = b"4" * 32
    assert decrypt_gcm(key, encrypt_gcm(key, b"roundtrip")) == b"roundtrip"


# ── sounds ─────────────────────────────────────────────────────────

def test_sound_event_names_and_files(app):
    expected = ["ready", "start", "open", "chord", "flag_on", "flag_off", "win", "lose"]
    assert sounds.SOUND_EVENT_NAMES == tuple(expected)
    assert [e.value for e in sounds.SoundEvent] == expected
    assert sounds.SOUND_FILES == {
        e: f"{e.value}.wav" for e in sounds.SoundEvent
    }
    assert len(sounds.SOUND_PRIORITY) == len(expected)
    assert sounds.SOUND_PRIORITY[sounds.SoundEvent.WIN] == 100
    assert sounds.EXCLUSIVE_EVENTS == frozenset(
        {sounds.SoundEvent.WIN, sounds.SoundEvent.LOSE})


def test_default_pack_and_skin_labels(app):
    assert sounds.default_pack_label() == "默认音效（不替换）"
    assert sounds.default_skin_label() == "默认皮肤（不替换）"
    assert sounds.DEFAULT_PACK == ""
    assert sounds.SOUND_META_FILE == "sound.json"
    assert sounds.SKIN_META_FILE == "skin.json"


@pytest.mark.parametrize("name,expected", [
    ("", False),
    ("_hidden", False),
    ("pack-1", True),
    ("中文包", True),
    ("../escape", False),
    ("/abs/path", False),
    ("a/b", False),
    ("a..b", False),  # '.' 不在白名单内
    ("bad*name", False),
    ("with space", False),
    ("normal_2", True),
])
def test_is_safe_pack_name(name, expected):
    assert sounds.is_safe_pack_name(name) is expected


def test_read_meta_name_missing_file_returns_fallback(tmp_path):
    # 覆盖 line 99：文件不存在
    assert sounds.read_meta_name(tmp_path / "nope.json", "fallback") == "fallback"


def test_read_meta_name_variants(tmp_path):
    meta = tmp_path / "sound.json"
    meta.write_text(json.dumps({"name": "漂亮音效"}), encoding="utf-8")
    assert sounds.read_meta_name(meta, "dir") == "漂亮音效"

    meta.write_text(json.dumps({"name": ""}), encoding="utf-8")
    assert sounds.read_meta_name(meta, "dir") == "dir"

    for bad in ("null", "[]", '"a string"', "123", "{not json"):
        meta.write_text(bad, encoding="utf-8")
        assert sounds.read_meta_name(meta, "dir") == "dir"

    meta.write_bytes(b"\xff\xfe\x00invalid")
    assert sounds.read_meta_name(meta, "dir") == "dir"


def test_list_packs_none_root():
    # 覆盖 line 118
    assert sounds.list_packs(None) == []


def test_list_packs_non_dir_and_missing(tmp_path):
    plain_file = tmp_path / "afile"
    plain_file.write_text("x", encoding="utf-8")
    assert sounds.list_packs(plain_file) == []
    assert sounds.list_packs(tmp_path / "missing") == []


def test_list_packs_sorted_skips_underscore_and_resolves_meta(tmp_path):
    (tmp_path / "zeta").mkdir()
    (tmp_path / "_template").mkdir()
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "sound.json").write_text(
        json.dumps({"name": "阿尔法"}), encoding="utf-8")
    (tmp_path / "not_a_dir.txt").write_text("x", encoding="utf-8")
    assert sounds.list_packs(str(tmp_path)) == [
        ("alpha", "阿尔法"), ("zeta", "zeta"),
    ]
    # 自定义 meta_file 用于皮肤
    assert sounds.list_packs(tmp_path, meta_file="skin.json") == [
        ("alpha", "alpha"), ("zeta", "zeta"),
    ]


def test_list_packs_iterdir_oserror(monkeypatch):
    # 覆盖 line 124-125：iterdir 抛 OSError 时静默返回 []
    def boom(self):
        raise OSError("cannot list")
    monkeypatch.setattr(Path, "iterdir", boom)
    assert sounds.list_packs(Path(".")) == []


def test_list_packs_child_is_dir_oserror(monkeypatch, tmp_path):
    # 覆盖 line 131-132：单个子项 is_dir() 抛 OSError 时跳过该项
    (tmp_path / "bad").mkdir()
    real_is_dir = Path.is_dir

    def flaky(self):
        if self.name == "bad":
            raise OSError("stat failed")
        return real_is_dir(self)
    monkeypatch.setattr(Path, "is_dir", flaky)
    assert sounds.list_packs(tmp_path) == []


# ── lib_zmq_plugins/shared/base ────────────────────────────────────

class _ProtoEvent(BaseEvent, tag="cov.proto.event"):
    value: int = 0


class _ProtoCommand(BaseCommand, tag="cov.proto.command"):
    value: int = 0


class _ProtoQuery(BaseQuery, tag="cov.proto.query"):
    value: int = 0


class _ProtoResult(BaseQueryResult, tag="cov.proto.result"):
    value: int = 0


class _TagAsType:
    """__struct_config__.tag 是 type，get_struct_tag/get_event_tag 需转成类名。"""
    __struct_config__ = SimpleNamespace(tag=ValueError)


def test_peek_struct_tag_valid_and_invalid():
    assert peek_struct_tag(msgspec.msgpack.encode(_ProtoCommand())) == "cov.proto.command"
    assert peek_struct_tag(b"not-msgpack") == ""


def test_get_struct_tag_from_class_instance_and_type_tag():
    assert get_struct_tag(_ProtoCommand) == "cov.proto.command"
    assert get_struct_tag(_ProtoCommand()) == "cov.proto.command"
    # 覆盖 base.py line 94：tag 为 type 时取 __name__
    assert get_struct_tag(_TagAsType) == "ValueError"
    assert get_struct_tag(SyncCommand()) == "__sync__"


def test_get_event_tag_string_and_type_tag():
    assert get_event_tag(_ProtoEvent) == "cov.proto.event"
    # 覆盖 base.py line 102：tag 为 type 时取 __name__
    assert get_event_tag(_TagAsType) == "ValueError"


def test_command_response_roundtrip_and_defaults():
    resp = CommandResponse(request_id="r1", success=True)
    assert resp.error is None and resp.data is None
    blob = msgspec.msgpack.encode(resp)
    back = msgspec.msgpack.decode(blob, type=CommandResponse)
    assert back.request_id == "r1" and back.success is True
    assert back.error is None and back.data is None


def test_base_query_result_failure_defaults():
    result = BaseQueryResult(request_id="q1", success=False, error="boom")
    blob = msgspec.msgpack.encode(result)
    back = msgspec.msgpack.decode(blob, type=BaseQueryResult)
    assert back.request_id == "q1" and back.success is False
    assert back.error == "boom"


# ── lib_zmq_plugins/serializer ─────────────────────────────────────

class _Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class _EnumEvent(BaseEvent, tag="cov.enum.event"):
    color: _Color = _Color.RED


def test_enc_dec_hooks():
    assert _enc_hook(_Color.BLUE) == "blue"
    assert _dec_hook(_Color, "red") is _Color.RED
    with pytest.raises(NotImplementedError, match="Cannot encode int"):
        _enc_hook(42)
    with pytest.raises(NotImplementedError, match="Cannot decode to int"):
        _dec_hook(int, 1)
    # 非 type 的 type_hint（如 typing.Union）走兜底。
    # 注意：源码 f-string 用 type_hint.__name__，非 type 对象会先抛
    # AttributeError —— 这是源码缺陷，见最终报告；这里如实记录现状。
    with pytest.raises(AttributeError, match="__name__"):
        _dec_hook("not-a-type", 1)


def test_make_union_single_and_multiple():
    assert _make_union([_ProtoEvent]) is _ProtoEvent
    from typing import Union, get_args
    assert set(get_args(_make_union([_ProtoEvent, _EnumEvent]))) == {
        _ProtoEvent, _EnumEvent}


def test_serializer_enum_roundtrip():
    s = Serializer()
    s.register_event_types(_EnumEvent)
    blob = s.encode_event(_EnumEvent(color=_Color.BLUE))
    back = s.decode_event(blob)
    assert isinstance(back, _EnumEvent) and back.color is _Color.BLUE


def test_serializer_unregistered_decode_raises_explicit_errors():
    s = Serializer()
    with pytest.raises(ValueError, match="No event types registered"):
        # 覆盖 serializer.py line 87
        s.decode_event(msgspec.msgpack.encode(_EnumEvent()))
    with pytest.raises(ValueError, match="No command types registered"):
        # line 97
        s.decode_command(msgspec.msgpack.encode(_ProtoCommand()))
    with pytest.raises(ValueError, match="No query types registered"):
        # line 115
        s.decode_query(msgspec.msgpack.encode(_ProtoQuery()))
    # line 125：清空内置 query result 注册后也必须报错
    s._query_result_types.clear()
    with pytest.raises(ValueError, match="No query result types registered"):
        s.decode_query_result(msgspec.msgpack.encode(_ProtoResult()))


def test_serializer_full_registration_and_is_tag_checks():
    s = Serializer()
    assert s.is_query_tag("cov.proto.query") is False
    assert s.is_query_result_tag(get_struct_tag(BaseQueryResult)) is True
    assert s.is_query_result_tag("cov.proto.result") is False

    s.register_event_types(_ProtoEvent, _EnumEvent)
    s.register_command_types(_ProtoCommand)
    s.register_query_types(_ProtoQuery)
    s.register_query_result_types(_ProtoResult)

    assert s.is_query_tag("cov.proto.query") is True
    assert s.is_query_tag("cov.proto.command") is False
    assert s.is_query_result_tag("cov.proto.result") is True

    for encode, decode, value in [
        (s.encode_event, s.decode_event, _ProtoEvent(value=7)),
        (s.encode_command, s.decode_command, _ProtoCommand(value=8)),
        (s.encode_query, s.decode_query, _ProtoQuery(value=9)),
        (s.encode_query_result, s.decode_query_result, _ProtoResult(value=10)),
        (s.encode_response, s.decode_response,
         CommandResponse(request_id="r", success=True, data=b"d")),
    ]:
        back = decode(encode(value))
        assert type(back) is type(value)
        if isinstance(value, CommandResponse):
            assert back.data == b"d" and back.error is None
        elif hasattr(value, "value"):
            assert back.value == value.value


def test_serializer_base_query_result_is_always_decodable():
    s = Serializer()
    blob = s.encode_query_result(BaseQueryResult(request_id="x", success=False, error="e"))
    back = s.decode_query_result(blob)
    assert isinstance(back, BaseQueryResult) and back.error == "e"
