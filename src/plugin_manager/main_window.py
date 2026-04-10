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

from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer
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
    QLabel,
    QListWidget,
    QListWidgetItem,
    QListView,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QSystemTrayIcon,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QDialog,
)

from .plugin_state import PluginStateManager, PluginState
from .plugin_base import PluginLifecycle, WindowMode, LogLevel
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

        self.setWindowTitle(f"{plugin_name} - {self.tr('插件')}")
        self.setMinimumSize(400, 300)
        self.resize(600, 450)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 顶部提示栏
        hint_bar = QLabel(self.tr("📎  关闭此窗口可自动嵌回到标签页"))
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
        ):
            distance = (event.globalPos() - self._drag_start_pos).manhattanLength()
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
            window.move(pos)
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
        widget.setParent(None)

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
        widget.setParent(None)
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
            self._status_label.setStyleSheet("color: green; font-weight: bold;")
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
        other_info: "OtherInfoBase | None" = None,
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
        for mode in WindowMode._values():
            label = WindowMode.LABELS.get(mode, mode)
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
        for level in LogLevel._values():
            label = LogLevel.LABELS.get(level, level)
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
# 主窗口
# ═══════════════════════════════════════════════════════════════════

class PluginManagerWindow(QMainWindow):
    """插件管理器主窗口"""

    connection_changed = pyqtSignal(bool)

    def __init__(self, plugin_manager: PluginManager, parent=None):
        super().__init__(parent)

        self._manager = plugin_manager

        # 状态持久化
        self._state_mgr = PluginStateManager(get_data_dir() / "plugin_states.json")
        self._state_mgr.load()

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
        # 主布局：左侧插件列表 + 右侧标签页
        main_splitter = QWidget()
        main_layout = QHBoxLayout(main_splitter)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)

        # ── 左侧：插件列表面板 ──
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(4, 4, 4, 4)

        # 连接状态行
        conn_row = QHBoxLayout()
        conn_row.addWidget(QLabel(self.tr("主进程:")))
        btn = QPushButton(self.tr("连接"))
        btn.setCheckable(True)
        self._conn_btn = btn
        conn_row.addWidget(btn)
        conn_row.addStretch()
        left_layout.addLayout(conn_row)

        # 插件列表
        lst = QListWidget()
        lst.setViewMode(QListView.ListMode)
        lst.setSelectionMode(QListView.SingleSelection)
        lst.setEditTriggers(QListView.NoEditTriggers)
        lst.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list = lst
        left_layout.addWidget(lst)

        # 刷新 + 调试按钮行
        btn_row = QHBoxLayout()
        self._refresh_btn = QPushButton(self.tr("刷新"))
        btn_row.addWidget(self._refresh_btn)
        btn_row.addStretch()

        self._debug_btn = QPushButton("🐛 Debug")
        self._debug_btn.setCheckable(True)
        self._debug_btn.setToolTip(self.tr("开启/关闭远程调试 (debugpy)"))
        btn_row.addWidget(self._debug_btn)

        left_layout.addLayout(btn_row)

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
        QApplication.instance().quit()

    def _connect_signals(self) -> None:
        self._refresh_btn.clicked.connect(self._refresh_plugin_list)
        self._list.itemDoubleClicked.connect(self._on_list_double_clicked)
        self._list.customContextMenuRequested.connect(self._on_list_context_menu)
        self.connection_changed.connect(self._on_conn_changed)

        # 调试开关
        self._debug_btn.toggled.connect(self._toggle_debug)

    # ── 连接状态 ────────────────────────────────────────

    def set_connected(self, ok: bool) -> None:
        self.connection_changed.emit(ok)

    def _on_conn_changed(self, ok: bool) -> None:
        rc = self._manager.reconnect_count
        self._conn_status.set_status(ok, rc)
        self._conn_btn.setChecked(ok)
        self._conn_btn.setText(
            self.tr("已连接") if ok else self.tr("连接")
        )
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

    def _toggle_debug(self, enabled: bool) -> None:
        """开启/关闭 debugpy 远程调试"""
        if enabled:
            self._start_debug()
        else:
            self._stop_debug()

    def _start_debug(self) -> None:
        """启动 debugpy 监听"""
        try:
            import debugpy
            # in_process_debug_adapter=True: 不启动子进程，直接在当前进程中运行 adapter
            # 解决 PyInstaller 打包后子进程找不到 Python/debugpy 的问题
            debugpy.listen(("0.0.0.0", 5678), in_process_debug_adapter=True)
            PluginManagerWindow._debug_active = True
            self._debug_btn.setText("🐛 Listening...")
            self._debug_btn.setStyleSheet("background: #4caf50; color: white; font-weight: bold;")
            self.statusBar().showMessage(self.tr("Debug server listening on port 5678, waiting for VS Code attach..."))
            logger.info("Debug server started on port 5678")
        except ImportError as e:
            self._debug_btn.setChecked(False)
            QMessageBox.warning(
                self, "Debug",
                f"debugpy import failed:\n{e}",
            )
        except Exception as e:
            self._debug_btn.setChecked(False)
            QMessageBox.warning(self, "Debug", f"Failed to start debugger:\n{e}")

    def _stop_debug(self) -> None:
        """停止 debugpy"""
        try:
            import debugpy
            debugpy.stop_listen()
        except Exception:
            pass
        PluginManagerWindow._debug_active = False
        self._debug_btn.setText("🐛 Debug")
        self._debug_btn.setStyleSheet("")
        self.statusBar().showMessage(self.tr("Debug stopped"))
        logger.info("Debug server stopped")

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
                if lst.item(i).data(Qt.UserRole) == current_name:
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
        act_disable.setEnabled(lc == PluginLifecycle.READY and plugin.is_enabled)
        act_enable.triggered.connect(lambda: self._toggle_plugin(name, True))
        act_disable.triggered.connect(lambda: self._toggle_plugin(name, False))

        menu.addSeparator()

        # 插件详情（子菜单，只读）
        detail_menu = QMenu("ℹ️ " + self.tr("插件详情"), self)
        detail_menu.addAction(self.tr("名称: {name}").format(name=plugin.name)).setEnabled(False)
        detail_menu.addAction(self.tr("版本: {v}").format(v=plugin.info.version)).setEnabled(False)
        detail_menu.addAction(self.tr("作者: {a}").format(a=plugin.info.author or '-')).setEnabled(False)
        desc = plugin.info.description or self.tr("暂无描述")
        detail_menu.addAction(self.tr("描述: {d}").format(d=desc)).setEnabled(False)
        menu.addMenu(detail_menu)

        menu.addSeparator()

        # 打开/关闭窗口
        has_tab = any(t.tabText(i) == name for i in range(t.count()))
        has_detached = name in t._detached_windows
        has_closed = name in self._closed_plugins

        act_open = menu.addAction("🖥 " + self.tr("打开窗口"))
        act_close = menu.addAction("🚫 " + self.tr("关闭窗口"))

        # 窗口操作只有就绪状态才可用
        can_open = lc == PluginLifecycle.READY and (has_closed or (not has_tab and plugin.widget is not None))
        act_open.setEnabled(can_open)
        act_close.setEnabled(lc == PluginLifecycle.READY and (has_tab or has_detached))

        # 打开日志文件
        act_log = menu.addAction("📋 " + self.tr("打开日志"))

        act_open.triggered.connect(lambda: self._open_plugin_window(name))
        act_close.triggered.connect(lambda: self._close_plugin_window(name))
        act_log.triggered.connect(lambda: self._open_plugin_log(name))

        menu.addSeparator()

        # 设置
        act_settings = menu.addAction("⚙️ " + self.tr("设置..."))
        act_settings.triggered.connect(lambda: self._open_plugin_settings(name))

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
                        widget.setParent(None)
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
                widget.setParent(None)
                break

        self._closed_plugins.add(name)
        # 同步状态：窗口模式 → closed
        self._sync_state(name, window_mode=WindowMode.CLOSED)

    def _open_plugin_log(self, name: str) -> None:
        """用系统默认程序打开插件日志文件"""
        from .app_paths import get_log_dir
        log_file = get_log_dir() / "plugins" / f"{name}.log"
        if not log_file.exists():
            # 文件不存在时创建一个空文件，避免打开报错
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.touch()
        import subprocess
        import os
        try:
            if os.name == "nt":
                os.startfile(str(log_file))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(log_file)])
        except Exception as e:
            logger.warning(f"Failed to open log file {log_file}: {e}")

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
                plugin.save_config()

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


