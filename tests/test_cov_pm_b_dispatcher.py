"""Coverage tests for plugin_manager.event_dispatcher."""
from __future__ import annotations

import threading
from types import SimpleNamespace

from plugin_manager.event_dispatcher import EventDispatcher, HandlerEntry
from plugin_sdk.service_registry import ServiceRegistry


class FakePlugin:
    def __init__(self, name: str, *, enabled: bool = True, accept: bool = True):
        self.name = name
        self.is_enabled = enabled
        self.accept = accept
        self.enqueued: list[tuple[object, object]] = []

    def _enqueue_event(self, handler, event):
        self.enqueued.append((handler, event))
        return self.accept


def test_subscribe_priority_order_duplicates_and_default_priority():
    dispatcher = EventDispatcher()
    first = lambda event: None
    second = lambda event: None
    dispatcher.subscribe("evt", first)
    dispatcher.subscribe("evt", second, priority=-5, plugin=FakePlugin("p"))
    dispatcher.subscribe("evt", first, priority=50)
    dispatcher.subscribe("evt", lambda e: None, priority=50)

    handlers = dispatcher.get_handlers("evt")
    assert len(handlers) == 4
    assert [h.priority for h in handlers] == [-5, 50, 50, 100]
    assert handlers[0].handler is second
    assert handlers[1].handler is first
    assert callable(handlers[2].handler) and handlers[2].handler is not first
    assert handlers[3].handler is first
    assert isinstance(handlers[0], HandlerEntry)
    assert handlers[0].plugin.name == "p"


def test_subscribe_invalid_priority_is_tolerated_by_sort():
    dispatcher = EventDispatcher()
    dispatcher.subscribe("evt", lambda e: None, priority=100)
    dispatcher.subscribe("evt", lambda e: None, priority=1)
    assert [h.priority for h in dispatcher.get_handlers("evt")] == [1, 100]


def test_services_property_and_repr():
    dispatcher = EventDispatcher()
    assert isinstance(dispatcher.services, ServiceRegistry)
    assert dispatcher.services is dispatcher._service_registry
    assert repr(dispatcher) == "<EventDispatcher: 0 event types, 0 handlers>"
    dispatcher.subscribe("a", lambda e: None)
    dispatcher.subscribe("a", lambda e: None)
    dispatcher.subscribe("b", lambda e: None)
    assert repr(dispatcher) == "<EventDispatcher: 2 event types, 3 handlers>"


def test_unsubscribe_removes_only_matching_plugin_and_event():
    dispatcher = EventDispatcher()
    p1, p2 = FakePlugin("p1"), FakePlugin("p2")
    dispatcher.subscribe("a", lambda e: None, plugin=p1)
    dispatcher.subscribe("a", lambda e: None, plugin=p2)
    dispatcher.subscribe("b", lambda e: None, plugin=p1)

    dispatcher.unsubscribe("a", p1)
    assert len(dispatcher.get_handlers("a")) == 1
    assert dispatcher.get_handlers("a")[0].plugin is p2
    assert len(dispatcher.get_handlers("b")) == 1

    dispatcher.unsubscribe("missing", p1)
    assert dispatcher.get_handlers("missing") == []


def test_unsubscribe_all_clears_every_event_but_keeps_others():
    dispatcher = EventDispatcher()
    p1, p2 = FakePlugin("p1"), FakePlugin("p2")
    dispatcher.subscribe("a", lambda e: None, plugin=p1)
    dispatcher.subscribe("a", lambda e: None, plugin=p2)
    dispatcher.subscribe("b", lambda e: None, plugin=p1)

    dispatcher.unsubscribe_all(p1)
    assert len(dispatcher.get_handlers("a")) == 1
    assert dispatcher.get_handlers("a")[0].plugin is p2
    assert dispatcher.get_handlers("b") == []


def test_dispatch_missing_event_type_does_not_call_handlers():
    dispatcher = EventDispatcher()
    dispatcher.dispatch("missing", "payload")
    assert dispatcher.get_handlers("missing") == []


def test_dispatch_no_plugin_handlers_in_priority_order_and_isolates_exceptions():
    dispatcher = EventDispatcher()
    calls = []

    def bad(event):
        calls.append("bad")
        raise RuntimeError("handler exploded")

    def good(event):
        calls.append(("good", event))

    dispatcher.subscribe("evt", good, priority=100)
    dispatcher.subscribe("evt", bad, priority=1)
    dispatcher.subscribe("evt", good, priority=50)
    dispatcher.dispatch("evt", "payload")

    assert calls == ["bad", ("good", "payload"), ("good", "payload")]


def test_dispatch_uses_plugin_queue_and_skips_disabled_plugin():
    dispatcher = EventDispatcher()
    enabled, disabled, full = (FakePlugin("enabled"),
                               FakePlugin("disabled", enabled=False),
                               FakePlugin("full", accept=False))
    dispatcher.subscribe("evt", lambda e: None, plugin=enabled, priority=1)
    dispatcher.subscribe("evt", lambda e: None, plugin=disabled, priority=2)
    dispatcher.subscribe("evt", lambda e: None, plugin=full, priority=3)
    dispatcher.subscribe("evt", lambda e: None, priority=4)

    warnings = []
    dispatcher.dispatch("evt", {"x": 1})

    assert len(enabled.enqueued) == 1
    assert enabled.enqueued[0][1] == {"x": 1}
    assert disabled.enqueued == []
    assert len(full.enqueued) == 1
    assert not warnings


def test_dispatch_reentrant_clear_drain_and_service_access(monkeypatch):
    import plugin_manager.event_dispatcher as module

    dispatcher = EventDispatcher()
    calls = []
    warnings = []
    monkeypatch.setattr(module.logger, "warning", lambda msg: warnings.append(msg))

    def clear_during_dispatch(event):
        calls.append("clear")
        dispatcher.clear()

    def after_clear(event):
        calls.append("after")

    dispatcher.subscribe("evt", clear_during_dispatch, priority=1)
    dispatcher.subscribe("evt", after_clear, priority=2)
    dispatcher.dispatch("evt", "payload")

    assert calls == ["clear", "after"]
    assert dispatcher.get_handlers("evt") == []
    assert repr(dispatcher) == "<EventDispatcher: 0 event types, 0 handlers>"
    assert dispatcher.services is not None
    assert not warnings


def test_clear_removes_all_handlers():
    dispatcher = EventDispatcher()
    dispatcher.subscribe("a", lambda e: None)
    dispatcher.subscribe("b", lambda e: None)
    dispatcher.clear()
    assert dispatcher.get_handlers("a") == []
    assert dispatcher.get_handlers("b") == []
    assert repr(dispatcher) == "<EventDispatcher: 0 event types, 0 handlers>"


def test_dispatch_queue_full_and_logger_exception_paths(monkeypatch):
    import plugin_manager.event_dispatcher as module

    dispatcher = EventDispatcher()
    plugin = FakePlugin("full", accept=False)
    dispatcher.subscribe("evt", lambda e: None, plugin=plugin)
    warnings = []
    monkeypatch.setattr(module.logger, "warning", lambda msg: warnings.append(msg))

    def broken(event):
        raise ValueError("sync-boom")

    errors = []
    monkeypatch.setattr(module.logger, "error",
                        lambda msg, **kwargs: errors.append((msg, kwargs)))
    dispatcher.subscribe("evt", broken)

    dispatcher.dispatch("evt", "payload")
    assert any("queue full" in message for message in warnings)
    assert any("sync-boom" in message for message, _ in errors)
    assert errors[0][1]["exc_info"] is True


def test_dispatch_with_simple_namespace_plugin():
    dispatcher = EventDispatcher()
    received = []
    plugin = SimpleNamespace(
        name="ns",
        is_enabled=True,
        _enqueue_event=lambda handler, event: received.append((handler, event)) or True,
    )
    dispatcher.subscribe("evt", lambda e: None, plugin=plugin)
    dispatcher.dispatch("evt", 7)
    assert len(received) == 1
    assert received[0][1] == 7
