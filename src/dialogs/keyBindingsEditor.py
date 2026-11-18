"""快捷键自定义界面：为每个登记的动作提供一个按键录输入框。"""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from config.key_bindings import (
    SECTION, WHEEL_MODIFIER_KEY, WHEEL_MODIFIERS, available_bindings,
    default_values, find_conflicts, load_bindings, save_bindings,
)

def _translate(context: str, text: str) -> str:
    """lupdate 可识别的翻译入口；同时供动态文本在运行时取译文。"""
    return QtCore.QCoreApplication.translate(context, text)


class _ShortcutEdit(QtWidgets.QKeySequenceEdit):
    """只保留一个组合键，避免录入多段序列造成歧义。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(32)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

    def keySequence(self) -> QtGui.QKeySequence:
        sequence = super().keySequence()
        if sequence.count() > 1:
            return QtGui.QKeySequence(sequence[0])
        return sequence


class KeyBindingsEditor:
    """可嵌入现有设置对话框的快捷键编辑页。"""

    def __init__(self, game_setting):
        self.game_setting = game_setting
        self.widget = QtWidgets.QWidget()
        self._edits: dict[str, _ShortcutEdit] = {}
        self.key_binding_values: dict[str, str] = {}

        layout = QtWidgets.QVBoxLayout(self.widget)
        layout.setContentsMargins(6, 4, 6, 4)

        top = QtWidgets.QHBoxLayout()
        hint = QtWidgets.QLabel(_translate(
            "KeyBindings", "点击按键框后直接按下想要的组合键；清空输入框可禁用该快捷键。"))
        hint.setWordWrap(True)
        top.addWidget(hint, 1)
        reset_button = QtWidgets.QPushButton(_translate("KeyBindings", "恢复默认"))
        reset_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        reset_button.clicked.connect(self.reset_defaults)
        top.addWidget(reset_button)
        layout.addLayout(top)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        container = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(container)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(3)

        for binding in available_bindings():
            edit = _ShortcutEdit()
            edit.setToolTip(_translate("KeyBindings", binding.label))
            edit.keySequenceChanged.connect(self._on_sequence_changed)
            self._edits[binding.id] = edit
            form.addRow(QtWidgets.QLabel(_translate("KeyBindings", binding.label)), edit)

        self.wheel_combo = QtWidgets.QComboBox()
        for label, _modifier in WHEEL_MODIFIERS:
            self.wheel_combo.addItem(label)
        form.addRow(QtWidgets.QLabel(_translate("KeyBindings", "滚轮缩放棋盘的修饰键：")), self.wheel_combo)

        self.scroll.setWidget(container)
        layout.addWidget(self.scroll, 1)

        self.conflict_label = QtWidgets.QLabel()
        self.conflict_label.setWordWrap(True)
        self.conflict_label.setStyleSheet("color: #c62828;")
        layout.addWidget(self.conflict_label)

        self.load()

    def _on_sequence_changed(self):
        self._update_conflict()

    def _update_conflict(self):
        conflicts = find_conflicts(self.collect())
        if not conflicts:
            self.conflict_label.setText("")
            return
        details = "; ".join(
            f"{key}: " + ", ".join(_translate("KeyBindings", name) for name in names)
            for key, names in conflicts.items())
        self.conflict_label.setText(_translate("KeyBindings", "注意：以下快捷键被重复指定：") + details)

    def load(self):
        values = load_bindings(self.game_setting)
        for binding in available_bindings():
            edit = self._edits[binding.id]
            edit.blockSignals(True)
            edit.setKeySequence(QtGui.QKeySequence(values[binding.id]))
            edit.blockSignals(False)
        wheel_name = self.game_setting.value(
            f"{SECTION}/{WHEEL_MODIFIER_KEY}", WHEEL_MODIFIERS[0][0], str)
        index = self.wheel_combo.findText(wheel_name or WHEEL_MODIFIERS[0][0])
        self.wheel_combo.setCurrentIndex(max(0, index))
        self._update_conflict()

    def reset_defaults(self):
        values = default_values()
        for binding in available_bindings():
            edit = self._edits[binding.id]
            edit.blockSignals(True)
            edit.setKeySequence(QtGui.QKeySequence(values[binding.id]))
            edit.blockSignals(False)
        self.wheel_combo.setCurrentIndex(0)
        self._update_conflict()

    def collect(self) -> dict[str, str]:
        values = {}
        for binding in available_bindings():
            sequence = self._edits[binding.id].keySequence()
            values[binding.id] = "" if sequence.isEmpty() else sequence.toString()
        values[WHEEL_MODIFIER_KEY] = self.wheel_combo.currentText()
        return values

    def commit(self) -> bool:
        """校验并保存。返回 False 表示存在冲突、没有写入。"""
        values = self.collect()
        conflicts = find_conflicts(values)
        if conflicts:
            details = "\n".join(
                f"{key}: " + ", ".join(_translate("KeyBindings", name) for name in names)
                for key, names in conflicts.items())
            QtWidgets.QMessageBox.warning(
                self.widget, _translate("KeyBindings", "快捷键冲突"),
                _translate("KeyBindings", "以下快捷键被重复指定，请修改后再保存：\n") + details)
            return False
        save_bindings(self.game_setting, values)
        self.key_binding_values = values
        return True
