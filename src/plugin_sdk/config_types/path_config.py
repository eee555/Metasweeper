"""
目录配置类型 → 目录选择器
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QFileDialog

from .base_config import BaseConfig, ConfigWidgetBase


@dataclass
class PathConfig(BaseConfig[str]):
    """
    目录配置 → QLineEdit + QPushButton (浏览)

    Args:
        default: 默认目录路径
        label: 显示标签
        description: tooltip 提示

    用法::

        log_dir = PathConfig("", "日志目录")
        cache_dir = PathConfig("", "缓存目录")
    """

    widget_type = "path"

    def __post_init__(self) -> None:
        """确保默认值是字符串"""
        self.default = str(self.default) if self.default else ""

    def create_widget(self) -> ConfigWidgetBase:
        """创建目录选择器"""

        class PathWidget(ConfigWidgetBase):
            def __init__(self, default: str, description: str, parent=None):
                super().__init__(parent)

                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(4)

                self._line_edit = QLineEdit(default)
                if description:
                    self._line_edit.setToolTip(description)

                btn = QPushButton(QCoreApplication.translate("Form", "浏览"))
                btn.setFixedWidth(50)
                btn.clicked.connect(self._on_browse)

                layout.addWidget(self._line_edit, 1)
                layout.addWidget(btn)

                self._line_edit.textChanged.connect(
                    lambda: self.value_change.emit(self.get_value()))

            def _on_browse(self):
                path = QFileDialog.getExistingDirectory(
                    self, QCoreApplication.translate(
                        "Form", "选择目录"), self._line_edit.text()
                )
                if path:
                    self._line_edit.setText(path)

            def get_value(self) -> str:
                return self._line_edit.text()

            def set_value(self, value: str) -> None:
                self._line_edit.setText(value)

        return PathWidget(self.default, self.description)

    def to_storage(self, value: str) -> str:
        """转换为存储格式"""
        return str(value)

    def from_storage(self, data: Any) -> str:
        """从存储格式恢复"""
        return str(data) if data else self.default
