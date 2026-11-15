"""actions_rc.py 资源注册/注销的回归测试。

Qt 资源注册是进程级全局状态：qInitResources() 重复调用会叠加注册，
而 qCleanupResources() 只注销一份，残留的重复注册会让后续 QFile 读取
访问已释放的资源树（access violation）。因此本文件严格保证
「注销一次 → 重新注册一次」成对出现，且 finally 中只在资源确实缺失时
才补注册，绝不重复注册。

模块级 qInitResources() 语句由正常 import 覆盖，这里不再 exec 源码。
"""
from __future__ import annotations

import importlib
from contextlib import contextmanager

import pytest
from PySide6.QtCore import QFile

RESOURCE_PATH = ":/plugin_manager/actions/app.svg"


@pytest.fixture
def resource_module(qapp, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    return importlib.import_module("plugin_manager.actions_rc")


@contextmanager
def _unregistered(module):
    """临时注销资源，退出时保证恰好恢复一次注册。"""
    assert QFile(RESOURCE_PATH).exists() is True, "资源应在导入时已注册"
    module.qCleanupResources()
    try:
        assert QFile(RESOURCE_PATH).exists() is False
        yield
    finally:
        # 仅在确实缺失时补注册，避免重复注册导致资源树重复。
        if not QFile(RESOURCE_PATH).exists():
            module.qInitResources()


def test_qinit_qcleanup_are_callable(resource_module):
    assert callable(resource_module.qInitResources)
    assert callable(resource_module.qCleanupResources)


def test_cleanup_then_reinit_restores_known_resource(resource_module):
    with _unregistered(resource_module):
        assert QFile(RESOURCE_PATH).exists() is False
    assert QFile(RESOURCE_PATH).exists() is True


def test_resource_payload_is_readable_after_reinit(resource_module):
    with _unregistered(resource_module):
        assert QFile(RESOURCE_PATH).exists() is False
    f = QFile(RESOURCE_PATH)
    assert f.open(QFile.OpenModeFlag.ReadOnly) is True
    try:
        assert f.readAll().size() > 0
    finally:
        f.close()
    assert QFile(RESOURCE_PATH).exists() is True


def test_cleanup_is_restored_even_when_body_raises(resource_module):
    """断言失败等异常路径下也必须恢复注册，且只恢复一次。"""
    with pytest.raises(RuntimeError, match="boom"):
        with _unregistered(resource_module):
            raise RuntimeError("boom")
    assert QFile(RESOURCE_PATH).exists() is True
    # 恢复后仍可正常读取，说明没有残留的重复注册。
    f = QFile(RESOURCE_PATH)
    assert f.open(QFile.OpenModeFlag.ReadOnly) is True
    f.close()


def test_repeated_cleanup_init_cycles_stay_balanced(resource_module):
    for _ in range(3):
        with _unregistered(resource_module):
            assert QFile(RESOURCE_PATH).exists() is False
        assert QFile(RESOURCE_PATH).exists() is True
    f = QFile(RESOURCE_PATH)
    assert f.open(QFile.OpenModeFlag.ReadOnly) is True
    try:
        assert f.readAll().size() > 0
    finally:
        f.close()
