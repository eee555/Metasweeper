"""
历史记录表格
"""

from __future__ import annotations

from ast import List
import sqlite3
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QCoreApplication, pyqtSignal
from PyQt5.QtGui import QCloseEvent as _QCloseEvent
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QMenu,
    QTableView,
    QMessageBox,
    QFileDialog,
    QHeaderView,
)

from plugin_manager.app_paths import get_executable_dir

from .models import HistoryData
from .table_model import HistoryTableModel

_translate = QCoreApplication.translate


class HistoryTable(QWidget):
    """历史记录表格"""

    # 信号：列显示配置变化 (show_fields_json)
    show_fields_changed = pyqtSignal(str)

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

    def __init__(self, show_fields: list[str], db_path: Path, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        layout = QVBoxLayout(self)
        self.table = QTableView(self)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.showFields: list[str] = show_fields
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
            parent_widget.load_data()  # type: ignore

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(_translate("Form", "播放"), self.play_row)
        menu.addAction(_translate("Form", "导出"), self.export_row)
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

        exe = exec_dir / "metaminesweeper.exe"
        main_py = exec_dir / "src" / "main.py"

        if main_py.exists():
            subprocess.Popen(
                [sys.executable, str(main_py), str(temp_filename)])
        elif exe.exists():
            subprocess.Popen([str(exe), str(temp_filename)])
        else:
            QMessageBox.warning(
                self, "错误", "找不到主程序 (main.py 或 metaminesweeper.exe)"
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
