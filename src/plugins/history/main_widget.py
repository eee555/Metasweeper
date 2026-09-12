"""
历史记录插件主界面
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast

from .db import db_connection

from PyQt5.QtCore import QCoreApplication, pyqtSignal
from PyQt5.QtGui import QCloseEvent as _QCloseEvent
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSpacerItem,
    QSizePolicy,
    QLabel,
    QComboBox,
    QSpinBox,
    QMessageBox,
)

from .columns_dialog import ColumnsDialog
from .filter_dialog import FilterDialog
from .history_table import HistoryTable
from .models import HistoryData
from .query_builder import build_where, build_order_by
from .table_views import SortModel
from .sort_dialog import SortDialog
from .table_views import FilterModel
from .computed_column import ComputedColumn

_translate = QCoreApplication.translate

# history 表物理字段集合（SELECT 拼接时非物理字段需双引号包裹）
_PHYSICAL_FIELDS = frozenset(HistoryData.fields())


class HistoryMainWidget(QWidget):
    """历史记录插件的主界面（作为插件的 widget 返回）"""

    # 信号：排序和过滤状态变化 (filter_json, sort_json)
    filter_sort_state_changed = pyqtSignal(str, str)
    # 信号：列显示配置变化 (show_fields_json)
    show_fields_changed = pyqtSignal(str)
    # 信号：计算列变化 (columns_json)
    computed_columns_changed = pyqtSignal(list)
    # 信号：自定义函数脚本变化 (script)
    custom_functions_changed = pyqtSignal(str)

    def __init__(
        self,
        db_path: Path,
        config_path: Path,
        float_decimals: int = 2,
        page_size: str = "50",
        parent=None,
    ):
        super().__init__(parent)
        self._db_path = db_path
        self._config_path = config_path
        self._float_decimals = float_decimals
        self._computed_columns: list[ComputedColumn] = []
        self._custom_functions: str = ""

        # 存储过滤和排序条件数据（每次对话框确认后更新）
        self._filter_rows: list[dict] = []
        self._sort_rows: list[dict] = []

        self.setWindowTitle(_translate("Form", "历史记录"))
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # 查询按钮 + 过滤/排序按钮
        btn_layout = QHBoxLayout()
        self.query_button = QPushButton(_translate("Form", "查询"))
        self.filter_button = QPushButton(_translate("Form", "过滤"))
        self.sort_button = QPushButton(_translate("Form", "排序"))
        self.columns_button = QPushButton(_translate("Form", "列设置"))
        self.computed_columns_button = QPushButton(_translate("Form", "计算列"))
        btn_layout.addWidget(self.query_button)
        btn_layout.addWidget(self.filter_button)
        btn_layout.addWidget(self.sort_button)
        btn_layout.addWidget(self.columns_button)
        btn_layout.addWidget(self.computed_columns_button)
        btn_layout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # 当前过滤/排序条件显示
        self.filter_label = QLabel("")
        self.filter_label.setWordWrap(True)
        self.sort_label = QLabel("")
        self.sort_label.setWordWrap(True)

        # 表格
        self.table = HistoryTable(
            self._get_show_fields(), db_path, self._computed_columns, self)

        # 分页
        limit_layout = QHBoxLayout()
        self.previous_button = QPushButton(_translate("Form", "上一页"))
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setValue(1)
        self.next_button = QPushButton(_translate("Form", "下一页"))
        self.one_page_combo = QComboBox()
        self.one_page_combo.addItems(
            ["10", "20", "50", "100", "200", "500", "1000"])
        # 设置默认每页条数
        idx = self.one_page_combo.findText(page_size)
        if idx >= 0:
            self.one_page_combo.setCurrentIndex(idx)

        self.limit_label = QLabel("")
        limit_layout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )
        limit_layout.addWidget(self.limit_label)
        limit_layout.addWidget(self.previous_button)
        limit_layout.addWidget(self.page_spin)
        limit_layout.addWidget(self.next_button)
        limit_layout.addWidget(self.one_page_combo)

        layout.addLayout(btn_layout)
        layout.addWidget(self.filter_label)
        layout.addWidget(self.sort_label)
        layout.addWidget(self.table)
        layout.addLayout(limit_layout)
        self.setLayout(layout)

        self._connect_signals()
        self.load_data()

    def retranslateUi(self):
        self.setWindowTitle(_translate("Form", "历史记录"))
        self.query_button.setText(_translate("Form", "查询"))
        self.filter_button.setText(_translate("Form", "过滤"))
        self.sort_button.setText(_translate("Form", "排序"))
        self.columns_button.setText(_translate("Form", "列设置"))
        self.computed_columns_button.setText(_translate("Form", "计算列"))
        self.previous_button.setText(_translate("Form", "上一页"))
        self.next_button.setText(_translate("Form", "下一页"))

    def set_filter_sort_state(self, filter_json: str, sort_json: str) -> None:
        """设置排序和过滤状态（由插件调用）"""
        try:
            filter_rows = json.loads(filter_json)
            if filter_rows:
                self._filter_rows = filter_rows
        except (json.JSONDecodeError, TypeError):
            pass

        try:
            sort_rows = json.loads(sort_json)
            if sort_rows:
                self._sort_rows = sort_rows
        except (json.JSONDecodeError, TypeError):
            pass

        # 恢复后触发一次查询
        self._on_query()

    def _connect_signals(self):
        self.query_button.clicked.connect(self._on_query)
        self.filter_button.clicked.connect(self._show_filter_dialog)
        self.sort_button.clicked.connect(self._show_sort_dialog)
        self.columns_button.clicked.connect(self._show_columns_dialog)
        self.computed_columns_button.clicked.connect(
            self._show_computed_columns_dialog)
        self.previous_button.clicked.connect(
            lambda: self.page_spin.setValue(self.page_spin.value() - 1)
        )
        self.next_button.clicked.connect(
            lambda: self.page_spin.setValue(self.page_spin.value() + 1)
        )
        self.one_page_combo.currentTextChanged.connect(self.load_data)
        self.page_spin.valueChanged.connect(self.load_data)
        self.table.show_fields_changed.connect(self.show_fields_changed)

    def _show_filter_dialog(self):
        """显示过滤对话框，确认后执行查询"""
        filter_dialog = FilterDialog(
            self._float_decimals, self._computed_columns, self)
        # 从已有条件数据恢复到对话框
        if self._filter_rows:
            model = cast(FilterModel, filter_dialog.table.model())
            for row_data in self._filter_rows:
                row = model.rowCount()
                model.insertRow(row)
                model.setData(model.index(row, FilterModel.COL_LBRACKET),
                              row_data.get("left_bracket"))
                model.setData(model.index(row, FilterModel.COL_FIELD),
                              row_data.get("field"))
                model.setData(model.index(row, FilterModel.COL_COMPARE),
                              row_data.get("compare"))
                model.setData(model.index(row, FilterModel.COL_VALUE),
                              row_data.get("value"))
                model.setData(model.index(row, FilterModel.COL_RBRACKET),
                              row_data.get("right_bracket"))
                model.setData(model.index(row, FilterModel.COL_LOGIC),
                              row_data.get("logic"))
        if filter_dialog.exec_():
            # 保存过滤条件数据
            model = cast(FilterModel, filter_dialog.table.model())
            self._filter_rows = [model.get_row_data(
                row) for row in range(model.rowCount())]
            self._on_query()

    def _show_sort_dialog(self):
        """显示排序对话框，确认后执行查询"""
        sort_dialog = SortDialog(self._computed_columns, self)
        # 从已有条件数据恢复到对话框
        if self._sort_rows:
            model = cast(SortModel, sort_dialog.sort_table.model())
            for row_data in self._sort_rows:
                row = model.rowCount()
                model.insertRow(row)
                model.setData(model.index(row, SortModel.COL_FIELD),
                              row_data.get("field"))
                model.setData(model.index(row, SortModel.COL_ORDER),
                              row_data.get("order"))
        if sort_dialog.exec_():
            # 保存排序条件数据
            model = cast(SortModel, sort_dialog.sort_table.model())
            self._sort_rows = [model.get_row_data(
                row) for row in range(model.rowCount())]
            self._on_query()

    def _show_columns_dialog(self):
        """显示列设置对话框，确认后应用更改"""
        all_headers = HistoryTable.all_headers(self._computed_columns)
        columns_dialog = ColumnsDialog(
            all_headers, self.table.showFields, self)
        if columns_dialog.exec_():
            new_fields = columns_dialog.get_show_fields()
            self.table.showFields = new_fields
            self.table.model.update_show_fields(new_fields)
            self.show_fields_changed.emit(json.dumps(
                list(new_fields), ensure_ascii=False))

    def _on_query(self):
        if self.page_spin.value() > 1:
            self.page_spin.setValue(1)
        else:
            self.load_data()

    def _get_show_fields(self) -> list[str]:
        if not self._config_path.exists():
            return list(HistoryData.fields())
        with open(self._config_path, "r") as f:
            return list(json.load(f))

    def load_data(self):
        if not self._db_path.exists():
            self.page_spin.setMaximum(1)
            self.limit_label.setText(_translate("Form", "共0行,0页"))
            return

        try:
            with db_connection(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                filter_result = self._gen_filter_str()
                if filter_result is None:
                    # 过滤条件校验失败：更新标签后提前返回
                    self._save_filter_sort_state()
                    return
                filter_str, filter_params = filter_result
                order_str = self._gen_order_str()
                if order_str is None:
                    # 排序条件校验失败：更新标签后提前返回
                    self._save_filter_sort_state()
                    return
                # 构建查询字段：显示字段 + 计算列
                show_fields = list(self.table.showFields)
                if self._computed_columns:
                    computed_names = [
                        col.name for col in self._computed_columns]
                    for name in computed_names:
                        if name not in show_fields:
                            show_fields.append(name)
                select_fields = ','.join(
                    f'"{f}"' if f not in _PHYSICAL_FIELDS else f
                    for f in show_fields
                )
                # 有计算列时用子查询，否则直接查原表
                subquery = ComputedColumn.build_subquery_sql(
                    self._computed_columns)
                if subquery:
                    from_clause = f"({subquery})"
                else:
                    from_clause = "history"
                sql = f"SELECT {select_fields}, COUNT(*) OVER() AS total_count FROM {from_clause}"
                if filter_str:
                    sql += " WHERE " + filter_str
                sql += order_str
                # LIMIT/OFFSET 参数绑定
                per_page = int(self.one_page_combo.currentText())
                offset = (self.page_spin.value() - 1) * per_page
                sql += " LIMIT ? OFFSET ?"
                cursor.execute(sql, (*filter_params, per_page, offset))
                datas = cursor.fetchall()

                if not datas:
                    self.page_spin.setMaximum(1)
                    self.limit_label.setText(_translate("Form", "共0行,0页"))
                else:
                    per_page = int(self.one_page_combo.currentText())
                    total = datas[0]["total_count"]
                    max_page = math.ceil(total / per_page)
                    self.page_spin.setMaximum(max_page)
                    self.limit_label.setText(
                        _translate("Form", "共%1行,%2页").replace("%1", str(total)).replace("%2", str(max_page)))

                history_data = [HistoryData.from_dict(dict(d)) for d in datas]
        except sqlite3.Error as e:
            QMessageBox.warning(
                self, _translate("Form", "错误"),
                _translate("Form", "加载历史记录失败: %1").replace("%1", str(e)))
            # 查询出错也要更新过滤/排序标签
            self._save_filter_sort_state()
            return

        self.table.load(history_data)

        # 保存当前的排序和过滤状态
        self._save_filter_sort_state(filter_str, order_str)

    def _format_filter_display(self, filter_rows: list[dict]) -> str:
        """将过滤行数据格式化为易读字符串"""
        if not filter_rows:
            return ""
        parts = []
        for row_data in filter_rows:
            left_bracket = row_data.get("left_bracket") or ""
            field = row_data.get("field") or ""
            compare_text = row_data.get("compare") or ""
            value = row_data.get("value") or ""
            right_bracket = row_data.get("right_bracket") or ""
            logic_text = row_data.get("logic") or ""

            if not field or not compare_text:
                continue

            # 格式化值：日期时间戳转为可读格式
            field_value = self._get_field_value_type(field)
            if isinstance(field_value, datetime) and value:
                try:
                    ts = int(float(value))
                    if ts > 1e15:
                        ts = ts // 1_000_000
                    elif ts > 1e12:
                        ts = ts // 1_000
                    value = datetime.fromtimestamp(
                        ts).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError, OSError):
                    pass

            parts.append(
                f"{left_bracket}{field} {compare_text} {value}{right_bracket}")
            if logic_text:
                parts.append(logic_text)

        return " ".join(parts)

    def _format_sort_display(self, sort_rows: list[dict]) -> str:
        """将排序行数据格式化为易读字符串"""
        if not sort_rows:
            return ""
        parts = []
        for row_data in sort_rows:
            field = row_data.get("field") or ""
            order = row_data.get("order") or ""
            if not field:
                continue
            parts.append(f"{field} {order}")
        return ", ".join(parts)

    def _get_known_fields(self) -> set[str]:
        """获取字段白名单（物理字段 + 已加载计算列名）"""
        fields = set(HistoryData.fields())
        fields.update(col.name for col in self._computed_columns)
        return fields

    def _get_field_types(self) -> dict:
        """获取字段类型样本值映射（供查询构建器做枚举/日期/数值转换）"""
        types = {
            f: HistoryData.get_field_value(f) for f in HistoryData.fields()
        }
        for col in self._computed_columns:
            types[col.name] = 0 if col.result_type == "int" else 0.0
        return types

    def _get_field_value_type(self, field_name: str):
        """获取字段值类型（支持计算列）"""
        result = HistoryData.get_field_value(field_name)
        if result is not None:
            return result
        # 尝试计算列
        for col in self._computed_columns:
            if col.name == field_name:
                if col.result_type == "int":
                    return 0
                elif col.result_type == "float":
                    return 0.0
        return None

    def _gen_filter_str(self) -> tuple[str, list] | None:
        """根据 _filter_rows 生成过滤 SQL 片段与绑定参数

        Returns:
            (sql_fragment, params)，无过滤条件时为 ("", [])；
            校验失败时弹出错误提示并返回 None。
        """
        if not self._filter_rows:
            return "", []
        try:
            return build_where(
                self._filter_rows,
                self._get_known_fields(),
                self._get_field_types(),
            )
        except ValueError as e:
            QMessageBox.warning(self, _translate("Form", "错误"), str(e))
            return None

    def _gen_order_str(self) -> str | None:
        """根据 _sort_rows 生成排序 SQL 片段

        Returns:
            ORDER BY 片段；无排序条件时默认按 replay_id 倒序（最新在前）；
            校验失败时弹出错误提示并返回 None。
        """
        try:
            return build_order_by(
                self._sort_rows, self._get_known_fields()
            ) or " ORDER BY replay_id DESC"
        except ValueError as e:
            QMessageBox.warning(self, _translate("Form", "错误"), str(e))
            return None

    def _save_filter_sort_state(self, filter_str: str = "", order_str: str = "") -> None:
        """发射排序和过滤状态变化信号"""
        self.filter_sort_state_changed.emit(
            json.dumps(self._filter_rows, ensure_ascii=False),
            json.dumps(self._sort_rows, ensure_ascii=False)
        )

        # 更新过滤条件标签（易读格式）
        filter_display = self._format_filter_display(self._filter_rows)
        if filter_display:
            self.filter_label.setText(
                _translate("Form", "过滤: %1").replace("%1", filter_display))
        else:
            self.filter_label.setText(_translate("Form", "过滤: 无"))

        # 更新排序条件标签（易读格式）
        sort_display = self._format_sort_display(self._sort_rows)
        if sort_display:
            self.sort_label.setText(
                _translate("Form", "排序: %1").replace("%1", sort_display))
        else:
            self.sort_label.setText(_translate("Form", "排序: 无"))

    def closeEvent(self, event: _QCloseEvent):
        """关闭事件"""
        super().closeEvent(event)

    def set_float_decimals(self, decimals: int) -> None:
        """动态设置小数位数"""
        self._float_decimals = decimals

    def restore_show_fields(self, show_fields_json: str) -> None:
        """恢复列显示配置"""
        try:
            fields = json.loads(show_fields_json)
            if not fields:
                fields = HistoryTable.all_headers(self._computed_columns)
            self.table.showFields = list(fields)
            self.table.model.update_show_fields(self.table.showFields)
        except (json.JSONDecodeError, TypeError):
            pass

    def on_computed_columns_changed(self, columns: list[ComputedColumn], reload: bool = True) -> None:
        """计算列变更回调（由 plugin.py 调用）"""
        self._computed_columns = columns
        self.table.set_computed_columns(columns)
        # 新增的计算列自动加入 show_fields
        all_headers = HistoryTable.all_headers(columns)
        for col in columns:
            if col.name not in self.table.showFields:
                self.table.showFields.append(col.name)
        # 移除已删除的计算列
        computed_names = {col.name for col in columns}
        self.table.showFields = [
            f for f in self.table.showFields
            if f in all_headers
        ]
        self.table.model.update_show_fields(self.table.showFields)
        if reload:
            self.load_data()

    def set_custom_functions(self, script: str) -> None:
        """设置自定义函数脚本（由 plugin.py 初始化时调用）"""
        self._custom_functions = script

    def _show_computed_columns_dialog(self):
        """显示计算列管理对话框"""
        from .computed_columns_dialog import ComputedColumnsDialog
        dialog = ComputedColumnsDialog(
            self._computed_columns, self._db_path,
            self._custom_functions, self)
        if dialog.exec_():
            new_columns = dialog.get_columns()
            new_functions = dialog.get_custom_functions()
            self._custom_functions = new_functions
            # 通过信号通知 plugin 保存配置并重建视图
            self.computed_columns_changed.emit(new_columns)
            self.custom_functions_changed.emit(new_functions)
