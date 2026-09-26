"""
颜色配置类型 → 颜色选择按钮
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton, QColorDialog, QHBoxLayout

from .base_config import BaseConfig, ConfigWidgetBase


@dataclass
class ColorConfig(BaseConfig[str]):
    """
    颜色配置 → QPushButton + QColorDialog

    Args:
        default: 默认颜色（格式 "#RRGGBB" 或 "#AARRGGBB"）
        label: 显示标签
        description: tooltip 提示

    用法::

        theme_color = ColorConfig("#1976d2", "主题颜色")
        highlight_color = ColorConfig("#ff5722", "高亮颜色")
    """

    widget_type = "color"

    def __post_init__(self) -> None:
        """确保默认值是有效的颜色格式"""
        if not self.default.startswith("#"):
            self.default = "#" + self.default

    def create_widget(self) -> ConfigWidgetBase:
        """创建颜色选择按钮"""

        class ColorWidget(ConfigWidgetBase):
            def __init__(self, default: str, description: str, parent=None):
                super().__init__(parent)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(4)

                self._color = default

                # 颜色预览按钮
                self._btn = QPushButton()
                self._btn.setFixedSize(40, 24)
                self._btn.setStyleSheet(
                    f"background-color: {default}; border: 1px solid #999;")
                if description:
                    self._btn.setToolTip(description)

                # 文本显示
                self._text_btn = QPushButton(default)
                self._text_btn.setFixedHeight(24)
                self._text_btn.setStyleSheet(
                    "text-align: left; padding-left: 4px;")

                self._btn.clicked.connect(self._on_click)
                self._text_btn.clicked.connect(self._on_click)

                layout.addWidget(self._btn)
                layout.addWidget(self._text_btn, 1)

            def _on_click(self):
                color = QColorDialog.getColor(QColor(self._color))
                if color.isValid():
                    self.set_value(color.name())

            def get_value(self) -> str:
                return self._color

            def set_value(self, value: str) -> None:
                if value and value.startswith("#"):
                    self._color = value
                    self._btn.setStyleSheet(
                        f"background-color: {value}; border: 1px solid #999;")
                    self._text_btn.setText(value)
                    self.value_change.emit(value)

        return ColorWidget(self.default, self.description)

    def to_storage(self, value: str) -> str:
        """转换为存储格式"""
        return str(value)

    def from_storage(self, data: Any) -> str:
        """从存储格式恢复"""
        if isinstance(data, str) and data.startswith("#"):
            return data
        return self.default
