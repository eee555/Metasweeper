"""验证真实 ZMQ 连接和替换客户端都能获取语言快照。"""
import threading

from lib_zmq_plugins.client.zmq_client import ZMQClient
from plugin_sdk.server_bridge import GameServerBridge
from shared_types.events import LanguageChangeEvent


def test_language_snapshot_on_new_and_restarted_client(monkeypatch):
    monkeypatch.setattr(GameServerBridge, "_instance", None)
    bridge = GameServerBridge("tcp://127.0.0.1")
    bridge.start()
    clients = []
    try:
        bridge.send_event(LanguageChangeEvent(language="de_DE"))

        def connect_client():
            received = []
            arrived = threading.Event()
            client = ZMQClient(bridge.endpoint, pub_endpoint=bridge.pub_endpoint,
                               ctrl_endpoint=bridge.ctrl_endpoint)
            clients.append(client)
            client.register_event_types(LanguageChangeEvent)
            client.subscribe(LanguageChangeEvent,
                             lambda event: (received.append(event.language), arrived.set()))
            client.connect()
            assert arrived.wait(5), "language snapshot was not received"
            return client, received, arrived

        first, received, arrived = connect_client()
        assert received[-1] == "de_DE"
        arrived.clear()
        bridge.send_event(LanguageChangeEvent(language="ja_JP"))
        assert arrived.wait(5), "live language event was not received"
        assert received[-1] == "ja_JP"
        first.disconnect()
        _, restarted, _ = connect_client()
        assert restarted[-1] == "ja_JP"
    finally:
        for client in clients:
            client.disconnect()
        bridge.stop()
