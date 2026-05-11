"""
通用对话框基类

提供确认/取消按钮组合的对话框基类，使用 QDialogButtonBox
"""

from __future__ import annotations

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QDialogButtonBox,
    QWidget,
)

_translate = QCoreApplication.translate


class ConfirmDialog(QDialog):
    """
    带确认/取消按钮的对话框基类

    使用 Qt 内置的 QDialogButtonBox 提供标准按钮。

    Usage:
        class MyDialog(ConfirmDialog):
            def _create_content(self) -> QWidget:
                widget = QWidget()
                layout = QVBoxLayout(widget)
                # 添加自定义控件...
                return widget

            def _on_accepted(self):
                # 处理确认逻辑
                pass
    """

    def __init__(
        self,
        parent=None,
        title: str = "",
        buttons: QDialogButtonBox.StandardButtons = QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
    ):
        """
        Args:
            parent: 父控件
            title: 对话框标题
            buttons: 标准按钮组合（默认 Ok | Cancel）
        """
        super().__init__(parent)
        self.setWindowTitle(title or _translate("Dialog", "对话框"))
        self._buttons = buttons

        self._setup_ui()

    def _setup_ui(self):
        """设置 UI 布局"""
        layout = QVBoxLayout(self)

        # 内容区域（子类实现）
        content = self._create_content()
        if content:
            layout.addWidget(content)

        # 使用 QDialogButtonBox（Qt 内置标准按钮框）
        self.button_box = QDialogButtonBox(self._buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _create_content(self) -> QWidget | None:
        """
        创建内容区域（子类重写）

        Returns:
            内容控件，或 None
        """
        return None

    def _on_accepted(self):
        """确认时调用（子类重写）"""
        pass

    def _on_rejected(self):
        """取消时调用（子类重写）"""
        pass

    def accept(self):
        """确认"""
        self._on_accepted()
        super().accept()

    def reject(self):
        """取消"""
        self._on_rejected()
        super().reject()

    def button(self, standard_button: QDialogButtonBox.StandardButton) -> QWidget | None:
        """
        获取指定标准按钮

        Args:
            standard_button: 标准按钮类型

        Returns:
            按钮控件，或 None
        """
        return self.button_box.button(standard_button)
