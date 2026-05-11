"""
列显示设置对话框（支持上下移动排序）
"""

from __future__ import annotations

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QMenu,
    QWidget,
)

from shared_types.widgets import ConfirmDialog

_translate = QCoreApplication.translate


class ColumnListWidget(QListWidget):
    """自定义列表控件，处理移动快捷键"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._move_up_callback = None
        self._move_down_callback = None

    def set_move_callbacks(self, move_up, move_down):
        """设置移动回调函数"""
        self._move_up_callback = move_up
        self._move_down_callback = move_down

    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件：Ctrl+Shift+↑↓ 移动选中项"""
        if (event.modifiers() & Qt.ControlModifier) and (event.modifiers() & Qt.ShiftModifier):  # type: ignore
            if event.key() == Qt.Key_Up and self._move_up_callback:
                self._move_up_callback()
                return
            elif event.key() == Qt.Key_Down and self._move_down_callback:
                self._move_down_callback()
                return
        super().keyPressEvent(event)


class ColumnsDialog(ConfirmDialog):
    """列显示设置对话框"""

    def __init__(self, headers: list[str], show_fields: list[str], parent=None):
        self._headers = headers
        self._show_fields = show_fields
        super().__init__(
            parent,
            title=_translate("Form", "列设置（右键/Ctrl+Shift+↑↓ 排序）"),
        )
        self.resize(300, 500)

    def _create_content(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 全选/取消全选
        select_layout = QHBoxLayout()
        self.select_all_btn = QPushButton(_translate("Form", "全选"))
        self.deselect_all_btn = QPushButton(_translate("Form", "取消全选"))
        select_layout.addWidget(self.select_all_btn)
        select_layout.addWidget(self.deselect_all_btn)
        layout.addLayout(select_layout)

        # 列表（支持多选）
        self.list_widget = ColumnListWidget()
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(
            self._show_context_menu)
        self.list_widget.set_move_callbacks(self._move_up, self._move_down)

        # 初始化列表
        self._init_list()

        layout.addWidget(self.list_widget)

        self.select_all_btn.clicked.connect(self._select_all)
        self.deselect_all_btn.clicked.connect(self._deselect_all)

        return widget

    def _init_list(self):
        """初始化列表内容"""
        self.list_widget.clear()

        # 按 show_fields 顺序排列
        ordered_fields = [f for f in self._show_fields if f in self._headers]
        remaining_fields = [
            f for f in self._headers if f not in self._show_fields]

        for field in ordered_fields + remaining_fields:
            item = QListWidgetItem(field)
            item.setCheckState(
                Qt.Checked if field in self._show_fields else Qt.Unchecked)
            self.list_widget.addItem(item)

    def set_show_fields(self, show_fields: list[str]):
        """设置当前显示的字段列表（下次打开时使用）"""
        self._show_fields = show_fields

    def item(self, row: int) -> QListWidgetItem:
        return self.list_widget.item(row)  # type: ignore

    def _select_all(self):
        for i in range(self.list_widget.count()):
            self.item(i).setCheckState(Qt.Checked)

    def _deselect_all(self):
        for i in range(self.list_widget.count()):
            self.item(i).setCheckState(Qt.Unchecked)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        menu.addAction(_translate("Form", "上移 (Ctrl+Shift+↑)"), self._move_up)
        menu.addAction(_translate(
            "Form", "下移 (Ctrl+Shift+↓)"), self._move_down)
        menu.exec_(self.list_widget.mapToGlobal(pos))

    def _move_up(self):
        """上移选中的项目"""
        selected = self.list_widget.selectedItems()
        if not selected:
            return

        # 按行号升序排列
        for item in sorted(selected, key=lambda x: self.list_widget.row(x)):
            row = self.list_widget.row(item)
            if row > 0:
                # 检查上一行是否也在选中列表中
                prev_item = self.list_widget.item(row - 1)
                if prev_item not in selected:
                    self.list_widget.takeItem(row)
                    self.list_widget.insertItem(row - 1, item)
                    item.setSelected(True)

        # 滚动到选中的第一行
        self._scroll_to_first_selected()

    def _move_down(self):
        """下移选中的项目"""
        selected = self.list_widget.selectedItems()
        if not selected:
            return

        count = self.list_widget.count()
        # 按行号降序排列（从下往上处理）
        for item in sorted(selected, key=lambda x: self.list_widget.row(x), reverse=True):
            row = self.list_widget.row(item)
            if row < count - 1:
                # 检查下一行是否也在选中列表中
                next_item = self.list_widget.item(row + 1)
                if next_item not in selected:
                    self.list_widget.takeItem(row)
                    self.list_widget.insertItem(row + 1, item)
                    item.setSelected(True)

        # 滚动到选中的第一行
        self._scroll_to_first_selected()

    def _scroll_to_first_selected(self):
        """滚动到选中的第一行"""
        selected = self.list_widget.selectedItems()
        if selected:
            first_row = min(self.list_widget.row(item) for item in selected)
            self.list_widget.scrollToItem(self.list_widget.item(first_row))

    def get_show_fields(self) -> list[str]:
        """获取当前勾选的字段列表（按显示顺序）"""
        result = []
        for i in range(self.list_widget.count()):
            item = self.item(i)
            if item.checkState() == Qt.Checked:
                result.append(item.text())
        return result

    def set_field_checked(self, field: str, checked: bool):
        """设置指定字段的勾选状态"""
        for i in range(self.list_widget.count()):
            item = self.item(i)
            if item.text() == field:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                break
