"""语言快照与实时事件交错，以及 Qt 分发线程的回归测试。"""
from __future__ import annotations

import threading
from collections import deque
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QThread

from lib_zmq_plugins.shared.base import get_event_tag
from plugin_manager import plugin_manager as module
from shared_types.events import GameFinishedEvent, LanguageChangeEvent


@pytest.fixture
def manager():
    instance = object.__new__(module.PluginManager)
    instance._events_lock = threading.Lock()
    instance._pending_events = deque()
    instance._events_ready = True
    instance._events_draining = False
    instance._shutdown_requested = False
    instance._main_window = None
    instance._language_source_id = ""
    instance._language_revision = 0
    instance._retired_language_sources = set()
    instance._gui_executor = None
    instance._translator_installer = None
    instance._dispatcher = SimpleNamespace(dispatch=lambda tag, event: None)
    return instance


def emit(manager, event):
    manager._queue_zmq_event(get_event_tag(type(event)), event)


def language(value, revision, source="main"):
    return LanguageChangeEvent(language=value, source_id=source, revision=revision)


def test_late_snapshot_and_duplicate_cannot_roll_back_live_language(manager):
    seen = []
    manager._dispatcher.dispatch = lambda tag, event: seen.append(event)
    newest = language("ja_JP", 3)
    emit(manager, newest)
    emit(manager, language("de_DE", 2))
    emit(manager, language("ja_JP", 3))
    emit(manager, LanguageChangeEvent(language="en_US"))
    assert seen == [newest]


def test_snapshot_ahead_of_delayed_pub_keeps_newer_revision(manager):
    seen = []
    manager._dispatcher.dispatch = lambda tag, event: seen.append(event)
    snapshot, live = language("de_DE", 2), language("pl_PL", 4)
    for event in [snapshot, language("en_US", 1), live, language("ja_JP", 3)]:
        emit(manager, event)
    assert seen == [snapshot, live]


def test_source_change_allows_revision_reset_but_rejects_retired_source(manager):
    seen = []
    manager._dispatcher.dispatch = lambda tag, event: seen.append(event)
    old, new = language("de_DE", 20, "old"), language("ja_JP", 1, "new")
    for event in [old, new, language("en_US", 21, "old"), language("pl_PL", 2, "new")]:
        emit(manager, event)
    assert [(event.source_id, event.revision) for event in seen] == [
        ("old", 20), ("new", 1), ("new", 2),
    ]


def test_legacy_language_events_remain_supported(manager):
    seen = []
    manager._dispatcher.dispatch = lambda tag, event: seen.append(event.language)
    emit(manager, LanguageChangeEvent(language="de_DE"))
    emit(manager, LanguageChangeEvent(language="ja_JP"))
    assert seen == ["de_DE", "ja_JP"]


def test_synchronous_language_burst_does_not_recurse(manager):
    seen = []
    manager._events_ready = False
    manager._translator_installer = SimpleNamespace(install=lambda value, done: done())
    manager._dispatcher.dispatch = lambda tag, event: seen.append(event)
    for revision in range(1, 1601):
        emit(manager, language("de_DE", revision))
    manager._release_startup_events()
    assert len(seen) == 1600
    assert not manager._events_draining


def test_async_install_blocks_following_events_and_resumes(manager):
    callbacks, seen = [], []
    manager._translator_installer = SimpleNamespace(
        install=lambda value, done: callbacks.append(done),
    )
    manager._dispatcher.dispatch = lambda tag, event: seen.append(event)
    first, second, last = language("de_DE", 1), language("ja_JP", 2), GameFinishedEvent()
    emit(manager, first)
    emit(manager, second)
    emit(manager, last)
    assert not seen and len(callbacks) == 1
    callbacks.pop(0)()
    assert seen == [first] and len(callbacks) == 1
    callbacks.pop(0)()
    assert seen == [first, second, last]
    assert not manager._events_draining


def test_install_failure_does_not_strand_following_events(manager):
    seen = []
    manager._translator_installer = SimpleNamespace(
        install=lambda value, done: (_ for _ in ()).throw(RuntimeError("failed")),
    )
    manager._dispatcher.dispatch = lambda tag, event: seen.append(event)
    manager._events_ready = False
    emit(manager, language("de_DE", 1))
    last = GameFinishedEvent()
    emit(manager, last)
    manager._release_startup_events()
    assert seen == [last]
    assert not manager._events_draining


def test_entire_event_sequence_runs_on_gui_thread(qapp, qtbot, manager):
    seen = []
    manager._gui_executor = module._GuiExecutor()
    manager._translator_installer = SimpleNamespace(
        install=lambda value, done: (seen.append((value, QThread.currentThread())), done()),
    )
    manager._dispatcher.dispatch = lambda tag, event: seen.append((event, QThread.currentThread()))
    before, changed, after = GameFinishedEvent(), language("de_DE", 1), GameFinishedEvent()
    worker = threading.Thread(target=lambda: [emit(manager, event) for event in [before, changed, after]])
    worker.start()
    worker.join(2)
    assert not worker.is_alive() and not seen
    qtbot.waitUntil(lambda: len(seen) == 4)
    assert [item[0] for item in seen] == [before, "de_DE", changed, after]
    assert all(thread == qapp.thread() for _, thread in seen)


def test_shutdown_before_gui_drain_prevents_install(qapp, qtbot, manager):
    seen = []
    manager._gui_executor = module._GuiExecutor()
    manager._translator_installer = SimpleNamespace(install=lambda *args: seen.append("install"))
    worker = threading.Thread(target=lambda: emit(manager, language("de_DE", 1)))
    worker.start()
    worker.join(2)
    assert not worker.is_alive()
    with manager._events_lock:
        manager._shutdown_requested = True
        manager._pending_events.clear()
    qapp.processEvents()
    assert not seen and not manager._events_draining


def test_connection_notifications_use_gui_thread(qapp, qtbot, manager):
    seen = []
    manager._gui_executor = module._GuiExecutor()
    manager._language_sync_wakeup = threading.Event()
    manager._main_window = SimpleNamespace(set_connected=lambda value: seen.append((value, QThread.currentThread())))
    worker = threading.Thread(target=lambda: (manager._on_connected(), manager._on_disconnected()))
    worker.start()
    worker.join(2)
    assert not worker.is_alive() and not seen
    qtbot.waitUntil(lambda: len(seen) == 2)
    assert [value for value, _ in seen] == [True, False]
    assert all(thread == qapp.thread() for _, thread in seen)
