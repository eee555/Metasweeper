"""
插件管理器主窗口

独立进程的主界面，用于管理和展示插件
- 支持标签页双击/拖拽弹出为独立窗口
- 支持关闭独立窗口自动嵌回标签页
- 增强型连接状态显示（含 endpoint、重连次数、实时心跳检测）
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QEvent
from PyQt5.QtGui import QColor, QMouseEvent, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QListView,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QSystemTrayIcon,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QDialog,
)

from .plugin_state import PluginStateManager, PluginState
from .settings_manager import SettingsManager
from plugin_sdk.plugin_base import PluginLifecycle, WindowMode, LogLevel
from plugin_sdk.control_auth import ControlAuthorizationManager
from plugin_sdk.config_types import OtherInfoBase
from .app_paths import get_data_dir

if TYPE_CHECKING:
    from .plugin_manager import PluginManager

import loguru
logger = loguru.logger.bind(name="MainWindow")


# ═══════════════════════════════════════════════════════════════════
# 可分离标签页组件
# ═══════════════════════════════════════════════════════════════════

class DetachedPluginWindow(QDialog):
    """
    弹出的独立插件窗口

    特性：
    - 关闭时自动将 widget 嵌回主窗口标签页
    - 标题栏显示"📎 嵌回"提示
    """

    # 信号：窗口被用户关闭，请求将 widget 嵌回标签页
    embed_requested = pyqtSignal(str)

    def __init__(self, plugin_name: str, widget: QWidget, parent=None):
        super().__init__(parent)
        self._plugin_name = plugin_name
        self._widget = widget
        self._icon: QIcon | None = None
        self._dragging = False
        self._drag_offset = QPoint()

        self.setWindowTitle(f"{plugin_name} - {self.tr('插件')}")
        self.setMinimumSize(400, 300)
        self.resize(600, 450)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
       # 顶部提示栏
        hint_bar = QLabel(self.tr("📎  关闭此窗口可自动嵌回到标签页"))
        hint_bar.setFixedHeight(25)
        hint_bar.setAlignment(Qt.AlignCenter)
        hint_bar.setStyleSheet("""
            QLabel {
                background: #e8f4fd;
                color: #1976d2;
                padding: 4px;
                font-size: 12px;
                border-bottom: 1px solid #b3d9ff;
            }
        """)
        layout.addWidget(hint_bar)
        # 将 widget 从旧父窗口转移到新窗口，并确保可见
        widget.setParent(self)
        layout.addWidget(widget)
        widget.setVisible(True)
        widget.show()

    def start_drag(self, global_pos: QPoint) -> None:
        """启动拖拽模式（从外部调用）"""
        self._dragging = True
        # 计算鼠标相对于窗口左上角的偏移
        self._drag_offset = global_pos - self.pos()
        # 捕获鼠标
        self.grabMouse()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPos() - self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.releaseMouse()
        super().mouseReleaseEvent(event)

    def closeEvent(self, event) -> None:
        """关闭时发出嵌入请求信号，不销毁 widget"""
        self.embed_requested.emit(self._plugin_name)
        self.hide()
        event.ignore()


class _DetachableTabBar(QTabBar):
    """支持拖拽弹出的标签栏"""

    drag_initiated = pyqtSignal(int, str, QPoint)  # index, name, global_pos

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos: QPoint | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._drag_start_pos is not None
            and (event.buttons() & Qt.LeftButton)
        ):  # type: ignore
            distance = (event.globalPos() -
                        self._drag_start_pos).manhattanLength()
            if distance > QApplication.startDragDistance():
                idx = self.tabAt(self.mapFromGlobal(self._drag_start_pos))
                if idx >= 0:
                    # 判断是否向下拖出了标签栏区域（垂直偏移大）
                    delta_y = event.globalPos().y() - self._drag_start_pos.y()
                    if abs(delta_y) > QApplication.startDragDistance():
                        name = self.tabText(idx)
                        self.drag_initiated.emit(idx, name, event.globalPos())
                        self._drag_start_pos = None
                        return
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            idx = self.tabAt(event.pos())
            if idx >= 0:
                name = self.tabText(idx)
                self.drag_initiated.emit(idx, name, event.globalPos())
                return
        super().mouseDoubleClickEvent(event)


class DetachableTabWidget(QTabWidget):
    """
    可分离的 TabWidget

    操作方式：
    - 双击标签页 → 弹出为独立窗口
    - 向下拖拽标签页 → 弹出为独立窗口
    - 关闭独立窗口 → 自动嵌回
    """

    tab_detached = pyqtSignal(str)           # 标签页被弹出 (plugin_name)
    tab_attach_requested = pyqtSignal(str)    # 请求嵌回 (plugin_name)
    tab_close_requested = pyqtSignal(str)     # 请求关闭标签页 (plugin_name)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 用自定义的标签栏替换默认的
        self._tab_bar = _DetachableTabBar(self)
        self.setTabBar(self._tab_bar)

        self.setDocumentMode(True)
        self.setTabsClosable(True)   # 每个标签页显示关闭按钮
        self.setMovable(True)         # 允许内部重排序

        self._detached_windows: dict[str, DetachedPluginWindow] = {}

        # 连接自定义标签栏的拖拽信号
        self._tab_bar.drag_initiated.connect(self._on_drag_from_bar)

        # 连接关闭按钮信号
        self.tabCloseRequested.connect(self._on_tab_close_requested)

    def add_detachable_tab(self, widget: QWidget, name: str, icon=None) -> int:
        """添加一个可分离的标签页，返回 index"""
        idx = self.addTab(widget, name)
        if icon is not None:
            self.setTabIcon(idx, icon)
        return idx

    def _on_drag_from_bar(self, index: int, name: str, pos: QPoint) -> None:
        """响应标签栏发起的拖拽/双击弹出"""
        self._detach_tab(index, name, pos=pos)

    def _detach_tab(self, index: int, name: str, pos: QPoint | None = None) -> None:
        """将指定标签页弹出为独立窗口"""
        widget = self.widget(index)
        if widget is None:
            return

        icon = self.tabIcon(index)
        self.removeTab(index)

        window = DetachedPluginWindow(name, widget, parent=self.window())
        window._icon = icon
        if icon and not icon.isNull():
            window.setWindowIcon(icon)
        window.embed_requested.connect(self._attach_tab)
        self._detached_windows[name] = window

        if pos is not None:
            # 先显示窗口以获取正确的尺寸
            window.show()
            # 将标题栏中心移动到鼠标位置
            # 水平居中，垂直方向标题栏高度约 30px
            title_height = window.frameGeometry().height() - window.height()
            new_x = pos.x() - window.width() // 2
            new_y = pos.y() - title_height // 2
            window.move(new_x, new_y)
            # 启动拖拽模式，让窗口跟随鼠标
            window.start_drag(pos)
        else:
            window.show()
        window.activateWindow()

        self.tab_detached.emit(name)

    def _cleanup_detached(self, name: str) -> None:
        """安全清理 detached 窗口引用"""
        if name in self._detached_windows:
            w = self._detached_windows[name]
            w.blockSignals(True)
            w.close()
            w.deleteLater()
            del self._detached_windows[name]

    def _attach_tab(self, name: str) -> None:
        """将弹出的窗口嵌回标签页"""
        if name not in self._detached_windows:
            return

        window = self._detached_windows[name]
        saved_icon = window._icon  # type: ignore[attr-defined]
        # 防止重复调用：手动关闭时已清理过的情况
        lay = window.layout()
        if lay is None or lay.count() < 2:
            self._cleanup_detached(name)
            return

        item = lay.itemAt(1)
        if item is None:
            self._cleanup_detached(name)
            return
        widget = item.widget()
        if widget is None:
            self._cleanup_detached(name)
            return

        # 从窗口取出 widget
        window.layout().removeWidget(widget)
        widget.setParent(None)  # type: ignore

        window.deleteLater()
        del self._detached_windows[name]

        # 检查是否已存在同名标签页
        for i in range(self.count()):
            if self.tabText(i) == name:
                self.insertTab(i, widget, name)
                if saved_icon and not saved_icon.isNull():
                    self.setTabIcon(i, saved_icon)
                widget.setVisible(True)
                return

        idx = self.addTab(widget, name)
        if saved_icon and not saved_icon.isNull():
            self.setTabIcon(idx, saved_icon)
        widget.setVisible(True)
        self.tab_attach_requested.emit(name)

    def _on_tab_close_requested(self, index: int) -> None:
        """处理标签页关闭按钮点击"""
        name = self.tabText(index)
        widget = self.widget(index)
        if widget is None:
            return
        # 隐藏并移除标签页，不销毁 widget（保留插件数据）
        self.removeTab(index)
        widget.hide()
        widget.setParent(None)  # type: ignore
        self.tab_close_requested.emit(name)


# ═══════════════════════════════════════════════════════════════════
# 连接状态组件
# ═══════════════════════════════════════════════════════════════════

class ConnectionStatusWidget(QWidget):
    """增强型连接状态显示组件"""

    def __init__(self, endpoint: str, parent=None):
        super().__init__(parent)
        self._endpoint = endpoint

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 状态指示灯
        self._status_label = QLabel(self.tr("● 未连接"))
        self._status_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self._status_label)

        # 重连次数
        self._reconnect_label = QLabel("")
        self._reconnect_label.setStyleSheet(
            "color: orange; font-size: 11px; margin-left: 6px;"
        )
        layout.addWidget(self._reconnect_label)

        layout.addStretch()

        # 端点地址
        ep_label = QLabel(endpoint)
        ep_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(ep_label)

    def set_status(
        self,
        connected: bool,
        reconnect_count: int = 0,
    ) -> None:
        """更新连接状态显示"""
        if connected:
            self._status_label.setText(self.tr("● 已连接"))
            self._status_label.setStyleSheet(
                "color: green; font-weight: bold;")
            if reconnect_count > 0:
                self._reconnect_label.setText(
                    self.tr("(重连 {n} 次").format(n=reconnect_count)
                )
                self._reconnect_label.show()
            else:
                self._reconnect_label.hide()
        else:
            self._status_label.setText(self.tr("● 未连接"))
            self._status_label.setStyleSheet("color: red; font-weight: bold;")
            if reconnect_count > 0:
                self._reconnect_label.setText(
                    self.tr("(断开, 重连 {n} 次)").format(n=reconnect_count)
                )
                self._reconnect_label.show()
            else:
                self._reconnect_label.hide()


# ═══════════════════════════════════════════════════════════════════
# 插件设置编辑对话框
# ═══════════════════════════════════════════════════════════════════

class PluginSettingsDialog(QDialog):
    """编辑单个插件的持久化状态"""

    def __init__(
        self,
        plugin_name: str,
        state: PluginState,
        other_info: OtherInfoBase | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._name = plugin_name
        self._other_info = other_info

        self.setWindowTitle(self.tr("插件设置 - {n}").format(n=plugin_name))
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # ── 启用 / 显示窗口 ──
        grp = QGroupBox(self.tr("基本设置"))
        form = QFormLayout(grp)

        self._chk_enabled = QCheckBox()
        self._chk_enabled.setChecked(state.enabled)
        form.addRow(self.tr("启用插件:"), self._chk_enabled)

        self._chk_show = QCheckBox()
        self._chk_show.setChecked(state.show_window)
        form.addRow(self.tr("启动时显示窗口:"), self._chk_show)
        layout.addWidget(grp)

        # ── 窗口模式 ──
        grp2 = QGroupBox(self.tr("窗口加载方式"))
        form2 = QFormLayout(grp2)

        self._combo_mode = QComboBox()
        for mode in WindowMode:
            label = WindowMode.LABELS().get(mode, mode)
            self._combo_mode.addItem(label, mode)
        # WindowMode 继承自 str，直接 str() 转换
        idx = self._combo_mode.findData(str(state.window_mode))
        if idx >= 0:
            self._combo_mode.setCurrentIndex(idx)
        else:
            self._combo_mode.setCurrentIndex(0)  # default to tab
        form2.addRow(self.tr("窗口位置:"), self._combo_mode)
        layout.addWidget(grp2)

        # ── 日志级别 ──
        grp3 = QGroupBox(self.tr("日志设置"))
        form3 = QFormLayout(grp3)

        self._combo_loglevel = QComboBox()
        for level in LogLevel:
            label = LogLevel.LABELS().get(level, level)
            self._combo_loglevel.addItem(label, level)
        # LogLevel 继承自 str，直接 str() 转换
        _lvl_idx = self._combo_loglevel.findData(str(state.log_level).upper())
        if _lvl_idx >= 0:
            self._combo_loglevel.setCurrentIndex(_lvl_idx)
        else:
            self._combo_loglevel.setCurrentIndex(1)  # default DEBUG
        form3.addRow(self.tr("日志级别:"), self._combo_loglevel)
        layout.addWidget(grp3)

        # ── 插件自定义配置 ──
        self._config_widget = None
        if other_info is not None:
            from .config_widget import OtherInfoScrollArea

            grp4 = QGroupBox(self.tr("插件配置"))
            grp4_layout = QVBoxLayout(grp4)

            scroll_area = OtherInfoScrollArea(other_info, grp4)
            scroll_area.setMinimumHeight(150)
            grp4_layout.addWidget(scroll_area)

            layout.addWidget(grp4)
            self._config_widget = scroll_area

        layout.addStretch()

        # 按钮
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @property
    def result_state(self) -> PluginState:
        return PluginState(
            enabled=self._chk_enabled.isChecked(),
            show_window=self._chk_show.isChecked(),
            window_mode=WindowMode(str(self._combo_mode.currentData())),
            log_level=LogLevel(str(self._combo_loglevel.currentData())),
        )

    def apply_config(self) -> None:
        """应用配置到 other_info 对象"""
        if self._config_widget:
            self._config_widget.apply_to_config()


# ═══════════════════════════════════════════════════════════════════
# 基础设置对话框
# ═══════════════════════════════════════════════════════════════════

class BasicSettingsDialog(QDialog):
    """
    插件管理器基础设置对话框

    包含日志等级等基础配置。
    """

    # 设置变更信号
    settings_changed = pyqtSignal()

    def __init__(self, settings_manager: "SettingsManager", parent=None) -> None:
        super().__init__(parent)
        self._settings_manager = settings_manager
        self.setWindowTitle("基础设置")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── 主进程日志设置组 ──
        main_log_group = QGroupBox("主进程文件日志")
        main_log_layout = QFormLayout(main_log_group)

        self._file_log_level_combo = QComboBox()
        self._file_log_level_combo.addItems(SettingsManager.LOG_LEVELS)
        index = self._file_log_level_combo.findText(
            self._settings_manager.file_log_level)
        if index >= 0:
            self._file_log_level_combo.setCurrentIndex(index)

        file_log_label = QLabel("日志等级")
        file_log_label.setToolTip("主进程日志文件的记录等级")
        main_log_layout.addRow(file_log_label, self._file_log_level_combo)

        layout.addWidget(main_log_group)

        # ── 日志查看器设置组 ──
        viewer_group = QGroupBox("日志查看器")
        viewer_layout = QFormLayout(viewer_group)

        self._viewer_log_level_combo = QComboBox()
        self._viewer_log_level_combo.addItems(SettingsManager.LOG_LEVELS)
        index = self._viewer_log_level_combo.findText(
            self._settings_manager.viewer_log_level)
        if index >= 0:
            self._viewer_log_level_combo.setCurrentIndex(index)

        viewer_log_label = QLabel("日志等级")
        viewer_log_label.setToolTip("日志查看器显示的日志等级")
        viewer_layout.addRow(viewer_log_label, self._viewer_log_level_combo)

        self._auto_scroll_cb = QCheckBox()
        self._auto_scroll_cb.setChecked(
            self._settings_manager.viewer_auto_scroll)
        viewer_layout.addRow("自动滚动", self._auto_scroll_cb)

        self._show_source_cb = QCheckBox()
        self._show_source_cb.setChecked(
            self._settings_manager.viewer_show_source)
        viewer_layout.addRow("显示来源", self._show_source_cb)

        layout.addWidget(viewer_group)

        # 按钮盒
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_accept(self) -> None:
        """保存设置"""
        changed = False

        # 主进程文件日志等级
        new_file_level = self._file_log_level_combo.currentText()
        if new_file_level != self._settings_manager.file_log_level:
            self._settings_manager.set_file_log_level(
                new_file_level)  # type: ignore
            changed = True

        # 日志查看器等级
        new_viewer_level = self._viewer_log_level_combo.currentText()
        if new_viewer_level != self._settings_manager.viewer_log_level:
            self._settings_manager.set_viewer_log_level(
                new_viewer_level)  # type: ignore
            changed = True

        # 自动滚动
        new_auto_scroll = self._auto_scroll_cb.isChecked()
        if new_auto_scroll != self._settings_manager.viewer_auto_scroll:
            self._settings_manager.set_viewer_auto_scroll(new_auto_scroll)
            changed = True

        # 显示来源
        new_show_source = self._show_source_cb.isChecked()
        if new_show_source != self._settings_manager.viewer_show_source:
            self._settings_manager.set_viewer_show_source(new_show_source)
            changed = True

        if changed:
            self.settings_changed.emit()
        self.accept()


# ═══════════════════════════════════════════════════════════════════
# 日志查看对话框
# ═══════════════════════════════════════════════════════════════════

class LogViewerDialog(QDialog):
    """
    日志查看对话框（非模态）

    通过 loguru sink 实时显示日志。
    """

    # 日志信号: time_str, level, source, message
    _log_signal = pyqtSignal(str, str, str, str)

    # 支持的日志等级
    LOG_LEVELS = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def __init__(
        self,
        plugin_names: list[str],
        initial_log: str = "main",
        initial_level: str = "DEBUG",
        auto_scroll: bool = True,
        show_source: bool = False,
        parent=None
    ) -> None:
        """
        Args:
            plugin_names: 插件名称列表
            initial_log: 初始显示的日志（"main" 或插件名）
            initial_level: 初始日志等级
            auto_scroll: 自动滚动默认值
            show_source: 显示来源信息默认值
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("日志查看")
        self.setMinimumSize(900, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        self._plugin_names = plugin_names
        self._current_log = initial_log
        self._current_level = initial_level
        self._auto_scroll_default = auto_scroll
        self._show_source_default = show_source
        self._sink_id: int | None = None

        self._setup_ui()
        self._log_signal.connect(self._append_log_line)
        self._attach_sink(initial_log)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 顶部：日志选择
        top_layout = QHBoxLayout()

        top_layout.addWidget(QLabel("日志源:"))

        self._log_combo = QComboBox()
        self._log_combo.addItem("主进程", "main")
        for name in self._plugin_names:
            self._log_combo.addItem(f"插件: {name}", name)
        self._log_combo.currentIndexChanged.connect(self._on_log_changed)
        top_layout.addWidget(self._log_combo)

        top_layout.addSpacing(20)

        # 日志等级
        top_layout.addWidget(QLabel("等级:"))

        self._level_combo = QComboBox()
        self._level_combo.addItems(self.LOG_LEVELS)
        self._level_combo.setCurrentText(self._current_level)
        self._level_combo.currentIndexChanged.connect(self._on_level_changed)
        top_layout.addWidget(self._level_combo)

        top_layout.addSpacing(20)

        # 自动滚动
        self._auto_scroll_cb = QCheckBox("自动滚动")
        self._auto_scroll_cb.setChecked(self._auto_scroll_default)
        top_layout.addWidget(self._auto_scroll_cb)

        # 显示来源
        self._show_source_cb = QCheckBox("显示来源")
        self._show_source_cb.setChecked(self._show_source_default)
        top_layout.addWidget(self._show_source_cb)

        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear_log)
        top_layout.addWidget(clear_btn)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        # 中部：日志内容
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(5000)  # 限制行数
        self._log_view.setStyleSheet("""
            QPlainTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
        """)
        layout.addWidget(self._log_view)

        # 底部：按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)

    def _attach_sink(self, log_name: str) -> None:
        """添加 loguru sink"""
        # 移除旧 sink
        if self._sink_id is not None:
            try:
                loguru.logger.remove(self._sink_id)
            except ValueError:
                pass
            self._sink_id = None

        self._current_log = log_name

        # 清空显示
        self._log_view.clear()

        # 保存信号引用（闭包需要）
        log_signal = self._log_signal

        # 根据日志源设置过滤器
        if log_name == "main":
            # 主进程日志：排除插件日志
            def filter_func(record):  # type: ignore
                return True
        else:
            # 插件日志：只显示该插件
            def filter_func(record, pn=log_name):
                return record["extra"].get("plugin") == pn

        # sink 函数
        def sink_write(message):
            record = message.record
            time_obj = record["time"]
            time_str = time_obj.strftime(
                "%Y-%m-%d %H:%M:%S.%f")[:-3]  # 去掉最后3位微秒
            level = record["level"].name
            # 来源信息: name:function:line
            source = f"{record['name']}:{record['function']}:{record['line']}"
            text = str(message)
            log_signal.emit(time_str, level, source, text)

        # 添加 sink
        self._sink_id = loguru.logger.add(
            sink_write,
            level=self._current_level,
            filter=filter_func,
            format="{message}",
        )
        logger.debug(
            f"Log viewer sink attached: {log_name}, level={self._current_level}, sink_id={self._sink_id}")

    def _append_log_line(self, time_str: str, level: str, source: str, message: str) -> None:
        """追加一行日志"""
        if self._show_source_cb.isChecked():
            line = f"{time_str} | {level:<7} | {source} | {message}"
        else:
            line = f"{time_str} | {level:<7} | {message}"

        # 简单的颜色标记
        if "ERROR" in level or "CRITICAL" in level:
            self._log_view.appendHtml(
                f'<span style="color:#f44747">{line}</span>')
        elif "WARNING" in level:
            self._log_view.appendHtml(
                f'<span style="color:#dcdcaa">{line}</span>')
        elif "DEBUG" in level or "TRACE" in level:
            self._log_view.appendHtml(
                f'<span style="color:#808080">{line}</span>')
        elif "INFO" in level:
            self._log_view.appendHtml(
                f'<span style="color:#4ec9b0">{line}</span>')
        else:
            self._log_view.appendPlainText(line)

        if self._auto_scroll_cb.isChecked():
            self._log_view.ensureCursorVisible()

    def _on_log_changed(self, index: int) -> None:
        """日志源切换"""
        log_name = self._log_combo.itemData(index)
        self._attach_sink(log_name)

    def _on_level_changed(self, index: int) -> None:
        """日志等级切换"""
        self._current_level = self._level_combo.currentText()
        self._attach_sink(self._current_log)

    def _clear_log(self) -> None:
        """清空日志显示"""
        self._log_view.clear()

    def closeEvent(self, event) -> None:
        """关闭时移除 sink"""
        if self._sink_id is not None:
            try:
                loguru.logger.remove(self._sink_id)
            except ValueError:
                pass
            self._sink_id = None
        super().closeEvent(event)

    def show_log(self, log_name: str) -> None:
        """切换到指定日志"""
        # 如果日志源不在列表中，添加它
        index = self._log_combo.findData(log_name)
        if index < 0 and log_name != "main":
            self._log_combo.addItem(f"插件: {log_name}", log_name)
            index = self._log_combo.count() - 1

        if index >= 0:
            self._log_combo.setCurrentIndex(index)

    def update_settings(self, level: str, auto_scroll: bool, show_source: bool) -> None:
        """更新设置"""
        # 更新日志等级
        if level != self._current_level:
            self._current_level = level
            self._level_combo.setCurrentText(level)
            self._attach_sink(self._current_log)

        # 更新自动滚动
        self._auto_scroll_cb.setChecked(auto_scroll)

        # 更新显示来源
        self._show_source_cb.setChecked(show_source)


# ═══════════════════════════════════════════════════════════════════
# 控制授权配置对话框
# ═══════════════════════════════════════════════════════════════════

class ControlAuthorizationDialog(QDialog):
    """
    控制授权配置对话框

    管理插件对控制命令的使用权限。
    只显示声明了需要该控制权限的插件。
    """

    def __init__(
        self,
        plugin_controls: dict[str, list[type]],
        parent=None,
    ):
        """
        Args:
            plugin_controls: {plugin_name: [command_type, ...]}
                插件声明需要的控制权限
        """
        super().__init__(parent)
        self._plugin_controls = plugin_controls
        self._auth_manager = ControlAuthorizationManager.instance()

        self.setWindowTitle(self.tr("控制授权配置"))
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        self._setup_ui()
        self._load_authorizations()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 说明文字
        info_label = QLabel(self.tr(
            "每个控制命令只能授权给一个插件。\n"
            "未授权的控制命令，所有插件都不能使用。\n"
            "下拉列表仅显示声明了该权限的插件。"
        ))
        info_label.setStyleSheet("color: gray; padding: 8px;")
        layout.addWidget(info_label)

        # 表格
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([
            self.tr("控制命令"),
            self.tr("授权插件"),
            self.tr("状态"),
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self._table.setColumnWidth(2, 80)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        # 按钮
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load_authorizations(self) -> None:
        """加载授权状态到表格"""
        control_types = self._auth_manager.get_all_control_types()
        status = self._auth_manager.get_authorization_status()

        self._table.setRowCount(len(control_types))
        self._combos: list[QComboBox] = []

        for row, cmd_type in enumerate(control_types):
            try:
                tag = self._auth_manager._get_tag(cmd_type)
            except ValueError:
                continue

            # 控制命令名称
            name_item = QTableWidgetItem(cmd_type.__name__)
            name_item.setData(Qt.UserRole, cmd_type)  # 存储类型
            self._table.setItem(row, 0, name_item)

            # 找出声明了该控制权限的插件
            eligible_plugins = [
                plugin_name
                for plugin_name, controls in self._plugin_controls.items()
                if any(
                    self._is_same_command_type(cmd_type, c)
                    for c in controls
                )
            ]

            # 插件下拉框
            combo = QComboBox()
            combo.addItem(self.tr("未授权"), None)  # index 0 = 未授权

            if eligible_plugins:
                for plugin_name in sorted(eligible_plugins):
                    combo.addItem(plugin_name, plugin_name)
            else:
                # 没有插件声明需要该权限，禁用下拉框
                combo.setEnabled(False)

            # 设置当前值
            current_plugin = status.get(tag)
            if current_plugin and current_plugin in eligible_plugins:
                idx = combo.findData(current_plugin)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            self._table.setCellWidget(row, 1, combo)
            self._combos.append(combo)

            # 状态显示
            self._update_status(row, current_plugin, eligible_plugins)

            # 连接下拉框变化
            combo.currentIndexChanged.connect(
                lambda _, r=row: self._on_combo_changed(r))

    def _is_same_command_type(self, type1: type, type2: type) -> bool:
        """判断两个命令类型是否相同（通过 tag）"""
        try:
            tag1 = self._auth_manager._get_tag(type1)
            tag2 = self._auth_manager._get_tag(type2)
            return tag1 == tag2
        except ValueError:
            return type1 is type2

    def _update_status(
        self,
        row: int,
        plugin_name: str | None,
        eligible_plugins: list[str],
    ) -> None:
        """更新状态列"""
        if not eligible_plugins:
            status_item = QTableWidgetItem(self.tr("无申请"))
            status_item.setForeground(QColor("#9e9e9e"))
        elif plugin_name:
            status_item = QTableWidgetItem(self.tr("● 已授权"))
            status_item.setForeground(QColor("#4caf50"))
        else:
            status_item = QTableWidgetItem(self.tr("○ 未授权"))
            status_item.setForeground(QColor("#ff9800"))
        self._table.setItem(row, 2, status_item)

    def _on_combo_changed(self, row: int) -> None:
        """下拉框变化时更新状态"""
        combo: QComboBox = self._table.cellWidget(row, 1)  # type: ignore
        plugin_name = combo.currentData()
        self._update_status(row, plugin_name, [])  # 简化，不重新计算 eligible_plugins

    def _on_accept(self) -> None:
        """确定按钮：保存授权"""
        for row in range(self._table.rowCount()):
            name_item: QTableWidgetItem = self._table.item(
                row, 0)  # type: ignore
            combo: QComboBox = self._table.cellWidget(row, 1)  # type: ignore

            cmd_type = name_item.data(Qt.UserRole)
            plugin_name = combo.currentData()

            if plugin_name is None:
                self._auth_manager.revoke(cmd_type)
            else:
                self._auth_manager.authorize(cmd_type, plugin_name)

        self._auth_manager.save()
        self.accept()


# ═══════════════════════════════════════════════════════════════════
# 主窗口
# ═══════════════════════════════════════════════════════════════════

class PluginManagerWindow(QMainWindow):
    """插件管理器主窗口"""

    connection_changed = pyqtSignal(bool)

    def __init__(self, plugin_manager: PluginManager, parent=None):
        super().__init__(parent)

        self._manager = plugin_manager

        # 状态持久化
        self._state_mgr = PluginStateManager(
            get_data_dir() / "plugin_states.json")
        self._state_mgr.load()

        # 设置管理
        self._settings_mgr = SettingsManager(get_data_dir())

        self.setWindowTitle(self.tr("插件管理器"))
        self.setMinimumSize(800, 600)

        self._setup_ui()
        self._connect_signals()
        self._setup_tray_icon()

        # 应用已保存的状态到插件
        self._apply_saved_states()

        # 连接所有插件的 ready 信号，就绪后自动刷新列表
        for p in self._manager.plugins.values():
            p.ready.connect(lambda _p=p: self._on_plugin_ready(_p))

        self._refresh_plugin_list()

        # 定时刷新连接状态
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_connection_status)
        self._timer.start(1000)

    # ── UI ───────────────────────────────────────────────

    def _setup_ui(self) -> None:
        """构建界面"""
        # ── 菜单栏 ──
        menubar = self.menuBar()

        # 选项菜单
        options_menu = menubar.addMenu(self.tr("选项"))

        # 设置子菜单
        settings_menu = options_menu.addMenu(self.tr("设置"))

        # 基础设置动作
        act_basic_settings = settings_menu.addAction(self.tr("基础设置..."))
        act_basic_settings.triggered.connect(self._open_basic_settings_dialog)

        # 控制授权动作
        act_control_auth = settings_menu.addAction(self.tr("控制授权..."))
        act_control_auth.triggered.connect(self._open_control_auth_dialog)

        settings_menu.addSeparator()

        # 调试动作
        self._debug_act = settings_menu.addAction(self.tr("启动调试"))
        self._debug_act.triggered.connect(self._start_debug)

        options_menu.addSeparator()

        # 插件开发指南动作
        act_dev_guide = options_menu.addAction(self.tr("插件开发指南"))
        act_dev_guide.triggered.connect(self._open_dev_guide)

        # ── 查看菜单 ──
        view_menu = menubar.addMenu(self.tr("查看"))

        # 日志查看动作
        act_log_viewer = view_menu.addAction(self.tr("日志查看"))
        act_log_viewer.triggered.connect(lambda: self._open_log_viewer())

        # ── 工具栏 ──
        toolbar = QToolBar(self.tr("工具栏"))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # 刷新按钮
        self._refresh_btn = QPushButton(self.tr("刷新"))
        self._refresh_btn.setToolTip(self.tr("刷新插件列表"))
        toolbar.addWidget(self._refresh_btn)

        toolbar.addSeparator()

        # 控制授权按钮
        self._control_auth_btn = QPushButton("🔐 " + self.tr("控制授权"))
        self._control_auth_btn.setToolTip(self.tr("配置插件控制命令权限"))
        toolbar.addWidget(self._control_auth_btn)

        # ── 主布局：左侧插件列表 + 右侧标签页 ──
        main_splitter = QWidget()
        main_layout = QHBoxLayout(main_splitter)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)

        # ── 左侧：插件列表面板 ──
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # 标题
        title_label = QLabel(self.tr("插件列表"))
        title_label.setStyleSheet("font-weight: bold; padding: 4px;")
        left_layout.addWidget(title_label)

        # 插件列表
        lst = QListWidget()
        lst.setViewMode(QListView.ListMode)
        lst.setSelectionMode(QListView.SingleSelection)
        lst.setEditTriggers(QListView.NoEditTriggers)
        lst.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list = lst
        left_layout.addWidget(lst)

        left_panel.setMaximumWidth(200)
        main_layout.addWidget(left_panel)

        # 记录被关闭（但未销毁）的插件名称
        self._closed_plugins: set[str] = set()

        # ── 右侧：可分离标签页 ──
        self._tab_widget = DetachableTabWidget()
        self._tab_widget.tab_detached.connect(self._on_tab_detached)
        self._tab_widget.tab_attach_requested.connect(self._on_tab_attached)
        self._tab_widget.tab_close_requested.connect(self._on_tab_closed)
        main_layout.addWidget(self._tab_widget, stretch=1)

        self.setCentralWidget(main_splitter)

        # 状态栏
        bar = QStatusBar()
        self.setStatusBar(bar)

        conn_w = ConnectionStatusWidget(self._manager.connection_endpoint)
        bar.addPermanentWidget(conn_w)
        self._conn_status = conn_w
        bar.showMessage(self.tr("正在连接..."))

    def _setup_tray_icon(self) -> None:
        """创建系统托盘图标，关闭主窗口时最小化到托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统不支持托盘图标")
            return

        icon = self._create_tray_icon()
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip(self.tr("插件管理器 - 右键打开菜单"))

        menu = QMenu(self)
        act_show = menu.addAction(self.tr("显示主窗口"))
        act_show.triggered.connect(self.show_and_raise)
        menu.addSeparator()
        act_quit = menu.addAction(self.tr("退出"))
        act_quit.triggered.connect(self._really_quit)
        tray.setContextMenu(menu)

        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self._tray_icon = tray

    @staticmethod
    def _create_tray_icon() -> QIcon:
        """生成一个简单的托盘图标（蓝色圆形 + 插件符号）"""
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QFont
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        # 蓝色圆形背景
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#1976d2")))
        p.drawEllipse(pix.rect().adjusted(3, 3, -3, -3))
        # 白色 "P" 字母
        pen = QPen(QColor("white"), 2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        font = QFont("Arial", 32, QFont.Bold)
        p.setFont(font)
        p.drawText(pix.rect(), Qt.AlignCenter, "P")
        p.end()
        return QIcon(pix)

    def show_and_raise(self) -> None:
        """显示主窗口并置顶"""
        if not self.isVisible():
            self.show()
        self.activateWindow()
        self.raise_()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """托盘图标被双击时恢复窗口"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_and_raise()

    def _really_quit(self) -> None:
        """真正退出程序（从托盘菜单触发）"""
        self._tray_icon.hide()
        self._state_mgr.save()
        self._manager.stop()
        QApplication.instance().quit()  # type: ignore

    def _open_global_settings(self) -> None:
        """打开全局设置（目前显示控制授权对话框）"""
        self._open_control_auth_dialog()

    def _open_dev_guide(self) -> None:
        """用 Qt 控件打开插件开发指南文档"""
        from PyQt5.QtWidgets import QTextBrowser
        from PyQt5.QtGui import QFont, QPalette, QColor
        from .app_paths import get_executable_dir

        # 获取 plugin-dev-tutorial.md 的路径
        guide_path = get_executable_dir() / "plugin-dev-tutorial.md"

        if not guide_path.exists():
            QMessageBox.warning(
                self,
                self.tr("插件开发指南"),
                self.tr("未找到插件开发指南文档：\n{path}").format(path=str(guide_path)),
            )
            return

        # 读取文档内容
        try:
            content = guide_path.read_text(encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("插件开发指南"),
                self.tr("无法读取文档：\n{error}").format(error=str(e)),
            )
            return

        # 创建显示对话框
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("插件开发指南"))
        dlg.setMinimumSize(900, 700)

        layout = QVBoxLayout(dlg)

        # 使用 QTextBrowser 显示 Markdown 内容
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setMarkdown(content)

        # 设置字体
        font = QFont("Microsoft YaHei", 11)
        font.setStyleHint(QFont.SansSerif)
        text_browser.setFont(font)

        # 设置调色板（颜色主题）
        palette = text_browser.palette()
        palette.setColor(QPalette.Text, QColor("#24292f"))  # 文字颜色
        palette.setColor(QPalette.Link, QColor("#0969da"))  # 链接颜色
        palette.setColor(QPalette.LinkVisited, QColor("#8250df"))  # 已访问链接
        text_browser.setPalette(palette)

        # 设置文档边距
        doc = text_browser.document()
        doc.setDocumentMargin(16)

        layout.addWidget(text_browser)

        # 关闭按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(dlg.close)
        layout.addWidget(btn_box)

        dlg.exec_()

    def _connect_signals(self) -> None:
        self._refresh_btn.clicked.connect(self._refresh_plugin_list)
        self._list.itemDoubleClicked.connect(self._on_list_double_clicked)
        self._list.customContextMenuRequested.connect(
            self._on_list_context_menu)
        self.connection_changed.connect(self._on_conn_changed)

        # 控制授权按钮
        self._control_auth_btn.clicked.connect(self._open_control_auth_dialog)

    def _open_basic_settings_dialog(self) -> None:
        """打开基础设置对话框"""
        dialog = BasicSettingsDialog(self._settings_mgr, self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec_()

    def _on_settings_changed(self) -> None:
        """设置变更后的回调"""
        # 应用日志等级
        self._apply_log_level()
        self.statusBar().showMessage(self.tr("设置已保存"), 2000)

    def _apply_log_level(self) -> None:
        """应用日志等级到日志系统"""
        from .logging_setup import set_console_log_level
        level = self._settings_mgr.file_log_level
        set_console_log_level(level)
        logger.info(f"控制台日志等级已设置为: {level}")

    def _open_log_viewer(self, initial_log: str = "main") -> None:
        """打开日志查看对话框（非模态）"""
        # 获取所有插件名称
        plugin_names = list(self._manager.plugins.keys())

        # 获取日志查看器设置
        viewer_level = self._settings_mgr.viewer_log_level
        auto_scroll = self._settings_mgr.viewer_auto_scroll
        show_source = self._settings_mgr.viewer_show_source

        # 创建或复用对话框
        if not hasattr(self, "_log_viewer_dlg") or self._log_viewer_dlg is None:
            self._log_viewer_dlg = LogViewerDialog(
                plugin_names, initial_log, viewer_level, auto_scroll, show_source, self
            )
        else:
            # 更新设置并切换到指定日志
            self._log_viewer_dlg.update_settings(
                viewer_level, auto_scroll, show_source)
            self._log_viewer_dlg.show_log(initial_log)

        self._log_viewer_dlg.show()
        self._log_viewer_dlg.raise_()
        self._log_viewer_dlg.activateWindow()

    def _open_control_auth_dialog(self) -> None:
        """打开控制授权配置对话框"""
        # 获取插件声明需要的控制权限
        plugin_controls: dict[str, list[type]] = {}

        for p in self._manager.plugins.values():
            if p.lifecycle == PluginLifecycle.READY:
                required = p.info.required_controls or []
                if required:
                    plugin_controls[p.name] = required

        dialog = ControlAuthorizationDialog(plugin_controls, self)
        dialog.exec_()

    # ── 连接状态 ────────────────────────────────────────

    def set_connected(self, ok: bool) -> None:
        self.connection_changed.emit(ok)

    def _on_conn_changed(self, ok: bool) -> None:
        rc = self._manager.reconnect_count
        self._conn_status.set_status(ok, rc)
        msg = (
            self.tr("已连接到主进程")
            if ok
            else self.tr("未连接 (重连 {n} 次)").format(n=rc) if rc
            else self.tr("未连接到主进程")
        )
        self.statusBar().showMessage(msg)

    def _poll_connection_status(self) -> None:
        try:
            ok = self._manager.is_connected
            rc = self._manager.reconnect_count
            self._conn_status.set_status(ok, rc)
        except Exception:
            pass

    # ── 远程调试 ────────────────────────────────────────

    _debug_active: bool = False

    def _start_debug(self) -> None:
        """启动 debugpy 监听"""
        try:
            import debugpy
            # in_process_debug_adapter=True: 不启动子进程，直接在当前进程中运行 adapter
            # 解决 PyInstaller 打包后子进程找不到 Python/debugpy 的问题
            debugpy.listen(("0.0.0.0", 5678), in_process_debug_adapter=True)
            PluginManagerWindow._debug_active = True

            # 启动后禁用菜单项，不可重复启动
            self._debug_act.setText(self.tr("调试已启动"))
            self._debug_act.setEnabled(False)

            self.statusBar().showMessage(self.tr("调试服务已在端口 5678 启动，等待 VS Code 连接。重启插件管理器可关闭调试。"))
            logger.info("Debug server started on port 5678")
        except ImportError as e:
            QMessageBox.warning(
                self, "Debug",
                f"debugpy import failed:\n{e}",
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Debug", f"Failed to start debugger:\n{e}")

    # ── 插件列表 ────────────────────────────────────────

    # ── 插件列表 ────────────────────────────────────────

    def _on_plugin_ready(self, plugin) -> None:
        """插件初始化完成，刷新列表显示"""
        self._refresh_plugin_list()
        self.statusBar().showMessage(
            self.tr("插件 {name} 就绪").format(name=plugin.name), 2000
        )

    def _refresh_plugin_list(self) -> None:
        """刷新插件列表和标签页"""
        t = self._tab_widget
        lst = self._list
        t.setUpdatesEnabled(False)
        lst.setUpdatesEnabled(False)

        # 保存当前选中项
        current_name = None
        item = lst.currentItem()
        if item:
            current_name = item.data(Qt.UserRole)

        lst.clear()
        while t.count() > 0:
            t.removeTab(0)

        # 需要弹出的 detached 插件（延迟到 updatesEnabled 之后）
        _pending_detach: list[str] = []

        for name, p in self._manager.plugins.items():
            li = QListWidgetItem(p.name)
            li.setData(Qt.UserRole, name)
            li.setIcon(p.plugin_icon)

            lc = p.lifecycle

            # 根据生命周期状态显示
            if lc == PluginLifecycle.INITIALIZING:
                li.setForeground(QColor("#f57c00"))  # 橙色：初始化中
                li.setText(f"{p.name} (⏳ 初始化中...)")
            elif not p.is_enabled:
                li.setForeground(Qt.gray)  # 灰色：已禁用
            elif lc == PluginLifecycle.SHUTTING_DOWN:
                li.setForeground(QColor("#c62828"))  # 红色：关闭中
                li.setText(f"{p.name} (⏸ 关闭中...)")

            lst.addItem(li)

            # 只有就绪状态才创建窗口（INITIALIZING/STOPPED 不创建）
            if p.lifecycle == PluginLifecycle.READY and p.widget and name not in t._detached_windows and name not in self._closed_plugins:
                st = self._effective_state(name)
                if st.window_mode == WindowMode.DETACHED:
                    t.add_detachable_tab(p.widget, name, icon=p.plugin_icon)
                    _pending_detach.append(name)
                else:
                    t.add_detachable_tab(p.widget, name, icon=p.plugin_icon)

        # 恢复选中项
        if current_name:
            for i in range(lst.count()):
                if lst.item(i).data(Qt.UserRole) == current_name:  # type: ignore
                    lst.setCurrentRow(i)
                    break

        t.setUpdatesEnabled(True)
        lst.setUpdatesEnabled(True)

        # 延迟弹出到独立窗口
        for name in _pending_detach:
            for i in range(t.count()):
                if t.tabText(i) == name:
                    t._detach_tab(i, name)
                    break

        total = len(self._manager.plugins)
        en = sum(1 for p in self._manager.plugins.values() if p.is_enabled)
        self.statusBar().showMessage(
            self.tr("已加载 {total} 个插件，{enabled} 个已启用").format(
                total=total, enabled=en
            )
        )

    def _on_list_context_menu(self, pos) -> None:
        """右键菜单"""
        item = self._list.itemAt(pos)
        if not item:
            return

        name = item.data(Qt.UserRole)
        plugin = self._manager.plugins.get(name)
        if not plugin:
            return

        menu = QMenu(self)
        t = self._tab_widget

        # 启用/禁用（非就绪状态不可切换，但 STOPPED 可以重新启用）
        lc = plugin.lifecycle
        can_control = lc in (PluginLifecycle.READY, PluginLifecycle.STOPPED)
        act_enable = menu.addAction("✅ " + self.tr("启用"))
        act_disable = menu.addAction("❌ " + self.tr("禁用"))
        act_enable.setEnabled(can_control and not plugin.is_enabled)
        act_disable.setEnabled(
            lc == PluginLifecycle.READY and plugin.is_enabled)
        act_enable.triggered.connect(lambda: self._toggle_plugin(name, True))
        act_disable.triggered.connect(lambda: self._toggle_plugin(name, False))

        menu.addSeparator()

        # 插件详情（子菜单，只读）
        detail_menu = QMenu("ℹ️ " + self.tr("插件详情"), self)
        detail_menu.addAction(self.tr("名称: {name}").format(
            name=plugin.name)).setEnabled(False)
        detail_menu.addAction(self.tr("版本: {v}").format(
            v=plugin.info.version)).setEnabled(False)
        detail_menu.addAction(self.tr("作者: {a}").format(
            a=plugin.info.author or '-')).setEnabled(False)
        desc = plugin.info.description or self.tr("暂无描述")
        detail_menu.addAction(
            self.tr("描述: {d}").format(d=desc)).setEnabled(False)
        menu.addMenu(detail_menu)

        menu.addSeparator()

        # 打开/关闭窗口
        has_tab = any(t.tabText(i) == name for i in range(t.count()))
        has_detached = name in t._detached_windows
        has_closed = name in self._closed_plugins

        act_open = menu.addAction("🖥 " + self.tr("打开窗口"))
        act_close = menu.addAction("🚫 " + self.tr("关闭窗口"))

        # 窗口操作只有就绪状态才可用
        can_open = lc == PluginLifecycle.READY and (
            has_closed or (not has_tab and plugin.widget is not None))
        act_open.setEnabled(can_open)
        act_close.setEnabled(
            lc == PluginLifecycle.READY and (has_tab or has_detached))

        # 打开日志文件
        act_log = menu.addAction("📋 " + self.tr("打开日志"))

        act_open.triggered.connect(lambda: self._open_plugin_window(name))
        act_close.triggered.connect(lambda: self._close_plugin_window(name))
        act_log.triggered.connect(lambda: self._open_plugin_log(name))

        menu.addSeparator()

        # 设置
        act_settings = menu.addAction("⚙️ " + self.tr("设置..."))
        act_settings.triggered.connect(
            lambda: self._open_plugin_settings(name))

        menu.exec_(self._list.viewport().mapToGlobal(pos))

    def _toggle_plugin(self, name: str, enable: bool) -> None:
        """切换插件启用状态"""
        if enable:
            self._manager.enable_plugin(name)
        else:
            # 禁用时先关闭窗口（处理 detached 窗口清理），再 shutdown
            self._close_plugin_window(name)
            self._manager.disable_plugin(name)
        self._sync_state(name, enabled=enable)
        self._refresh_plugin_list()

    def _open_plugin_window(self, name: str) -> None:
        """打开/恢复插件窗口"""
        plugin = self._manager.plugins.get(name)
        if not plugin or not plugin.widget:
            return

        t = self._tab_widget

        # 如果已弹出为独立窗口，激活它
        if name in t._detached_windows:
            w = t._detached_windows[name]
            w.show()
            w.activateWindow()
            return

        # 如果已有标签页，切换过去
        for i in range(t.count()):
            if t.tabText(i) == name:
                t.setCurrentIndex(i)
                return

        # 从关闭列表中移除并重新打开
        if name in self._closed_plugins:
            self._closed_plugins.discard(name)
            t.add_detachable_tab(plugin.widget, name, icon=plugin.plugin_icon)

    def _close_plugin_window(self, name: str) -> None:
        """关闭插件窗口（不销毁）"""
        t = self._tab_widget

        # 关闭独立窗口 → 取出 widget 后关闭
        if name in t._detached_windows:
            window = t._detached_windows[name]
            lay = window.layout()
            if lay is not None and lay.count() >= 2:
                item = lay.itemAt(1)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        lay.removeWidget(widget)
                        widget.setParent(None)  # type: ignore
            window.blockSignals(True)  # 防止 closeEvent 二次触发
            window.close()
            window.deleteLater()
            del t._detached_windows[name]

        # 关闭标签页
        for i in range(t.count()):
            if t.tabText(i) == name:
                widget = t.widget(i)
                t.removeTab(i)
                widget.hide()
                widget.setParent(None)  # type: ignore
                break

        self._closed_plugins.add(name)
        # 同步状态：窗口模式 → closed
        self._sync_state(name, window_mode=WindowMode.CLOSED)

    def _open_plugin_log(self, name: str) -> None:
        """打开插件日志查看对话框"""
        self._open_log_viewer(initial_log=name)

    def _open_plugin_settings(self, name: str) -> None:
        """打开插件设置对话框"""
        current = self._effective_state(name)
        # 获取插件的 other_info
        plugin = self._manager.plugins.get(name)
        other_info = plugin.other_info if plugin else None

        dlg = PluginSettingsDialog(name, current, other_info, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            new_state = dlg.result_state
            self._state_mgr.set(name, new_state)
            self._state_mgr.save()

            # 应用插件自定义配置
            if other_info:
                dlg.apply_config()
                plugin.save_config()  # type: ignore

            # 立即应用启用/禁用
            if current.enabled != new_state.enabled:
                if new_state.enabled:
                    self._manager.enable_plugin(name)
                else:
                    self._close_plugin_window(name)
                    self._manager.disable_plugin(name)

            # 立即应用窗口模式变化
            if current.window_mode != new_state.window_mode:
                t = self._tab_widget
                if new_state.window_mode == WindowMode.CLOSED:
                    # 关闭窗口
                    self._closed_plugins.add(name)
                    if name in t._detached_windows:
                        # 如果是独立窗口，嵌回标签页然后关闭
                        t._attach_tab(name)
                    self._close_plugin_window(name)
                elif new_state.window_mode == WindowMode.DETACHED:
                    # 弹出为独立窗口
                    self._closed_plugins.discard(name)
                    if name not in t._detached_windows:
                        # 当前是标签页，弹出为独立窗口
                        for i in range(t.count()):
                            if t.tabText(i) == name:
                                t._detach_tab(i, name)
                                break
                else:  # TAB
                    # 嵌回标签页
                    self._closed_plugins.discard(name)
                    if name in t._detached_windows:
                        t._attach_tab(name)

            # 立即应用日志级别
            if plugin and current.log_level != new_state.log_level:
                plugin.set_log_level(new_state.log_level)
            self._refresh_plugin_list()

    # ── 状态持久化辅助 ────────────────────────────────

    def _get_plugin_default_state(self, name: str) -> PluginState | None:
        """从插件的 PluginInfo 读取声明的默认状态"""
        p = self._manager.plugins.get(name)
        if p:
            return PluginState(
                enabled=p.info.enabled,
                show_window=p.info.show_window,
                window_mode=p.info.window_mode,
                log_level=p.info.log_level,
            )
        return None

    def _effective_state(self, name: str) -> PluginState:
        """获取插件的有效状态（JSON 覆盖 > 插件声明 > 系统默认）"""
        return self._state_mgr.get_effective(name, self._get_plugin_default_state(name))

    def _apply_saved_states(self) -> None:
        """
        启动时根据已保存的状态（或插件声明）设置：
        - 启用/禁用
        - 窗口是否显示 + 加载方式
        - 日志级别
        """
        for name, p in self._manager.plugins.items():
            st = self._effective_state(name)

            # 启用/禁用
            if not st.enabled and p.is_enabled:
                self._manager.disable_plugin(name)

            # 窗口加载方式：记录到 _closed_plugins 或稍后处理 detached
            mode = st.window_mode
            if not st.show_window or mode == WindowMode.CLOSED:
                self._closed_plugins.add(name)

            # 日志级别
            try:
                p.set_log_level(st.log_level)
            except Exception:
                pass

    def _sync_state(self, name: str, *, enabled: bool | None = None,
                    window_mode: WindowMode | None = None) -> None:
        """将运行时变化同步到状态管理器（不立即写盘）"""
        st = self._state_mgr.get(name)
        changes = {}
        if enabled is not None:
            changes["enabled"] = enabled
        if window_mode is not None:
            changes["window_mode"] = window_mode
        if changes:
            ns = PluginState(**{**st.__dict__, **changes})
            self._state_mgr.set(name, ns)

    def _on_list_double_clicked(self, item) -> None:
        """双击列表项：打开对应插件窗口"""
        if not item:
            return
        name = item.data(Qt.UserRole)
        self._open_plugin_window(name)

    # ── 标签页弹出/嵌回 ─────────────────────────────────

    def _on_tab_detached(self, name: str) -> None:
        logger.debug(f"Tab detached: {name}")

    def _on_tab_attached(self, name: str) -> None:
        logger.debug(f"Tab attached back: {name}")

    def _on_tab_closed(self, name: str) -> None:
        logger.debug(f"Tab closed: {name}")
        self._closed_plugins.add(name)

    # ── 窗口事件 ────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """关闭主窗口 → 最小化到系统托盘，不退出"""
        if hasattr(self, "_tray_icon") and self._tray_icon.isVisible():
            event.ignore()
            self.hide()
            if self._tray_icon.supportsMessages():
                self._tray_icon.showMessage(
                    self.tr("插件管理器"),
                    self.tr("程序已在系统托盘中运行"),
                    QSystemTrayIcon.Information,
                    2000,
                )
            return

        # 无托盘支持时走原来的确认流程
        reply = QMessageBox.question(
            self,
            self.tr("确认关闭"),
            self.tr("关闭窗口将停止插件管理器，确定吗？"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._state_mgr.save()
            self._manager.stop()
            event.accept()
        else:
            event.ignore()
