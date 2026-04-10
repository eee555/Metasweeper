"""
插件配置 UI 组件

根据 OtherInfoBase 自动生成配置界面。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QFormLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .config_types.base_config import BaseConfig
from .config_types.other_info import OtherInfoBase

if TYPE_CHECKING:
    pass


class OtherInfoWidget(QWidget):
    """
    根据 OtherInfoBase 自动生成配置 UI

    自动绑定配置字段 → UI 控件 → 值同步

    Signals:
        config_changed: 配置值变化信号，参数为 (字段名, 新值)
    """

    config_changed = pyqtSignal(str, object)  # (field_name, new_value)

    def __init__(self, other_info: OtherInfoBase, parent: QWidget | None = None) -> None:
        """
        初始化配置 UI

        Args:
            other_info: 配置容器实例
            parent: 父控件
        """
        super().__init__(parent)
        self._other_info = other_info
        self._widgets: dict[str, QWidget] = {}
        self._getters: dict[str, Callable[[], Any]] = {}
        self._setters: dict[str, Callable[[Any], None]] = {}
        self._signals: dict[str, QObject] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        """构建 UI"""
        # 使用 FormLayout 布局
        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        fields = self._other_info._fields

        if not fields:
            # 无配置项时显示提示
            label = QLabel("此插件无自定义配置")
            label.setStyleSheet("color: gray; font-style: italic;")
            layout.addRow(label)
            return

        for name, config_field in fields.items():
            # 使用 config_field 自己的 create_widget 方法
            widget, getter, setter, signal = config_field.create_widget()

            # 设置当前值
            current = getattr(self._other_info, name)
            setter(current)

            # 创建标签
            label = QLabel(config_field.label)

            # 添加到布局
            layout.addRow(label, widget)

            # 保存引用
            self._widgets[name] = widget
            self._getters[name] = getter
            self._setters[name] = setter
            self._signals[name] = signal

            # 连接变化信号
            self._connect_change_signal(signal, name)

    def _connect_change_signal(self, signal: QObject, name: str) -> None:
        """
        连接控件变化信号

        Args:
            signal: 值变化信号对象（QObject 或 pyqtSignal）
            name: 字段名
        """
        def on_change(*args) -> None:
            self._on_changed(name)

        # 信号可能是 QObject（有 connect 方法）或信号的 bound signal
        try:
            signal.connect(on_change)
        except (TypeError, AttributeError):
            pass  # 如果信号连接失败，忽略

    def _on_changed(self, name: str) -> None:
        """
        控件值变化时只发射信号，不立即应用到配置

        Args:
            name: 字段名
        """
        value = self._getters[name]()
        # 只发射 UI 信号，不修改配置对象
        # 配置将在 apply_to_config() 时统一应用
        self.config_changed.emit(name, value)

    def apply_to_config(self) -> None:
        """将所有 UI 值同步到 OtherInfo 配置对象（此时才触发变化回调）"""
        for name, getter in self._getters.items():
            # 设置配置值，此时会触发 OtherInfoBase 的变化回调
            setattr(self._other_info, name, getter())

    def refresh_from_config(self) -> None:
        """从 OtherInfo 配置对象刷新 UI 值"""
        for name, setter in self._setters.items():
            value = getattr(self._other_info, name)
            setter(value)

    @property
    def other_info(self) -> OtherInfoBase:
        """获取配置对象"""
        return self._other_info


class OtherInfoScrollArea(QScrollArea):
    """
    带滚动条的配置 UI 容器

    用于配置项较多时提供滚动支持。
    """

    config_changed = pyqtSignal(str, object)

    def __init__(self, other_info: OtherInfoBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)

        # 创建内部 widget
        self._inner_widget = OtherInfoWidget(other_info, self)
        self.setWidget(self._inner_widget)

        # 转发信号
        self._inner_widget.config_changed.connect(self.config_changed.emit)

    def apply_to_config(self) -> None:
        """将所有 UI 值同步到 OtherInfo 配置对象"""
        self._inner_widget.apply_to_config()

    def refresh_from_config(self) -> None:
        """从 OtherInfo 配置对象刷新 UI 值"""
        self._inner_widget.refresh_from_config()

    @property
    def other_info(self) -> OtherInfoBase:
        """获取配置对象"""
        return self._inner_widget.other_info
