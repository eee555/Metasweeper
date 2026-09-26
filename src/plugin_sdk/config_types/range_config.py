"""
数值范围配置类型 → 两个 QSpinBox
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QSpinBox, QLabel

from .base_config import BaseConfig, ConfigWidgetBase


@dataclass
class RangeConfig(BaseConfig[tuple[int, int]]):
    """
    数值范围配置 → 两个 QSpinBox

    Args:
        default: 默认范围值 (min, max)
        label: 显示标签
        description: tooltip 提示
        min_value: 最小允许值
        max_value: 最大允许值
        step: 步进值

    用法::

        time_range = RangeConfig((0, 300), "时间范围(秒)", min_value=0, max_value=999)
        bbbv_range = RangeConfig((0, 999), "3BV范围", min_value=0, max_value=9999)
    """

    min_value: int = 0
    max_value: int = 9999
    step: int = 1

    widget_type = "range"

    def __post_init__(self) -> None:
        """确保默认值是元组"""
        if not isinstance(self.default, tuple):
            self.default = (self.min_value, self.max_value)
        self.default = (int(self.default[0]), int(self.default[1]))

    def create_widget(self) -> ConfigWidgetBase:
        """创建范围选择器"""

        class RangeWidget(ConfigWidgetBase):
            def __init__(self, default: tuple[int, int], min_val: int, max_val: int, step: int, description: str, parent=None):
                super().__init__(parent)

                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(4)

                # 最小值
                self._min_spin = QSpinBox()
                self._min_spin.setRange(min_val, max_val)
                self._min_spin.setValue(default[0])
                self._min_spin.setSingleStep(step)

                # 分隔符
                sep = QLabel("-")

                # 最大值
                self._max_spin = QSpinBox()
                self._max_spin.setRange(min_val, max_val)
                self._max_spin.setValue(default[1])
                self._max_spin.setSingleStep(step)

                if description:
                    self._min_spin.setToolTip(description)
                    self._max_spin.setToolTip(description)

                layout.addWidget(self._min_spin)
                layout.addWidget(sep)
                layout.addWidget(self._max_spin)

                self._min_spin.valueChanged.connect(self._on_change)
                self._max_spin.valueChanged.connect(self._on_change)

            def _on_change(self):
                self.value_change.emit(self.get_value())

            def get_value(self) -> tuple[int, int]:
                return (self._min_spin.value(), self._max_spin.value())

            def set_value(self, value: tuple[int, int]) -> None:
                if isinstance(value, tuple) and len(value) == 2:
                    self._min_spin.setValue(int(value[0]))
                    self._max_spin.setValue(int(value[1]))

        return RangeWidget(self.default, self.min_value, self.max_value, self.step, self.description)

    def to_storage(self, value: tuple[int, int]) -> list[int]:
        """转换为存储格式（JSON 不支持元组）"""
        return [int(value[0]), int(value[1])]

    def from_storage(self, data: Any) -> tuple[int, int]:
        """从存储格式恢复"""
        if isinstance(data, (list, tuple)) and len(data) == 2:
            return (int(data[0]), int(data[1]))
        return self.default
