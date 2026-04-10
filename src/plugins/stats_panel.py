"""
实时游戏统计面板

通过 HistoryService 获取历史记录进行统计分析。
收到 VideoSaveEvent 时触发刷新，不直接使用 event 数据。
"""
from __future__ import annotations

from collections import defaultdict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QGroupBox, QHeaderView,
)
from PyQt5.QtCore import pyqtSignal

from plugin_manager import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from shared_types.events import VideoSaveEvent
from shared_types.services.history import HistoryService, GameRecord


class StatsPanel(QWidget):
    """统计面板 UI"""

    _signal_refresh = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total_games = 0
        self._best_time = float('inf')
        self._stats_by_level = defaultdict(lambda: {"count": 0, "best_time": float('inf')})

        self._setup_ui()
        self._signal_refresh.connect(self._do_refresh)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        cards_layout = QHBoxLayout()

        self._lbl_total = self._make_stat_card("Total", "0", "#1976D2")
        self._lbl_best = self._make_stat_card("Best", "--", "#F57C00")

        for card in [self._lbl_total, self._lbl_best]:
            cards_layout.addWidget(card)

        main_layout.addLayout(cards_layout)

        group = QGroupBox("Recent Games")
        group_layout = QVBoxLayout(group)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Level", "Time(s)", "3BV", "Clicks"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        group_layout.addWidget(self._table)

        main_layout.addWidget(group)

    @staticmethod
    def _make_stat_card(title: str, value: str, color: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet(f"background: {color}; border-radius: 8px; padding: 8px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px;")
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)
        return card

    def _do_refresh(self):
        """刷新显示（由插件调用）"""
        # 更新总数显示
        self._lbl_total.findChild(QLabel).setText(str(self._total_games))

        # 更新最佳时间
        if self._best_time < float('inf'):
            self._lbl_best.findChild(QLabel).setText(f"{self._best_time:.2f}")

    def clear_table(self):
        """清空表格"""
        self._table.setRowCount(0)

    def add_record(self, level: int, rtime: float, bbbv: int, left: int, right: int):
        """添加一条记录到表格"""
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(str(level)))
        self._table.setItem(row, 1, QTableWidgetItem(f"{rtime:.2f}"))
        self._table.setItem(row, 2, QTableWidgetItem(str(bbbv)))
        ops = left + right
        self._table.setItem(row, 3, QTableWidgetItem(str(ops)))

    def update_stats(self, total: int, best_time: float):
        """更新统计数据"""
        self._total_games = total
        self._best_time = best_time


class StatsPlugin(BasePlugin):
    """实时游戏统计插件

    数据来源：仅依赖 HistoryService
    - 初始化时加载历史统计
    - 收到 VideoSaveEvent 时触发刷新（重新查询历史）
    """

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="stats_panel",
            version="1.0.0",
            author="Example",
            description="Real-time game statistics panel (via HistoryService)",
            icon=make_plugin_icon("#E91E63", "S", 64),
            window_mode=WindowMode.TAB,
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._on_video_save)

    def _create_widget(self) -> QWidget:
        self._panel = StatsPanel()
        return self._panel

    def on_initialized(self) -> None:
        # 检查 HistoryService 是否可用
        if self.has_service(HistoryService):
            self.logger.info("HistoryService 已连接")
            self._load_history_stats()
        else:
            self.logger.warning("HistoryService 不可用，统计面板将无法工作")

    def _load_history_stats(self) -> None:
        """从 HistoryService 加载历史统计（在服务提供者线程执行）"""
        try:
            # 获取服务代理对象（IDE 友好）
            history = self.get_service_proxy(HistoryService)
            
            # 直接调用方法（IDE 完整补全）
            total = history.get_record_count()
            self.logger.info(f"历史记录总数: {total}")

            # 清空表格
            self._panel.clear_table()

            # 获取最近记录
            records = history.query_records(100, 0, None)

            # 计算最佳时间
            best_time = float('inf')
            for r in records:
                if r.rtime > 0 and r.rtime < best_time:
                    best_time = r.rtime

            # 更新统计
            self._panel.update_stats(total, best_time)

            # 添加最近记录到表格（显示最近 20 条）
            for r in records[:20]:
                self._panel.add_record(
                    level=r.level,
                    rtime=r.rtime,
                    bbbv=r.bbbv,
                    left=r.left,
                    right=r.right,
                )

            # 触发 UI 刷新
            self._panel._signal_refresh.emit()

        except Exception as e:
            self.logger.warning(f"加载历史统计失败: {e}")

    def on_shutdown(self) -> None:
        self.logger.info("StatsPlugin shutting down")

    def _on_video_save(self, event: VideoSaveEvent):
        """收到录像保存事件，触发重新加载历史统计"""
        self.logger.info(f"Video saved, refreshing stats...")

        # 不直接使用 event 数据，而是重新查询 HistoryService
        self._load_history_stats()
