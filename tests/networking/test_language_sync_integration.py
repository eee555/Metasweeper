"""真实 ZMQ + Qt：首次连接、重连、替换进程及语言快照修复。"""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QThread

from plugin_manager import plugin_manager as module
from plugin_sdk.server_bridge import GameServerBridge
from shared_types.events import LanguageChangeEvent


@pytest.fixture
def sync_system(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(GameServerBridge, "_instance", None)
    bridge = GameServerBridge("tcp://127.0.0.1")
    # 与主程序契约一致：实际语言先于插件进程启动写入，甚至可先于 server.start。
    bridge.send_event(LanguageChangeEvent(language="de_DE"))
    bridge.start()
    monkeypatch.setattr(module, "get_data_dir", lambda: tmp_path)
    monkeypatch.setattr(module, "apply_plugin_lib_dir", lambda value: None)
    monkeypatch.setattr(module.PluginManager, "_register_shutdown_handlers", lambda self: None)
    monkeypatch.setattr(module.PluginManager, "_validate_control_authorizations", lambda self: None)
    monkeypatch.setattr(module.PluginManager, "_LANGUAGE_SYNC_INTERVAL", 0.05)
    monkeypatch.setattr(module.PluginManager, "_instance", None)
    managers, installed = [], []
    monkeypatch.setattr(module, "TranslationManager", lambda: SimpleNamespace(
        install=lambda value, done: (installed.append((value, QThread.currentThread())), done()),
        set_catalogs=lambda value: None,
        close=lambda: None,
    ))

    def create_manager():
        manager = module.PluginManager(bridge.endpoint, plugin_dirs=[],
                                       pub_endpoint=bridge.pub_endpoint,
                                       ctrl_endpoint=bridge.ctrl_endpoint)
        managers.append(manager)
        monkeypatch.setattr(manager._loader, "load_all", lambda: [])
        received = []
        manager.dispatcher.subscribe("language_change", received.append)
        manager.start()
        return manager, received

    yield bridge, create_manager, installed
    for manager in managers:
        manager.stop()
        thread = manager._language_sync_thread
        assert thread is None or not thread.is_alive()
    bridge.stop()


def test_initial_connect_same_client_reconnect_and_restarted_manager(sync_system, qapp, qtbot):
    bridge, create_manager, installed = sync_system
    manager, received = create_manager()
    qtbot.waitUntil(lambda: bool(received), timeout=4000)
    assert received[-1].language == "de_DE"
    assert received[-1].source_id and received[-1].revision == 1

    manager.client.disconnect()
    bridge.send_event(LanguageChangeEvent(language="ja_JP"))
    manager.client.connect()
    qtbot.waitUntil(lambda: received[-1].language == "ja_JP", timeout=4000)
    assert [event.revision for event in received] == [1, 2]

    manager.stop()
    bridge.send_event(LanguageChangeEvent(language="pl_PL"))
    replacement, restarted = create_manager()
    qtbot.waitUntil(lambda: bool(restarted), timeout=4000)
    assert restarted[-1].language == "pl_PL" and restarted[-1].revision == 3
    assert all(thread == qapp.thread() for _, thread in installed)
    assert replacement.is_connected


def test_failed_initial_snapshot_is_retried(sync_system, qtbot):
    bridge, create_manager, _ = sync_system
    ready = threading.Event()
    failures = []
    original = bridge._language_snapshot

    def provider():
        if not ready.is_set():
            failures.append(True)
            raise RuntimeError("snapshot temporarily unavailable")
        return original()

    bridge.server.register_snapshot_provider(LanguageChangeEvent, provider)
    manager, received = create_manager()
    qtbot.waitUntil(lambda: len(failures) >= 2, timeout=4000)
    assert not received
    ready.set()
    qtbot.waitUntil(lambda: bool(received), timeout=4000)
    assert received[-1].language == "de_DE"
    assert manager.is_connected


def test_periodic_snapshot_repairs_dropped_pub_without_duplicate_gui_install(sync_system, qtbot, monkeypatch):
    bridge, create_manager, installed = sync_system
    manager, received = create_manager()
    qtbot.waitUntil(lambda: bool(received), timeout=4000)
    # 不发布这次变更，模拟订阅建立窗口或 HWM 丢弃；服务端缓存仍正确更新。
    monkeypatch.setattr(bridge.server, "publish", lambda *args: None)
    bridge.send_event(LanguageChangeEvent(language="ja_JP"))
    qtbot.waitUntil(lambda: received[-1].language == "ja_JP", timeout=4000)
    assert [value for value, _ in installed] == ["de_DE", "ja_JP"]
    # 确认后续周期确实执行过请求，而相同版本不再次安装/分发。
    snapshots = []
    original = bridge._language_snapshot
    bridge.server.register_snapshot_provider(
        LanguageChangeEvent, lambda: (snapshots.append(True), original())[1])
    qtbot.waitUntil(lambda: len(snapshots) >= 2, timeout=4000)
    assert [event.revision for event in received] == [1, 2]
    assert len(installed) == 2
    assert manager.is_connected


def test_transport_timeout_reconnect_resynchronizes_cached_language(sync_system, qtbot, monkeypatch):
    bridge, create_manager, _ = sync_system
    # 初次请求完成后暂停周期校准，让客户端真实走超时、重建 socket 和重订阅。
    monkeypatch.setattr(module.PluginManager, "_LANGUAGE_SYNC_INTERVAL", 10.0)
    snapshots = []
    original_snapshot = bridge._language_snapshot
    bridge.server.register_snapshot_provider(
        LanguageChangeEvent, lambda: (snapshots.append(True), original_snapshot())[1])
    manager, received = create_manager()
    qtbot.waitUntil(lambda: bool(received) and len(snapshots) >= 2, timeout=4000)
    monkeypatch.setattr(bridge.server, "publish", lambda *args: None)
    bridge.send_event(LanguageChangeEvent(language="ja_JP"))
    client = manager.client
    original_probe = client._probe_connection
    original_disconnected = client.on_disconnected

    def disconnected():
        client._probe_connection = original_probe
        original_disconnected()

    client.on_disconnected = disconnected
    monkeypatch.setattr(client, "_CONNECTION_TIMEOUT", 0.15)
    monkeypatch.setattr(client, "_PROBE_INTERVAL", 0.02)
    monkeypatch.setattr(client, "_probe_connection", lambda: False)
    qtbot.waitUntil(lambda: client.reconnect_count >= 1 and received[-1].language == "ja_JP",
                    timeout=4000)
    assert [event.revision for event in received] == [1, 2]


def test_shutdown_cancels_waiting_sync_request_and_joins_worker(sync_system, qtbot):
    bridge, create_manager, installed = sync_system
    manager, received = create_manager()
    qtbot.waitUntil(lambda: bool(received), timeout=4000)
    entered, release = threading.Event(), threading.Event()
    original = bridge._language_snapshot

    def blocked_provider():
        entered.set()
        assert release.wait(3)
        return original()

    bridge.server.register_snapshot_provider(LanguageChangeEvent, blocked_provider)
    try:
        qtbot.waitUntil(entered.is_set, timeout=4000)
        manager.stop()
        assert not manager._language_sync_thread.is_alive()
        assert [value for value, _ in installed] == ["de_DE"]
    finally:
        release.set()
