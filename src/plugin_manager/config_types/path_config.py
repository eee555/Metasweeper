"""
目录配置类型 → 目录选择器
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QFileDialog

from .base_config import BaseConfig


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

    def create_widget(self) -> tuple[QWidget, Callable[[], str], Callable[[str], None], QObject]:
        """创建目录选择器，返回 (控件, getter, setter, 信号)"""

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
            path = QFileDialog.getExistingDirectory(
                container, "选择目录", line_edit.text()
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
