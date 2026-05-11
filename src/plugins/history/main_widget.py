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
from .models import HistoryData, CompareSymbol, LogicSymbol
from .table_views import SortModel
from .sort_dialog import SortDialog
from .table_views import FilterModel
from shared_types.enums import BaseDiaPlayEnum

_translate = QCoreApplication.translate


class HistoryMainWidget(QWidget):
    """历史记录插件的主界面（作为插件的 widget 返回）"""

    # 信号：排序和过滤状态变化 (filter_json, sort_json)
    filter_sort_state_changed = pyqtSignal(str, str)
    # 信号：列显示配置变化 (show_fields_json)
    show_fields_changed = pyqtSignal(str)

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
        btn_layout.addWidget(self.query_button)
        btn_layout.addWidget(self.filter_button)
        btn_layout.addWidget(self.sort_button)
        btn_layout.addWidget(self.columns_button)
        btn_layout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # 当前过滤/排序条件显示
        self.filter_label = QLabel("")
        self.filter_label.setWordWrap(True)
        self.sort_label = QLabel("")
        self.sort_label.setWordWrap(True)

        # 表格
        self.table = HistoryTable(self._get_show_fields(), db_path, self)

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
        filter_dialog = FilterDialog(self._float_decimals, self)
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
            self._filter_rows = [model.get_row_data(row) for row in range(model.rowCount())]
            self._on_query()

    def _show_sort_dialog(self):
        """显示排序对话框，确认后执行查询"""
        sort_dialog = SortDialog(self)
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
            self._sort_rows = [model.get_row_data(row) for row in range(model.rowCount())]
            self._on_query()

    def _show_columns_dialog(self):
        """显示列设置对话框，确认后应用更改"""
        columns_dialog = ColumnsDialog(
            HistoryTable.HEADERS, self.table.showFields, self)
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

    def _get_limit_str(self):
        per_page = int(self.one_page_combo.currentText())
        offset = (self.page_spin.value() - 1) * per_page
        return f" LIMIT {per_page} OFFSET {offset}"

    def _get_show_fields(self) -> list[str]:
        if not self._config_path.exists():
            return list(HistoryData.fields())
        with open(self._config_path, "r") as f:
            return list(json.load(f))

    def load_data(self):
        if not self._db_path.exists():
            QMessageBox.warning(self, "错误", "历史记录数据库不存在")
            return

        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            filter_str = self._gen_filter_str()
            order_str = self._gen_order_str()
            sql = "SELECT *, COUNT(*) OVER() AS total_count FROM history"
            if filter_str:
                sql += " WHERE " + filter_str
            elif filter_str is None:
                return
            sql += order_str
            sql += self._get_limit_str()
            cursor.execute(sql)
            datas = cursor.fetchall()

            if not datas:
                self.page_spin.setMaximum(1)
                self.limit_label.setText("共0行,0页")
            else:
                per_page = int(self.one_page_combo.currentText())
                total = datas[0]["total_count"]
                max_page = math.ceil(total / per_page)
                self.page_spin.setMaximum(max_page)
                self.limit_label.setText(f"共{total}行,{max_page}页")

            history_data = [HistoryData.from_dict(dict(d)) for d in datas]
            conn.close()
        except sqlite3.Error as e:
            QMessageBox.warning(self, "错误", f"加载历史记录失败: {e}")
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
            try:
                field_value = HistoryData.get_field_value(field)
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
            except (KeyError, IndexError):
                pass

            part = f"{left_bracket}{field} {compare_text} {value}{right_bracket}"
            parts.append((part, logic_text))

        if not parts:
            return ""

        result = ""
        for i, (part, logic) in enumerate(parts):
            result += part
            if i < len(parts) - 1 and logic:
                result += f" {logic} "
        return result

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

    def _gen_filter_str(self) -> str | None:
        """根据 _filter_rows 生成过滤 SQL 语句"""
        if not self._filter_rows:
            return ""

        filter_str = ""
        left_count = 0
        right_count = 0

        for row, data in enumerate(self._filter_rows):
            field_value_type = HistoryData.get_field_value(data.get("field") or "")

            left_bracket = data.get("left_bracket") or ""
            field = data.get("field") or ""
            compare_text = data.get("compare") or ""
            value = data.get("value") or ""
            right_bracket = data.get("right_bracket") or ""
            logic_text = data.get("logic") or ""

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
                            ts = int(float(v))
                            parsed_values.append(str(ts))
                        except ValueError:
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
                    ts = int(float(value))
                    value = str(ts)
                except ValueError:
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

            is_last = row == len(self._filter_rows) - 1
            filter_str += (
                f" {left_bracket} {field} {compare.to_sql} {value} {right_bracket} "
            )
            if not is_last:
                filter_str += logic

        if left_count != right_count:
            QMessageBox.warning(self, "错误", "左括号数量和右括号数量不匹配，请检查")
            return None
        return filter_str

    def _gen_order_str(self) -> str:
        """根据 _sort_rows 生成排序 SQL 语句"""
        if not self._sort_rows:
            return ""

        orders = []
        for row_data in self._sort_rows:
            field = row_data.get("field") or ""
            order_text = row_data.get("order") or ""
            if not field:
                continue
            order_sql = "ASC" if order_text == _translate("Form", "升序") else "DESC"
            orders.append(f"{field} {order_sql}")

        if orders:
            return " ORDER BY " + ", ".join(orders)
        return ""

    def _save_filter_sort_state(self, filter_str: str = "", order_str: str = "") -> None:
        """发射排序和过滤状态变化信号"""
        self.filter_sort_state_changed.emit(
            json.dumps(self._filter_rows, ensure_ascii=False), 
            json.dumps(self._sort_rows, ensure_ascii=False)
        )

        # 更新过滤条件标签（易读格式）
        filter_display = self._format_filter_display(self._filter_rows)
        if filter_display:
            self.filter_label.setText(f"过滤: {filter_display}")
        else:
            self.filter_label.setText("过滤: 无")

        # 更新排序条件标签（易读格式）
        sort_display = self._format_sort_display(self._sort_rows)
        if sort_display:
            self.sort_label.setText(f"排序: {sort_display}")
        else:
            self.sort_label.setText("排序: 无")

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
                fields = self.table.HEADERS
            self.table.showFields = list(fields)
            self.table.model.update_show_fields(self.table.showFields)
        except (json.JSONDecodeError, TypeError):
            pass
