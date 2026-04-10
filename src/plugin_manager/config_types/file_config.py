"""
文件配置类型 → 文件选择器
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QFileDialog

from .base_config import BaseConfig


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

    def create_widget(self) -> tuple[QWidget, Callable[[], str], Callable[[str], None], QObject]:
        """创建文件选择器，返回 (控件, getter, setter, 信号)"""

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        line_edit = QLineEdit(str(self.default))
        if self.description:
            line_edit.setToolTip(self.description)

        btn = QPushButton("浏览")
        btn.setFixedWidth(50)

        def on_browse():
            if self.save_mode:
                path, _ = QFileDialog.getSaveFileName(
                    container, "选择文件", line_edit.text(), self.filter
                )
            else:
                path, _ = QFileDialog.getOpenFileName(
                    container, "选择文件", line_edit.text(), self.filter
                )
            if path:
                line_edit.setText(path)

        btn.clicked.connect(on_browse)

        layout.addWidget(line_edit, 1)
        layout.addWidget(btn)

        return container, line_edit.text, line_edit.setText, line_edit.textChanged

    def to_storage(self, value: str) -> str:
        """转换为存储格式"""
        return str(value)

    def from_storage(self, data: Any) -> str:
        """从存储格式恢复"""
        return str(data) if data else self.default
