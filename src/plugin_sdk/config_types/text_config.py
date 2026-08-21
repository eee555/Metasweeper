"""
文本配置类型 → QLineEdit
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLineEdit, QPushButton, QWidget

from .base_config import BaseConfig, ConfigWidgetWrapper


@dataclass
class TextConfig(BaseConfig[str]):
    """
    文本配置 → QLineEdit

    Args:
        default: 默认值
        label: 显示标签
        placeholder: 占位符文本
        password: 是否为密码输入（显示为 ***）
        copy_button: 是否在输入框右侧显示「复制」按钮
        description: tooltip 提示

    用法::

        api_key = TextConfig("", "API密钥", password=True, placeholder="输入密钥...")
        name = TextConfig("", "名称", placeholder="请输入名称")
    """

    placeholder: str = ""
    password: bool = False
    copy_button: bool = False

    widget_type = "textedit"

    def __post_init__(self) -> None:
        """确保默认值是字符串类型"""
        self.default = str(self.default)

    def create_widget(self) -> ConfigWidgetWrapper:
        """创建 QLineEdit 控件（可选附带复制按钮）"""
        line_edit = QLineEdit()
        line_edit.setText(str(self.default))

        if self.placeholder:
            line_edit.setPlaceholderText(self.placeholder)

        if self.password:
            line_edit.setEchoMode(QLineEdit.Password)

        if self.readonly:
            line_edit.setReadOnly(True)

        host: QWidget = line_edit
        if self.copy_button:
            host = QWidget()
            row = QHBoxLayout(host)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(line_edit, 1)

            copy_btn = QPushButton(QCoreApplication.translate("Form", "复制"))

            def _update_copy_enabled(_: str = "") -> None:
                copy_btn.setEnabled(bool(line_edit.text().strip()))

            def _copy_to_clipboard() -> None:
                text = line_edit.text().strip()
                if text:
                    QApplication.clipboard().setText(text)

            line_edit.textChanged.connect(_update_copy_enabled)
            copy_btn.clicked.connect(_copy_to_clipboard)
            row.addWidget(copy_btn)
            _update_copy_enabled()

        if self.description:
            host.setToolTip(self.description)

        return ConfigWidgetWrapper(
            host, line_edit.text, line_edit.setText, line_edit.textChanged
        )

    def to_storage(self, value: str) -> str:
        """转换为存储格式"""
        return str(value)

    def from_storage(self, data: Any) -> str:
        """从存储格式恢复"""
        return str(data) if data is not None else self.default
