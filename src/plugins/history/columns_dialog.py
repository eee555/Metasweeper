"""
列显示设置对话框
"""

from __future__ import annotations

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QCheckBox,
    QDialog,
)

_translate = QCoreApplication.translate


class ColumnsDialog(QDialog):
    """列显示设置对话框"""

    def __init__(self, headers: list[str], show_fields: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(_translate("Form", "列设置"))
        self.resize(300, 500)
        self._headers = headers

        layout = QVBoxLayout(self)

        # 全选/取消全选
        select_layout = QHBoxLayout()
        self.select_all_btn = QPushButton(_translate("Form", "全选"))
        self.deselect_all_btn = QPushButton(_translate("Form", "取消全选"))
        select_layout.addWidget(self.select_all_btn)
        select_layout.addWidget(self.deselect_all_btn)
        layout.addLayout(select_layout)

        # 勾选列表
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(4, 4, 4, 4)

        self.checks: dict[str, QCheckBox] = {}
        for field in headers:
            cb = QCheckBox(field)
            cb.setChecked(field in show_fields)
            scroll_layout.addWidget(cb)
            self.checks[field] = cb

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # 确定按钮
        self.ok_button = QPushButton(_translate("Form", "确定"))
        layout.addWidget(self.ok_button)

        self.select_all_btn.clicked.connect(self._select_all)
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        self.ok_button.clicked.connect(self.accept)

    def _select_all(self):
        for cb in self.checks.values():
            cb.setChecked(True)

    def _deselect_all(self):
        for cb in self.checks.values():
            cb.setChecked(False)

    def get_show_fields(self) -> list[str]:
        """获取当前勾选的字段集合"""
        return [field for field, cb in self.checks.items() if cb.isChecked()]
