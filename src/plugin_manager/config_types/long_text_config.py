"""
多行文本配置类型 → QTextEdit
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QTextEdit

from .base_config import BaseConfig


@dataclass
class LongTextConfig(BaseConfig[str]):
    """
    多行文本配置 → QTextEdit

    Args:
        default: 默认文本内容
        label: 显示标签
        description: tooltip 提示
        placeholder: 占位符文本
        max_height: 最大高度（像素）

    用法::

        description = LongTextConfig("", "描述", placeholder="输入描述...")
        script = LongTextConfig("", "脚本内容", max_height=150)
    """

    placeholder: str = ""
    max_height: int = 100

    widget_type = "longtext"

    def __post_init__(self) -> None:
        """确保默认值是字符串"""
        self.default = str(self.default) if self.default else ""

    def create_widget(self) -> tuple[QTextEdit, Callable[[], str], Callable[[str], None], QObject]:
        """创建多行文本编辑器，返回 (控件, getter, setter, 信号)"""
        widget = QTextEdit()
        widget.setPlainText(str(self.default))
        widget.setMaximumHeight(self.max_height)

        if self.placeholder:
            widget.setPlaceholderText(self.placeholder)

        if self.description:
            widget.setToolTip(self.description)

        return widget, widget.toPlainText, widget.setPlainText, widget.textChanged

    def to_storage(self, value: str) -> str:
        """转换为存储格式"""
        return str(value)

    def from_storage(self, data: Any) -> str:
        """从存储格式恢复"""
        return str(data) if data is not None else self.default
