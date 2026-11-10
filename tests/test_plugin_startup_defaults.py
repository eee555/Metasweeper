"""插件「启动时显示窗口」默认值与配置解耦回归测试。"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from plugin_manager.plugin_state import PluginState, PluginStateManager
from plugin_sdk.plugin_base import PluginInfo


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def test_named_plugins_declare_startup_window_hidden(app):
    """三个点名插件在自己 plugin_info() 中声明默认不自动开启界面。"""
    from plugins.clipboard_replay.plugin import ClipboardReplayPlugin
    from plugins.llm_minesweeper_controller.plugin import (
        LlmMinesweeperControllerPlugin,
    )
    from plugins.skin_manager.plugin import SkinManagerPlugin

    for cls in (ClipboardReplayPlugin, LlmMinesweeperControllerPlugin,
                SkinManagerPlugin):
        assert cls.plugin_info().show_window is False


def test_untouched_plugins_keep_sdk_default():
    """未声明 show_window 的插件沿用 SDK 默认值，通用层不做定制。"""
    assert PluginInfo(name="x").show_window is True
    assert PluginState().show_window is True


def test_startup_load_is_read_only(tmp_path: Path):
    """启动期读取状态不写盘；显式 set/save 才落盘。"""
    f = tmp_path / "plugin_states.json"
    raw = {"some_plugin": {
        "enabled": True,
        "show_window": True,
        "window_mode": "tab",
        "log_level": "DEBUG",
    }}
    f.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    before = f.read_text("utf-8")

    mgr = PluginStateManager(f)
    mgr.load()
    assert f.read_text("utf-8") == before
    assert mgr._dirty is False

    mgr.set("some_plugin", PluginState(show_window=False))
    mgr.save()
    assert mgr.get("some_plugin").show_window is False
