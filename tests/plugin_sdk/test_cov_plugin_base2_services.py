"""Service registration, discovery and dispatch contract for BasePlugin."""
from concurrent.futures import TimeoutError
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from loguru import logger
from PySide6.QtWidgets import QApplication

from plugin_manager.event_dispatcher import EventDispatcher
from plugin_sdk.plugin_base import BasePlugin, PluginInfo, _ServiceProxy
from plugin_sdk.service_registry import ServiceAlreadyRegisteredError, ServiceNotFoundError


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr("plugin_manager.logging_setup.get_plugin_logger", lambda *a, **k: (logger, None))
    monkeypatch.setattr("plugin_manager.logging_setup.set_plugin_log_level", lambda *a, **k: None)
    return application


class ProbePlugin(BasePlugin):
    @classmethod
    def plugin_info(cls):
        return PluginInfo(name="service-probe", other_info=None)

    def _setup_subscriptions(self):
        pass


@pytest.fixture
def plugin(app):
    return ProbePlugin(ProbePlugin.plugin_info())


class Contract:
    _is_protocol = True
    ignored = None
    constant = 12

    def calculate(self, left, right):
        raise NotImplementedError

    @property
    def label(self):
        raise NotImplementedError

    def _private(self):
        raise NotImplementedError


class Provider(Contract):
    _is_protocol = False

    def __init__(self):
        self.calls = []
        self.events = []

    def calculate(self, left, right):
        self.calls.append((left, right))
        return left + right

    @property
    def label(self):
        return "provider"

    def fail(self):
        raise ValueError("provider exploded")

    def _enqueue_event(self, handler, event):
        self.events.append(event)
        handler(event)
        return True


def test_register_without_dispatcher_and_without_inferred_protocol(plugin):
    provider = Provider()
    plugin.register_service(provider, protocol=Contract)
    assert plugin._registered_protocols == []
    dispatcher = EventDispatcher()
    plugin.set_event_dispatcher(dispatcher)
    plugin.register_service(object())
    assert dispatcher.services.list_services() == []
    assert plugin._registered_protocols == []


def test_protocol_validation_checks_public_methods_and_properties(plugin):
    class Missing:
        def calculate(self, left, right):
            return left + right

    assert plugin._check_protocol_implementation(Missing(), Contract) == ["label"]
    assert plugin._check_protocol_implementation(Provider(), Contract) == []
    class Empty:
        pass
    assert plugin._check_protocol_implementation(Empty(), Contract) == ["calculate", "label"]
    dispatcher = EventDispatcher()
    plugin.set_event_dispatcher(dispatcher)
    with pytest.raises(TypeError, match=r"Missing does not implement Contract\. Missing methods: label"):
        plugin.register_service(Missing(), protocol=Contract)
    assert dispatcher.services.list_services() == []
    assert plugin._registered_protocols == []


def test_register_infers_protocol_and_rejects_duplicate_registry_entry(plugin):
    dispatcher = EventDispatcher()
    plugin.set_event_dispatcher(dispatcher)
    provider = Provider()
    plugin.register_service(provider)
    assert dispatcher.services.get(Contract) is provider
    assert dispatcher.services.list_services() == [(Contract, plugin.name)]
    assert plugin._registered_protocols == [Contract]
    with pytest.raises(ServiceAlreadyRegisteredError, match="Service already registered: Contract"):
        plugin.register_service(provider, protocol=Contract)
    assert plugin._registered_protocols == [Contract]
    plugin._unsubscribe_resources()
    assert not dispatcher.services.has(Contract)
    assert plugin._registered_protocols == []


def test_registration_record_deduplicated_when_registry_accepts_reregistration(plugin):
    services = SimpleNamespace(register=Mock())
    plugin.set_event_dispatcher(SimpleNamespace(services=services))
    provider = Provider()
    plugin.register_service(provider, protocol=Contract)
    plugin.register_service(provider, protocol=Contract)
    assert services.register.call_args_list == [
        ((Contract, provider, plugin.name), {}), ((Contract, provider, plugin.name), {})
    ]
    assert plugin._registered_protocols == [Contract]


def test_discovery_without_dispatcher(plugin):
    with pytest.raises(ServiceNotFoundError, match="Service not found: Contract"):
        plugin._get_service(Contract)
    assert plugin._try_get_service(Contract) is None
    assert plugin.has_service(Contract) is False
    assert plugin.wait_for_service(Contract, timeout=0) is None
    with pytest.raises(ServiceNotFoundError, match="Service not found: Contract"):
        plugin._call_service(Contract, "calculate", 1, 2)


def test_discovery_forwards_protocol_and_timeout(plugin):
    provider = Provider()
    services = SimpleNamespace(get=Mock(return_value=provider), try_get=Mock(return_value=provider),
                               has=Mock(return_value=True), wait_for=Mock(return_value=provider))
    plugin.set_event_dispatcher(SimpleNamespace(services=services))
    assert plugin._get_service(Contract) is provider
    assert plugin._try_get_service(Contract) is provider
    assert plugin.has_service(Contract) is True
    assert plugin.wait_for_service(Contract, timeout=1.25) is provider
    services.get.assert_called_once_with(Contract)
    services.try_get.assert_called_once_with(Contract)
    services.has.assert_called_once_with(Contract)
    services.wait_for.assert_called_once_with(Contract, 1.25)


@pytest.fixture
def connected(plugin):
    dispatcher = EventDispatcher()
    provider = Provider()
    dispatcher.services.register(Contract, provider, "fake-provider")
    plugin.set_event_dispatcher(dispatcher)
    return plugin, provider


def test_call_service_executes_provider_and_propagates_error(connected):
    plugin, provider = connected
    assert plugin._call_service(Contract, "calculate", 3, 4, timeout=0.1) == 7
    assert provider.calls == [(3, 4)]
    assert provider.events == [None]
    with pytest.raises(ValueError, match="provider exploded"):
        plugin._call_service(Contract, "fail", timeout=0.1)
    assert provider.events == [None, None]


def test_call_service_timeout_when_provider_never_executes(connected, monkeypatch):
    plugin, provider = connected
    enqueue = Mock(return_value=True)
    monkeypatch.setattr(provider, "_enqueue_event", enqueue)
    with pytest.raises(TimeoutError):
        plugin._call_service(Contract, "calculate", 1, 2, timeout=0.001)
    assert enqueue.call_count == 1
    assert enqueue.call_args.args[1] is None
    assert provider.calls == []


def test_stopping_provider_rejects_sync_and_async_calls(connected, monkeypatch):
    plugin, provider = connected
    monkeypatch.setattr(provider, "_enqueue_event", lambda handler, event: False)
    with pytest.raises(RuntimeError, match="Service provider is stopping: Contract"):
        plugin._call_service(Contract, "calculate", 1, 2, timeout=1)
    future = plugin.call_service_async(Contract, "calculate", 1, 2)
    assert future.done()
    with pytest.raises(RuntimeError, match="Service provider is stopping: Contract"):
        future.result()


def test_async_service_missing_dispatcher_or_registration(plugin):
    future = plugin.call_service_async(Contract, "calculate", 1, 2)
    assert future.done()
    with pytest.raises(ServiceNotFoundError, match="Service not found: Contract"):
        future.result()
    plugin.set_event_dispatcher(EventDispatcher())
    future = plugin.call_service_async(Contract, "calculate", 1, 2)
    assert future.done()
    with pytest.raises(ServiceNotFoundError, match="Service not found: Contract"):
        future.result()


def test_async_service_result_and_exception(connected):
    plugin, provider = connected
    future = plugin.call_service_async(Contract, "calculate", 8, 9)
    assert future.done() and future.result() == 17
    assert provider.calls == [(8, 9)]
    failure = plugin.call_service_async(Contract, "fail")
    assert failure.done()
    assert isinstance(failure.exception(), ValueError)
    with pytest.raises(ValueError, match="provider exploded"):
        failure.result()
    assert provider.events == [None, None]


def test_proxy_forwards_calls_timeout_and_rejects_kwargs(connected, monkeypatch):
    plugin, provider = connected
    proxy = plugin.get_service_proxy(Contract)
    assert isinstance(proxy, _ServiceProxy)
    assert repr(proxy) == "<ServiceProxy: Contract>"
    assert proxy.calculate(2, 6, timeout=0.5) == 8
    assert provider.calls == [(2, 6)]
    with pytest.raises(TypeError, match="keyword arguments is not supported"):
        proxy.calculate(2, right=6)
    assert provider.calls == [(2, 6)]
    forward = Mock(return_value="ok")
    monkeypatch.setattr(plugin, "_call_service", forward)
    assert proxy.anything("arg", timeout=2.5) == "ok"
    forward.assert_called_once_with(Contract, "anything", "arg", timeout=2.5)
