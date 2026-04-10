"""
选择配置类型 → QComboBox
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QComboBox

from .base_config import BaseConfig


@dataclass
class ChoiceConfig(BaseConfig[str]):
    """
    选择配置 → QComboBox

    Args:
        default: 默认值（选项的 value）
        label: 显示标签
        choices: 选项列表，格式为 [(value, display_text), ...]
        description: tooltip 提示

    用法::

        theme = ChoiceConfig(
            "dark", "主题",
            choices=[("light", "明亮"), ("dark", "暗黑"), ("auto", "跟随系统")]
        )
    """

    choices: list[tuple[str, str]] = field(default_factory=list)

    widget_type = "combobox"

    def __post_init__(self) -> None:
        """确保默认值是字符串类型"""
        self.default = str(self.default)

    def create_widget(self) -> tuple[QComboBox, Callable[[], str], Callable[[str], None], QObject]:
        """创建 QComboBox 控件，返回 (控件, getter, setter, 信号)"""

        widget = QComboBox()
        for value, text in self.choices:
            widget.addItem(text, value)

        # 设置默认值
        idx = widget.findData(self.default)
        if idx >= 0:
            widget.setCurrentIndex(idx)

        if self.description:
            widget.setToolTip(self.description)

        def get_value() -> str:
            data = widget.currentData()
            return str(data) if data is not None else self.default

        def set_value(value: str) -> None:
            idx = widget.findData(value)
            if idx >= 0:
                widget.setCurrentIndex(idx)

        return widget, get_value, set_value, widget.currentIndexChanged

    def to_storage(self, value: str) -> str:
        """转换为存储格式"""
        return str(value)

    def from_storage(self, data: Any) -> str:
        """从存储格式恢复"""
        return str(data)
