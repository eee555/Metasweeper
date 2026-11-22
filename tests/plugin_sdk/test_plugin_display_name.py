"""插件显示名可翻译，但不得影响任何以稳定标识为键的逻辑。"""
from __future__ import annotations

from pathlib import Path

from plugin_sdk.plugin_base import PluginInfo, resolve_display_name
from utils.plugin_i18n import PluginText


class _FakeTranslate:
    """模拟 PluginTranslate：保留上下文与源文本，可按当前语言解析。"""

    def __init__(self, translated: str):
        self._translated = translated

    def tr(self, source: str) -> PluginText:
        text = PluginText("Demo", source)
        # PluginText 依赖 Qt 翻译器；这里用桩替换解析结果
        text.translated = lambda: self._translated  # type: ignore[method-assign]
        return text


def test_display_name_is_independent_from_stable_name():
    info = PluginInfo(name="demo_stable_id",
                      display_name="演示插件")
    assert info.name == "demo_stable_id"
    assert info.display_name == "演示插件"


def test_missing_display_name_falls_back_to_stable_name():
    assert resolve_display_name(None, "demo") == "demo"
    assert resolve_display_name("", "demo") == "demo"


def test_plugin_text_display_name_resolves_per_language():
    translate = _FakeTranslate("Demo Plugin")
    info = PluginInfo(name="demo", display_name=translate.tr("演示插件"))
    assert info.name == "demo"
    assert resolve_display_name(info.display_name, info.name) == "Demo Plugin"


def test_display_name_does_not_leak_into_config_paths(tmp_path: Path):
    """配置目录、状态键与日志文件都应使用稳定标识。"""
    from plugin_manager.config_manager import PluginConfigManager

    manager = PluginConfigManager(tmp_path)
    path = manager.config_path("demo")
    assert path.parent.name == "demo"
    assert "演示插件" not in str(path)


def test_invalid_stable_name_still_rejected():
    import pytest

    for bad in ("", "a/b", "a\\b", ".", "..", "x" * 65):
        with pytest.raises(ValueError):
            PluginInfo(name=bad)
