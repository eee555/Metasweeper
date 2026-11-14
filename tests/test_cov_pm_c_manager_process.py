"""Coverage tests for run_plugin_manager_process and the process-level helpers."""
from __future__ import annotations

import sys
import time
from types import SimpleNamespace

import pytest

from plugin_manager import plugin_manager as module

from test_cov_pm_c_fakes import (  # noqa: F401  (fixtures and constants)
    SHUTDOWN_REGISTRATION,
    FakeClient,
    FakePlugin,
    base_env,
    manager,
)


@pytest.mark.parametrize("show_main_window", [True, False])
def test_run_process_with_gui(base_env, monkeypatch, show_main_window):
    calls = []
    stops = []
    made = []

    class FakeManager:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            made.append(kwargs)

        def exec_gui(self, *, show_main_window):
            calls.append(show_main_window)
            return 11

        def stop(self):
            stops.append(True)

    monkeypatch.setattr(module, "PluginManager", FakeManager)
    result = module.run_plugin_manager_process(
        "inproc://process", plugin_dirs=["plugins"], with_gui=True,
        show_main_window=show_main_window, pub_endpoint="tcp://pub",
        ctrl_endpoint="tcp://ctrl",
    )
    assert result == 11
    assert calls == [show_main_window]
    assert stops == [True]
    assert made[0]["endpoint"] == "inproc://process"
    assert made[0]["plugin_dirs"] == ["plugins"]
    assert made[0]["pub_endpoint"] == "tcp://pub"
    assert made[0]["ctrl_endpoint"] == "tcp://ctrl"
    assert isinstance(made[0]["log_handler"], module._LogHandler)


@pytest.mark.parametrize("show_main_window", [True, False])
def test_run_process_without_gui_stops_on_keyboard_interrupt(
        base_env, monkeypatch, show_main_window):
    calls, stops, sleeps = [], [], []

    class FakeManager:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start(self):
            calls.append("start")

        def stop(self):
            stops.append(True)

    def interrupt(_seconds):
        sleeps.append(_seconds)
        raise KeyboardInterrupt()

    monkeypatch.setattr(module, "PluginManager", FakeManager)
    monkeypatch.setattr(time, "sleep", interrupt)
    result = module.run_plugin_manager_process(
        "inproc://headless", with_gui=False, show_main_window=show_main_window,
    )
    assert result == 0
    assert calls == ["start"]
    assert sleeps == [1]
    assert stops == [True]


def test_run_process_exception_still_stops_and_propagates(base_env, monkeypatch):
    stops = []

    class FakeManager:
        def __init__(self, **kwargs):
            pass

        def start(self):
            raise RuntimeError("startup failed")

        def stop(self):
            stops.append(True)

    monkeypatch.setattr(module, "PluginManager", FakeManager)
    with pytest.raises(RuntimeError, match="startup failed"):
        module.run_plugin_manager_process("inproc://error", with_gui=False)
    assert stops == [True]


def test_run_process_with_real_manager_stubbed_start(base_env, monkeypatch):
    started, stopped = [], []
    monkeypatch.setattr(module.PluginManager, "start",
                        lambda self: started.append(True))
    monkeypatch.setattr(module.PluginManager, "stop",
                        lambda self: stopped.append(True))
    monkeypatch.setattr(time, "sleep",
                        lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()))

    assert module.run_plugin_manager_process(
        "inproc://real", plugin_dirs=[], with_gui=False) == 0
    assert started == [True]
    assert stopped == [True]


def test_run_process_with_real_manager_gui(base_env, monkeypatch):
    calls, stopped = [], []
    monkeypatch.setattr(module.PluginManager, "exec_gui",
                        lambda self, *, show_main_window: (
                            calls.append(show_main_window), 3)[1])
    monkeypatch.setattr(module.PluginManager, "stop",
                        lambda self: stopped.append(True))
    assert module.run_plugin_manager_process(
        "inproc://real-gui", plugin_dirs=[], with_gui=True,
        show_main_window=False) == 3
    assert calls == [False]
    assert stopped == [True]
