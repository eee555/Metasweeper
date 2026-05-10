"""
UI 组件（兼容性转发，实际类已拆分到各子模块）
"""

from .columns_dialog import ColumnsDialog
from .delegates import ComboBoxDelegate, EditableComboBoxDelegate, FilterValueDelegate
from .filter_dialog import FilterDialog
from .history_table import HistoryTable
from .main_widget import HistoryMainWidget
from .sort_dialog import SortDialog
from .table_views import AutoEditTableView, FilterModel, SortModel

__all__ = [
    "ComboBoxDelegate",
    "EditableComboBoxDelegate",
    "FilterValueDelegate",
    "AutoEditTableView",
    "FilterModel",
    "SortModel",
    "FilterDialog",
    "SortDialog",
    "ColumnsDialog",
    "HistoryTable",
    "HistoryMainWidget",
]
