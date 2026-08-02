"""
历史记录表格
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .db import db_connection

from PyQt5.QtCore import Qt, QCoreApplication, pyqtSignal
from PyQt5.QtGui import QCloseEvent as _QCloseEvent
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QMenu,
    QTableView,
    QAbstractItemView,
    QApplication,
    QMessageBox,
    QFileDialog,
    QHeaderView,
)

from shared_types.enums import BaseDiaPlayEnum

from plugin_manager.app_paths import get_executable_dir

from .models import HistoryData
from .table_model import HistoryTableModel
from .compression import decompress
from .computed_column import ComputedColumn

_translate = QCoreApplication.translate


class HistoryTable(QWidget):
    """历史记录表格"""

    # 信号：列显示配置变化 (show_fields_json)
    show_fields_changed = pyqtSignal(str)

    NF_COLUMN_WIDTH = 50

    # 物理字段（固定）
    PHYSICAL_HEADERS = [
        "replay_id",
        "game_state",
        "nf",
        "row",
        "column",
        "mine_num",
        "rtime",
        "left",
        "right",
        "double",
        "level",
        "cl",
        "ce",
        "rce",
        "lce",
        "dce",
        "bbbv",
        "bbbv_solved",
        "zini",
        "flag",
        "path",
        "start_time",
        "end_time",
        "mode",
        "software",
        "player_identifier",
        "race_identifier",
        "unique_identifier",
        "is_official",
        "is_fair",
        "op",
        "isl",
        "pluck",
        "board",
    ]

    HEADERS = PHYSICAL_HEADERS  # 向后兼容

    @classmethod
    def all_headers(cls, computed_columns: list[ComputedColumn] | None = None) -> list[str]:
        """获取完整列头列表（物理字段 + 计算列）"""
        headers = list(cls.PHYSICAL_HEADERS)
        if computed_columns:
            for col in computed_columns:
                if col.name not in headers:
                    headers.append(col.name)
        return headers

    def __init__(self, show_fields: list[str], db_path: Path,
                 computed_columns: list[ComputedColumn] | None = None, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._computed_columns = computed_columns or []
        layout = QVBoxLayout(self)
        self.table = QTableView(self)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.showFields: list[str] = show_fields
        self.headers = self.all_headers(self._computed_columns)

        self.model = HistoryTableModel([], self.headers, self.showFields, self)
        self.table.setModel(self.model)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.model.modelReset.connect(self._apply_column_widths)
        self._apply_column_widths()

    def load(self, data: list[HistoryData]):
        self.model.update_data(data)

    def set_computed_columns(self, columns: list[ComputedColumn]):
        """更新计算列，重建 headers 和 model"""
        self._computed_columns = columns
        self.headers = self.all_headers(columns)
        self.model = HistoryTableModel([], self.headers, self.showFields, self)
        self.table.setModel(self.model)
        self.model.modelReset.connect(self._apply_column_widths)

    def _apply_column_widths(self):
        visible_headers = getattr(self.model, "_visible_headers", [])

        if "board" in visible_headers:
            col = visible_headers.index("board")
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
            width = self.table.fontMetrics().width('中' * 30 + '  ')
            self.table.setColumnWidth(col, width)

        if "nf" in visible_headers:
            col = visible_headers.index("nf")
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, self.NF_COLUMN_WIDTH)

    def refresh(self):
        parent_widget = self.parent()
        if hasattr(parent_widget, "load_data"):
            parent_widget.load_data()  # type: ignore

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(_translate("Form", "播放"), self.play_row)
        menu.addAction(_translate("Form", "导出录像"), self.export_row)
        menu.addAction(_translate("Form", "复制JSON"), self.export_row_json)
        menu.addAction(_translate("Form", "刷新"), self.refresh)
        menu.exec_(self.table.mapToGlobal(pos))

    def _get_current_replay_id(self) -> int | None:
        row_idx = self.table.currentIndex().row()
        if row_idx < 0:
            return None
        visible = self.model._visible_headers
        if "replay_id" in visible:
            col = visible.index("replay_id")
            rid = self.model.data(self.model.index(row_idx, col), Qt.UserRole)
            return rid  # type: ignore
        return getattr(self.model._data[row_idx], "replay_id", None)

    def _read_raw_data(self, replay_id: int) -> bytes | None:
        with db_connection(self._db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT raw_data FROM history WHERE replay_id = ?", (
                    replay_id,)
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                return decompress(row[0])
            return None

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

        exe = exec_dir / "metasweeper.exe"
        main_py = exec_dir / "src" / "main.py"

        if main_py.exists():
            subprocess.Popen(
                [sys.executable, str(main_py), str(temp_filename)])
        elif exe.exists():
            subprocess.Popen([str(exe), str(temp_filename)])
        else:
            QMessageBox.warning(
                self, _translate("Form", "错误"), _translate(
                    "Form", "找不到主程序 (main.py 或 metaminesweeper.exe)")
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

    def export_row_json(self):
        row_idx = self.table.currentIndex().row()
        if row_idx < 0:
            return
        result = {}
        headers = self.table.horizontalHeader().visibleSectionNames()  # type: ignore
        for idx, field in enumerate(headers):
            value = self.model.data(
                self.model.index(row_idx, idx), Qt.DisplayRole)
            result[field] = value

        clipboard = QApplication.clipboard()
        clipboard.setText(self._compact_json(result))

    @staticmethod
    def _compact_json(obj, indent=0):
        pad = "  "
        if isinstance(obj, dict):
            if not obj:
                return "{}"
            items = []
            for k, v in obj.items():
                val = HistoryTable._compact_json(v, indent + 1)
                items.append(f'{pad * (indent + 1)}"{k}": {val}')
            return "{\n" + ",\n".join(items) + "\n" + pad * indent + "}"
        if isinstance(obj, list) and obj and isinstance(obj[0], list):
            inner = ", ".join(json.dumps(row, ensure_ascii=False)
                              for row in obj)
            return "[\n" + pad * (indent + 1) + inner + "\n" + pad * indent + "]"
        if isinstance(obj, list):
            if not obj:
                return "[]"
            inner = ",\n".join(
                pad * (indent + 1) +
                HistoryTable._compact_json(item, indent + 1)
                for item in obj
            )
            return "[\n" + inner + "\n" + pad * indent + "]"
        if isinstance(obj, bool):
            return "true" if obj else "false"
        if obj is None:
            return "null"
        if isinstance(obj, (int, float)):
            return json.dumps(obj)
        return json.dumps(obj, ensure_ascii=False)
