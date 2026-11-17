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

from PySide6.QtCore import QCoreApplication, QEvent, QSignalBlocker, Signal
from PySide6.QtGui import QCloseEvent as _QCloseEvent
from PySide6.QtWidgets import (
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
    QProgressBar,
)

from .columns_dialog import ColumnsDialog
from .filter_dialog import FilterDialog
from .history_table import HistoryTable
from .models import HistoryData, CompareSymbol, LogicSymbol, SortOrder
from .query_builder import build_where, build_order_by
from .table_views import SortModel
from .sort_dialog import SortDialog
from .table_views import FilterModel
from .computed_column import ComputedColumn
from utils.plugin_i18n import PluginTranslate
from utils.translated_widgets import TranslatedLabel as QLabel

_translate = PluginTranslate("HistoryPlugin")

# history 表物理字段集合（SELECT 拼接时非物理字段需双引号包裹）
_PHYSICAL_FIELDS = frozenset(HistoryData.fields())

# 旧数据迁移阶段：稳定 token（插件线程/后端使用）→ 界面本地化文案。
# token 不随语言变化，避免后端依赖某种语言的字符串。
_MIGRATION_PHASE_TOKENS = ("replays", "verify", "boards", "cleanup")


class HistoryMainWidget(QWidget):
    """历史记录插件的主界面（作为插件的 widget 返回）"""

    # 信号：排序和过滤状态变化 (filter_json, sort_json)
    filter_sort_state_changed = Signal(str, str)
    # 信号：列显示配置变化 (show_fields_json)
    show_fields_changed = Signal(str)
    # 信号：计算列变化 (columns_json)
    computed_columns_changed = Signal(list)
    # 信号：自定义函数脚本变化 (script)
    custom_functions_changed = Signal(str)
    # 信号：记录删除后请求后台回收分块内的墓碑槽位
    compaction_requested = Signal()

    def __init__(
        self,
        db_path: Path,
        config_path: Path,
        float_decimals: int = 2,
        page_size: str = "50",
        board_preview: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._db_path = db_path
        self._config_path = config_path
        self._float_decimals = float_decimals
        self._board_preview_enabled = bool(board_preview)
        self._computed_columns: list[ComputedColumn] = []
        self._custom_functions: str = ""

        # 存储过滤和排序条件数据（每次对话框确认后更新）
        self._filter_rows: list[dict] = []
        self._sort_rows: list[dict] = []

        self.setWindowTitle(_translate("HistoryPlugin", "历史记录"))
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # 查询按钮 + 过滤/排序按钮
        btn_layout = QHBoxLayout()
        self.query_button = QPushButton(_translate("HistoryPlugin", "查询"))
        self.filter_button = QPushButton(_translate("HistoryPlugin", "过滤"))
        self.sort_button = QPushButton(_translate("HistoryPlugin", "排序"))
        self.columns_button = QPushButton(_translate("HistoryPlugin", "列设置"))
        self.computed_columns_button = QPushButton(_translate("HistoryPlugin", "计算列"))
        btn_layout.addWidget(self.query_button)
        btn_layout.addWidget(self.filter_button)
        btn_layout.addWidget(self.sort_button)
        btn_layout.addWidget(self.columns_button)
        btn_layout.addWidget(self.computed_columns_button)
        btn_layout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )

        # 当前过滤/排序条件显示
        self.filter_label = QLabel("")
        self.filter_label.setWordWrap(True)
        self.sort_label = QLabel("")
        self.sort_label.setWordWrap(True)

        # 表格
        self.table = HistoryTable(
            self._get_show_fields(), db_path, self._computed_columns, self)
        self.table.set_board_preview_enabled(self._board_preview_enabled)

        # 分页
        limit_layout = QHBoxLayout()
        self.previous_button = QPushButton(_translate("HistoryPlugin", "上一页"))
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setValue(1)
        self.next_button = QPushButton(_translate("HistoryPlugin", "下一页"))
        self.one_page_combo = QComboBox()
        self.one_page_combo.addItems(
            ["10", "20", "50", "100", "200", "500", "1000"])
        # 设置默认每页条数
        idx = self.one_page_combo.findText(page_size)
        if idx >= 0:
            self.one_page_combo.setCurrentIndex(idx)

        self.limit_label = QLabel("")
        limit_layout.addItem(
            QSpacerItem(10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )
        limit_layout.addWidget(self.limit_label)
        limit_layout.addWidget(self.previous_button)
        limit_layout.addWidget(self.page_spin)
        limit_layout.addWidget(self.next_button)
        limit_layout.addWidget(self.one_page_combo)

        # 旧数据迁移进度条：默认隐藏，仅在后端确认存在旧数据迁移时显示。
        # 通过 set_migration_progress() 由 GUI 线程更新（父插件经 run_on_widget 投递）。
        self.migration_progress_row = QWidget(self)
        migration_row = QHBoxLayout(self.migration_progress_row)
        migration_row.setContentsMargins(0, 0, 0, 0)
        self.migration_label = QLabel("", self.migration_progress_row)
        self.migration_label.setWordWrap(False)
        self.migration_progress = QProgressBar(self.migration_progress_row)
        self.migration_progress.setObjectName("migrationProgress")
        self.migration_progress.setTextVisible(True)
        self.migration_progress.setRange(0, 1)
        self.migration_progress.setValue(0)
        self.migration_progress.setFormat("")
        self.migration_progress.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        migration_row.addWidget(self.migration_label)
        migration_row.addWidget(self.migration_progress, 1)
        self.migration_progress.setVisible(False)
        self.migration_progress_row.setVisible(False)
        self._migration_phase = ""
        self._migration_active = False

        layout.addLayout(btn_layout)
        layout.addWidget(self.migration_progress_row)
        layout.addWidget(self.filter_label)
        layout.addWidget(self.sort_label)
        layout.addWidget(self.table)
        layout.addLayout(limit_layout)
        self.setLayout(layout)

        self._connect_signals()
        # 构造阶段只装配控件；计算列、过滤/排序、显示列恢复后由插件触发首次查询，
        # 避免启动期对大表重复执行分页查询。
        self._startup_query_pending = True
        # 最近一次查询的总行/总页数，语言切换时用于重建分页标签
        self._total_rows: int | None = None
        self._max_pages: int | None = None
        self._retranslate_ready = True

    def changeEvent(self, event: QEvent) -> None:
        # 语言切换事件由 Qt 投递；构造未完成时控件尚未装配，跳过重译。
        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange and getattr(
                self, "_retranslate_ready", False):
            self.retranslateUi()

    def retranslateUi(self):
        self.setWindowTitle(_translate("HistoryPlugin", "历史记录"))
        self.query_button.setText(_translate("HistoryPlugin", "查询"))
        self.filter_button.setText(_translate("HistoryPlugin", "过滤"))
        self.sort_button.setText(_translate("HistoryPlugin", "排序"))
        self.columns_button.setText(_translate("HistoryPlugin", "列设置"))
        self.computed_columns_button.setText(_translate("HistoryPlugin", "计算列"))
        self.previous_button.setText(_translate("HistoryPlugin", "上一页"))
        self.next_button.setText(_translate("HistoryPlugin", "下一页"))
        # 分页/过滤/排序标签由运行期数据拼装，需按当前语言重新生成
        self._render_limit_label()
        self._render_filter_sort_labels()
        # 迁移进行中：按缓存 token 重新生成文案，保留进度与总量
        if self._migration_active:
            self.migration_label.setText(self._migration_phase_text())
            self.migration_progress.setFormat(self._migration_progress_format())

    def _render_limit_label(self) -> None:
        """按缓存的总行/总页重建分页标签；尚未查询时保持空白。"""
        total = self._total_rows
        max_page = self._max_pages
        if total is None or max_page is None:
            return
        self.limit_label.setText(
            _translate("HistoryPlugin", "共%1行,%2页")
            .replace("%1", str(total)).replace("%2", str(max_page)))

    def _migration_phase_text(self) -> str:
        """把稳定 phase token 映射为当前语言下的文案（重译时重新调用）。"""
        if self._migration_phase == "replays":
            return _translate("HistoryPlugin", "迁移旧录像数据")
        if self._migration_phase == "verify":
            return _translate("HistoryPlugin", "校验迁移数据")
        if self._migration_phase == "boards":
            return _translate("HistoryPlugin", "压缩雷图数据")
        if self._migration_phase == "cleanup":
            return _translate("HistoryPlugin", "清理低完成率录像")
        return _translate("HistoryPlugin", "正在迁移旧数据")

    @staticmethod
    def _coerce_count(value: object) -> int:
        """把后端传入的计数转成非负整数，非法值当作 0。"""
        try:
            return max(0, int(value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0

    def _migration_progress_format(self) -> str:
        """有界进度显示百分比；不确定进度不显示文本。"""
        if self.migration_progress.maximum() <= 0:
            return ""
        # Qt 进度条占位符，不是用户可见文案，无需翻译
        return "%p%"

    def set_migration_progress(
        self,
        active: bool,
        done: int = 0,
        total: int = 0,
        phase: str = "",
    ) -> None:
        """更新旧数据迁移进度条（仅 GUI 线程调用）。

        父插件应在插件线程中通过 ``run_on_widget`` 投递到 GUI 线程。

        Args:
            active: 是否正在迁移。为 ``False`` 时隐藏进度条（成功、失败、
                取消都走这个分支），不保留任何进度状态。
            done: 已完成数量；会被夹取到 ``[0, total]``。
            total: 总数量。``<= 0`` 表示不确定进度（indeterminate），
                ``> 0`` 表示有界进度。
            phase: 稳定阶段 token，目前支持 ``"replays"``、``"verify"``、
                ``"boards"``；未知 token 使用兜底文案。
        """
        if not active:
            self._migration_phase = ""
            self._migration_active = False
            self.migration_progress.setRange(0, 1)
            self.migration_progress.setValue(0)
            self.migration_progress.setFormat("")
            self.migration_label.setText("")
            self.migration_progress.setVisible(False)
            self.migration_progress_row.setVisible(False)
            return

        # 夹取输入，容忍后端传入负值、字符串或超出总量的 done
        total = self._coerce_count(total)
        done = self._coerce_count(done)
        self._migration_phase = phase if phase in _MIGRATION_PHASE_TOKENS else ""
        self._migration_active = True
        self.migration_label.setText(self._migration_phase_text())

        if total > 0:
            done = min(done, total)
            self.migration_progress.setRange(0, total)
            self.migration_progress.setValue(done)
        else:
            # Qt 的 0/0 区间即不确定进度（繁忙指示）
            self.migration_progress.setRange(0, 0)
            self.migration_progress.setValue(0)
        self.migration_progress.setFormat(self._migration_progress_format())
        self.migration_progress_row.setVisible(True)
        self.migration_progress.setVisible(True)

    def set_filter_sort_state(self, filter_json: str, sort_json: str) -> None:
        """设置排序和过滤状态（由插件调用）"""
        try:
            filter_rows = json.loads(filter_json)
            if filter_rows:
                self._filter_rows = self._normalize_filter_rows(filter_rows)
        except (json.JSONDecodeError, TypeError):
            pass

        try:
            sort_rows = json.loads(sort_json)
            if sort_rows:
                self._sort_rows = self._normalize_sort_rows(sort_rows)
        except (json.JSONDecodeError, TypeError):
            pass

        # 由插件在所有列配置恢复完成后统一调用 run_startup_query()；
        # 这里不查询，避免构造阶段和恢复配置阶段重复扫描历史表。
        self._startup_query_pending = True

    @staticmethod
    def _normalize_filter_rows(rows: list[dict]) -> list[dict]:
        """把旧版按译文持久化的比较符/逻辑符迁移到稳定编号。

        旧配置可能保存任意内置语言的译文（如英文 "equals"），
        甚至在当前语言切换后才读取；无法识别的值保持原样，
        交由查询构建器给出带上下文的错误提示。
        """
        normalized: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            row = dict(row)
            compare = row.get("compare")
            if compare:
                stable = CompareSymbol.to_stable(compare)
                if stable is not None:
                    row["compare"] = stable
            logic = row.get("logic")
            if logic:
                stable = LogicSymbol.to_stable(logic)
                if stable is not None:
                    row["logic"] = stable
            normalized.append(row)
        return normalized

    @staticmethod
    def _normalize_sort_rows(rows: list[dict]) -> list[dict]:
        """把旧版按译文持久化的排序方向迁移到稳定编号。"""
        normalized: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            row = dict(row)
            order = row.get("order")
            if order:
                stable = SortOrder.to_stable(order)
                if stable is not None:
                    row["order"] = stable
            normalized.append(row)
        return normalized

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
        self.table.compaction_requested.connect(self.compaction_requested)

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
        if filter_dialog.exec():
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
        if sort_dialog.exec():
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
        if columns_dialog.exec():
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

    def run_startup_query(self) -> None:
        """插件恢复全部配置后执行首次查询；没有恢复流程时也能手动触发。"""
        if getattr(self, "_startup_query_pending", False):
            self._startup_query_pending = False
            self._on_query()

    def load_data(self):
        if not self._db_path.exists():
            with QSignalBlocker(self.page_spin):
                self.page_spin.setMaximum(1)
            self._total_rows, self._max_pages = 0, 0
            self.limit_label.setText(
                _translate("HistoryPlugin", "共%1行,%2页").replace("%1", "0").replace("%2", "0"))
            self.table.load([])
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
                # replay_id 用于播放、导出和删除，即使用户隐藏该列也必须保留在查询结果中。
                query_fields = list(show_fields)
                if "replay_id" not in query_fields:
                    query_fields.insert(0, "replay_id")
                if self._computed_columns:
                    computed_names = [
                        col.name for col in self._computed_columns]
                    for name in computed_names:
                        if name not in query_fields:
                            query_fields.append(name)
                # board 是每格一个字符的 ASCII 字符串，直接显示和过滤。
                select_fields = ','.join(
                    f'"{f}"' if f not in _PHYSICAL_FIELDS else f
                    for f in query_fields
                )
                subquery = ComputedColumn.build_subquery_sql(
                    self._computed_columns)
                if subquery:
                    from_clause = f"({subquery})"
                else:
                    from_clause = "history"
                # 先用最便宜的 ORDER BY + LIMIT/OFFSET 选出本页 replay_id，
                # 再只对这些行计算计算列和读取宽列。
                per_page = int(self.one_page_combo.currentText())
                offset = (self.page_spin.value() - 1) * per_page
                base_from = from_clause if subquery else "history"
                page_sql = (
                    "SELECT replay_id FROM " + base_from
                    + ((" WHERE " + filter_str) if filter_str else "")
                    + order_str + " LIMIT ? OFFSET ?"
                )
                sql = f"SELECT {select_fields} FROM {from_clause}"
                page_where = "replay_id IN (" + page_sql + ")"
                if filter_str:
                    sql += " WHERE (" + filter_str + ") AND " + page_where
                else:
                    sql += " WHERE " + page_where
                sql += order_str
                page_params = (*filter_params, *filter_params,
                               per_page, offset)
                cursor.execute(sql, page_params)
                datas = cursor.fetchall()

                # 行数单独查询。COUNT(*) OVER() 会迫使 SQLite 在 LIMIT 前
                # 对全表计算列求值，大表启动时会卡住。
                count_sql = f"SELECT COUNT(*) FROM {base_from}"
                if filter_str:
                    count_sql += " WHERE " + filter_str
                total = cursor.execute(count_sql, filter_params).fetchone()[0]

                max_page = math.ceil(total / per_page)
                with QSignalBlocker(self.page_spin):
                    self.page_spin.setMaximum(max(1, max_page))
                if total and not datas:
                    offset = (self.page_spin.value() - 1) * per_page
                    page_params = (*filter_params, *filter_params,
                                   per_page, offset)
                    cursor.execute(sql, page_params)
                    datas = cursor.fetchall()
                self.limit_label.setText(
                    _translate("HistoryPlugin", "共%1行,%2页").replace("%1", str(total)).replace("%2", str(max_page)))
                self._total_rows, self._max_pages = total, max_page

                history_data = [HistoryData.from_dict(dict(d)) for d in datas]
        except sqlite3.Error as e:
            QMessageBox.warning(
                self, _translate("HistoryPlugin", "错误"),
                _translate("HistoryPlugin", "加载历史记录失败: %1").replace("%1", str(e)))
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

            # 稳定编号（或旧版译文）统一按当前语言显示
            compare_display = compare_text
            try:
                compare_display = CompareSymbol.from_display_name(
                    compare_text).display_name
            except (TypeError, ValueError):
                pass
            logic_display = ""
            if logic_text:
                try:
                    logic_display = LogicSymbol.from_display_name(
                        logic_text).display_name
                except (TypeError, ValueError):
                    logic_display = logic_text

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
                f"{left_bracket}{field} {compare_display} {value}{right_bracket}")
            if logic_display:
                parts.append(logic_display)

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
            try:
                order = SortOrder.from_text(order).display_name
            except (TypeError, ValueError):
                pass
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
            types[col.name] = col.sample_value
        return types

    def _get_field_value_type(self, field_name: str):
        """获取字段值类型（支持计算列）"""
        result = HistoryData.get_field_value(field_name)
        if result is not None:
            return result
        # 尝试计算列（用类型样本值区分 int / float / string）
        for col in self._computed_columns:
            if col.name == field_name:
                return col.sample_value
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
            QMessageBox.warning(self, _translate("HistoryPlugin", "错误"), str(e))
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
            QMessageBox.warning(self, _translate("HistoryPlugin", "错误"), str(e))
            return None

    def _save_filter_sort_state(self, filter_str: str = "", order_str: str = "") -> None:
        """发射排序和过滤状态变化信号"""
        self.filter_sort_state_changed.emit(
            json.dumps(self._filter_rows, ensure_ascii=False),
            json.dumps(self._sort_rows, ensure_ascii=False)
        )

        self._render_filter_sort_labels()

    def _render_filter_sort_labels(self) -> None:
        """按当前语言与已保存条件重建过滤/排序标签（语言切换时复用）。"""
        # 更新过滤条件标签（易读格式）
        filter_display = self._format_filter_display(self._filter_rows)
        if filter_display:
            self.filter_label.setText(
                _translate("HistoryPlugin", "过滤: %1").replace("%1", filter_display))
        else:
            self.filter_label.setText(_translate("HistoryPlugin", "过滤: 无"))

        # 更新排序条件标签（易读格式）
        sort_display = self._format_sort_display(self._sort_rows)
        if sort_display:
            self.sort_label.setText(
                _translate("HistoryPlugin", "排序: %1").replace("%1", sort_display))
        else:
            self.sort_label.setText(_translate("HistoryPlugin", "排序: 无"))

    def closeEvent(self, event: _QCloseEvent):
        """关闭事件"""
        super().closeEvent(event)

    def set_float_decimals(self, decimals: int) -> None:
        """动态设置小数位数"""
        self._float_decimals = decimals

    def set_board_preview_enabled(self, enabled: bool) -> None:
        """动态开关 board 列局面预览（配置变更时调用）"""
        self._board_preview_enabled = bool(enabled)
        self.table.set_board_preview_enabled(self._board_preview_enabled)

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
        if dialog.exec():
            new_columns = dialog.get_columns()
            new_functions = dialog.get_custom_functions()
            self._custom_functions = new_functions
            # 通过信号通知 plugin 保存配置并重建视图
            self.computed_columns_changed.emit(new_columns)
            self.custom_functions_changed.emit(new_functions)
