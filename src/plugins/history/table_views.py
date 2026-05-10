"""
自定义表格视图和模型
"""

from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import Qt, QModelIndex, QTimer
from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtWidgets import QTableView

from .models import HistoryData


class AutoEditTableView(QTableView):
    """自动进入编辑状态的 TableView"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_edit_columns = set()  # 需要自动编辑的列
        self.suppress_auto_edit = False  # 标记是否阻止自动编辑
        self.clicked.connect(self._on_click_auto_edit)
        # 垂直表头点击选中整行
        self.verticalHeader().sectionClicked.connect(self._on_header_select_row)
        self.verticalHeader().setMaximumWidth(24)
        self.verticalHeader().setMinimumWidth(24)

    def mousePressEvent(self, event):
        """鼠标按下事件：右键点击时阻止自动编辑"""
        # 右键点击，阻止自动编辑
        if event.button() == Qt.RightButton:
            self.suppress_auto_edit = True
        super().mousePressEvent(event)
        self.reset_suppress_flag()

    def reset_suppress_flag(self):
        """重置阻止自动编辑标志"""
        self.suppress_auto_edit = False

    def setAutoEditColumn(self, column: int):
        """设置指定列自动进入编辑"""
        self._auto_edit_columns.add(column)

    def setAutoEditColumns(self, columns: list[int]):
        """设置多个列自动进入编辑"""
        self._auto_edit_columns.update(columns)

    def _on_header_select_row(self, section: int):
        """通过垂直表头点击选中整行时，清除单元格焦点"""
        self.selectRow(section)
        # 清除单元格焦点，让焦点回到 TableView 本身
        self.setFocus()

    def _on_click_auto_edit(self, index: QModelIndex):
        """鼠标点击时自动进入编辑"""
        # 如果 index 无效，不做任何操作
        if not index.isValid():
            return

        # 右键点击后不自动编辑
        if self.suppress_auto_edit:
            return

        # 如果模型没有行，不自动编辑
        model = self.model()
        if model is None or model.rowCount() == 0:
            return

        if index.column() in self._auto_edit_columns:
            if self.state() != QTableView.EditingState:
                self.edit(index)
            return

        # 如果不是自动编辑列，不进入编辑
        self.selectionModel().setCurrentIndex(index, self.selectionModel().NoUpdate)

    def currentChanged(self, current: QModelIndex, previous: QModelIndex):
        """当焦点单元格改变时，自动进入编辑状态（表头选择整行时不触发）"""
        super().currentChanged(current, previous)

        # 如果没有有效的单元格，不自动进入编辑
        if not current.isValid():
            return

        # 右键点击或表头选择整行，不自动进入编辑
        if self.suppress_auto_edit:
            return

        if current.column() in self._auto_edit_columns:
            QTimer.singleShot(0, lambda: self._try_edit(current))

    def _try_edit(self, index: QModelIndex):
        """尝试进入编辑状态"""
        if self.state() != QTableView.EditingState:
            self.edit(index)

    def addRow(self):
        """添加一行"""
        self.suppress_auto_edit = True
        model = self.model()
        if model is None:
            return

        model.insertRow(model.rowCount())
        self.suppress_auto_edit = False

    def insertRow(self, row: int):
        """插入一行"""
        self.suppress_auto_edit = True
        model = self.model()
        if model is None:
            return

        model.insertRow(row)
        self.suppress_auto_edit = False

    def removeRow(self, row: int):
        """删除一行"""
        self.suppress_auto_edit = True
        model = self.model()
        if model is None:
            return

        model.removeRow(row)
        self.suppress_auto_edit = False


class FilterModel(QStandardItemModel):
    """过滤表格模型"""

    COL_LBRACKET, COL_FIELD, COL_COMPARE, COL_VALUE, COL_RBRACKET, COL_LOGIC = range(
        6)

    def __init__(self, parent=None):
        super().__init__(0, 6, parent)
        self.setHorizontalHeaderLabels(
            ["左括号", "字段", "比较符", "值", "右括号", "逻辑符"]
        )

    def data(self, index, role=Qt.DisplayRole):
        """重写 data 方法，格式化某些列的显示"""
        if not index.isValid():
            return None

        if role == Qt.DisplayRole:
            column = index.column()
            raw_data = super().data(index, Qt.EditRole)

            # 值列需要格式化显示
            if column == self.COL_VALUE:
                if not raw_data:
                    return ""

                # 获取同行字段名来确定类型
                field_index = self.index(index.row(), self.COL_FIELD)
                field_name = super().data(field_index, Qt.EditRole)

                if field_name:
                    field_value = HistoryData.get_field_value(field_name)
                    if isinstance(field_value, datetime):
                        # 尝试解析时间戳并格式化为可读格式
                        try:
                            ts = int(raw_data)
                            if ts > 1e15:  # 微秒
                                ts = ts / 1_000_000
                            elif ts > 1e12:  # 毫秒
                                ts = ts / 1_000
                            dt = datetime.fromtimestamp(ts)
                            return dt.strftime("%Y-%m-%d %H:%M:%S")
                        except (ValueError, TypeError, OSError):
                            return raw_data

            return raw_data

        return super().data(index, role)

    def get_row_data(self, row: int) -> dict:
        """获取指定行的所有数据"""
        return {
            "left_bracket": self.data(self.index(row, self.COL_LBRACKET)),
            "field": self.data(self.index(row, self.COL_FIELD)),
            "compare": self.data(self.index(row, self.COL_COMPARE)),
            "value": self.data(self.index(row, self.COL_VALUE)),
            "right_bracket": self.data(self.index(row, self.COL_RBRACKET)),
            "logic": self.data(self.index(row, self.COL_LOGIC)),
        }

    def get_field_value_type(self, row: int):
        """获取指定行字段的原始值类型"""
        field_name = str(self.data(self.index(row, self.COL_FIELD)))
        return HistoryData.get_field_value(field_name)


class SortModel(QStandardItemModel):
    """排序表格模型"""

    COL_FIELD, COL_ORDER = range(2)

    def __init__(self, parent=None):
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["排序字段", "升序/降序"])

    def get_row_data(self, row: int) -> dict:
        """获取指定行的所有数据"""
        return {
            "field": self.data(self.index(row, self.COL_FIELD)),
            "order": self.data(self.index(row, self.COL_ORDER)),
        }
