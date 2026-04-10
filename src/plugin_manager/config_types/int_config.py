"""
整数配置类型 → QSpinBox 或 QSlider
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSpinBox, QSlider

from .base_config import BaseConfig


@dataclass
class IntConfig(BaseConfig[int]):
    """
    整数配置 → QSpinBox 或 QSlider

    Args:
        default: 默认值
        label: 显示标签
        min_value: 最小值
        max_value: 最大值
        step: 步进值
        use_slider: 是否使用滑块控件
        description: tooltip 提示

    用法::

        interval = IntConfig(30, "间隔(秒)", min_value=1, max_value=300, step=10)
        quality = IntConfig(80, "质量", min_value=1, max_value=100, use_slider=True)
    """

    min_value: int = 0
    max_value: int = 9999
    step: int = 1
    use_slider: bool = False

    widget_type = "spinbox"

    def __post_init__(self) -> None:
        """确保默认值是整数类型"""
        self.default = int(self.default)

    def create_widget(
        self,
    ) -> tuple[QSpinBox | QSlider, Callable[[], int], Callable[[int], None], QObject]:
        """创建 QSpinBox 或 QSlider 控件，返回 (控件, getter, setter, 信号)"""
        from PyQt5.QtCore import QObject
        
        if self.use_slider:
            widget = QSlider(Qt.Horizontal)
            widget.setRange(self.min_value, self.max_value)
            widget.setValue(self.default)
            widget.setSingleStep(self.step)
            if self.description:
                widget.setToolTip(self.description)
            return widget, widget.value, widget.setValue, widget.valueChanged
        else:
            widget = QSpinBox()
            widget.setRange(self.min_value, self.max_value)
            widget.setValue(self.default)
            widget.setSingleStep(self.step)
            if self.description:
                widget.setToolTip(self.description)
            return widget, widget.value, widget.setValue, widget.valueChanged

    def to_storage(self, value: int) -> int:
        """转换为存储格式"""
        return int(value)

    def from_storage(self, data: Any) -> int:
        """从存储格式恢复"""
        try:
            return int(data)
        except (ValueError, TypeError):
            return self.default
