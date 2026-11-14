"""logging_setup.py 覆盖；所有 loguru sink 在 try/finally 中清理。

loguru.logger 是进程级全局对象：本文件的 log_env fixture 会快照并恢复
handlers / handlers_count / _console_sink_id，避免污染其他测试。
"""
from __future__ import annotations

import importlib
import itertools
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import loguru
import pytest

from plugin_manager.logging_setup import DEFAULT_LOG_CONFIG, LogConfig


@pytest.fixture
def log_env(monkeypatch, tmp_path):
    ls = importlib.import_module("plugin_manager.logging_setup")
    lg = loguru.logger
    core = lg._core
    original_handlers = dict(core.handlers)
    original_count = core.handlers_count
    original_console_id = ls._console_sink_id
    env = SimpleNamespace(
        module=ls,
        logger=lg,
        core=core,
        real_add=lg.add,
        real_remove=lg.remove,
        added_ids=[],
        tmp_path=tmp_path,
    )
    monkeypatch.setattr(ls, "_console_sink_id", None)
    try:
        yield env
    finally:
        for sink_id in env.added_ids:
            if sink_id in core.handlers:
                try:
                    env.real_remove(sink_id)
                except ValueError:
                    pass
        core.handlers.clear()
        core.handlers.update(original_handlers)
        core.handlers_count = original_count
        ls._console_sink_id = original_console_id


def _patch_add_remove(monkeypatch, env, *, real_add=False):
    """打桩 logger.add / logger.remove；返回 (adds, removes) 记录列表。"""
    adds, removes = [], []
    ids = itertools.count(100)

    if real_add:
        def fake_add(*args, **kwargs):
            sink_id = env.real_add(*args, **kwargs)
            env.added_ids.append(sink_id)
            adds.append((sink_id, args, kwargs))
            return sink_id
    else:
        def fake_add(*args, **kwargs):
            sink_id = next(ids)
            adds.append((sink_id, args, kwargs))
            return sink_id

    def fake_remove(*args, **kwargs):
        removes.append((args, kwargs))

    monkeypatch.setattr(env.logger, "add", fake_add)
    monkeypatch.setattr(env.logger, "remove", fake_remove)
    return adds, removes


# ── LogConfig ─────────────────────────────────────────────────────────────


def test_log_config_defaults(log_env):
    cfg = LogConfig()
    assert cfg.rotation == "10 MB"
    assert cfg.retention == 5
    assert DEFAULT_LOG_CONFIG == LogConfig()


def test_log_config_custom_and_frozen(log_env):
    cfg = LogConfig(rotation="1 MB", retention=2)
    assert (cfg.rotation, cfg.retention) == ("1 MB", 2)
    with pytest.raises(FrozenInstanceError):
        cfg.rotation = "2 MB"


# ── init_logging ──────────────────────────────────────────────────────────


def test_init_logging_real_file_sink_and_console(log_env, monkeypatch):
    adds, removes = _patch_add_remove(monkeypatch, log_env, real_add=True)
    log_dir = log_env.tmp_path / "custom" / "logs"
    log_env.module.init_logging(log_dir, console=True, level="INFO")
    try:
        assert removes == [((), {})]
        assert len(adds) == 2
        main_sink_id, main_args, main_kwargs = adds[0]
        assert main_args[0] == str(log_dir / "main.log")
        assert main_kwargs["level"] == "DEBUG"
        assert main_kwargs["rotation"] == "10 MB"
        assert main_kwargs["retention"] == 5
        assert main_kwargs["encoding"] == "utf-8"
        assert "{level" in main_kwargs["format"]

        console_sink_id, console_args, console_kwargs = adds[1]
        assert callable(console_args[0])
        assert console_kwargs["level"] == "INFO"
        assert console_kwargs["colorize"] is True
        assert "<green>" in console_kwargs["format"]
        assert log_env.module._console_sink_id == console_sink_id

        assert (log_dir / "plugins").is_dir()
        assert (log_dir / "main.log").is_file()
        log_env.logger.info("real-file-sink-message")
        assert "real-file-sink-message" in (
            log_dir / "main.log"
        ).read_text(encoding="utf-8")

        console_handler = log_env.core.handlers[console_sink_id]
        assert console_handler._levelno == log_env.core.levels["INFO"].no
        log_env.module.set_console_log_level("WARNING")
        assert console_handler._levelno == log_env.core.levels["WARNING"].no
        log_env.module.set_console_log_level("NOT_A_LEVEL")
        assert console_handler._levelno == log_env.core.levels["WARNING"].no
        assert main_sink_id in log_env.core.handlers
    finally:
        removed = [sid for sid, _, _ in adds]
        for sink_id in removed:
            if sink_id in log_env.core.handlers:
                log_env.real_remove(sink_id)
                log_env.added_ids.remove(sink_id)


def test_init_logging_without_console(log_env, monkeypatch):
    adds, removes = _patch_add_remove(monkeypatch, log_env)
    log_dir = log_env.tmp_path / "logs-no-console"
    log_env.module.init_logging(log_dir, console=False, level="WARNING")
    assert removes == [((), {})]
    assert len(adds) == 1
    assert adds[0][1][0] == str(log_dir / "main.log")
    assert adds[0][2]["level"] == "DEBUG"
    assert log_env.module._console_sink_id is None
    assert (log_dir / "plugins").is_dir()


def test_init_logging_custom_config_and_string_log_dir(log_env, monkeypatch):
    adds, _ = _patch_add_remove(monkeypatch, log_env)
    cfg = LogConfig(rotation="2 MB", retention=9)
    log_env.module.init_logging(
        str(log_env.tmp_path / "string-logs"),
        console=True, level="ERROR", log_config=cfg,
    )
    assert adds[0][2]["rotation"] == "2 MB"
    assert adds[0][2]["retention"] == 9
    assert adds[1][2]["level"] == "ERROR"
    assert (log_env.tmp_path / "string-logs" / "plugins").is_dir()


def test_init_logging_repeated_calls_are_idempotent(log_env, monkeypatch):
    adds, removes = _patch_add_remove(monkeypatch, log_env)
    for _ in range(3):
        log_env.module.init_logging(
            log_env.tmp_path / "repeat", console=True, level="DEBUG",
        )
    assert len(removes) == 3
    assert len(adds) == 6  # 每次重置：main.log sink + console sink
    assert log_env.module._console_sink_id == adds[-1][0]
    assert len({sid for sid, _, _ in adds}) == len(adds)


# ── get_plugin_logger ─────────────────────────────────────────────────────


def test_get_plugin_logger_with_custom_dir_and_filter(log_env):
    custom_root = log_env.tmp_path / "custom-plugin-logs"
    lg, sink_id = log_env.module.get_plugin_logger(
        "demo_plugin", log_dir=custom_root, log_config=LogConfig("3 MB", 7),
    )
    log_env.added_ids.append(sink_id)
    try:
        log_file = custom_root / "plugins" / "demo_plugin.log"
        assert log_file.is_file()
        assert lg is not loguru.logger
        handler = log_env.core.handlers[sink_id]
        assert handler._levelno == log_env.core.levels["DEBUG"].no

        lg.info("demo-plugin-message")
        assert "demo-plugin-message" in log_file.read_text(encoding="utf-8")

        # filter 只接收相同 plugin extra 的记录。
        other = loguru.logger.bind(plugin="other_plugin")
        other.info("should-be-filtered")
        assert "should-be-filtered" not in log_file.read_text(encoding="utf-8")

        log_env.module.set_plugin_log_level(sink_id, "ERROR")
        assert handler._levelno == log_env.core.levels["ERROR"].no
        assert handler._levelname == "ERROR"
        log_env.module.set_plugin_log_level(sink_id, "NOT_A_LEVEL")
        assert handler._levelno == log_env.core.levels["ERROR"].no
    finally:
        log_env.real_remove(sink_id)
        log_env.added_ids.remove(sink_id)


def test_get_plugin_logger_default_dir_uses_app_paths(log_env, monkeypatch):
    app_paths = importlib.import_module("plugin_manager.app_paths")
    monkeypatch.setattr(app_paths, "get_data_dir", lambda: log_env.tmp_path)
    lg, sink_id = log_env.module.get_plugin_logger("default_dir_plugin")
    log_env.added_ids.append(sink_id)
    try:
        assert (log_env.tmp_path / "logs" / "plugins" / "default_dir_plugin.log").is_file()
        assert lg is not loguru.logger
        assert sink_id in log_env.core.handlers
    finally:
        log_env.real_remove(sink_id)
        log_env.added_ids.remove(sink_id)


# ── 日志级别设置 ─────────────────────────────────────────────────────────


def test_set_plugin_log_level_valid_invalid_and_missing_sink(log_env, monkeypatch):
    handler = SimpleNamespace(_levelno=10, _levelname="DEBUG")
    monkeypatch.setitem(log_env.core.handlers, 4201, handler)
    log_env.module.set_plugin_log_level(4201, "warning")
    assert (handler._levelno, handler._levelname) == (
        log_env.core.levels["WARNING"].no, "WARNING",
    )
    log_env.module.set_plugin_log_level(4201, "NOT_A_LEVEL")
    assert (handler._levelno, handler._levelname) == (
        log_env.core.levels["WARNING"].no, "WARNING",
    )
    log_env.module.set_plugin_log_level(4201, "eRrOr")
    assert (handler._levelno, handler._levelname) == (
        log_env.core.levels["ERROR"].no, "ERROR",
    )
    log_env.module.set_plugin_log_level(999999, "CRITICAL")  # 缺失 sink：静默忽略
    assert (handler._levelno, handler._levelname) == (
        log_env.core.levels["ERROR"].no, "ERROR",
    )


def test_set_console_log_level_no_console_sink(log_env):
    assert log_env.module._console_sink_id is None
    log_env.module.set_console_log_level("INFO")  # 早退，不抛异常
    assert log_env.module._console_sink_id is None


def test_set_console_log_level_valid_invalid_and_missing_sink(
    log_env, monkeypatch,
):
    handler = SimpleNamespace(_levelno=10, _levelname="DEBUG")
    monkeypatch.setitem(log_env.core.handlers, 4301, handler)
    monkeypatch.setattr(log_env.module, "_console_sink_id", 4301)
    log_env.module.set_console_log_level("CRITICAL")
    assert (handler._levelno, handler._levelname) == (
        log_env.core.levels["CRITICAL"].no, "CRITICAL",
    )
    log_env.module.set_console_log_level("bogus")
    assert (handler._levelno, handler._levelname) == (
        log_env.core.levels["CRITICAL"].no, "CRITICAL",
    )
    log_env.module.set_console_log_level("trace")
    assert (handler._levelno, handler._levelname) == (
        log_env.core.levels["TRACE"].no, "TRACE",
    )
    monkeypatch.setattr(log_env.module, "_console_sink_id", 999999)
    log_env.module.set_console_log_level("DEBUG")  # 缺失 sink：静默忽略
    assert (handler._levelno, handler._levelname) == (
        log_env.core.levels["TRACE"].no, "TRACE",
    )
