"""
表格模型
"""

from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex

from shared_types.enums import BaseDiaPlayEnum
from .models import HistoryData


class HistoryTableModel(QAbstractTableModel):
    def __init__(
        self,
        data: list[HistoryData],
        headers: list[str],
        show_fields: list[str],
        parent=None,
    ):
        super().__init__(parent)
        self._data = data
        self._headers = headers
        self._show_fields = show_fields
        self._visible_headers = [h for h in headers if h in show_fields]

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._visible_headers)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row >= len(self._data) or col >= len(self._visible_headers):
            return None

        if role == Qt.DisplayRole:
            field_name = self._visible_headers[col]
            value = getattr(self._data[row], field_name)
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d %H:%M:%S.%f")
            elif isinstance(value, BaseDiaPlayEnum):
                return value.display_name
            else:
                # 对于可能是枚举但值不在定义中的情况，直接显示数值
                return str(value)

        elif role == Qt.UserRole:
            field_name = self._visible_headers[col]
            return getattr(self._data[row], field_name)

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter | Qt.AlignVCenter

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole
    ):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section < len(self._visible_headers):
                return self._visible_headers[section]
        return None

    def update_data(self, data: list[HistoryData]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def update_show_fields(self, show_fields: list[str]):
        self.beginResetModel()
        self._show_fields = show_fields
        self._visible_headers = [h for h in self._headers if h in show_fields]
        self.endResetModel()
