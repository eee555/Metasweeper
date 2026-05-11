"""
过滤条件对话框
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

from PyQt5.QtCore import Qt, QCoreApplication, QTimer
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QMenu,
    QTableView,
    QMessageBox,
    QSizePolicy,
    QHeaderView,
    QWidget,
)

from shared_types.widgets import ConfirmDialog
from .delegates import ComboBoxDelegate, EditableComboBoxDelegate, FilterValueDelegate
from .models import HistoryData, LogicSymbol, CompareSymbol
from .table_views import AutoEditTableView, FilterModel

_translate = QCoreApplication.translate


class FilterDialog(ConfirmDialog):
    """过滤条件对话框"""

    def __init__(self, float_decimals: int = 2, parent=None):
        self._float_decimals = float_decimals
        super().__init__(parent, title=_translate("Form", "过滤条件"))
        self.resize(700, 300)

    def _create_content(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = AutoEditTableView()
        self.table.setModel(FilterModel(self))
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.setSelectionBehavior(QTableView.SelectItems)
        self.table.setSelectionMode(QTableView.ExtendedSelection)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 设置所有列自动进入编辑
        self.table.setAutoEditColumns(
            list(range(FilterModel.COL_LBRACKET, FilterModel.COL_LOGIC + 1)))
        # 禁用双击编辑
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        layout.addWidget(self.table)

        self._setup_delegates()
        self._connect_field_change_signal()

        return widget

    def _connect_field_change_signal(self):
        """当字段列改变时，更新值列的默认值"""
        self.table.model().dataChanged.connect(self._on_field_changed)

    def _on_field_changed(self, topLeft, bottomRight, roles):
        """字段列或比较符列改变时触发"""
        if Qt.EditRole not in roles:
            return
        model = self.table.model()
        for row in range(topLeft.row(), bottomRight.row() + 1):
            for col in range(topLeft.column(), bottomRight.column() + 1):
                if col == FilterModel.COL_FIELD:
                    self._update_value_default(row)
                # 字段或比较符变化时，关闭值列的编辑器，下次打开会使用正确的编辑器类型
                if col in (FilterModel.COL_FIELD, FilterModel.COL_COMPARE):
                    value_index = model.index(row, FilterModel.COL_VALUE)
                    self._close_value_editor(value_index)

    def _close_value_editor(self, index):
        """关闭值列的编辑器（针对非持久编辑器）"""
        # 检查值列是否正在编辑
        if self.table.state() == QTableView.EditingState and self.table.currentIndex() == index:
            # 临时阻止自动编辑
            self.table.suppress_auto_edit = True
            # 先移到其他列，关闭当前编辑器
            row = index.row()
            model = self.table.model()
            self.table.setCurrentIndex(
                model.index(row, FilterModel.COL_LBRACKET))
            # 恢复自动编辑
            self.table.suppress_auto_edit = False
            # 延迟移回值列，让编辑器重新创建
            QTimer.singleShot(
                50, lambda idx=index: self.table.setCurrentIndex(idx))

    def _update_value_default(self, row: int):
        """更新指定行的值列默认值"""
        model = self.table.model()
        field_name = model.data(model.index(row, FilterModel.COL_FIELD))

        if not field_name:
            return

        field_value = HistoryData.get_field_value(field_name)
        new_default = self._get_default_value(field_value)

        # 获取当前值（使用 EditRole 获取原始数据）
        current_value = model.data(model.index(
            row, FilterModel.COL_VALUE), Qt.EditRole)

        # 始终更新为新类型的默认值
        model.setData(
            model.index(row, FilterModel.COL_VALUE),
            new_default,
            Qt.EditRole
        )

    def _get_default_value(self, field_value) -> str:
        """获取字段类型的默认值"""
        from shared_types.enums import BaseDiaPlayEnum

        if field_value is None:
            return ""
        elif isinstance(field_value, BaseDiaPlayEnum):
            # 枚举类型返回第一个选项
            return field_value.__class__.display_names()[0]
        elif isinstance(field_value, datetime):
            # 日期类型返回当前时间戳（微秒）
            ts = int(datetime.now().timestamp() * 1_000_000)
            return str(ts)
        elif isinstance(field_value, float):
            return "0.0"
        elif isinstance(field_value, int):
            return "0"
        else:
            return ""

    def _setup_delegates(self):
        """设置列代理"""
        # 左括号
        self.table.setItemDelegateForColumn(
            FilterModel.COL_LBRACKET,
            ComboBoxDelegate(["", "(", "(("], self)
        )
        # 字段
        self.table.setItemDelegateForColumn(
            FilterModel.COL_FIELD,
            EditableComboBoxDelegate(HistoryData.fields(), self)
        )
        # 比较符
        self.table.setItemDelegateForColumn(
            FilterModel.COL_COMPARE,
            ComboBoxDelegate(CompareSymbol.display_names(), self)
        )
        # 值列 - 使用智能代理
        self.table.setItemDelegateForColumn(
            FilterModel.COL_VALUE,
            FilterValueDelegate(self._float_decimals, self)
        )
        # 右括号
        self.table.setItemDelegateForColumn(
            FilterModel.COL_RBRACKET,
            ComboBoxDelegate(["", ")", "))"], self)
        )
        # 逻辑符
        self.table.setItemDelegateForColumn(
            FilterModel.COL_LOGIC,
            ComboBoxDelegate(LogicSymbol.display_names(), self)
        )

    def set_float_decimals(self, decimals: int) -> None:
        """动态设置小数位数"""
        self._float_decimals = decimals
        # 更新值列代理
        self.table.setItemDelegateForColumn(
            FilterModel.COL_VALUE,
            FilterValueDelegate(self._float_decimals, self)
        )

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(_translate("Form", "添加"), self.add_row)
        menu.addAction(
            _translate("Form", "插入"), lambda: self.insert_row(
                self.table.currentIndex().row())
        )
        menu.addAction(_translate("Form", "删除"), self.del_row)
        menu.exec_(self.table.mapToGlobal(pos))

    def add_row(self):
        self.insert_row(self.table.model().rowCount())

    def del_row(self):
        # 获取所有选中的行
        selected_rows = set(index.row()
                            for index in self.table.selectionModel().selectedIndexes())
        if not selected_rows:
            return
        # 取消行选中
        self.table.clearSelection()
        # 从后往前删除，避免索引变化
        for row in sorted(selected_rows, reverse=True):
            self.table.removeRow(row)

    def insert_row(self, row: int):
        if row < 0:
            row = 0
        model = self.table.model()
        self.table.insertRow(row)
        # 设置默认值
        model.setData(model.index(row, FilterModel.COL_FIELD),
                      HistoryData.fields()[0])
        model.setData(model.index(row, FilterModel.COL_COMPARE),
                      CompareSymbol.display_names()[0])
        model.setData(model.index(row, FilterModel.COL_LOGIC),
                      LogicSymbol.display_names()[0])
        # 不需要手动设置值，代理会根据字段类型自动处理

    def gen_filter_str(self):
        model = cast(FilterModel, self.table.model())
        filter_str = ""
        left_count = 0
        right_count = 0
        for row in range(model.rowCount()):
            data = model.get_row_data(row)
            field_value_type = model.get_field_value_type(row)

            left_bracket = data["left_bracket"] or ""
            field = data["field"] or ""
            compare_text = data["compare"] or ""
            value = data["value"] or ""
            right_bracket = data["right_bracket"] or ""
            logic_text = data["logic"] or ""

            if not field or not compare_text:
                continue

            compare = CompareSymbol.from_display_name(compare_text)
            logic = LogicSymbol.from_display_name(logic_text).to_sql

            if left_bracket == "(":
                left_count += 1
            elif left_bracket == "((":
                left_count += 2
            if right_bracket == ")":
                right_count += 1
            elif right_bracket == "))":
                right_count += 2

            if right_count > left_count:
                QMessageBox.warning(
                    self, "错误", f"第{row}行 右括号数量大于左括号数量，请检查"
                )
                return None

            # 处理值
            from shared_types.enums import BaseDiaPlayEnum
            if isinstance(field_value_type, BaseDiaPlayEnum) and compare.value not in (CompareSymbol.Contains, CompareSymbol.NotContains):
                enum_cls = field_value_type.__class__
                for e in enum_cls:
                    if e.display_name == value:
                        value = str(e.value)
                        break
            elif compare.value in (CompareSymbol.Contains, CompareSymbol.NotContains):
                if isinstance(field_value_type, (int, float)):
                    values = value.split(",")
                    for v in values:
                        if not v.replace("-", "").replace(".", "").isdigit():
                            QMessageBox.warning(
                                self, "错误", f"第{row}行 {v} 不是数字"
                            )
                            return None
                    value = ",".join(v for v in values)
                elif isinstance(field_value_type, datetime):
                    values = value.split(",")
                    parsed_values = []
                    for v in values:
                        v = v.strip()
                        if not v:
                            continue
                        try:
                            # 尝试解析为时间戳（微秒）
                            ts = int(float(v))
                            parsed_values.append(str(ts))
                        except ValueError:
                            # 尝试解析为日期时间字符串
                            try:
                                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                                    try:
                                        dt = datetime.strptime(v, fmt)
                                        parsed_values.append(
                                            str(int(dt.timestamp() * 1_000_000)))
                                        break
                                    except ValueError:
                                        continue
                                else:
                                    raise ValueError(f"无法解析日期: {v}")
                            except ValueError as e:
                                QMessageBox.warning(
                                    self, "错误", f"第{row}行 {v} 不是合法的日期时间"
                                )
                                return None
                    value = ",".join(parsed_values) if parsed_values else ""
                elif isinstance(field_value_type, BaseDiaPlayEnum):
                    enum_cls = field_value_type.__class__
                    values = value.split(",")
                    parsed_values = []
                    for v in values:
                        v = v.strip()
                        if not v:
                            continue
                        for e in enum_cls:
                            if e.display_name == v:
                                parsed_values.append(str(e.value))
                                break
                        else:
                            QMessageBox.warning(
                                self, "错误", f"第{row}行 {v} 不是合法的枚举选项"
                            )
                            return None
                    value = ",".join(parsed_values) if parsed_values else ""

                else:
                    value = ",".join(
                        f"'{v}'" for v in value.split(",") if v.strip())
                value = f"({value})" if value else "()"
            elif isinstance(field_value_type, datetime) and value:
                try:
                    # 可能是时间戳字符串
                    ts = int(float(value))
                    value = str(ts)
                except ValueError:
                    # 尝试解析日期时间字符串
                    try:
                        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                            try:
                                dt = datetime.strptime(value, fmt)
                                value = str(int(dt.timestamp() * 1_000_000))
                                break
                            except ValueError:
                                continue
                        else:
                            QMessageBox.warning(
                                self, "错误", f"第{row}行 {value} 不是合法的日期时间"
                            )
                            return None
                    except ValueError:
                        QMessageBox.warning(
                            self, "错误", f"第{row}行 {value} 不是合法的日期时间"
                        )
                        return None
            elif value and not value.startswith("'"):
                value = f"'{value}'"

            is_last = row == model.rowCount() - 1
            filter_str += (
                f" {left_bracket} {field} {compare.to_sql} {value} {right_bracket} "
            )
            if not is_last:
                filter_str += logic

        if left_count != right_count:
            QMessageBox.warning(self, "错误", "左括号数量和右括号数量不匹配，请检查")
            return None
        return filter_str
