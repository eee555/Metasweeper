"""皮肤管理插件的界面：状态提示 + 重新应用按钮。

皮肤的下拉选择框由 config.py 的 ChoiceConfig 在「插件设置」里自动生成，
这里只显示当前状态与操作提示，不重复做选择器。
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)


class SkinManagerWidget(QWidget):
    """状态面板：提示去哪选皮肤，以及最近一次应用结果。"""

    apply_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("皮肤管理")
        title.setStyleSheet("font-size: 15pt; font-weight: bold;")
        layout.addWidget(title)

        tip = QLabel(
            "在插件列表里右键本插件 →「设置...」，从「当前皮肤」下拉框选择，"
            "选择后立即生效，无需重启。\n"
            "选「默认皮肤」即可还原。"
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)

        bar = QHBoxLayout()
        self._status = QLabel("尚未应用皮肤")
        self._status.setWordWrap(True)
        bar.addWidget(self._status, 1)
        reapply = QPushButton("重新应用")
        reapply.setToolTip("强制把当前选中的皮肤重新发送到主进程")
        reapply.clicked.connect(self.apply_requested.emit)
        bar.addWidget(reapply)
        layout.addLayout(bar)

        hint = QLabel(
            "皮肤资源放在插件目录 skins/<名称>/ 下，新增目录后重启插件"
            "即自动出现在下拉框里（也可用设置里的「额外皮肤库目录」）。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)
        layout.addStretch(1)

    def set_status(self, text: str) -> None:
        self._status.setText(text)
