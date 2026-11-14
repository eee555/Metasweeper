"""插件管理器两个命令行入口的覆盖测试（全部依赖打桩，不启动真实应用）。"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ENV_KEYS = (
    "METASWEEPER_ZMQ_ENDPOINT",
    "METASWEEPER_ZMQ_PUB_ENDPOINT",
    "METASWEEPER_ZMQ_CTRL_ENDPOINT",
)
_QT_DEFAULTS = {
    "QT_ENABLE_HIGHDPI_SCALING": "1",
    "QT_SCALE_FACTOR_ROUNDING_POLICY": "PassThrough",
}


def _load_entrypoints():
    # 模块导入时会 os.environ.setdefault；把导入带来的环境改动还原。
    before = {key: os.environ.get(key) for key in _QT_DEFAULTS}
    try:
        return (
            importlib.import_module("plugin_manager.__main__"),
            importlib.import_module("plugin_manager._run"),
        )
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


MAIN_MODULE, RUN_MODULE = _load_entrypoints()


def _configure(monkeypatch, tmp_path, module):
    pm = importlib.import_module("plugin_manager")
    app_paths = importlib.import_module("plugin_manager.app_paths")
    logging_setup = importlib.import_module("plugin_manager.logging_setup")
    rec = SimpleNamespace(
        overrides=[], init=[], run=[], exit=[], log_dir=tmp_path / "logs",
    )
    monkeypatch.setattr(
        app_paths, "set_data_dir_override", lambda path: rec.overrides.append(path),
    )
    monkeypatch.setattr(app_paths, "get_log_dir", lambda: rec.log_dir)
    monkeypatch.setattr(
        logging_setup, "init_logging", lambda *a, **kw: rec.init.append((a, kw)),
    )
    monkeypatch.setattr(
        pm, "run_plugin_manager_process", lambda **kw: rec.run.append(kw) or 17,
    )
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(sys, "argv", ["plugin_manager"])
    monkeypatch.setattr(module, "_mutex_handle", None)

    # 默认注入假的 pywin32：真实互斥体、网络、进程都不可用。
    fake_win32api = SimpleNamespace(
        GetLastError=lambda: 0, CloseHandle=lambda handle: None,
    )
    fake_win32event = SimpleNamespace(
        CreateMutex=lambda *args: "FAKE_HANDLE",
    )
    fake_winerror = SimpleNamespace(ERROR_ALREADY_EXISTS=183)
    monkeypatch.setitem(sys.modules, "win32api", fake_win32api)
    monkeypatch.setitem(sys.modules, "win32event", fake_win32event)
    monkeypatch.setitem(sys.modules, "winerror", fake_winerror)
    return SimpleNamespace(module=module, rec=rec)


@pytest.fixture(params=[MAIN_MODULE, RUN_MODULE], ids=["__main__", "_run"])
def entry(request, monkeypatch, tmp_path):
    return _configure(monkeypatch, tmp_path, request.param)


@pytest.fixture(params=[MAIN_MODULE, RUN_MODULE], ids=["__main__", "_run"])
def mutex_entry(request, monkeypatch, tmp_path):
    return _configure(monkeypatch, tmp_path, request.param)


@pytest.fixture
def run_entry(monkeypatch, tmp_path):
    return _configure(monkeypatch, tmp_path, RUN_MODULE)


# ── _acquire_mutex ─────────────────────────────────────────────────────────


def test_acquire_mutex_success(mutex_entry):
    module = mutex_entry.module
    assert module._acquire_mutex() is True
    assert module._mutex_handle == "FAKE_HANDLE"


def test_acquire_mutex_already_exists_closes_handle(mutex_entry, monkeypatch):
    module = mutex_entry.module
    closed = []
    monkeypatch.setitem(sys.modules, "win32api", SimpleNamespace(
        GetLastError=lambda: 183,
        CloseHandle=closed.append,
    ))
    assert module._acquire_mutex() is False
    assert closed == ["FAKE_HANDLE"]
    assert module._mutex_handle is None


def test_acquire_mutex_import_error_falls_back(mutex_entry, monkeypatch):
    monkeypatch.setitem(sys.modules, "win32api", None)
    module = mutex_entry.module
    assert module._acquire_mutex() is True
    assert module._mutex_handle is None


def test_acquire_mutex_create_failure_falls_back(mutex_entry, monkeypatch):
    def boom(*args):
        raise RuntimeError("CreateMutex failed")

    monkeypatch.setitem(sys.modules, "win32event", SimpleNamespace(CreateMutex=boom))
    module = mutex_entry.module
    assert module._acquire_mutex() is True
    assert module._mutex_handle is None


# ── main() ────────────────────────────────────────────────────────────────


def test_main_returns_zero_when_instance_exists(entry, monkeypatch, capsys):
    monkeypatch.setattr(entry.module, "_acquire_mutex", lambda: False)
    assert entry.module.main() == 0
    assert "已有实例" in capsys.readouterr().out
    assert not entry.rec.run
    assert not entry.rec.init


def test_main_uses_builtin_defaults(entry):
    assert entry.module.main() == 17
    assert entry.rec.run == [{
        "endpoint": "tcp://127.0.0.1:5555",
        "with_gui": True,
        "show_main_window": True,
        "pub_endpoint": None,
        "ctrl_endpoint": None,
    }]
    assert entry.rec.init == [((entry.rec.log_dir,), {
        "console": True, "level": "DEBUG",
    })]
    assert not entry.rec.overrides


def test_main_reads_endpoints_from_environment(entry, monkeypatch):
    monkeypatch.setenv("METASWEEPER_ZMQ_ENDPOINT", "tcp://env:1111")
    monkeypatch.setenv("METASWEEPER_ZMQ_PUB_ENDPOINT", "tcp://env:2222")
    monkeypatch.setenv("METASWEEPER_ZMQ_CTRL_ENDPOINT", "tcp://env:3333")
    assert entry.module.main() == 17
    kw = entry.rec.run[-1]
    assert kw["endpoint"] == "tcp://env:1111"
    assert kw["pub_endpoint"] == "tcp://env:2222"
    assert kw["ctrl_endpoint"] == "tcp://env:3333"


def test_main_explicit_flags_override_env_and_set_data_dir(
    entry, monkeypatch, tmp_path,
):
    monkeypatch.setenv("METASWEEPER_ZMQ_ENDPOINT", "tcp://env:1111")
    monkeypatch.setenv("METASWEEPER_ZMQ_PUB_ENDPOINT", "tcp://env:2222")
    monkeypatch.setenv("METASWEEPER_ZMQ_CTRL_ENDPOINT", "tcp://env:3333")
    data_dir = tmp_path / "custom-data"
    monkeypatch.setattr(sys, "argv", [
        "plugin_manager",
        "--endpoint", "tcp://flag:1",
        "--pub-endpoint", "tcp://flag:2",
        "--ctrl-endpoint", "tcp://flag:3",
        "--mode", "tray",
        "--no-gui",
        "--data-dir", str(data_dir),
    ])
    assert entry.module.main() == 17
    assert entry.rec.overrides == [str(data_dir)]
    kw = entry.rec.run[-1]
    assert kw == {
        "endpoint": "tcp://flag:1",
        "with_gui": False,
        "show_main_window": False,
        "pub_endpoint": "tcp://flag:2",
        "ctrl_endpoint": "tcp://flag:3",
    }
    assert entry.rec.init == [((entry.rec.log_dir,), {
        "console": True, "level": "DEBUG",
    })]


@pytest.mark.parametrize("flags, with_gui, show_window", [
    ([], True, True),
    (["--mode", "window"], True, True),
    (["--mode", "tray"], True, False),
    (["--no-gui"], False, False),
    (["--mode", "tray", "--no-gui"], False, False),
])
def test_main_gui_mode_matrix(entry, monkeypatch, flags, with_gui, show_window):
    monkeypatch.setattr(sys, "argv", ["plugin_manager", *flags])
    assert entry.module.main() == 17
    kw = entry.rec.run[-1]
    assert kw["with_gui"] is with_gui
    assert kw["show_main_window"] is show_window


def test_main_data_dir_without_other_flags(entry, monkeypatch, tmp_path):
    data_dir = tmp_path / "only-data"
    monkeypatch.setattr(sys, "argv", [
        "plugin_manager", "--data-dir", str(data_dir),
    ])
    assert entry.module.main() == 17
    assert entry.rec.overrides == [str(data_dir)]
    assert entry.rec.run[-1]["show_main_window"] is True


def test_main_guard_calls_sys_exit(entry, monkeypatch):
    """执行源码的 __main__ 分支，sys.exit 被替换成记录器。"""
    module = entry.module
    for key, value in _QT_DEFAULTS.items():
        monkeypatch.setenv(key, value)  # setdefault 不再改动真实环境
    exits = []
    monkeypatch.setattr(sys, "exit", lambda code=0: exits.append(code))
    source = Path(module.__file__).read_text(encoding="utf-8")
    namespace = {
        "__name__": "__main__",
        "__file__": module.__file__,
        "__package__": "plugin_manager",
        "__spec__": module.__spec__,
    }
    exec(compile(source, str(module.__file__), "exec"), namespace)
    assert exits == [17]
    assert len(entry.rec.run) == 1


# ── _run.py 的 debugpy 分支 ───────────────────────────────────────────────


def test_run_debugpy_listen_and_wait(run_entry, monkeypatch, capsys):
    calls = []
    fake_debugpy = SimpleNamespace(
        listen=lambda *a, **kw: calls.append(("listen", a, kw)),
        wait_for_client=lambda: calls.append(("wait",)),
    )
    monkeypatch.setitem(sys.modules, "debugpy", fake_debugpy)
    monkeypatch.setattr(sys, "argv", [
        "plugin_manager", "--debug", "--debug-port", "6001",
    ])
    assert run_entry.module.main() == 17
    assert calls[0][1] == (("0.0.0.0", 6001),)
    assert calls[0][2] == {"in_process_debug_adapter": True}
    assert calls[1] == ("wait",)
    out = capsys.readouterr().out
    assert "Waiting for debugger attach on port 6001" in out
    assert "Debugger attached" in out


def test_run_debugpy_default_port(run_entry, monkeypatch, capsys):
    listens = []
    fake_debugpy = SimpleNamespace(
        listen=lambda *a, **kw: listens.append((a, kw)),
        wait_for_client=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "debugpy", fake_debugpy)
    monkeypatch.setattr(sys, "argv", ["plugin_manager", "--debug"])
    assert run_entry.module.main() == 17
    assert listens == [((("0.0.0.0", 5678),), {"in_process_debug_adapter": True})]
    assert "Waiting for debugger attach on port 5678" in capsys.readouterr().out


def test_run_debugpy_import_error_is_only_a_warning(
    run_entry, monkeypatch, capsys,
):
    monkeypatch.setitem(sys.modules, "debugpy", None)
    monkeypatch.setattr(sys, "argv", ["plugin_manager", "--debug"])
    assert run_entry.module.main() == 17
    assert "debugpy import failed" in capsys.readouterr().out
    assert len(run_entry.rec.run) == 1
    assert len(run_entry.rec.init) == 1


def test_run_debug_port_without_debug_never_touches_debugpy(
    run_entry, monkeypatch,
):
    def boom(*args, **kwargs):
        raise AssertionError("debugpy must not be used without --debug")

    monkeypatch.setitem(sys.modules, "debugpy", SimpleNamespace(
        listen=boom, wait_for_client=boom,
    ))
    monkeypatch.setattr(sys, "argv", [
        "plugin_manager", "--debug-port", "7000",
    ])
    assert run_entry.module.main() == 17
