"""
插件配置 UI 组件

根据 OtherInfoBase 自动生成配置界面。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt5.QtCore import Qt, pyqtSignal, QCoreApplication
from PyQt5.QtWidgets import (
    QFormLayout,
    QLabel,
    QScrollArea,
    QWidget,
)

from plugin_sdk.config_types.base_config import ConfigWidgetBase
from plugin_sdk.config_types.other_info import OtherInfoBase

if TYPE_CHECKING:
    from plugin_sdk.plugin_base import BasePlugin

_ERROR_LABEL_STYLE = "color: #c62828; font-weight: bold;"


class OtherInfoWidget(QWidget):
    """
    根据 OtherInfoBase 自动生成配置 UI

    自动绑定配置字段 → UI 控件 → 值同步

    Signals:
        config_changed: 配置值变化信号，参数为 (字段名, 新值)
    """

    config_changed = pyqtSignal(str, object)  # (field_name, new_value)

    def __init__(self, other_info: OtherInfoBase, parent: QWidget | None = None) -> None:
        """
        初始化配置 UI

        Args:
            other_info: 配置容器实例
            parent: 父控件
        """
        super().__init__(parent)
        self._other_info = other_info
        self._widgets: dict[str, ConfigWidgetBase] = {}
        self._labels: dict[str, QLabel] = {}
        self._default_label_style: dict[str, str] = {}
        self._descriptions: dict[str, str] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        """构建 UI"""
        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        fields = self._other_info._fields

        if not fields:
            _tr = QCoreApplication.translate
            label = QLabel(_tr("Form", "此插件无自定义配置"))
            label.setStyleSheet("color: gray; font-style: italic;")
            layout.addRow(label)
            return

        for name, config_field in fields.items():
            if not config_field.visible:
                continue

            widget = config_field.create_widget()
            current = getattr(self._other_info, name)
            widget.set_value(current)

            label = QLabel(config_field.label)
            layout.addRow(label, widget)

            self._widgets[name] = widget
            self._labels[name] = label
            self._default_label_style[name] = label.styleSheet() or ""

            if config_field.description:
                widget.setToolTip(config_field.description)
                self._descriptions[name] = config_field.description

            widget.value_change.connect(lambda *_, n=name: self._on_changed(n))

    def _on_changed(self, name: str) -> None:
        widget = self._widgets[name]
        value = widget.get_value()
        self.config_changed.emit(name, value)

    def collect_pending(self) -> dict[str, Any]:
        """读取控件当前值，尚未写入 other_info。"""
        return {name: widget.get_value() for name, widget in self._widgets.items()}

    def validate_pending(self, plugin: BasePlugin | None) -> dict[str, str]:
        """
        校验即将保存的配置：字段 validator → plugin.validate_config。

        Returns:
            {字段名: 错误文案}，空 dict 表示通过
        """
        errors: dict[str, str] = {}
        pending = self.collect_pending()

        for name, value in pending.items():
            field = self._other_info._fields.get(name)
            if field is None:
                continue
            error = field.validate(value)
            if error:
                errors[name] = error

        if plugin is not None:
            run_fn = getattr(plugin, "run_validate_config", None)
            if callable(run_fn):
                try:
                    plugin_errors = run_fn(pending)
                except Exception as e:
                    errors["_plugin"] = str(e)
                else:
                    if isinstance(plugin_errors, dict):
                        for key, message in plugin_errors.items():
                            if message:
                                errors[str(key)] = str(message)
            else:
                validate_fn = getattr(plugin, "validate_config", None)
                if callable(validate_fn):
                    try:
                        plugin_errors = validate_fn(pending)
                    except Exception as e:
                        errors["_plugin"] = str(e)
                    else:
                        if isinstance(plugin_errors, dict):
                            for key, message in plugin_errors.items():
                                if message:
                                    errors[str(key)] = str(message)

        return errors

    def field_label(self, name: str) -> str:
        if name == "_plugin":
            return QCoreApplication.translate("Form", "插件")
        field = self._other_info._fields.get(name)
        if field is not None and field.label:
            return field.label
        return name

    def set_field_description(self, field_name: str, text: str) -> None:
        widget = self._widgets.get(field_name)
        if widget is not None:
            widget.setToolTip(text)
        self._descriptions[field_name] = text

    def highlight_errors(self, errors: dict[str, str]) -> None:
        for name, label in self._labels.items():
            if name in errors:
                label.setStyleSheet(_ERROR_LABEL_STYLE)
            else:
                label.setStyleSheet(self._default_label_style.get(name, ""))

    def clear_highlights(self) -> None:
        for name, label in self._labels.items():
            label.setStyleSheet(self._default_label_style.get(name, ""))

    def apply_to_config(self) -> None:
        """
        将 UI 值写入 other_info。

        设置页在确定时已跑过 validator，此处用 apply_pending 避免重复联网校验。
        """
        self._other_info.apply_pending(self.collect_pending(), silent=True)

    def refresh_from_config(self) -> None:
        for name, widget in self._widgets.items():
            value = getattr(self._other_info, name)
            widget.set_value(value)

    @property
    def other_info(self) -> OtherInfoBase:
        return self._other_info


class OtherInfoScrollArea(QScrollArea):
    """
    带滚动条的配置 UI 容器

    用于配置项较多时提供滚动支持。
    """

    config_changed = pyqtSignal(str, object)

    def __init__(self, other_info: OtherInfoBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        self._inner_widget = OtherInfoWidget(other_info, self)
        self.setWidget(self._inner_widget)
        self._inner_widget.config_changed.connect(self.config_changed.emit)

    def validate_pending(self, plugin: BasePlugin | None) -> dict[str, str]:
        return self._inner_widget.validate_pending(plugin)

    def field_label(self, name: str) -> str:
        return self._inner_widget.field_label(name)

    def set_field_description(self, field_name: str, text: str) -> None:
        self._inner_widget.set_field_description(field_name, text)

    def highlight_errors(self, errors: dict[str, str]) -> None:
        self._inner_widget.highlight_errors(errors)

    def clear_highlights(self) -> None:
        self._inner_widget.clear_highlights()

    def apply_to_config(self) -> None:
        self._inner_widget.apply_to_config()

    def refresh_from_config(self) -> None:
        self._inner_widget.refresh_from_config()

    @property
    def other_info(self) -> OtherInfoBase:
        return self._inner_widget.other_info
