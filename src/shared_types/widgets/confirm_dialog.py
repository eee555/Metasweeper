"""
通用对话框基类

提供确认/取消按钮组合的对话框基类，使用 QDialogButtonBox
"""

from __future__ import annotations
import typing

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtWidgets import (
    QDialog,
    QPushButton,
    QVBoxLayout,
    QDialogButtonBox,
    QLayout,
)


_translate = QCoreApplication.translate


class ConfirmDialog(QDialog):
    """
    带确认/取消按钮的对话框基类

    使用 Qt 内置的 QDialogButtonBox 提供标准按钮。

    Usage:
        class MyDialog(ConfirmDialog):
            def _create_content(self) -> QLayout:
                layout = QVBoxLayout()
                # 添加自定义控件...
                return layout

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
        self.setWindowFlags(self.windowFlags() & ~
                            Qt.WindowContextHelpButtonHint)
        self._buttons = buttons

        self._setup_ui()

    def _setup_ui(self):
        """设置 UI 布局"""
        layout = QVBoxLayout(self)

        # 内容区域（子类实现）
        content = self._create_content()
        if content:
            layout.addLayout(content)

        # 使用 QDialogButtonBox（Qt 内置标准按钮框）
        self._button_box = QDialogButtonBox(self._buttons)
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

    def _create_content(self) -> QLayout | None:
        """
        创建内容区域（子类重写）

        Returns:
            内容布局，或 None
        """
        return None

    def _on_accepted(self):
        """确认时调用（子类重写）"""
        pass

    def _on_rejected(self):
        """取消时调用（子类重写）"""
        pass

    @typing.override
    def accept(self):
        """确认"""
        self._on_accepted()
        super().accept()

    @typing.override
    def reject(self):
        """取消"""
        self._on_rejected()
        super().reject()

    @property
    def button_box(self) -> QDialogButtonBox:
        """获取按钮框"""
        return self._button_box

    def button(self, standard_button: QDialogButtonBox.StandardButton) -> QPushButton:
        """
        获取指定标准按钮

        Args:
            standard_button: 标准按钮类型

        Returns:
            按钮控件
        """
        return self.button_box.button(standard_button)

    def buttons(self) -> dict[QDialogButtonBox.StandardButton, QPushButton]:
        """获取所有按钮"""
        result: dict[QDialogButtonBox.StandardButton, QPushButton] = {}
        flags = self._buttons
        for btn in (
            QDialogButtonBox.Ok,
            QDialogButtonBox.Cancel,
            QDialogButtonBox.Save,
            QDialogButtonBox.Discard,
            QDialogButtonBox.Apply,
            QDialogButtonBox.Reset,
            QDialogButtonBox.RestoreDefaults,
            QDialogButtonBox.Help,
            QDialogButtonBox.SaveAll,
            QDialogButtonBox.Yes,
            QDialogButtonBox.YesToAll,
            QDialogButtonBox.No,
            QDialogButtonBox.NoToAll,
            QDialogButtonBox.Abort,
            QDialogButtonBox.Retry,
            QDialogButtonBox.Ignore,
            QDialogButtonBox.Close,
        ):
            if bool(flags & btn) and (b := self.button_box.button(btn)) is not None:
                result[btn] = b
        return result
