"""
排序条件对话框
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QMenu,
    QTableView,
    QSizePolicy,
    QHeaderView,
    QDialog,
)

from .delegates import ComboBoxDelegate, EditableComboBoxDelegate
from .models import HistoryData
from .table_views import AutoEditTableView, SortModel

_translate = QCoreApplication.translate


class SortDialog(QDialog):
    """排序条件对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_translate("Form", "排序条件"))
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        self.sort_table = AutoEditTableView()
        self.sort_table.setModel(SortModel(self))
        self.sort_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.sort_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.sort_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sort_table.customContextMenuRequested.connect(
            self.show_sort_context_menu)
        self.sort_table.setSelectionBehavior(QTableView.SelectItems)
        self.sort_table.setSelectionMode(QTableView.ExtendedSelection)
        self.sort_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 设置所有列自动进入编辑
        self.sort_table.setAutoEditColumns(
            [SortModel.COL_FIELD, SortModel.COL_ORDER])
        # 禁用双击编辑
        self.sort_table.setEditTriggers(QTableView.NoEditTriggers)
        layout.addWidget(self.sort_table)

        self._setup_delegates()

    def _setup_delegates(self):
        """设置列代理"""
        self.sort_table.setItemDelegateForColumn(
            SortModel.COL_FIELD,
            EditableComboBoxDelegate(HistoryData.fields(), self)
        )
        self.sort_table.setItemDelegateForColumn(
            SortModel.COL_ORDER,
            ComboBoxDelegate(
                [_translate("Form", "升序"), _translate("Form", "降序")], self
            )
        )

    def show_sort_context_menu(self, pos):
        """排序列表右键菜单"""
        menu = QMenu(self)
        menu.addAction(_translate("Form", "添加"), self._add_sort_row)
        menu.addAction(_translate("Form", "插入"), self._insert_sort_row)
        menu.addAction(_translate("Form", "删除"), self._del_sort_row)
        menu.exec_(self.sort_table.mapToGlobal(pos))

    def _add_sort_row(self):
        """添加排序行"""
        model = self.sort_table.model()
        row = model.rowCount()
        model.insertRow(row)
        model.setData(model.index(row, SortModel.COL_FIELD),
                      HistoryData.fields()[0])
        model.setData(model.index(row, SortModel.COL_ORDER),
                      _translate("Form", "升序"))

    def _add_sort_row_at(self, row: int, field: str | None = None, order: str | None = None):
        """在指定位置添加排序行"""
        model = self.sort_table.model()
        if field is None:
            field = HistoryData.fields()[0]
        if order is None:
            order = _translate("Form", "升序")

        self.sort_table.insertRow(row)
        model.setData(model.index(row, SortModel.COL_FIELD), field)
        model.setData(model.index(row, SortModel.COL_ORDER), order)

    def _insert_sort_row(self):
        """在当前行前插入排序行"""
        current_row = self.sort_table.currentIndex().row()
        self._add_sort_row_at(current_row if current_row >= 0 else 0)

    def _del_sort_row(self):
        """删除选中的排序行"""
        selected_rows = set(
            index.row() for index in self.sort_table.selectionModel().selectedIndexes())
        if not selected_rows:
            return
        for row in sorted(selected_rows, reverse=True):
            self.sort_table.removeRow(row)

    def _del_sort_row_at(self, row: int):
        """删除指定行的排序"""
        if row >= 0:
            self.sort_table.removeRow(row)

    def gen_order_str(self) -> str:
        """生成排序 SQL 语句"""
        model = self.sort_table.model()
        if model.rowCount() == 0:
            return ""

        orders = []
        for row in range(model.rowCount()):
            field = model.data(model.index(row, SortModel.COL_FIELD))
            order_text = model.data(model.index(row, SortModel.COL_ORDER))
            order_sql = "ASC" if order_text == _translate(
                "Form", "升序") else "DESC"
            orders.append(f"{field} {order_sql}")

        if orders:
            return " ORDER BY " + ", ".join(orders)
        return ""
