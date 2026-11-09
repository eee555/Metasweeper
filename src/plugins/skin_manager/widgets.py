"""皮肤与音效管理插件的界面：状态提示 + 重新应用 + 音效试听。

皮肤/音效的选择框均由 config.py 的 ChoiceConfig 在「插件设置」里自动生成，
这里只显示当前状态与操作提示，不重复做选择器。音效试听区与皮肤区相互独立。
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)


class SkinManagerWidget(QWidget):
    """状态面板：皮肤与音效两个独立分区。"""

    apply_requested = Signal()
    # 试听请求（携带事件名字符串），由插件发 SetSoundCommand(play_event=...)
    sound_preview_requested = Signal(str)

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

        # ── 音效区（与皮肤独立）──
        layout.addSpacing(8)
        sound_title = QLabel("音效")
        sound_title.setStyleSheet("font-size: 13pt; font-weight: bold;")
        layout.addWidget(sound_title)
        sound_tip = QLabel(
            "在插件「设置...」里分别设置「启用游戏音效」「音效音量」「当前音效包」，"
            "与皮肤设置相互独立，互不影响。授权也是独立的 SetSoundCommand。"
        )
        sound_tip.setWordWrap(True)
        layout.addWidget(sound_tip)

        preview_bar = QHBoxLayout()
        preview_bar.addWidget(QLabel("试听："))
        self._preview_combo = QComboBox()
        self._preview_combo.addItem("开格", "open")
        self._preview_combo.addItem("双击", "chord")
        self._preview_combo.addItem("插旗", "flag_on")
        self._preview_combo.addItem("开局", "start")
        self._preview_combo.addItem("就绪", "ready")
        self._preview_combo.addItem("胜利", "win")
        self._preview_combo.addItem("失败", "lose")
        preview_bar.addWidget(self._preview_combo, 1)
        preview = QPushButton("播放")
        preview.setToolTip("按当前音效设置发送试听请求（需已授权 SetSoundCommand）")
        preview.clicked.connect(self._on_preview_clicked)
        preview_bar.addWidget(preview)
        layout.addLayout(preview_bar)

        layout.addStretch(1)

    def _on_preview_clicked(self) -> None:
        self.sound_preview_requested.emit(self._preview_combo.currentData())

    def set_status(self, text: str) -> None:
        self._status.setText(text)
