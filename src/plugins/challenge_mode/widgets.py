"""
无猜闯关界面组件
"""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QCheckBox, QMessageBox, QSpinBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QCoreApplication

_translate = QCoreApplication.translate


class ChallengeModeUI(QWidget):
    """无猜闯关主界面"""

    _signal_update = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_cb = None
        self._next_cb = None
        self._reset_cb = None
        self._select_cb = None
        self._level_num = 1
        self._setup_ui()
        self._signal_update.connect(self._do_update)

    def set_callbacks(self, start_cb=None, next_cb=None, reset_cb=None, select_cb=None):
        self._start_cb = start_cb
        self._next_cb = next_cb
        self._reset_cb = reset_cb
        self._select_cb = select_cb

    def is_auto_next(self) -> bool:
        return self._auto_next_cb.isChecked()

    def selected_level_index(self) -> int:
        return self._level_select.value() - 1

    def _on_level_changed(self, value: int):
        if self._select_cb:
            self._select_cb(value - 1)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── 关卡信息区 ──
        info_frame = QFrame()
        info_frame.setStyleSheet(
            "QFrame { border: 1px solid #E0E0E0; border-radius: 6px; padding: 8px; }"
        )
        info_layout = QVBoxLayout(info_frame)

        self._level_label = QLabel(_translate("Form", "第 1 关"))
        self._level_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #333333; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif;"
        )
        self._level_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self._level_label)

        self._info_label = QLabel()
        self._info_label.setStyleSheet(
            "font-size: 13px; color: #666666; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif;"
        )
        self._info_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self._info_label)

        select_layout = QHBoxLayout()
        select_layout.addStretch()
        self._select_label = QLabel(_translate("Form", "选择关卡:"))
        self._select_label.setStyleSheet(
            "font-size: 13px; color: #666666; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif;"
        )
        select_layout.addWidget(self._select_label)
        self._level_select = QSpinBox()
        self._level_select.setRange(1, 1)
        self._level_select.setFixedWidth(90)
        self._level_select.setAlignment(Qt.AlignCenter)
        self._level_select.setStyleSheet(
            "QSpinBox { padding: 3px; font-size: 13px; }"
        )
        self._level_select.valueChanged.connect(self._on_level_changed)
        select_layout.addWidget(self._level_select)
        select_layout.addStretch()
        info_layout.addLayout(select_layout)

        btn_layout = QHBoxLayout()
        self._start_btn = QPushButton(_translate("Form", "开始本关"))
        self._start_btn.setStyleSheet(
            "QPushButton { padding: 6px 18px; font-size: 13px; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; }"
            "QPushButton:hover { background-color: #E3F2FD; }"
        )
        self._start_btn.clicked.connect(self._on_start)
        btn_layout.addWidget(self._start_btn)

        self._next_btn = QPushButton(_translate("Form", "下一关"))
        self._next_btn.setEnabled(False)
        self._next_btn.setStyleSheet(
            "QPushButton { padding: 6px 18px; font-size: 13px; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif; }"
            "QPushButton:hover { background-color: #E8F5E9; }"
        )
        self._next_btn.clicked.connect(self._on_next)
        btn_layout.addWidget(self._next_btn)

        self._auto_next_cb = QCheckBox(_translate("Form", "自动下一关"))
        self._auto_next_cb.setStyleSheet(
            "font-size: 12px; color: #888888; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif;"
        )
        btn_layout.addWidget(self._auto_next_cb)

        info_layout.addLayout(btn_layout)
        layout.addWidget(info_frame, 3)

        # ── 通关祝贺区（默认隐藏） ──
        self._congrats_frame = QFrame()
        self._congrats_frame.setStyleSheet(
            "QFrame { border: 2px solid #4CAF50; border-radius: 8px; padding: 16px; background-color: #E8F5E9; }"
        )
        congrats_layout = QVBoxLayout(self._congrats_frame)
        self._congrats_label = QLabel(_translate("Form", "恭喜通关！"))
        self._congrats_label.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #2E7D32; font-family: 'Microsoft YaHei', '微软雅黑', 'Segoe UI', Arial, sans-serif;"
        )
        self._congrats_label.setAlignment(Qt.AlignCenter)
        congrats_layout.addWidget(self._congrats_label)
        self._congrats_frame.setVisible(False)
        layout.addWidget(self._congrats_frame, 2)

        # ── 底部：重置齿轮 ──
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self._reset_btn = QPushButton("\u2699")
        self._reset_btn.setFixedSize(28, 28)
        self._reset_btn.setToolTip(_translate("Form", "重置闯关进度"))
        self._reset_btn.setStyleSheet(
            "QPushButton { border: none; color: #AAAAAA; font-size: 18px; }"
            "QPushButton:hover { color: #666666; }"
        )
        self._reset_btn.clicked.connect(self._on_reset)
        bottom_layout.addWidget(self._reset_btn)
        layout.addLayout(bottom_layout)

    def retranslateUi(self):
        self._level_label.setText(
            _translate("Form", "第 %1 关").replace("%1", str(self._level_num))
        )
        self._start_btn.setText(_translate("Form", "开始本关"))
        self._next_btn.setText(_translate("Form", "下一关"))
        self._select_label.setText(_translate("Form", "选择关卡:"))
        self._auto_next_cb.setText(_translate("Form", "自动下一关"))
        self._reset_btn.setToolTip(_translate("Form", "重置闯关进度"))
        self._congrats_label.setText(_translate("Form", "恭喜通关！"))

    def _on_start(self):
        if self._start_cb:
            self._start_cb()

    def _on_next(self):
        if self._next_cb:
            self._next_cb()

    def _on_reset(self):
        ret = QMessageBox.question(
            self,
            _translate("Form", "重置闯关进度"),
            _translate("Form", "确认重置闯关进度？此操作不可撤销。"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret == QMessageBox.Yes and self._reset_cb:
            self._reset_cb()

    def _do_update(self, data: dict):
        idx = data["current_level"]
        total = data["total_levels"]
        row = data["row"]
        col = data["col"]
        mines = data["mines"]
        completed = data["completed"]
        all_done = data["all_done"]
        max_level = data["max_level"]

        self._level_num = idx + 1
        self._level_label.setText(
            _translate("Form", "第 %1 关").replace("%1", str(idx + 1))
        )
        self._info_label.setText(
            _translate("Form", "行: %1  列: %2  雷: %3")
            .replace("%1", str(row))
            .replace("%2", str(col))
            .replace("%3", str(mines))
        )

        self._level_select.blockSignals(True)
        self._level_select.setMaximum(max_level)
        self._level_select.setValue(idx + 1)
        self._level_select.blockSignals(False)

        self._next_btn.setEnabled(completed and not all_done)
        self._congrats_frame.setVisible(all_done)
