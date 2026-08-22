from __future__ import annotations

from plugin_sdk import BoolConfig, OtherInfoBase, TextConfig
from plugin_manager.config_widget import OtherInfoWidget


class _SampleConfig(OtherInfoBase):
    name = TextConfig("", "名称", validator=lambda v: None if v.strip() else "不能为空")
    enabled = BoolConfig(True, "启用")


class _FakePlugin:
    def validate_config(self, pending: dict) -> dict[str, str]:
        if pending.get("name") == "bad":
            return {"name": "插件拒绝该名称"}
        return {}


def test_validate_pending_field_error(qtbot):
    config = _SampleConfig()
    widget = OtherInfoWidget(config)
    qtbot.addWidget(widget)
    widget._widgets["name"].set_value("   ")

    errors = widget.validate_pending(None)
    assert errors == {"name": "不能为空"}


def test_validate_pending_plugin_error(qtbot):
    config = _SampleConfig()
    widget = OtherInfoWidget(config)
    qtbot.addWidget(widget)
    widget._widgets["name"].set_value("bad")

    errors = widget.validate_pending(_FakePlugin())
    assert errors == {"name": "插件拒绝该名称"}


def test_apply_to_config_uses_apply_pending(qtbot):
    config = _SampleConfig()
    widget = OtherInfoWidget(config)
    qtbot.addWidget(widget)
    widget._widgets["name"].set_value("  Alice  ")
    widget._widgets["enabled"].set_value(False)

    widget.apply_to_config()

    assert config.name == "  Alice  "
    assert config.enabled is False
