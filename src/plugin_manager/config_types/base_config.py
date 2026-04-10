"""
配置字段基类

所有配置类型继承此类，通过类名决定 UI 控件类型。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Generic, TypeVar

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, QObject

T = TypeVar("T")


@dataclass
class BaseConfig(ABC, Generic[T]):
    """
    配置字段基类

    子类通过类名决定 UI 类型，变量名作为配置 key。

    Attributes:
        default: 默认值
        label: 显示标签
        description: tooltip 提示
        validator: 自定义验证函数

    类属性:
        widget_type: UI 控件类型标识，由工厂使用
    """

    default: T
    label: str = ""
    description: str = ""
    validator: Callable[[T], bool] | None = None

    # 类变量：用于 UI 工厂识别
    widget_type: ClassVar[str] = "base"

    def __post_init__(self) -> None:
        """初始化后处理"""
        # 确保 label 不为空
        if not self.label:
            self.label = ""

    @abstractmethod
    def create_widget(self) -> tuple[QWidget, Callable[[], T], Callable[[T], None], QObject]:
        """
        创建 PyQt 控件

        Returns:
            (控件, 获取值函数, 设置值函数, 值变化信号对象)
            
            信号对象应该是一个有 connect 方法的 QObject（如 pyqtSignal）。
            当值变化时，配置系统会自动连接这个信号来同步值。
        """
        pass

    @abstractmethod
    def to_storage(self, value: T) -> Any:
        """
        转换为存储格式（JSON 可序列化）

        Args:
            value: 配置值

        Returns:
            可 JSON 序列化的值
        """
        pass

    @abstractmethod
    def from_storage(self, data: Any) -> T:
        """
        从存储格式恢复

        Args:
            data: JSON 反序列化的数据

        Returns:
            配置值
        """
        pass

    def validate(self, value: T) -> bool:
        """
        验证值是否有效

        Args:
            value: 待验证的值

        Returns:
            True 表示有效
        """
        if self.validator is not None:
            return self.validator(value)
        return True
