"""
历史记录插件

功能：
- 监听 VideoSaveEvent，将游戏录像数据持久化到 SQLite 数据库
- 提供 GUI 界面：表格浏览、筛选、分页、播放/导出录像
- 使用 self.data_dir 存储数据库文件（每个插件独立目录）
"""

from __future__ import annotations

import base64
import json
import math
import sqlite3
import subprocess
import sys
import inspect
from datetime import datetime
from pathlib import Path
import time
from typing import Any

import msgspec

from plugin_manager import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from plugin_manager.app_paths import get_executable_dir
from shared_types.events import VideoSaveEvent
from shared_types.services.history import HistoryService, GameRecord

from PyQt5.QtCore import (
    QObject,
    Qt,
    QCoreApplication,
    QAbstractTableModel,
    QModelIndex,
    pyqtSignal,
)
from PyQt5.QtGui import QCloseEvent as _QCloseEvent
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QMenu,
    QAction,
    QTableWidgetItem,
    QHeaderView,
    QTableView,
    QMessageBox,
    QFileDialog,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QDateTimeEdit,
    QHBoxLayout,
    QPushButton,
    QSpacerItem,
    QSizePolicy,
    QLabel,
)

_translate = QCoreApplication.translate


# ── 枚举定义（替代原 utils 中的枚举）─────────────────────


class LogicSymbol:
    And = 0
    Or = 1

    _LABELS = {0: _translate("Form", "与"), 1: _translate("Form", "或")}
    _SQL = {0: "and", 1: "or"}

    @classmethod
    def display_names(cls):
        return [cls._LABELS[cls.And], cls._LABELS[cls.Or]]

    @classmethod
    def from_display_name(cls, name: str):
        for v, n in cls._LABELS.items():
            if n == name:
                return cls(v)
        raise ValueError(name)

    def __init__(self, value: int):
        self.value = value

    @property
    def display_name(self):
        return self._LABELS[self.value]

    @property
    def to_sql(self):
        return self._SQL[self.value]


class CompareSymbol:
    Equal = 0
    NotEqual = 1
    GreaterThan = 2
    LessThan = 3
    GreaterThanOrEqual = 4
    LessThanOrEqual = 5
    Contains = 6
    NotContains = 7

    _LABELS = {
        0: _translate("Form", "等于"),
        1: _translate("Form", "不等于"),
        2: _translate("Form", "大于"),
        3: _translate("Form", "小于"),
        4: _translate("Form", "大于等于"),
        5: _translate("Form", "小于等于"),
        6: _translate("Form", "包含"),
        7: _translate("Form", "不包含"),
    }
    _SQL = {
        0: "=",
        1: "!=",
        2: ">",
        3: "<",
        4: ">=",
        5: "<=",
        6: "in",
        7: "not in",
    }

    @classmethod
    def display_names(cls):
        return [cls._LABELS[i] for i in range(len(cls._LABELS))]

    @classmethod
    def from_display_name(cls, name: str):
        for v, n in cls._LABELS.items():
            if n == name:
                return cls(v)
        raise ValueError(name)

    def __init__(self, value: int):
        self.value = value

    @property
    def display_name(self):
        return self._LABELS[self.value]

    @property
    def to_sql(self):
        return self._SQL[self.value]


# ── 数据模型 ───────────────────────────────────────────────


class HistoryData:
    """历史记录数据行（纯数据类，用类属性定义字段）"""

    replay_id: int = 0
    game_board_state: int = 0
    rtime: float = 0
    left: int = 0
    right: int = 0
    double: int = 0
    left_s: float = 0.0
    right_s: float = 0.0
    double_s: float = 0.0
    level: int = 0
    cl: int = 0
    cl_s: float = 0.0
    ce: int = 0
    ce_s: float = 0.0
    rce: int = 0
    lce: int = 0
    dce: int = 0
    bbbv: int = 0
    bbbv_solved: int = 0
    bbbv_s: float = 0.0
    flag: int = 0
    path: float = 0.0
    etime: float = 0
    start_time: int = 0
    end_time: int = 0
    mode: int = 0
    software: str = ""
    player_identifier: str = ""
    race_identifier: str = ""
    uniqueness_identifier: str = ""
    stnb: float = 0.0
    corr: float = 0.0
    thrp: float = 0.0
    ioe: float = 0.0
    is_official: int = 0
    is_fair: int = 0
    op: int = 0
    isl: int = 0
    pluck: float = 0.0

    @classmethod
    def get_field_value(cls, field_name: str):
        for name, value in inspect.getmembers(cls):
            if (
                not name.startswith("__")
                and not callable(value)
                and not name.startswith("_")
                and name == field_name
            ):
                return value

    @classmethod
    def fields(cls):
        return [
            name
            for name, value in inspect.getmembers(cls)
            if not name.startswith("__")
            and not callable(value)
            and not name.startswith("_")
        ]

    @classmethod
    def query_all(cls):
        return f"select {','.join(cls.fields())} from history"

    @classmethod
    def from_dict(cls, data: dict):
        instance = cls()
        for name, value in inspect.getmembers(cls):
            if (
                not name.startswith("__")
                and not callable(value)
                and not name.startswith("_")
            ):
                new_value = data.get(name)
                # 时间戳字段转换
                if (
                    name in ("etime",)
                    and isinstance(new_value, (int, float))
                    and new_value
                ):
                    value = new_value
                elif (
                    name in ("start_time", "end_time")
                    and isinstance(new_value, (int, float))
                    and new_value
                ):
                    value = datetime.fromtimestamp(new_value / 1_000_000)
                elif isinstance(value, float):
                    value = round(new_value, 4)
                else:
                    value = new_value
                setattr(instance, name, value)
        return instance


# ── Table Model ────────────────────────────────────────────


class HistoryTableModel(QAbstractTableModel):
    def __init__(
        self,
        data: list[HistoryData],
        headers: list[str],
        show_fields: set[str],
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
            else:
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

    def update_show_fields(self, show_fields: set[str]):
        self.beginResetModel()
        self._show_fields = show_fields
        self._visible_headers = [h for h in self._headers if h in show_fields]
        self.endResetModel()


# ── 筛选控件 ──────────────────────────────────────────────


class FilterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        vbox = QVBoxLayout(self)
        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["左括号", "字段", "比较符", "值", "右括号", "逻辑符"]
        )
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        vbox.addWidget(self.table)
        self.setLayout(vbox)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(_translate("Form", "添加"), self.add_row)
        menu.addAction(_translate("Form", "删除"), self.del_row)
        menu.addAction(
            _translate("Form", "插入"), lambda: self.insert_row(
                self.table.currentRow())
        )
        menu.exec_(self.table.mapToGlobal(pos))

    def _build_left_bracket(self):
        w = QComboBox(self)
        w.addItems(["", "(", "(("])
        return w

    def _build_field(self):
        w = QComboBox(self)
        w.addItems(HistoryData.fields())
        w.currentIndexChanged.connect(self.on_field_changed)
        return w

    def _build_compare(self):
        w = QComboBox(self)
        w.addItems(CompareSymbol.display_names())
        w.currentIndexChanged.connect(self.on_compare_changed)
        return w

    def _build_right_bracket(self):
        w = QComboBox(self)
        w.addItems(["", ")", "))"])
        return w

    def _build_logic(self):
        w = QComboBox(self)
        w.addItems(LogicSymbol.display_names())
        return w

    def on_field_changed(self, index):
        combo: QComboBox = self.sender()
        item_index = self.table.indexAt(combo.pos())
        if not item_index.isValid():
            return
        row = item_index.row()
        field_name = combo.currentText()
        compare_w: QComboBox = self.table.cellWidget(row, 2)
        compare = CompareSymbol.from_display_name(compare_w.currentText())
        field_cls = HistoryData.get_field_value(field_name)
        self.table.setCellWidget(
            row, 3, self._build_value_widget(compare, field_cls))

    def on_compare_changed(self, index):
        combo: QComboBox = self.sender()
        item_index = self.table.indexAt(combo.pos())
        if not item_index.isValid():
            return
        row = item_index.row()
        field_w: QComboBox = self.table.cellWidget(row, 1)
        field_name = field_w.currentText()
        compare = CompareSymbol.from_display_name(combo.currentText())
        field_cls = HistoryData.get_field_value(field_name)
        self.table.setCellWidget(
            row, 3, self._build_value_widget(compare, field_cls))

    def _build_value_widget(self, compare: CompareSymbol, field_value: Any):
        if compare not in (CompareSymbol.Contains, CompareSymbol.NotContains):
            if isinstance(field_value, int):
                return QSpinBox(self)
            elif isinstance(field_value, float):
                return QDoubleSpinBox(self)
            elif isinstance(field_value, str):
                return QLineEdit(self)
            elif isinstance(field_value, datetime):
                return QDateTimeEdit(self)
        return QLineEdit(self)

    def add_row(self):
        self.insert_row(self.table.rowCount())

    def del_row(self):
        self.table.removeRow(self.table.currentRow())

    def insert_row(self, row: int):
        self.table.insertRow(row)
        field_w = self._build_field()
        compare_w = self._build_compare()
        compare = CompareSymbol.from_display_name(compare_w.currentText())
        field_value = HistoryData.get_field_value(field_w.currentText())
        self.table.setCellWidget(row, 0, self._build_left_bracket())
        self.table.setCellWidget(row, 1, field_w)
        self.table.setCellWidget(row, 2, compare_w)
        self.table.setCellWidget(
            row, 3, self._build_value_widget(compare, field_value))
        self.table.setCellWidget(row, 4, self._build_right_bracket())
        self.table.setCellWidget(row, 5, self._build_logic())

    def gen_filter_str(self):
        filter_str = ""
        left_count = 0
        right_count = 0
        for row in range(self.table.rowCount()):
            left_bracket_w = self.table.cellWidget(row, 0)
            field_w = self.table.cellWidget(row, 1)
            compare_w = self.table.cellWidget(row, 2)
            value_w = self.table.cellWidget(row, 3)
            right_bracket_w = self.table.cellWidget(row, 4)
            logic_w = self.table.cellWidget(row, 5)

            left_bracket = left_bracket_w.currentText()
            field = field_w.currentText()
            field_init_value = HistoryData.get_field_value(field)
            compare = CompareSymbol.from_display_name(compare_w.currentText())
            right_bracket = right_bracket_w.currentText()
            logic = LogicSymbol.from_display_name(logic_w.currentText()).to_sql

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

            # 获取值
            if isinstance(value_w, QComboBox):
                value = value_w.currentText()
            elif isinstance(value_w, QDateTimeEdit):
                value = int(
                    value_w.dateTime().toPyDateTime().timestamp() * 1_000_000)
            elif isinstance(value_w, QSpinBox):
                value = str(value_w.value())
            elif isinstance(value_w, QDoubleSpinBox):
                value = str(value_w.value())
            elif isinstance(value_w, QLineEdit):
                if compare in (CompareSymbol.Contains, CompareSymbol.NotContains):
                    if isinstance(field_init_value, (int, float)):
                        values = value_w.text().split(",")
                        for v in values:
                            if not v.replace("-", "").isdigit():
                                QMessageBox.warning(
                                    self, "错误", f"第{row}行 {v} 不是数字"
                                )
                                return None
                        value = ",".join(v for v in values)
                    elif isinstance(field_init_value, datetime):
                        values = value_w.text().split(",")
                        for v in values:
                            try:
                                datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                QMessageBox.warning(
                                    self, "错误", f"第{row}行 {v} 不是合法的日期时间"
                                )
                                return None
                        values = [
                            int(
                                datetime.strptime(
                                    v, "%Y-%m-%d %H:%M:%S").timestamp()
                                * 1_000_000
                            )
                            for v in values
                        ]
                        value = ",".join(str(v) for v in values)
                    else:
                        value = ",".join(
                            f"'{v}'" for v in value_w.text().split(","))
                    value = f"({value})"
                else:
                    value = f"'{value_w.text()}'"
            else:
                value = str(
                    getattr(value_w, "value", value_w.text())
                    if hasattr(value_w, "value")
                    else ""
                )

            is_last = row == self.table.rowCount() - 1
            filter_str += (
                f" {left_bracket} {field} {compare.to_sql} {value} {right_bracket} "
            )
            if not is_last:
                filter_str += logic

        if left_count != right_count:
            QMessageBox.warning(self, "错误", "左括号数量和右括号数量不匹配，请检查")
            return None
        return filter_str


# ── 历史记录表格 ──────────────────────────────────────────


class HistoryTable(QWidget):
    HEADERS = [
        "replay_id",
        "game_board_state",
        "rtime",
        "left",
        "right",
        "double",
        "left_s",
        "right_s",
        "double_s",
        "level",
        "cl",
        "cl_s",
        "ce",
        "ce_s",
        "rce",
        "lce",
        "dce",
        "bbbv",
        "bbbv_solved",
        "bbbv_s",
        "flag",
        "path",
        "etime",
        "start_time",
        "end_time",
        "mode",
        "software",
        "player_identifier",
        "race_identifier",
        "uniqueness_identifier",
        "stnb",
        "corr",
        "thrp",
        "ioe",
        "is_official",
        "is_fair",
        "op",
        "isl",
        "pluck",
    ]

    def __init__(self, show_fields: set[str], db_path: Path, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        layout = QVBoxLayout(self)
        self.table = QTableView(self)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.showFields: set[str] = show_fields
        self.headers = self.HEADERS

        self.model = HistoryTableModel([], self.headers, self.showFields, self)
        self.table.setModel(self.model)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def load(self, data: list[HistoryData]):
        self.model.update_data(data)

    def refresh(self):
        parent_widget = self.parent()
        if hasattr(parent_widget, "load_data"):
            parent_widget.load_data()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(_translate("Form", "播放"), self.play_row)
        menu.addAction(_translate("Form", "导出"), self.export_row)
        menu.addAction(_translate("Form", "刷新"), self.refresh)
        submenu = QMenu(_translate("Form", "显示字段"), self)
        for field in self.headers:
            action = QAction(field, self)
            action.setCheckable(True)
            action.setChecked(field in self.showFields)
            action.triggered.connect(
                lambda checked, a=action: self._on_toggle_field(a))
            submenu.addAction(action)
        menu.addMenu(submenu)
        menu.exec_(self.table.mapToGlobal(pos))

    def _on_toggle_field(self, action: QAction):
        name = action.text()
        if action.isChecked():
            self.showFields.add(name)
        else:
            self.showFields.discard(name)
        self.model.update_show_fields(self.showFields)

    def _get_current_replay_id(self) -> int | None:
        row_idx = self.table.currentIndex().row()
        if row_idx < 0:
            return None
        visible = self.model._visible_headers
        if "replay_id" in visible:
            col = visible.index("replay_id")
            rid = self.model.data(self.model.index(row_idx, col), Qt.UserRole)
            return rid
        return getattr(self.model._data[row_idx], "replay_id", None)

    def _read_raw_data(self, replay_id: int) -> bytes | None:
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT raw_data FROM history WHERE replay_id = ?", (
                    replay_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def save_evf(self, evf_path: str):
        replay_id = self._get_current_replay_id()
        if replay_id is None:
            return
        raw_data = self._read_raw_data(replay_id)
        if raw_data is None:
            return
        with open(evf_path, "wb") as f:
            f.write(raw_data)

    def play_row(self):
        exec_dir = get_executable_dir()
        temp_filename = exec_dir / "tmp.evf"
        self.save_evf(str(temp_filename))

        exe = exec_dir / "metaminsweeper.exe"
        main_py = exec_dir / "main.py"

        if main_py.exists():
            subprocess.Popen(
                [sys.executable, str(main_py), str(temp_filename)])
        elif exe.exists():
            subprocess.Popen([str(exe), str(temp_filename)])
        else:
            QMessageBox.warning(
                self, "错误", "找不到主程序 (main.py 或 metaminsweeper.exe)"
            )

    def export_row(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            _translate("Form", "导出evf文件"),
            str(get_executable_dir()),
            "evf文件 (*.evf)",
        )
        if file_path:
            self.save_evf(file_path)


# ── 主界面容器 ────────────────────────────────────────────


class HistoryMainWidget(QWidget):
    """历史记录插件的主界面（作为插件的 widget 返回）"""

    def __init__(
        self,
        db_path: Path,
        config_path: Path,
        parent=None,
    ):
        super().__init__(parent)
        self._db_path = db_path
        self._config_path = config_path

        self.setWindowTitle(_translate("Form", "历史记录"))
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # 查询按钮
        btn_layout = QHBoxLayout()
        self.query_button = QPushButton(_translate("Form", "查询"))
        btn_layout.addWidget(self.query_button)
        btn_layout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # 筛选 + 表格
        self.filter_widget = FilterWidget(self)
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
        layout.addWidget(self.filter_widget)
        layout.addWidget(self.table)
        layout.addLayout(limit_layout)
        self.setLayout(layout)

        self._connect_signals()
        self.load_data()

    def _connect_signals(self):
        self.query_button.clicked.connect(self._on_query)
        self.previous_button.clicked.connect(
            lambda: self.page_spin.setValue(self.page_spin.value() - 1)
        )
        self.next_button.clicked.connect(
            lambda: self.page_spin.setValue(self.page_spin.value() + 1)
        )
        self.one_page_combo.currentTextChanged.connect(self.load_data)
        self.page_spin.valueChanged.connect(self.load_data)

    def _on_query(self):
        if self.page_spin.value() > 1:
            self.page_spin.setValue(1)
        else:
            self.load_data()

    def _get_limit_str(self):
        per_page = int(self.one_page_combo.currentText())
        offset = (self.page_spin.value() - 1) * per_page
        return f" LIMIT {per_page} OFFSET {offset}"

    def _get_show_fields(self) -> set[str]:
        if not self._config_path.exists():
            return set(HistoryData.fields())
        with open(self._config_path, "r") as f:
            return set(json.load(f))

    def load_data(self):
        if not self._db_path.exists():
            QMessageBox.warning(self, "错误", "历史记录数据库不存在")
            return

        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            filter_str = self.filter_widget.gen_filter_str()
            sql = "SELECT *, COUNT(*) OVER() AS total_count FROM history"
            if filter_str:
                sql += " WHERE " + filter_str
            elif filter_str is None:
                return
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

    def closeEvent(self, event: _QCloseEvent):
        """关闭时保存列显示配置"""
        with open(self._config_path, "w") as f:
            json.dump(list(self.table.showFields), f)
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════
# 插件主体
# ═══════════════════════════════════════════════════════════════════


class HistoryPlugin(BasePlugin):
    """
    历史记录插件

    - 后台：监听 VideoSaveEvent，写入 SQLite
    - 界面：提供筛选、分页、播放/导出功能
    - 服务：提供 HistoryService 接口供其他插件查询历史记录
    """
    video_save_over = pyqtSignal()

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="history",
            description="游戏历史记录（SQLite 持久化）",
            author="ljzloser",
            version="1.0.0",
            icon=make_plugin_icon("#7b1fa2", "\N{SCROLL}"),
            window_mode=WindowMode.TAB,
        )

    def __init__(self, info):
        super().__init__(info)

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._on_video_save)

    def _create_widget(self) -> QWidget:
        db_path = self.data_dir / "history.db"
        config_path = self.data_dir / "history_show_fields.json"
        self._widget = HistoryMainWidget(db_path, config_path)
        self.video_save_over.connect(self._widget.query_button.click)
        return self._widget

    def on_initialized(self) -> None:
        self._init_db()
        self.register_service(self, protocol=HistoryService)
        self.logger.info("历史记录插件已初始化，HistoryService 已注册")

    # ── 数据库 ──────────────────────────────────────────────

    def _init_db(self) -> None:
        db_path = self.data_dir / "history.db"
        if db_path.exists():
            return
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE history (
                replay_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                game_board_state  INTEGER,
                rtime            REAL,
                left             INTEGER,
                right            INTEGER,
                double           INTEGER,
                left_s           REAL,
                right_s          REAL,
                double_s         REAL,
                level            INTEGER,
                cl               INTEGER,
                cl_s             REAL,
                ce               REAL,
                ce_s             REAL,
                rce              INTEGER,
                lce              INTEGER,
                dce              INTEGER,
                bbbv             INTEGER,
                bbbv_solved      INTEGER,
                bbbv_s           REAL,
                flag             INTEGER,
                path             REAL,
                etime            INTEGER,
                start_time       INTEGER,
                end_time         INTEGER,
                mode             INTEGER,
                software         TEXT,
                player_identifier   TEXT,
                race_identifier     TEXT,
                uniqueness_identifier TEXT,
                stnb             REAL,
                corr             REAL,
                thrp             REAL,
                ioe              REAL,
                is_official      INTEGER,
                is_fair          INTEGER,
                op               INTEGER,
                isl              INTEGER,
                pluck            REAL,
                raw_data         BLOB
            )
        """
        )
        conn.commit()
        conn.close()
        self.logger.info(f"Database created: {db_path}")

    # ── 事件处理 ──────────────────────────────────────────

    def _on_video_save(self, event: VideoSaveEvent) -> None:
        data: dict[str, Any] = msgspec.structs.asdict(event)
        raw_b64 = data.get("raw_data", "")
        try:
            data["raw_data"] = base64.b64decode(raw_b64) if raw_b64 else None
        except Exception as e:
            self.logger.warning(f"base64 decode failed: {e}")
            data["raw_data"] = None
        del data["timestamp"]
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())

        db_path = self.data_dir / "history.db"
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO history ({columns}) VALUES ({placeholders})",
                data,
            )
            conn.commit()
            self.logger.info(
                f"Saved: board_state={event.game_board_state} time={event.rtime:.1f}s"
            )
        finally:
            conn.close()
        self.video_save_over.emit()

    # ═══════════════════════════════════════════════════════════════════
    # HistoryService 接口实现
    # ═══════════════════════════════════════════════════════════════════

    def query_records(
        self,
        limit: int = 100,
        offset: int = 0,
        level: int | None = None,
    ) -> list[GameRecord]:
        """查询游戏记录"""
        db_path = self.data_dir / "history.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            if level is not None:
                cursor.execute(
                    """
                    SELECT * FROM history
                    WHERE level = ?
                    ORDER BY replay_id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (level, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM history
                    ORDER BY replay_id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
            rows = cursor.fetchall()
            return [GameRecord(
                replay_id=row["replay_id"],
                rtime=row["rtime"],
                level=row["level"],
                bbbv=row["bbbv"],
                bbbv_solved=row["bbbv_solved"],
                left=row["left"],
                right=row["right"],
                double=row["double"],
                cl=row["cl"],
                ce=row["ce"],
                flag=row["flag"],
                game_board_state=row["game_board_state"],
                mode=row["mode"],
                software=row["software"] or "",
                start_time=row["start_time"],
                end_time=row["end_time"],
            ) for row in rows]
        finally:
            conn.close()

    def get_record_count(self, level: int | None = None) -> int:
        """获取记录总数"""
        db_path = self.data_dir / "history.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            if level is not None:
                cursor.execute(
                    "SELECT COUNT(*) FROM history WHERE level = ?", (level,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM history")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def get_last_record(self) -> GameRecord | None:
        """获取最近一条记录"""
        records = self.query_records(limit=1)
        return records[0] if records else None

    def delete_record(self, record_id: int) -> bool:
        """删除指定记录"""
        db_path = self.data_dir / "history.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM history WHERE replay_id = ?", (record_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                self.logger.info(f"Deleted record: {record_id}")
            return deleted
        finally:
            conn.close()

    def _on_config_changed(self, name: str, value: Any) -> None:
        return super()._on_config_changed(name, value)
