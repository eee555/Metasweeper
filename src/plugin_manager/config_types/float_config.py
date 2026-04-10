"""
浮点数配置类型 → QDoubleSpinBox
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QDoubleSpinBox

from .base_config import BaseConfig


@dataclass
class FloatConfig(BaseConfig[float]):
    """
    浮点数配置 → QDoubleSpinBox

    Args:
        default: 默认值
        label: 显示标签
        min_value: 最小值
        max_value: 最大值
        step: 步进值
        decimals: 小数位数
        description: tooltip 提示

    用法::

        ratio = FloatConfig(0.8, "缩放比例", min_value=0.1, max_value=2.0, decimals=2)
    """

    min_value: float = 0.0
    max_value: float = 9999.0
    step: float = 0.1
    decimals: int = 2

    widget_type = "doublespinbox"

    def __post_init__(self) -> None:
        """确保默认值是浮点类型"""
        self.default = float(self.default)

    def create_widget(
        self,
    ) -> tuple[QDoubleSpinBox, Callable[[], float], Callable[[float], None], QObject]:
        """创建 QDoubleSpinBox 控件，返回 (控件, getter, setter, 信号)"""
        widget = QDoubleSpinBox()
        widget.setRange(self.min_value, self.max_value)
        widget.setValue(self.default)
        widget.setSingleStep(self.step)
        widget.setDecimals(self.decimals)
        if self.description:
            widget.setToolTip(self.description)
        return widget, widget.value, widget.setValue, widget.valueChanged

    def to_storage(self, value: float) -> float:
        """转换为存储格式"""
        return float(value)

    def from_storage(self, data: Any) -> float:
        """从存储格式恢复"""
        try:
            return float(data)
        except (ValueError, TypeError):
            return self.default
