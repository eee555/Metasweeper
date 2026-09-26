"""
文件配置类型 → 文件选择器
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QFileDialog

from .base_config import BaseConfig, ConfigWidgetBase


@dataclass
class FileConfig(BaseConfig[str]):
    """
    文件配置 → QLineEdit + QPushButton (浏览)

    Args:
        default: 默认文件路径
        label: 显示标签
        description: tooltip 提示
        filter: 文件过滤器（如 "JSON Files (*.json)"）
        save_mode: True 表示保存文件对话框，False 表示打开文件对话框

    用法::

        db_file = FileConfig("", "数据库文件", filter="SQLite (*.db)")
        export_file = FileConfig("", "导出文件", filter="JSON (*.json)", save_mode=True)
    """

    filter: str = ""
    save_mode: bool = False

    widget_type = "file"

    def __post_init__(self) -> None:
        """确保默认值是字符串"""
        self.default = str(self.default) if self.default else ""

    def create_widget(self) -> ConfigWidgetBase:
        """创建文件选择器"""

        class FileWidget(ConfigWidgetBase):
            def __init__(self, default: str, description: str, filter: str, save_mode: bool, parent=None):
                super().__init__(parent)
                self._filter = filter
                self._save_mode = save_mode

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
                if self._save_mode:
                    path, _ = QFileDialog.getSaveFileName(
                        self, QCoreApplication.translate(
                            "Form", "选择文件"), self._line_edit.text(), self._filter
                    )
                else:
                    path, _ = QFileDialog.getOpenFileName(
                        self, QCoreApplication.translate(
                            "Form", "选择文件"), self._line_edit.text(), self._filter
                    )
                if path:
                    self._line_edit.setText(path)

            def get_value(self) -> str:
                return self._line_edit.text()

            def set_value(self, value: str) -> None:
                self._line_edit.setText(value)

        return FileWidget(self.default, self.description, self.filter, self.save_mode)

    def to_storage(self, value: str) -> str:
        """转换为存储格式"""
        return str(value)

    def from_storage(self, data: Any) -> str:
        """从存储格式恢复"""
        return str(data) if data else self.default
