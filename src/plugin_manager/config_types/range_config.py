"""
数值范围配置类型 → 两个 QSpinBox
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSpinBox, QLabel

from .base_config import BaseConfig


class RangeChangeSignal(QObject):
    """范围变化信号发射器"""
    changed = pyqtSignal()


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

    def create_widget(
        self,
    ) -> tuple[QWidget, Callable[[], tuple[int, int]], Callable[[tuple[int, int]], None], QObject]:
        """创建范围选择器，返回 (控件, getter, setter, 信号)"""

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 创建信号发射器，并保存为容器的属性（防止垃圾回收）
        signal_emitter = RangeChangeSignal(parent=container)
        changed_signal = signal_emitter.changed

        # 最小值
        min_spin = QSpinBox()
        min_spin.setRange(self.min_value, self.max_value)
        min_spin.setValue(self.default[0])
        min_spin.setSingleStep(self.step)

        # 分隔符
        sep = QLabel("-")

        # 最大值
        max_spin = QSpinBox()
        max_spin.setRange(self.min_value, self.max_value)
        max_spin.setValue(self.default[1])
        max_spin.setSingleStep(self.step)

        if self.description:
            min_spin.setToolTip(self.description)
            max_spin.setToolTip(self.description)

        layout.addWidget(min_spin)
        layout.addWidget(sep)
        layout.addWidget(max_spin)

        # 连接两个 spinbox 的值变化信号到统一的 changed 信号
        min_spin.valueChanged.connect(lambda: changed_signal.emit())
        max_spin.valueChanged.connect(lambda: changed_signal.emit())

        def get_value() -> tuple[int, int]:
            return (min_spin.value(), max_spin.value())

        def set_value(value: tuple[int, int]) -> None:
            if isinstance(value, tuple) and len(value) == 2:
                min_spin.setValue(int(value[0]))
                max_spin.setValue(int(value[1]))

        return container, get_value, set_value, changed_signal

    def to_storage(self, value: tuple[int, int]) -> list[int]:
        """转换为存储格式（JSON 不支持元组）"""
        return [int(value[0]), int(value[1])]

    def from_storage(self, data: Any) -> tuple[int, int]:
        """从存储格式恢复"""
        if isinstance(data, (list, tuple)) and len(data) == 2:
            return (int(data[0]), int(data[1]))
        return self.default
