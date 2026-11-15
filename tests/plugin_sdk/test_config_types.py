from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QColorDialog, QFileDialog, QLineEdit, QPushButton

from plugin_sdk.config_types import (
    BaseConfig,
    BoolConfig,
    ChoiceConfig,
    ColorConfig,
    FileConfig,
    FloatConfig,
    IntConfig,
    LongTextConfig,
    OtherInfoBase,
    PathConfig,
    RangeConfig,
    TextConfig,
)
from plugin_sdk.config_types.base_config import ConfigWidgetBase


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("config, value, stored, restored", [
    (BoolConfig(1), True, True, True),
    (ChoiceConfig(3, choices=[("3", "Three")]), "3", "3", "4"),
    (FloatConfig("2.5"), 2.5, 2.5, 3.5),
    (IntConfig("2"), 2, 2, 3),
    (LongTextConfig(123), "123", "123", "restored"),
    (TextConfig(123), "123", "123", "restored"),
])
def test_scalar_config_storage_and_normalized_defaults(config, value, stored, restored):
    assert config.default == value
    assert config.to_storage(value) == stored
    assert config.from_storage(stored) == value
    assert config.from_storage(restored) == restored


def test_base_config_validation_descriptor_and_widget_contract(app):
    class Field(BaseConfig[int]):
        def create_widget(self):
            return ConfigWidgetBase()

        def to_storage(self, value):
            return value

        def from_storage(self, data):
            return data

    field = Field(1)
    assert field.validate(2) is None
    field.validator = lambda _: True
    assert field.validate(2) is None
    field.validator = lambda _: None
    assert field.validate(2) is None
    field.validator = lambda _: False
    assert field.validate(2)
    field.validator = lambda _: "custom"
    assert field.validate(2) == "custom"
    field.validator = lambda _: ""
    assert field.validate(2)
    field.validator = lambda _: 0
    assert field.validate(2)

    class Container:
        number = field

    assert Container.number is field
    assert Container().number == 1
    Container().number = 5
    with pytest.raises(NotImplementedError):
        ConfigWidgetBase().get_value()
    with pytest.raises(NotImplementedError):
        ConfigWidgetBase().set_value(1)


def test_wrapped_widgets_forward_values_and_emit_changes(app, qtbot):
    configurations = [
        BoolConfig(False, description="bool"),
        ChoiceConfig("a", choices=[("a", "A"), ("b", "B")]),
        FloatConfig(1.5),
        IntConfig(1),
        IntConfig(1, use_slider=True),
        LongTextConfig("first", placeholder="prompt"),
        TextConfig("first", placeholder="prompt", password=True),
        TextConfig("secret", copy_button=True),
    ]
    for config in configurations:
        wrapper = config.create_widget()
        qtbot.addWidget(wrapper)
        wrapper.set_value(config.from_storage(config.to_storage(config.default)))
        assert wrapper.get_value() == config.default
        received = []
        wrapper.value_change.connect(received.append, Qt.ConnectionType.DirectConnection)
        widget = wrapper._widget
        if isinstance(config, BoolConfig):
            widget.setChecked(True)
            assert received == [True]
        elif isinstance(config, ChoiceConfig):
            widget.setCurrentIndex(1)
            assert received == ["b"]
        elif isinstance(config, FloatConfig):
            widget.setValue(2.5)
            assert received == [2.5]
        elif isinstance(config, IntConfig):
            widget.setValue(2)
            assert received == [2]
        elif isinstance(config, LongTextConfig):
            widget.setPlainText("next")
            assert received == ["next"]
        elif isinstance(config, TextConfig):
            line_edit = widget if isinstance(widget, QLineEdit) else widget.findChild(QLineEdit)
            line_edit.setText(" next ")
            assert received == [" next "]


def test_choice_with_invalid_default_and_invalid_set_value(app, qtbot):
    config = ChoiceConfig("missing", choices=[("a", "A")])
    widget = config.create_widget()
    qtbot.addWidget(widget)
    assert widget.get_value() == "a"
    widget.set_value("missing")
    assert widget.get_value() == "a"


def test_color_widget_valid_and_invalid_values(app, qtbot, monkeypatch):
    config = ColorConfig("1976d2", description="color")
    assert config.default == "#1976d2"
    widget = config.create_widget()
    qtbot.addWidget(widget)
    changed = []
    widget.value_change.connect(changed.append, Qt.ConnectionType.DirectConnection)
    widget.set_value("invalid")
    assert widget.get_value() == config.default
    widget.set_value("#abcdef")
    assert widget.get_value() == "#abcdef"
    assert changed == ["#abcdef"]

    monkeypatch.setattr(QColorDialog, "getColor", lambda *_: QColor("#123456"))
    widget._btn.click()
    assert widget.get_value() == "#123456"
    monkeypatch.setattr(QColorDialog, "getColor", lambda *_: __import__("PySide6").QtGui.QColor())
    widget._text_btn.click()
    assert widget.get_value() == "#123456"


def test_file_and_path_widgets_browse_open_save_and_cancel(app, qtbot, monkeypatch):
    file_config = FileConfig(None, filter="JSON (*.json)", description="file")
    assert file_config.default == ""
    file_widget = file_config.create_widget()
    qtbot.addWidget(file_widget)
    file_changes = []
    file_widget.value_change.connect(file_changes.append, Qt.ConnectionType.DirectConnection)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: ("/tmp/open.json", ""))
    file_widget.findChild(QPushButton).click()
    assert file_widget.get_value() == "/tmp/open.json"
    assert file_changes == ["/tmp/open.json"]
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: ("", ""))
    file_widget.findChild(QPushButton).click()
    assert file_widget.get_value() == "/tmp/open.json"

    save_widget = FileConfig("out.json", save_mode=True).create_widget()
    qtbot.addWidget(save_widget)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: ("/tmp/save.json", ""))
    save_widget.findChild(QPushButton).click()
    assert save_widget.get_value() == "/tmp/save.json"

    path_widget = PathConfig("/tmp", description="path").create_widget()
    qtbot.addWidget(path_widget)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: "/tmp/new")
    path_widget.findChild(QPushButton).click()
    assert path_widget.get_value() == "/tmp/new"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: "")
    path_widget.findChild(QPushButton).click()
    assert path_widget.get_value() == "/tmp/new"


def test_file_path_and_text_storage_fallbacks(app):
    file_config = FileConfig("fallback")
    path_config = PathConfig("fallback")
    text_config = TextConfig("fallback")
    long_config = LongTextConfig("fallback")
    assert file_config.from_storage(None) == "fallback"
    assert path_config.from_storage(None) == "fallback"
    assert text_config.from_storage(None) == "fallback"
    assert long_config.from_storage(None) == "fallback"
    assert FileConfig(0).from_storage(0) == ""
    assert PathConfig(0).from_storage(0) == ""


def test_numeric_config_invalid_storage_and_range_widget(app, qtbot):
    assert FloatConfig(1.5).from_storage(None) == 1.5
    assert IntConfig(4).from_storage("bad") == 4
    range_config = RangeConfig([2, 8], min_value=0, max_value=10, description="range")
    assert range_config.default == (0, 10)
    widget = range_config.create_widget()
    qtbot.addWidget(widget)
    assert widget.get_value() == (0, 10)
    changed = []
    widget.value_change.connect(changed.append, Qt.ConnectionType.DirectConnection)
    widget.set_value((3, 9))
    assert widget.get_value() == (3, 9)
    assert changed
    before = widget.get_value()
    widget.set_value([4, 7])
    assert widget.get_value() == before
    assert range_config.to_storage((3, 9)) == [3, 9]
    assert range_config.from_storage([4, "7"]) == (4, 7)
    assert range_config.from_storage("bad") == range_config.default


def test_config_container_fields_callbacks_and_roundtrip(app):
    class Info(OtherInfoBase):
        count = IntConfig(2, validator=lambda value: value >= 0 or "negative")
        token = TextConfig("", password=True)
        bounds = RangeConfig((1, 3))

    info = Info()
    assert set(info.get_fields()) == {"count", "token", "bounds"}
    assert info.to_dict() == {"count": 2, "token": "", "bounds": [1, 3]}
    changes = []
    info.set_on_change(lambda key, value: changes.append((key, value)))
    info.count = 4
    assert changes == [("count", 4)]
    with pytest.raises(ValueError, match="negative"):
        info.count = -1
    info.apply_pending({"count": -2, "unknown": 3}, silent=True)
    assert info.count == -2
    info.token = "private"
    assert info.to_log_dict()["token"] == "***"
    assert "***" in repr(info)
    info.from_dict({"count": "bad", "bounds": [5, 9]}, silent=False)
    assert info.count == 2
    assert info.bounds == (5, 9)
    info.reset_to_defaults(silent=False)
    assert info.count == 2
    assert info.bounds == (1, 3)
    assert OtherInfoBase().to_dict() == {}
