"""
颜色配置类型 → 颜色选择按钮
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QPushButton, QColorDialog, QHBoxLayout, QWidget

from .base_config import BaseConfig


class ColorChangeSignal(QObject):
    """颜色变化信号发射器"""
    changed = pyqtSignal()


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

    def create_widget(self) -> tuple[QWidget, Callable[[], str], Callable[[str], None], QObject]:
        """创建颜色选择按钮，返回 (控件, getter, setter, 信号)"""

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 创建信号发射器，并保存为容器的属性（防止垃圾回收）
        signal_emitter = ColorChangeSignal(parent=container)
        changed_signal = signal_emitter.changed

        # 颜色预览按钮
        btn = QPushButton()
        btn.setFixedSize(40, 24)
        btn.setStyleSheet(f"background-color: {self.default}; border: 1px solid #999;")
        if self.description:
            btn.setToolTip(self.description)

        # 文本显示
        text_btn = QPushButton(self.default)
        text_btn.setFixedHeight(24)
        text_btn.setStyleSheet("text-align: left; padding-left: 4px;")

        layout.addWidget(btn)
        layout.addWidget(text_btn, 1)

        current_color = [self.default]  # 使用列表保存可变状态

        def on_click():
            color = QColorDialog.getColor(QColor(current_color[0]))
            if color.isValid():
                color_str = color.name()  # #RRGGBB
                current_color[0] = color_str
                btn.setStyleSheet(f"background-color: {color_str}; border: 1px solid #999;")
                text_btn.setText(color_str)
                changed_signal.emit()

        btn.clicked.connect(on_click)
        text_btn.clicked.connect(on_click)

        def get_value() -> str:
            return current_color[0]

        def set_value(value: str) -> None:
            if value and value.startswith("#"):
                current_color[0] = value
                btn.setStyleSheet(f"background-color: {value}; border: 1px solid #999;")
                text_btn.setText(value)

        return container, get_value, set_value, changed_signal

    def to_storage(self, value: str) -> str:
        """转换为存储格式"""
        return str(value)

    def from_storage(self, data: Any) -> str:
        """从存储格式恢复"""
        if isinstance(data, str) and data.startswith("#"):
            return data
        return self.default
