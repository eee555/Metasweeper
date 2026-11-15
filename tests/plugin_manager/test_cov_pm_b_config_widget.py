"""Coverage tests for plugin_manager.config_widget (OtherInfoWidget + scroll area)."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QSpinBox

from plugin_manager.config_widget import OtherInfoScrollArea, OtherInfoWidget
from plugin_sdk.config_types import (
    BoolConfig, ChoiceConfig, IntConfig, OtherInfoBase, TextConfig,
)
from shared_types.widgets import ToggleSwitch


@pytest.fixture(autouse=True)
def _offscreen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


class EmptyConfig(OtherInfoBase):
    pass


class SampleConfig(OtherInfoBase):
    retries = IntConfig(3, "重试次数", min_value=0, max_value=10,
                        description="失败重试次数")
    enabled = BoolConfig(True, "启用")
    mode = ChoiceConfig("a", "模式", choices=[("a", "A"), ("b", "B")])
    name = TextConfig("default", "名称", validator=lambda v: None if v.strip() else "不能为空")
    note = TextConfig("hidden", "备注", visible=False, description="隐藏字段")
    untitled = TextConfig("x", "")


class PluginWithValidate:
    def __init__(self, errors=None, raises=False):
        self.errors = errors or {}
        self.raises = raises
        self.pending_seen = None

    def validate_config(self, pending):
        self.pending_seen = pending
        if self.raises:
            raise RuntimeError("validate exploded")
        return self.errors


class PluginWithRunValidate:
    def __init__(self, errors=None, raises=False):
        self.errors = errors or {}
        self.raises = raises
        self.pending_seen = None
        self.legacy_called = False

    def run_validate_config(self, pending):
        self.pending_seen = pending
        if self.raises:
            raise RuntimeError("run_validate exploded")
        return self.errors

    def validate_config(self, pending):
        self.legacy_called = True
        return {"legacy": "should not be used"}


class PluginWithoutValidate:
    pass


class PluginWithBadValidator:
    @property
    def validate_config(self):
        return "not callable"


def _make_widget(qtbot, config=None):
    config = config or SampleConfig()
    widget = OtherInfoWidget(config)
    qtbot.addWidget(widget)
    return widget


def test_setup_ui_empty_config_shows_placeholder(qapp, qtbot):
    widget = _make_widget(qtbot, EmptyConfig())
    labels = widget.findChildren(QLabel)
    assert any("此插件无自定义配置" in label.text() for label in labels)
    assert widget._widgets == {}
    assert widget.collect_pending() == {}


def test_setup_ui_skips_invisible_field_and_initializes_widgets(qapp, qtbot):
    config = SampleConfig()
    widget = _make_widget(qtbot, config)
    assert set(widget._widgets) == {"retries", "enabled", "mode", "name", "untitled"}
    assert "note" not in widget._labels
    assert widget._widgets["retries"].get_value() == 3
    assert widget._widgets["enabled"].get_value() is True
    assert widget._widgets["mode"].get_value() == "a"
    assert widget._widgets["name"].get_value() == "default"
    assert widget._descriptions == {"retries": "失败重试次数"}
    assert widget._widgets["retries"].toolTip() == "失败重试次数"
    assert widget._default_label_style["retries"] == ""
    assert widget.other_info is config


def test_user_changes_are_collected_and_emitted(qapp, qtbot):
    widget = _make_widget(qtbot)
    seen = []
    widget.config_changed.connect(lambda name, value: seen.append((name, value)))

    widget.findChild(QSpinBox).setValue(9)
    widget.findChild(ToggleSwitch).setChecked(False)
    widget.findChild(QComboBox).setCurrentIndex(1)
    line_edits = widget.findChildren(QLineEdit)
    name_edit = next(edit for edit in line_edits if edit.text() == "default")
    name_edit.setText("Alice")

    pending = widget.collect_pending()
    assert pending == {"retries": 9, "enabled": False, "mode": "b",
                       "name": "Alice", "untitled": "x"}
    assert ("retries", 9) in seen
    assert ("enabled", False) in seen
    assert ("mode", "b") in seen
    assert ("name", "Alice") in seen


def test_on_changed_direct_call_emits_current_value(qapp, qtbot):
    widget = _make_widget(qtbot)
    seen = []
    widget.config_changed.connect(lambda name, value: seen.append((name, value)))
    widget._widgets["retries"].set_value(4)
    widget._on_changed("retries")
    assert seen[-1] == ("retries", 4)


def test_validate_pending_valid_and_field_error(qapp, qtbot):
    widget = _make_widget(qtbot)
    assert widget.validate_pending(None) == {}
    widget._widgets["name"].set_value("  ")
    assert widget.validate_pending(None) == {"name": "不能为空"}


def test_validate_pending_legacy_plugin_results_and_exception(qapp, qtbot):
    widget = _make_widget(qtbot)
    plugin = PluginWithValidate({"retries": "拒绝该值", "ignored": "", "code": 7})
    errors = widget.validate_pending(plugin)
    assert errors["retries"] == "拒绝该值"
    assert "ignored" not in errors
    assert errors["code"] == "7"
    assert plugin.pending_seen == widget.collect_pending()

    broken = PluginWithValidate(raises=True)
    assert widget.validate_pending(broken) == {"_plugin": "validate exploded"}
    assert widget.validate_pending(PluginWithValidate("not-a-dict")) == {}


def test_validate_pending_run_validate_takes_precedence_and_exceptions(qapp, qtbot):
    widget = _make_widget(qtbot)
    plugin = PluginWithRunValidate({"mode": "必须使用 b", "skip": None})
    errors = widget.validate_pending(plugin)
    assert errors == {"mode": "必须使用 b"}
    assert plugin.pending_seen == widget.collect_pending()
    assert plugin.legacy_called is False

    broken = PluginWithRunValidate(raises=True)
    assert widget.validate_pending(broken) == {"_plugin": "run_validate exploded"}
    assert widget.validate_pending(PluginWithRunValidate("not-a-dict")) == {}


def test_validate_pending_ignores_non_callable_and_missing_plugin_hooks(qapp, qtbot):
    widget = _make_widget(qtbot)
    assert widget.validate_pending(PluginWithoutValidate()) == {}
    assert widget.validate_pending(PluginWithBadValidator()) == {}


def test_validate_pending_skips_widget_without_field_definition(qapp, qtbot):
    widget = _make_widget(qtbot)
    widget._widgets["orphan"] = widget._widgets["name"]
    assert widget.validate_pending(None) == {}


def test_field_label_variants(qapp, qtbot):
    widget = _make_widget(qtbot)
    assert widget.field_label("_plugin") == "插件"
    assert widget.field_label("retries") == "重试次数"
    assert widget.field_label("untitled") == "untitled"
    assert widget.field_label("missing") == "missing"


def test_set_field_description_updates_existing_and_unknown_fields(qapp, qtbot):
    widget = _make_widget(qtbot)
    widget.set_field_description("retries", "新的说明")
    assert widget._widgets["retries"].toolTip() == "新的说明"
    assert widget._descriptions["retries"] == "新的说明"

    widget.set_field_description("ghost", "幽灵说明")
    assert widget._descriptions["ghost"] == "幽灵说明"


def test_highlight_and_clear_errors(qapp, qtbot):
    widget = _make_widget(qtbot)
    widget._labels["untitled"].setStyleSheet("color: blue;")
    widget._default_label_style["untitled"] = "color: blue;"

    widget.highlight_errors({"retries": "太少了", "ghost": " irrelevant"})
    assert "c62828" in widget._labels["retries"].styleSheet()
    assert widget._labels["enabled"].styleSheet() == ""
    assert widget._labels["untitled"].styleSheet() == "color: blue;"

    widget.clear_highlights()
    assert widget._labels["retries"].styleSheet() == ""
    assert widget._labels["untitled"].styleSheet() == "color: blue;"


def test_apply_to_config_and_refresh_from_config(qapp, qtbot):
    config = SampleConfig()
    changes = []
    config.set_on_change(lambda name, value: changes.append((name, value)))
    widget = _make_widget(qtbot, config)
    widget._widgets["retries"].set_value(8)
    widget._widgets["enabled"].set_value(False)
    widget._widgets["mode"].set_value("b")
    widget._widgets["name"].set_value("Bob")
    widget._widgets["untitled"].set_value("y")

    widget.apply_to_config()
    assert config.retries == 8
    assert config.enabled is False
    assert config.mode == "b"
    assert config.name == "Bob"
    assert config.untitled == "y"
    assert config.note == "hidden"
    assert ("retries", 8) in changes

    config.retries = 2
    config.enabled = True
    config.mode = "a"
    config.name = "Carol"
    config.untitled = "z"
    widget.refresh_from_config()
    assert widget.collect_pending() == {
        "retries": 2, "enabled": True, "mode": "a",
        "name": "Carol", "untitled": "z",
    }


def test_scroll_area_delegates_all_methods_and_signal(qapp, qtbot):
    config = SampleConfig()
    area = OtherInfoScrollArea(config)
    qtbot.addWidget(area)
    assert area.widgetResizable() is True
    assert area.other_info is config
    assert area.findChild(OtherInfoWidget) is area._inner_widget

    seen = []
    area.config_changed.connect(lambda name, value: seen.append((name, value)))
    area._inner_widget._widgets["retries"].set_value(6)
    area._inner_widget._on_changed("retries")
    assert seen and seen[-1] == ("retries", 6)

    plugin = PluginWithValidate({"mode": "must be b"})
    assert area.validate_pending(plugin) == {"mode": "must be b"}
    assert area.validate_pending(None) == {}
    assert area.field_label("retries") == "重试次数"
    assert area.field_label("_plugin") == "插件"
    assert area.field_label("missing") == "missing"

    area.set_field_description("retries", "委托说明")
    assert area._inner_widget._widgets["retries"].toolTip() == "委托说明"
    area.highlight_errors({"retries": "错误"})
    assert "c62828" in area._inner_widget._labels["retries"].styleSheet()
    area.clear_highlights()
    assert area._inner_widget._labels["retries"].styleSheet() == ""

    area._inner_widget._widgets["name"].set_value("Dana")
    area.apply_to_config()
    assert config.name == "Dana"
    config.name = "Eve"
    area.refresh_from_config()
    assert area._inner_widget.collect_pending()["name"] == "Eve"
