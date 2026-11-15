from __future__ import annotations

import threading
import time

import pytest

from plugin_sdk.service_registry import (
    ServiceAlreadyRegisteredError,
    ServiceNotFoundError,
    ServiceRegistry,
)


class SampleService:
    pass


def test_register_get_try_get_listing_and_duplicate_rejection():
    registry = ServiceRegistry()
    provider = SampleService()
    assert not registry.has(SampleService)
    assert registry.try_get(SampleService) is None
    with pytest.raises(ServiceNotFoundError) as missing:
        registry.get(SampleService)
    assert missing.value.protocol is SampleService
    with pytest.raises(ServiceNotFoundError):
        registry.get(SampleService)

    registry.register(SampleService, provider, "sample")
    assert registry.has(SampleService)
    assert registry.get(SampleService) is provider
    assert registry.try_get(SampleService) is provider
    assert registry.list_services() == [(SampleService, "sample")]
    assert "1 service(s)" in repr(registry)
    with pytest.raises(ServiceAlreadyRegisteredError) as duplicate:
        registry.register(SampleService, object())
    assert duplicate.value.protocol is SampleService


def test_unregister_clear_and_missing_results():
    registry = ServiceRegistry()
    registry.register(SampleService, SampleService())
    assert registry.unregister(SampleService)
    assert not registry.unregister(SampleService)
    assert registry.list_services() == []
    registry.register(SampleService, SampleService(), "sample")
    registry.clear()
    assert not registry.has(SampleService)
    assert "0 service(s)" in repr(registry)


def test_wait_for_registration_and_timeout():
    registry = ServiceRegistry()
    provider = SampleService()
    result = []
    waiter = threading.Thread(target=lambda: result.append(
        registry.wait_for(SampleService, timeout=1.0, poll_interval=0.01)
    ))
    waiter.start()
    deadline = time.monotonic() + 0.5
    while waiter.is_alive() and time.monotonic() < deadline:
        time.sleep(0.001)
    registry.register(SampleService, provider)
    waiter.join(timeout=1)
    assert not waiter.is_alive()
    assert result == [provider]
    assert registry.wait_for(SampleService, timeout=0.001) is provider

    registry.unregister(SampleService)
    started = time.monotonic()
    assert registry.wait_for(SampleService, timeout=0.01, poll_interval=0.002) is None
    assert time.monotonic() - started < 0.5
