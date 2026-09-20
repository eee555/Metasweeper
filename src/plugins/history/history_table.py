"""
历史记录表格
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from .db import db_connection, delete_record_tx

from PyQt5.QtCore import (
    QEvent, QModelIndex, QPoint, Qt, QCoreApplication, pyqtSignal, QTimer,
)
from PyQt5.QtGui import QCloseEvent as _QCloseEvent
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QMenu,
    QLabel,
    QDialog,
    QDialogButtonBox,
    QTableView,
    QAbstractItemView,
    QApplication,
    QMessageBox,
    QFileDialog,
    QHeaderView,
)

from shared_types.enums import BaseDiaPlayEnum
from shared_types.widgets import ConfirmDialog

from plugin_manager.app_paths import get_executable_dir

from .board_preview import BoardPreviewPopup, parse_board
from .models import HistoryData
from .table_model import HistoryTableModel
from .compression import decompress
from .computed_column import ComputedColumn

_translate = QCoreApplication.translate


class _DeleteConfirmDialog(ConfirmDialog):
    """删除记录确认对话框（基于共享 ConfirmDialog 基类）"""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title=_translate("Form", "删除确认"),
            buttons=QDialogButtonBox.Yes | QDialogButtonBox.No,
        )
        self.resize(320, 120)

    def _create_content(self):
        layout = QVBoxLayout()
        label = QLabel(
            _translate("Form", "确定要删除选中的这条历史记录吗？\n该操作不可恢复。"))
        label.setWordWrap(True)
        layout.addWidget(label)
        return layout

    def _on_accepted(self):
        # 确认逻辑由调用方在 exec_() 返回后处理
        pass


class HistoryTable(QWidget):
    """历史记录表格"""

    # 信号：列显示配置变化 (show_fields_json)
    show_fields_changed = pyqtSignal(str)

    NF_COLUMN_WIDTH = 50

    # 悬浮到 board 列多久后弹出局面预览（毫秒），0 表示立即弹出
    PREVIEW_DELAY_MS = 320

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

        # ── board 列悬浮预览 ──
        self._preview: BoardPreviewPopup | None = None
        self._preview_enabled = True      # 由插件配置「局面预览」控制
        self._preview_delay_ms = self.PREVIEW_DELAY_MS
        self._hover_key: tuple[int, int, str] | None = None
        self._pending_pos: QPoint | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._show_preview)
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().installEventFilter(self)
        self.table.verticalScrollBar().valueChanged.connect(self._hide_preview)
        self.table.horizontalScrollBar().valueChanged.connect(self._hide_preview)

    def load(self, data: list[HistoryData]):
        self._hide_preview()
        self.model.update_data(data)

    def set_computed_columns(self, columns: list[ComputedColumn]):
        """更新计算列，重建 headers 和 model"""
        self._hide_preview()
        self._computed_columns = columns
        self.headers = self.all_headers(columns)
        self.model = HistoryTableModel([], self.headers, self.showFields, self)
        self.table.setModel(self.model)
        self.model.modelReset.connect(self._apply_column_widths)
        self._apply_column_widths()

    def _apply_column_widths(self):
        """设置特殊列宽（board 定宽、nf 定宽），其余列按内容自适应

        注意：QHeaderView 的列宽与拉伸模式是**按列下标**记录的，列集合或顺序
        一变（列设置对话框增删/排序、恢复保存的列配置），上一次设置在旧下标上的
        Fixed 宽度就会残留在别的新列上，表现为某一列莫名特别宽
        （row / nf / flag / bbbvs 都踩过这个坑）。
        所以每次都要先把所有列恢复成「按内容自适应」，再设置需要定宽的列。
        """
        header = self.table.horizontalHeader()
        visible_headers = getattr(self.model, "_visible_headers", [])

        # 清掉上一次残留的定宽（含拉伸模式），避免宽度粘到别的列上
        header.setSectionResizeMode(QHeaderView.ResizeToContents)

        if "board" in visible_headers:
            col = visible_headers.index("board")
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            width = self.table.fontMetrics().width('中' * 30 + '  ')
            self.table.setColumnWidth(col, width)

        if "nf" in visible_headers:
            col = visible_headers.index("nf")
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            self.table.setColumnWidth(col, self.NF_COLUMN_WIDTH)

    # ── board 列悬浮预览 ──────────────────────────────────────
    def eventFilter(self, obj, event):
        """监听表格视口：鼠标移到 board 列时弹出局面预览"""
        if obj is self.table.viewport():
            etype = event.type()
            if etype == QEvent.MouseMove:
                self._handle_hover(
                    self.table.indexAt(event.pos()), event.globalPos())
            elif etype in (QEvent.Leave, QEvent.MouseButtonPress,
                           QEvent.Wheel):
                self._hide_preview()
        return super().eventFilter(obj, event)

    def hideEvent(self, event):
        self._hide_preview()
        super().hideEvent(event)

    def set_board_preview_enabled(self, enabled: bool) -> None:
        """开关 board 列悬浮局面预览（对应插件设置里的「局面预览」）"""
        self._preview_enabled = bool(enabled)
        if not self._preview_enabled:
            self._hide_preview()

    def is_board_preview_enabled(self) -> bool:
        return self._preview_enabled

    def _handle_hover(self, index: QModelIndex, global_pos: QPoint) -> None:
        """悬浮单元格变化时才重新计时，避免鼠标在单元格内移动时反复解析局面"""
        key = self._preview_key(index) if self._preview_enabled else None
        if key == self._hover_key:
            return
        self._hide_preview()
        if key is None:
            return
        self._hover_key = key
        self._pending_pos = global_pos
        if self._preview_delay_ms <= 0:
            self._show_preview()
        else:
            self._preview_timer.start(self._preview_delay_ms)

    def _preview_key(self, index: QModelIndex) -> tuple[int, int, str] | None:
        """可预览单元格的标识 (row, col, board 文本)；非 board 列或无效单元格返回 None"""
        if not index.isValid():
            return None
        if self.model.headerData(index.column(), Qt.Horizontal) != "board":
            return None
        text = self.model.data(index, Qt.DisplayRole)
        return (index.row(), index.column(), text if isinstance(text, str) else "")

    def _show_preview(self) -> None:
        """解析局面并弹出预览（计时结束或延迟为 0 时调用）"""
        if self._hover_key is None:
            return
        board = parse_board(self._hover_key[2])
        if not board:
            return
        if self._preview is None:
            self._preview = BoardPreviewPopup(self)
        pos = self._pending_pos
        if pos is None:
            pos = self.table.viewport().mapToGlobal(
                self.table.viewport().rect().center())
        self._preview.show_board(board, pos)

    def _hide_preview(self) -> None:
        """隐藏预览并清空悬浮状态（离开表格、滚动、点击、刷新数据时调用）"""
        self._preview_timer.stop()
        self._hover_key = None
        self._pending_pos = None
        if self._preview is not None and self._preview.isVisible():
            self._preview.hide()

    def hover_preview_board(self) -> list[list[int]] | None:
        """当前正在预览的局面；未显示时返回 None"""
        if self._preview is not None and self._preview.isVisible():
            return self._preview.board()
        return None

    def refresh(self):
        parent_widget = self.parent()
        if hasattr(parent_widget, "load_data"):
            parent_widget.load_data()  # type: ignore

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(_translate("Form", "播放"), self.play_row)
        menu.addAction(_translate("Form", "导出录像"), self.export_row)
        menu.addAction(_translate("Form", "复制JSON"), self.export_row_json)
        menu.addAction(_translate("Form", "删除"), self.delete_row)
        menu.addAction(_translate("Form", "刷新"), self.refresh)
        menu.exec_(self.table.mapToGlobal(pos))

    def delete_row(self):
        """删除当前选中的记录（确认后执行，删除后刷新）"""
        replay_id = self._get_current_replay_id()
        if replay_id is None:
            return
        dialog = _DeleteConfirmDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        try:
            with db_connection(self._db_path) as conn:
                delete_record_tx(conn, replay_id)
                conn.commit()
        except sqlite3.Error as e:
            QMessageBox.warning(
                self, _translate("Form", "错误"),
                _translate("Form", "删除记录失败: %1").replace("%1", str(e)))
            return
        self.refresh()

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
        """读取录像原始数据（兼容三种库形态）

        a) 新库 / 已迁移库：数据在 replay_data 子表
        b) 中间态旧库：优先 replay_data，回退 history.raw_data
        c) 全压缩旧库：raw_data 在 history.raw_data 且 compressed=1
        """
        with db_connection(self._db_path) as conn:
            cursor = conn.cursor()
            # 优先读 replay_data 子表
            try:
                cursor.execute(
                    "SELECT raw_data, compressed FROM replay_data "
                    "WHERE replay_id = ?",
                    (replay_id,),
                )
                row = cursor.fetchone()
            except sqlite3.OperationalError:
                row = None  # 子表不存在（极旧数据库）
            if row and row[0] is not None:
                # 子表内 compressed 列恒有值（0/1），按列判断
                return decompress(row[0], compressed=bool(row[1]))
            # 回退读 history.raw_data（中间态旧库尚未迁移的数据）
            try:
                try:
                    cursor.execute(
                        "SELECT raw_data, compressed FROM history "
                        "WHERE replay_id = ?",
                        (replay_id,),
                    )
                    row = cursor.fetchone()
                    flag = bool(row[1]) if row and row[1] is not None else None
                except sqlite3.OperationalError:
                    # 极旧数据库没有 compressed 列
                    cursor.execute(
                        "SELECT raw_data FROM history WHERE replay_id = ?",
                        (replay_id,),
                    )
                    row = cursor.fetchone()
                    flag = None
            except sqlite3.OperationalError:
                return None  # history 表结构异常（理论上不可达），放弃读取
            if row and row[0] is not None:
                return decompress(row[0], compressed=flag)
            return None

    def save_evf(self, evf_path: str):
        replay_id = self._get_current_replay_id()
        if replay_id is None:
            return False
        raw_data = self._read_raw_data(replay_id)
        if raw_data is None:
            return False
        with open(evf_path, "wb") as f:
            f.write(raw_data)
        
        return True

    def play_row(self):
        exec_dir = get_executable_dir()
        exe = exec_dir / "metasweeper.exe"
        main_py = exec_dir / "src" / "main.py"

        # 主程序不存在时直接提示，避免白写临时文件
        # （修正旧文案：误写为 metaminesweeper.exe，实际找 metasweeper.exe）
        if not main_py.exists() and not exe.exists():
            QMessageBox.warning(
                self, _translate("Form", "错误"), _translate(
                    "Form", "找不到主程序 (main.py 或 metasweeper.exe)")
            )
            return

        # 临时 evf 写到系统临时目录（exe 目录在 Program Files 下无写权限）
        with tempfile.NamedTemporaryFile(
            prefix="metasweeper_", suffix=".evf", delete=False
        ) as tmp:
            temp_filename = Path(tmp.name)
        if not self.save_evf(str(temp_filename)):
            QMessageBox.warning(
                self, _translate("Form", "错误"), _translate(
                    "Form", "保存 evf 文件失败")
            )
            return
        if main_py.exists():
            subprocess.Popen(
                [sys.executable, str(main_py), str(temp_filename)])
        else:
            subprocess.Popen([str(exe), str(temp_filename)])
        # 回放进程启动后延迟清理临时文件（留足进程读取文件的时间）
        def _cleanup():
            try:
                temp_filename.unlink(missing_ok=True)
            except OSError:
                pass  # 文件仍被回放进程占用，留待系统清理临时目录

        QTimer.singleShot(10_000, _cleanup)

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
        headers = self.model._visible_headers
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
