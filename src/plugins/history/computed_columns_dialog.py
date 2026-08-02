"""
计算列管理对话框

支持添加、编辑、删除计算列，并验证 SQL 表达式。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .db import db_connection

from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QMessageBox,
    QLabel,
    QPlainTextEdit,
)

from shared_types.widgets import ConfirmDialog
from .computed_column import ComputedColumn

_translate = QCoreApplication.translate


class ComputedColumnsDialog(ConfirmDialog):
    """计算列管理对话框"""

    def __init__(self, columns: list[ComputedColumn], db_path: Path,
                 custom_functions: str = "", parent=None):
        self._columns = [ComputedColumn(col.name, col.expression, col.result_type)
                         for col in columns]
        self._db_path = db_path
        self._custom_functions = custom_functions
        super().__init__(parent, title=_translate("Form", "计算列管理"))
        self.resize(650, 550)

    def _create_content(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # 表格
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels([
            _translate("Form", "列名"),
            _translate("Form", "SQL表达式"),
            _translate("Form", "结果类型"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

        # 按钮
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton(_translate("Form", "添加"))
        self.del_btn = QPushButton(_translate("Form", "删除"))
        self.validate_btn = QPushButton(_translate("Form", "验证"))
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.validate_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 自定义函数编辑区
        func_label = QLabel(
            _translate("Form", "自定义 Python 函数（可在 SQL 表达式中调用）:"))
        layout.addWidget(func_label)
        self.func_edit = QPlainTextEdit(self)
        self.func_edit.setPlaceholderText(
            "def py_my_func(x):\n    return x * 2\n")
        self.func_edit.setPlainText(self._custom_functions)
        self.func_edit.setMaximumHeight(120)
        layout.addWidget(self.func_edit)

        # 初始化表格
        self._init_table()

        # 连接信号
        self.add_btn.clicked.connect(self._add_row)
        self.del_btn.clicked.connect(self._del_row)
        self.validate_btn.clicked.connect(self._validate_all)

        return layout

    def _init_table(self):
        """用已有计算列填充表格"""
        for col in self._columns:
            self._add_column_row(col)

    def _add_column_row(self, col: ComputedColumn | None = None):
        """添加一行"""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 列名
        name_item = QTableWidgetItem(col.name if col else "")
        self.table.setItem(row, 0, name_item)

        # SQL 表达式
        expr_item = QTableWidgetItem(col.expression if col else "")
        self.table.setItem(row, 1, expr_item)

        # 结果类型
        type_combo = QComboBox()
        type_combo.addItems(["float", "int"])
        if col and col.result_type == "int":
            type_combo.setCurrentIndex(1)
        self.table.setCellWidget(row, 2, type_combo)

    def _add_row(self):
        self._add_column_row()

    def _del_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _validate_all(self) -> bool:
        """验证所有表达式，返回是否通过"""
        columns = self._collect_columns()
        if not columns:
            return True  # 没有计算列，无需验证

        # 检查列名合法性
        for col in columns:
            if not col.name.strip():
                QMessageBox.warning(
                    self,
                    _translate("Form", "验证失败"),
                    _translate("Form", "列名不能为空"),
                )
                return False
            if not col.name.isidentifier():
                QMessageBox.warning(
                    self,
                    _translate("Form", "验证失败"),
                    _translate("Form", "列名 '%1' 不是合法标识符").replace(
                        "%1", col.name),
                )
                return False

        # 尝试子查询验证
        subquery = ComputedColumn.build_subquery_sql(columns)
        if not subquery or not self._db_path.exists():
            QMessageBox.warning(
                self,
                _translate("Form", "验证失败"),
                _translate("Form", "无法验证：数据库不存在"),
            )
            return False

        with db_connection(self._db_path) as conn:
            # 先注册当前编辑区中的自定义函数，以便验证时可用
            from .db import _register_custom_functions
            script = self.func_edit.toPlainText()
            if script:
                import ast
                try:
                    tree = ast.parse(script)
                    namespace: dict = {}
                    exec(compile(tree, "<custom_functions>", "exec"), namespace)
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, ast.FunctionDef):
                            func = namespace.get(node.name)
                            if func and callable(func):
                                try:
                                    conn.create_function(
                                        node.name, len(node.args.args), func)  # type: ignore
                                except sqlite3.Error:
                                    pass
                except SyntaxError:
                    pass
            cursor = conn.cursor()
            try:
                # 用 LIMIT 0 验证表达式语法，不实际取数据
                cursor.execute(f"SELECT * FROM ({subquery}) LIMIT 0")
                conn.commit()
                return True
            except sqlite3.Error as e:
                conn.rollback()
                QMessageBox.warning(
                    self,
                    _translate("Form", "验证失败"),
                    _translate("Form", "SQL 错误: %1").replace("%1", str(e)),
                )
                return False

    def _collect_columns(self) -> list[ComputedColumn]:
        """从表格收集计算列"""
        columns = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            expr_item = self.table.item(row, 1)
            type_widget = self.table.cellWidget(row, 2)
            if type_widget is None or not isinstance(type_widget, QComboBox):
                continue

            name = name_item.text().strip() if name_item else ""
            expression = expr_item.text().strip() if expr_item else ""
            result_type = type_widget.currentText() if type_widget else "float"

            if name and expression:
                columns.append(ComputedColumn(name, expression, result_type))
        return columns

    def get_columns(self) -> list[ComputedColumn]:
        """获取对话框中的计算列列表"""
        return self._collect_columns()

    def accept(self):
        """点确定前先验证，验证失败不关闭"""
        if not self._validate_all():
            return
        super().accept()

    def get_custom_functions(self) -> str:
        """获取自定义函数脚本"""
        return self.func_edit.toPlainText()
