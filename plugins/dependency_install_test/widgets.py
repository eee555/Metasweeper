"""
dependency_install_test - UI 组件
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class DependencyInstallTestWidget(QWidget):
    """展示测试依赖的实际导入结果。"""

    def __init__(self, version: str, module_path: str, example: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("额外依赖已成功导入")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        for text in (
            f"依赖：humanize {version}",
            f"导入路径：{module_path}",
            f"调用结果：humanize.intcomma(1234567) = {example}",
        ):
            label = QLabel(text)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label)
        layout.addStretch()