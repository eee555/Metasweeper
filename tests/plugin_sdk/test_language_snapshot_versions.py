"""桥接器语言版本、快照副本及旧版 msgspec 帧兼容性。"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import msgspec
import pytest

from lib_zmq_plugins.shared.base import BaseEvent
from shared_types.events import LanguageChangeEvent
from tests.plugin_sdk.test_server_bridge import bridge  # noqa: F401


def test_provider_registered_before_first_language_and_seed_does_not_need_pub(bridge):
    provider = bridge.server.snapshot_providers[LanguageChangeEvent]
    with pytest.raises(RuntimeError, match="not been synchronized"):
        provider()
    incoming = LanguageChangeEvent(language="de_DE", source_id="foreign", revision=99)
    bridge.send_event(incoming)
    snapshot = provider()
    assert snapshot.language == "de_DE" and snapshot.revision == 1
    assert snapshot.source_id and snapshot.source_id != "foreign"
    assert incoming.source_id == "foreign" and incoming.revision == 99
    bridge.send_event(LanguageChangeEvent(language="ja_JP"))
    assert provider().revision == 2
    assert provider().source_id == snapshot.source_id
    assert snapshot.language == "de_DE" and snapshot.revision == 1


def test_snapshot_is_copy_and_preserves_published_version_and_timestamp(bridge, monkeypatch):
    published = []
    bridge.server._pub_socket = object()

    def publish(topic, event):
        event.timestamp = 123.0
        published.append(event)

    monkeypatch.setattr(bridge.server, "publish", publish)
    bridge.send_event(LanguageChangeEvent(language="de_DE"))
    first = bridge._language_snapshot()
    assert first == published[0] and first is not published[0]
    first.language = "modified-by-consumer"
    assert bridge._language_snapshot().language == "de_DE"
    assert bridge._language_snapshot().timestamp == 123.0
    bridge.send_event(LanguageChangeEvent(language="ja_JP"))
    assert bridge._language_snapshot().revision == 2
    assert published[0].revision == 1 and published[0].language == "de_DE"


def test_snapshot_cannot_observe_half_published_language(bridge, monkeypatch):
    entered, release, reading = threading.Event(), threading.Event(), threading.Event()
    bridge.server._pub_socket = object()

    def publish(topic, event):
        entered.set()
        assert release.wait(3)
        event.timestamp = 321.0

    monkeypatch.setattr(bridge.server, "publish", publish)

    def snapshot():
        reading.set()
        return bridge._language_snapshot()

    with ThreadPoolExecutor(max_workers=2) as pool:
        sending = pool.submit(bridge.send_event, LanguageChangeEvent(language="de_DE"))
        try:
            assert entered.wait(3)
            taking = pool.submit(snapshot)
            assert reading.wait(3)
            assert not taking.done()
        finally:
            release.set()
        sending.result(timeout=3)
        result = taking.result(timeout=3)
    assert result.language == "de_DE" and result.revision == 1 and result.timestamp == 321.0


def test_old_and_new_language_frames_can_be_decoded():
    class LegacyLanguageEvent(BaseEvent, tag="language_change"):
        language: str = "en_US"

    old = LegacyLanguageEvent(language="de_DE", timestamp=12.0)
    new = msgspec.msgpack.decode(msgspec.msgpack.encode(old), type=LanguageChangeEvent)
    assert new.language == "de_DE" and new.timestamp == 12.0
    assert new.source_id == "" and new.revision == 0

    current = LanguageChangeEvent(language="ja_JP", source_id="main", revision=10)
    legacy = msgspec.msgpack.decode(msgspec.msgpack.encode(current), type=LegacyLanguageEvent)
    assert legacy.language == "ja_JP"
    assert msgspec.msgpack.decode(msgspec.msgpack.encode(current), type=LanguageChangeEvent) == current
