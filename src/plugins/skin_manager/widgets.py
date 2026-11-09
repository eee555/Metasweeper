"""皮肤与音效管理插件的界面：状态提示 + 重新应用 + 音效试听。

皮肤/音效的选择框均由 config.py 的 ChoiceConfig 在「插件设置」里自动生成，
这里只显示当前状态与操作提示，不重复做选择器。音效试听区与皮肤区相互独立。
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from shared_types.sounds import SoundEvent

_translate = QCoreApplication.translate

# 事件名 -> 中文显示名（源文本，供 lupdate 抽取；运行时走 translate）
_EVENT_LABELS = {
    "ready": "就绪", "start": "开局", "open": "开格",
    "chord": "双击", "flag_on": "插旗", "flag_off": "拔旗",
    "win": "胜利", "lose": "失败",
}


def _i18n_event_labels() -> None:
    """lupdate 扫描用哑函数：把事件显示名逐条硬编码进 translate()。"""
    _translate("SkinManager", "就绪")
    _translate("SkinManager", "开局")
    _translate("SkinManager", "开格")
    _translate("SkinManager", "双击")
    _translate("SkinManager", "插旗")
    _translate("SkinManager", "拔旗")
    _translate("SkinManager", "胜利")
    _translate("SkinManager", "失败")


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

        title = QLabel(_translate("SkinManager", "皮肤管理"))
        title.setStyleSheet("font-size: 15pt; font-weight: bold;")
        layout.addWidget(title)

        tip = QLabel(_translate(
            "SkinManager",
            "在插件列表里右键本插件 →「设置...」，从「当前皮肤」下拉框选择，"
            "选择后立即生效，无需重启。\n选「默认皮肤」即可还原。"))
        tip.setWordWrap(True)
        layout.addWidget(tip)

        bar = QHBoxLayout()
        self._status = QLabel(_translate("SkinManager", "尚未应用皮肤"))
        self._status.setWordWrap(True)
        bar.addWidget(self._status, 1)
        reapply = QPushButton(_translate("SkinManager", "重新应用"))
        reapply.setToolTip(_translate(
            "SkinManager", "强制把当前选中的皮肤重新发送到主进程"))
        reapply.clicked.connect(self.apply_requested.emit)
        bar.addWidget(reapply)
        layout.addLayout(bar)

        hint = QLabel(_translate(
            "SkinManager",
            "在插件「设置...」里用「导入皮肤包」按钮安装 zip，或把资源放到"
            "插件目录 skins/<名称>/ 下，导入后即自动出现在下拉框里。"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        # ── 音效区（与皮肤独立）──
        layout.addSpacing(8)
        sound_title = QLabel(_translate("SkinManager", "音效"))
        sound_title.setStyleSheet("font-size: 13pt; font-weight: bold;")
        layout.addWidget(sound_title)
        sound_tip = QLabel(_translate(
            "SkinManager",
            "在插件「设置...」里分别设置「启用游戏音效」「音效音量」「当前音效包」，"
            "与皮肤设置相互独立，互不影响。授权也是独立的 SetSoundCommand。"))
        sound_tip.setWordWrap(True)
        layout.addWidget(sound_tip)

        preview_bar = QHBoxLayout()
        preview_bar.addWidget(QLabel(_translate("SkinManager", "试听：")))
        self._preview_combo = QComboBox()
        # 遍历枚举派生清单：新增/删除事件不再需要手工维护第二份下拉项，
        # 也不会漏掉 flag_off 等事件。
        for event in SoundEvent:
            label = _EVENT_LABELS.get(event.value, event.value)
            self._preview_combo.addItem(
                _translate("SkinManager", label), event.value)
        preview_bar.addWidget(self._preview_combo, 1)
        preview = QPushButton(_translate("SkinManager", "播放"))
        preview.setToolTip(_translate(
            "SkinManager", "按当前音效设置发送试听请求（需已授权 SetSoundCommand）"))
        preview.clicked.connect(self._on_preview_clicked)
        preview_bar.addWidget(preview)
        layout.addLayout(preview_bar)

        layout.addStretch(1)

    def _on_preview_clicked(self) -> None:
        self.sound_preview_requested.emit(self._preview_combo.currentData())

    def set_status(self, text: str) -> None:
        self._status.setText(text)
