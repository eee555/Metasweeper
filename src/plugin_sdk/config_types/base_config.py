"""
配置字段基类

所有配置类型继承此类，通过类名决定 UI 控件类型。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Generic, Type, TypeVar, overload

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtBoundSignal, pyqtSignal, QObject

T = TypeVar("T")


class ConfigWidgetBase(QWidget):
    """
    配置控件基类

    自定义配置类型的控件必须继承此类，并实现以下内容：
    - get_value(): 获取当前值
    - set_value(value): 设置当前值
    - value_change 信号: 值变化时发射（已提供默认实现）
    """

    value_change = pyqtSignal(object)

    def get_value(self) -> Any:
        """获取当前值"""
        raise NotImplementedError("子类必须实现 get_value 方法")

    def set_value(self, value: Any) -> None:
        """设置当前值"""
        raise NotImplementedError("子类必须实现 set_value 方法")


class ConfigWidgetWrapper(ConfigWidgetBase):
    """
    配置控件包装器

    将现有 Qt 控件包装为 ConfigWidgetBase，用于简化内置配置类型的实现。
    """

    def __init__(
        self,
        widget: QWidget,
        getter: Callable[[], Any],
        setter: Callable[[Any], None],
        signal: pyqtBoundSignal,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._widget = widget
        self._getter = getter
        self._setter = setter

        # 将控件添加到布局
        from PyQt5.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)

        # 连接原始信号到 value_change
        signal.connect(self._on_value_changed)

    def _on_value_changed(self) -> None:
        """内部信号变化时转发到 value_change"""
        self.value_change.emit(self._getter())

    def get_value(self) -> Any:
        return self._getter()

    def set_value(self, value: Any) -> None:
        self._setter(value)


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
        visible: 是否在 UI 中展示（默认 True，设为 False 可隐藏）

    类属性:
        widget_type: UI 控件类型标识，由工厂使用
    """

    default: T
    label: str = ""
    description: str = ""
    validator: Callable[[T], bool] | None = None
    visible: bool = True  # 是否在 UI 中展示

    # 类变量：用于 UI 工厂识别
    widget_type: ClassVar[str] = "base"

    def __post_init__(self) -> None:
        """初始化后处理"""
        # 确保 label 不为空
        if not self.label:
            self.label = ""

    @abstractmethod
    def create_widget(self) -> ConfigWidgetBase:
        """
        创建 PyQt 控件

        Returns:
            ConfigWidgetBase 实例，必须实现:
            - get_value(): 获取当前值
            - set_value(value): 设置当前值
            - value_change 信号: 值变化时发射
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

    @overload
    def __get__(self, instance: None, owner: Type[Any]) -> "BaseConfig[T]": ...

    @overload
    def __get__(self, instance: Any, owner: Type[Any]) -> T: ...

    def __get__(self, instance: Any, owner: Type[Any]) -> Any:
        # 运行时逻辑不需要变，因为 OtherInfoBase.__getattribute__ 会拦截它
        # 这里的代码只是为了骗过 IDE 的类型检查
        if instance is None:
            return self
        return self.default

    def __set__(self, instance: Any, value: T) -> None:
        """
        告诉 IDE：这个属性可以被赋予 _T 类型的值。
        运行时逻辑依然会被 OtherInfoBase.__setattr__ 拦截，
        所以这里不需要写实际的逻辑。
        """
        pass
