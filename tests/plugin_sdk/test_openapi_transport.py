from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from plugin_sdk.openapi_client.transport import (
    QtNetworkTransport,
    RequestsTransport,
    TransportError,
    TransportResponse,
    create_default_transport,
)


def test_transport_response_text_decodes_invalid_utf8_with_replacement():
    assert TransportResponse(200, {}, b"ok\xff").text == "ok\ufffd"


def test_requests_transport_headers_optional_arguments_and_errors(monkeypatch):
    class Session:
        def __init__(self):
            self.headers = {}
            self.calls = []
            self.result = SimpleNamespace(status_code=201, headers={"x": "y"}, content=b"body")
            self.error = None

        def request(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            if self.error:
                raise self.error
            return self.result

    session = Session()
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(Session=lambda: session))
    transport = RequestsTransport("agent")
    assert session.headers == {"User-Agent": "agent"}
    transport.set_default_headers({"Authorization": "Bearer token"})
    result = transport.request("POST", "https://host", headers={"x": "1"}, params={"q": 2},
                               data="a=b", files={"f": (None, "v")}, timeout=3)
    assert result == TransportResponse(201, {"x": "y"}, b"body")
    assert session.calls[-1] == (("POST", "https://host"), {
        "headers": {"x": "1"}, "params": {"q": 2}, "data": "a=b",
        "files": {"f": (None, "v")}, "timeout": 3,
    })

    transport.request("GET", "https://host")
    assert session.calls[-1] == (("GET", "https://host"), {})
    session.error = RuntimeError("connection lost")
    with pytest.raises(TransportError, match="connection lost") as caught:
        transport.request("GET", "https://host")
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert isinstance(create_default_transport("ua"), RequestsTransport)


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self.callbacks):
            callback(*args)


class FakeUrl:
    def __init__(self, value):
        self.value = value
        self.query = None

    def setQuery(self, query):
        self.query = query


class FakeUrlQuery:
    def __init__(self, url):
        self.url = url
        self.items = []

    def addQueryItem(self, key, value):
        self.items.append((key, value))


class FakeRequest:
    class Attribute:
        HttpStatusCodeAttribute = 42

    def __init__(self, url):
        self.url = url
        self.headers = {}

    def setRawHeader(self, key, value):
        self.headers[key] = value


class FakeTimer:
    current = None

    def __init__(self):
        self.timeout = Signal()
        self.single = False
        self.duration = None
        self.stopped = 0
        FakeTimer.current = self

    def setSingleShot(self, value): self.single = value
    def start(self, duration): self.duration = duration
    def stop(self): self.stopped += 1


class FakeReply:
    def __init__(self, status=200, body=b"ok", reason=""):
        self.finished = Signal()
        self.status = status
        self.body = body
        self.reason = reason
        self.deleted = 0
        self.aborted = 0

    def abort(self):
        self.aborted += 1
        self.finished.emit()

    def deleteLater(self): self.deleted += 1
    def attribute(self, _attribute): return self.status
    def errorString(self): return self.reason
    def readAll(self): return self.body


class FakeLoop:
    reply = None
    behavior = "finish"

    def __init__(self):
        self.quit_count = 0

    def quit(self): self.quit_count += 1

    def exec(self):
        if FakeLoop.behavior == "timeout":
            FakeTimer.current.timeout.emit()
        else:
            FakeLoop.reply.finished.emit()


class FakeManager:
    reply = None
    calls = []

    def __init__(self): pass

    def sendCustomRequest(self, request, method, body):
        self.calls.append((request, method, body))
        return self.reply


def install_qt_fakes(monkeypatch, *, status=200, body=b"ok", reason="", behavior="finish"):
    import PySide6.QtCore as qt_core

    FakeManager.calls.clear()
    FakeManager.reply = FakeReply(status, body, reason)
    FakeLoop.reply = FakeManager.reply
    FakeLoop.behavior = behavior
    monkeypatch.setattr(qt_core, "QUrlQuery", FakeUrlQuery, raising=False)
    monkeypatch.setattr(qt_core, "QTimer", FakeTimer)
    monkeypatch.setattr(
        "plugin_sdk.openapi_client.transport._require_qt",
        lambda: (FakeLoop, FakeUrl, FakeManager, object, FakeRequest),
    )
    return FakeManager.reply


def test_qt_network_transport_request_merges_url_headers_and_form_body(monkeypatch):
    reply = install_qt_fakes(monkeypatch)
    transport = QtNetworkTransport("agent")
    transport.set_default_headers({"Authorization": "token"})
    result = transport.request("POST", "https://host/path", headers={"X-Test": "yes"},
                               params={"a": 1, "b": "two"}, data="x=y", timeout=1.25)
    assert result == TransportResponse(200, {}, b"ok")
    request, method, body = FakeManager.calls[-1]
    assert request.url.value == "https://host/path"
    assert request.url.query.items == [("a", "1"), ("b", "two")]
    assert request.headers == {
        b"User-Agent": b"agent", b"Authorization": b"token", b"X-Test": b"yes",
    }
    assert method == b"POST" and body == b"x=y"
    assert FakeTimer.current.duration == 1250
    assert reply.deleted == 1


def test_qt_network_transport_multipart_and_network_errors(monkeypatch):
    install_qt_fakes(monkeypatch)
    transport = QtNetworkTransport()
    transport.request("POST", "https://host", files={"field": (None, "value"), "other": "x"})
    request, method, body = FakeManager.calls[-1]
    assert method == b"POST"
    assert b'name="field"' in body and b"value" in body and body.endswith(b"------\r\n") is False
    assert request.headers[b"Content-Type"].startswith(b"multipart/form-data; boundary=----MetasweeperQt")
    assert len(QtNetworkTransport._encode_multipart({})[0]) > 0

    install_qt_fakes(monkeypatch, status=None, reason="DNS failed")
    with pytest.raises(TransportError, match="DNS failed"):
        transport.request("GET", "https://missing")


def test_qt_network_transport_timeout_aborts_and_raises(monkeypatch):
    reply = install_qt_fakes(monkeypatch, behavior="timeout")
    transport = QtNetworkTransport()
    with pytest.raises(TransportError, match="请求超时"):
        transport.request("GET", "https://slow", timeout=0.01)
    assert reply.aborted == 1
    assert reply.deleted == 1
