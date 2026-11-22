"""
插件管理器主类

作为独立进程运行，管理所有插件的加载、生命周期和通信
所有插件共享同一个 ZMQClient，事件通过 EventDispatcher 内部分发
"""
from __future__ import annotations

import atexit
import os
import signal
import sys
import threading
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import loguru
import msgspec
from PySide6.QtCore import QCoreApplication, QObject, QThread, Qt, Signal, Slot
from lib_zmq_plugins.client.zmq_client import ZMQClient
from lib_zmq_plugins.log import LogHandler
from lib_zmq_plugins.shared.base import BaseEvent, SyncCommand, get_event_tag

from shared_types import COMMAND_TYPES, EVENT_TYPES, QUERY_RESULT_TYPES, QUERY_TYPES
from shared_types.events import LanguageChangeEvent

from .event_dispatcher import EventDispatcher
from plugin_sdk.plugin_base import BasePlugin
from .plugin_loader import PluginLoader
from .dependency_scan import PluginDependencyStatus
from .app_paths import get_all_plugin_dirs, get_bundle_dir, get_data_dir, patch_sys_path_for_frozen
from .plugin_lib_env import apply_plugin_lib_dir, dependency_environment_requires_restart
from .plugin_uninstall import is_managed_plugin
from .plugin_state import PluginState, PluginStateManager
from .settings_manager import SettingsManager
from .translations import TranslationManager
from .plugin_data_transfer import (
    DataTransferResult,
    export_plugin,
    export_plugins,
    import_plugin,
    import_plugins,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QWidget
    from .restart import RestartView

logger = loguru.logger.bind(name="PluginManager")


class _GuiExecutor(QObject):
    """将事件投递和连接状态更新送到同一个 Qt 应用线程。"""
    _requested = Signal(object)

    def __init__(self):
        super().__init__()
        app = QCoreApplication.instance()
        if app is not None and self.thread() != app.thread():
            self.moveToThread(app.thread())
        self._requested.connect(self._execute, Qt.ConnectionType.QueuedConnection)

    def submit(self, action: Callable[[], None]) -> None:
        if QCoreApplication.instance() is None or QThread.currentThread() == self.thread():
            action()
        else:
            self._requested.emit(action)

    @Slot(object)
    def _execute(self, action: Callable[[], None]) -> None:
        action()


class _LogHandler(LogHandler):
    def debug(self, msg: str, /, *args: object, **kwargs: object) -> None:
        logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, /, *args: object, **kwargs: object) -> None:
        logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, /, *args: object, **kwargs: object) -> None:
        logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, /, *args: object, **kwargs: object) -> None:
        logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, /, *args: object, **kwargs: object) -> None:
        logger.critical(msg, *args, **kwargs)


class PluginManager:
    """
    插件管理器

    核心设计：
    - 所有插件共享一个 ZMQClient
    - 事件通过 EventDispatcher 内部分发给各插件
    - 支持动态加载插件
    - 拥有独立的 PyQt 主窗口
    """

    # 共享的 Manager 实例（用于信号处理器和 atexit 回调）
    _instance: "PluginManager | None" = None
    _LANGUAGE_SYNC_INTERVAL = 5.0
    _LANGUAGE_SYNC_TIMEOUT = 2.0

    def __init__(
        self,
        endpoint: str,
        plugin_dirs: list[Path] | None = None,
        log_handler: LogHandler | None = None,
        pub_endpoint: str | None = None,
        ctrl_endpoint: str | None = None,
    ):
        self._endpoint = endpoint
        self._log = log_handler

        # 打包模式路径补丁
        patch_sys_path_for_frozen()

        # 默认插件目录
        if plugin_dirs is None:
            plugin_dirs = get_all_plugin_dirs()

        # 共享的 Client（主进程随机端口模式会显式传入真实 PUB/CTRL 端点）
        self._client = ZMQClient(
            endpoint=endpoint,
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
            log_handler=log_handler,
            pub_endpoint=pub_endpoint,
            ctrl_endpoint=ctrl_endpoint,
        )
        self._dispatcher = EventDispatcher()
        self._loader = PluginLoader(plugin_dirs)

        # 插件依赖库目录：必须在加载任何插件之前加入 sys.path
        self._settings = SettingsManager(get_data_dir())
        apply_plugin_lib_dir(self._settings.plugin_lib_dir)

        # 插件管理
        self._plugins: dict[str, BasePlugin] = {}
        self._plugins_lock = threading.RLock()
        self.state_manager = PluginStateManager(get_data_dir() / "plugin_states.json")
        self.state_manager.load()

        # 启动时只缓存事件，接收线程仍可处理插件初始化发出的查询响应。
        # 单一 drainer 在锁外投递；清空队列和交还所有权在同一锁内完成，
        # 避免实时事件越过启动缓冲，也允许分发回调重入/关闭管理器。
        self._events_lock = threading.Lock()
        self._pending_events: deque[tuple[str, BaseEvent]] = deque()
        self._events_ready = False
        self._events_draining = False
        self._starting = False
        self._language_source_id = ""
        self._language_revision = 0
        self._retired_language_sources: set[str] = set()
        self._language_sync_stop = threading.Event()
        self._language_sync_wakeup = threading.Event()
        self._language_sync_thread: threading.Thread | None = None
        self._gui_executor: _GuiExecutor | None = None

        # 主窗口
        self._main_window = None
        self._app = None
        self._translator_installer = None
        # 启动期收到 ShowPluginManagerEvent 但窗口尚未创建时置位，
        # 由 start_with_gui() 在创窗后重放。
        self._show_requested_pending = False

        # 注册类型
        self._client.register_event_types(*EVENT_TYPES)
        self._client.register_command_types(*COMMAND_TYPES)
        self._client.register_query_types(
            *QUERY_TYPES, result_types=tuple(QUERY_RESULT_TYPES))

        self._started = False
        self._shutdown_requested = False

        # 注册自身为共享实例
        PluginManager._instance = self

        # 注册信号处理和 atexit
        self._register_shutdown_handlers()

    # ═══════════════════════════════════════════════════════════════════
    # 属性
    # ═══════════════════════════════════════════════════════════════════

    @property
    def client(self) -> ZMQClient:
        return self._client

    @property
    def dispatcher(self) -> EventDispatcher:
        return self._dispatcher

    @property
    def plugins(self) -> dict[str, BasePlugin]:
        return self._plugins.copy()

    @property
    def main_window(self):
        return self._main_window

    @property
    def settings(self) -> SettingsManager:
        return self._settings

    @property
    def is_connected(self) -> bool:
        """当前连接状态"""
        return self._client.is_connected

    @property
    def reconnect_count(self) -> int:
        """重连次数"""
        return self._client.reconnect_count

    @property
    def connection_endpoint(self) -> str:
        """连接端点地址"""
        return self._endpoint

    # ═══════════════════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════════════════

    def _register_shutdown_handlers(self) -> None:
        """注册信号处理和 atexit 回调，确保优雅退出"""

        def handle_signal(signum: int, frame) -> None:
            sig_name = signal.Signals(signum).name
            logger.info(f"收到信号 {sig_name}，开始优雅关闭...")
            self._graceful_shutdown()
            if sys.platform != "win32":
                # 主线程可能停在 Qt 事件循环可中断点：处理器返回后事件循环
                # 会继续运行，进程永远无法自然退出，父进程只能等满超时后
                # 强杀（表现为关闭卡顿）。优雅关闭已完成，直接结束进程。
                os._exit(0)

        # 注册 SIGTERM 信号处理（父进程 terminate() 会发送此信号）
        signal.signal(signal.SIGTERM, handle_signal)

        # 注册 SIGINT 信号处理（Ctrl+C）
        signal.signal(signal.SIGINT, handle_signal)

        # 注册 atexit 回调作为兜底
        atexit.register(self._graceful_shutdown)

        if sys.platform == "win32":
            return  # Windows 上 terminate() 为强制结束，无需以下机制

        # 非 Windows：主线程阻塞在 Qt(Cocoa) 事件循环的 C 代码里时，
        # Python 层信号处理器不会被执行，SIGTERM 将永远无法触发关闭。
        # set_wakeup_fd 的写入发生在 C 层、不受阻塞影响，由看门狗线程
        # 读取后代为执行优雅关闭并退出进程。
        wakeup_read_fd, wakeup_write_fd = os.pipe()
        os.set_blocking(wakeup_write_fd, False)
        signal.set_wakeup_fd(wakeup_write_fd)

        def _signal_watchdog() -> None:
            try:
                os.read(wakeup_read_fd, 1)
            except OSError:
                return
            logger.info("信号触发优雅关闭（看门狗线程）...")
            self._graceful_shutdown()
            os._exit(0)  # 主线程仍在事件循环中，直接结束进程

        threading.Thread(
            target=_signal_watchdog, name="SignalWatchdog", daemon=True,
        ).start()

    def _graceful_shutdown(self) -> None:
        """关闭事件入口并丢弃缓冲，再清理资源；已开始的投递不强行中断。"""
        with self._events_lock:
            if self._shutdown_requested:
                return
            self._shutdown_requested = True
            self._events_ready = False
            self._pending_events.clear()

        self._language_sync_stop.set()
        self._language_sync_wakeup.set()
        logger.info("开始优雅关闭...")

        # 1. 关闭所有插件（让插件保存状态等）
        self._shutdown_plugins()

        # 2. 兜底落盘插件状态（脏状态可能来自 UI 操作，未显式保存）
        try:
            self.state_manager.save()
        except Exception as e:
            logger.error(f"保存插件状态失败: {e}")

        # 3. 断开 ZMQ 连接
        try:
            self._client.disconnect()
        except Exception as e:
            logger.error(f"断开 ZMQ 连接失败: {e}")

        # disconnect 会唤醒正在等响应的同步线程；避免停止后遗留后台任务。
        sync_thread = self._language_sync_thread
        if sync_thread is not None and sync_thread is not threading.current_thread():
            sync_thread.join(timeout=3.0)

        # 4. 清理事件分发器和翻译器；跨线程关闭时由应用线程执行移除。
        self._dispatcher.clear()
        if self._translator_installer is not None:
            self._translator_installer.close()

        self._started = False
        logger.info("优雅关闭完成")

    def start(self) -> None:
        """连接后初始化插件，再释放事件；失败关闭本实例，不支持停止后重启。"""
        with self._events_lock:
            if self._shutdown_requested:
                raise RuntimeError("Cannot restart a stopped plugin manager")
            if self._started or self._starting:
                return
            self._starting = True

        try:
            # 两者归属同一应用线程，翻译安装完成后才继续分发队列。
            self._gui_executor = _GuiExecutor()
            self._translator_installer = TranslationManager()

            self._load_plugins()
            self._apply_saved_plugin_states()
            self._refresh_plugin_translations()
            # 在 connect 启动接收线程前注册回调，覆盖首次快照和实时事件。
            self._setup_zmq_subscriptions()
            if self._shutdown_requested:
                return
            self._client.connect()
            if self._shutdown_requested:
                return
            self._start_language_sync()
            # initialize 同步注册订阅并启动 QThread；on_initialized 异步执行。
            self._initialize_plugins()
            if self._shutdown_requested:
                return
            self._validate_control_authorizations()
            self._release_startup_events()

            with self._events_lock:
                if self._shutdown_requested:
                    return
                self._started = True
            logger.info("Plugin manager started")
        except BaseException:
            self._graceful_shutdown()
            raise
        finally:
            with self._events_lock:
                self._starting = False

    def _validate_control_authorizations(self) -> None:
        """验证控制授权配置，清除无效插件的授权"""
        from plugin_sdk.control_auth import ControlAuthorizationManager

        auth_manager = ControlAuthorizationManager.instance()

        # 获取已加载的插件名称
        loaded_plugins = set(self._plugins.keys())

        # 验证并清除无效授权
        removed = auth_manager.validate_authorizations(loaded_plugins)

        if removed:
            logger.warning(f"控制授权已清除（插件未加载）: {removed}")

        # 保存更新后的配置
        auth_manager.save()

    def stop(self) -> None:
        """停止插件管理器（调用优雅关闭）"""
        self._graceful_shutdown()

    def start_with_gui(self, app: QApplication = None, *, show_main_window: bool = True,
                       restart_view: RestartView | None = None) -> None:  # type: ignore
        """
        启动插件管理器并显示主界面

        Args:
            app: QApplication 实例，如果不提供则创建新的
            show_main_window: 是否显示主窗口（False 时仅在托盘运行）
            restart_view: 接替进程需要恢复的界面状态
        """
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
        from .app_paths import get_bundle_dir
        from .main_window import PluginManagerWindow

        # 创建或使用现有的 QApplication
        if app is None:
            app = QApplication.instance()
            if app is None:
                app = QApplication([])

        app_icon = QIcon(str(get_bundle_dir() / "media" / "plugin_manager.ico"))
        if app_icon.isNull():
            from .icons import action_icon
            app_icon = action_icon("app")
        app.setWindowIcon(app_icon)
        self._app = app

        # 启动核心功能
        self.start()

        # 创建主窗口（始终创建以支持托盘图标）
        window = PluginManagerWindow(self)
        if restart_view is not None and restart_view.active_tab is not None:
            window.restore_restart_tab(restart_view.active_tab)
        # 与 _drain_zmq_events 的判空/置位在同一把锁内完成，
        # 避免「drainer 看到窗口为空置位 pending」与「此处清空 pending」交错丢失请求。
        with self._events_lock:
            self._main_window = window
            pending_show = self._show_requested_pending
            self._show_requested_pending = False
        if show_main_window and restart_view is None:
            window.show()

        # start() 期间（窗口尚不存在）收到的显示请求在此重放。
        if pending_show or (show_main_window and restart_view is not None):
            window._show_requested.emit()

        logger.info(
            f"Plugin manager started with GUI (window={show_main_window})")

    def exec_gui(self, *, show_main_window: bool = True, restart_view: RestartView | None = None) -> int:
        """
        启动 GUI 事件循环

        Args:
            show_main_window: 是否显示主窗口（False 时仅在托盘运行）
            restart_view: 接替进程需要恢复的界面状态

        Returns:
            退出代码
        """
        if self._app is None:
            restoration = {"restart_view": restart_view} if restart_view is not None else {}
            self.start_with_gui(show_main_window=show_main_window, **restoration)

        result = self._app.exec()
        self.stop()
        return result

    # ═══════════════════════════════════════════════════════════════════
    # ZMQ 订阅（使用事件类）
    # ═══════════════════════════════════════════════════════════════════

    def _refresh_plugin_translations(self, include: str | None = None) -> None:
        if self._translator_installer is None:
            return
        catalogs = {}
        with self._plugins_lock:
            for name, plugin in self._plugins.items():
                if plugin.is_enabled or name == include:
                    path = self._loader.get_plugin_translation_dir(name)
                    if path is not None:
                        catalogs[name] = path
        self._translator_installer.set_catalogs(catalogs)

    def _setup_zmq_subscriptions(self) -> None:
        """设置 ZMQ 事件订阅"""
        for event_type in EVENT_TYPES:
            tag = get_event_tag(event_type)
            self._client.subscribe(
                event_type,
                lambda event, t=tag: self._queue_zmq_event(t, event),
            )

    def _accept_language_event(self, event: LanguageChangeEvent) -> bool:
        """在入口锁内过滤跨 PUB/CTRL 通道迟到的快照、实时事件和重复同步。"""
        if not event.source_id or event.revision <= 0:
            return not getattr(self, "_language_source_id", "")
        if event.source_id in self._retired_language_sources:
            return False
        if event.source_id != self._language_source_id:
            if self._language_source_id:
                self._retired_language_sources.add(self._language_source_id)
            self._language_source_id = event.source_id
            self._language_revision = 0
        if event.revision <= self._language_revision:
            return False
        self._language_revision = event.revision
        return True

    def _post_gui(self, action: Callable[[], None]) -> None:
        executor = getattr(self, "_gui_executor", None)
        if executor is None:
            action()
        else:
            executor.submit(action)

    def _queue_zmq_event(self, tag: str, event: BaseEvent) -> None:
        with self._events_lock:
            if self._shutdown_requested:
                return
            if isinstance(event, LanguageChangeEvent) and not self._accept_language_event(event):
                return
            self._pending_events.append((tag, event))
            if not self._events_ready or self._events_draining:
                return
            self._events_draining = True
        self._post_gui(self._drain_zmq_events)

    def _release_startup_events(self) -> None:
        with self._events_lock:
            if self._shutdown_requested:
                return
            self._events_ready = True
            if self._events_draining:
                return
            self._events_draining = True
        self._post_gui(self._drain_zmq_events)

    def _drain_zmq_events(self) -> None:
        from shared_types.events import ShowPluginManagerEvent

        while True:
            with self._events_lock:
                if self._shutdown_requested or not self._pending_events:
                    self._events_draining = False
                    return
                tag, event = self._pending_events.popleft()

            # 不持有入口锁：回调可查询、接收新事件或触发 stop()。
            try:
                if isinstance(event, LanguageChangeEvent):
                    # 同步完成就迭代继续；异步完成回调保留并交还 drainer 所有权。
                    if not self._on_language_change(event):
                        return
                elif isinstance(event, ShowPluginManagerEvent):
                    with self._events_lock:
                        window = self._main_window
                        if window is None:
                            # 窗口尚未创建（start() 早于 start_with_gui() 创窗），
                            # 记录待显示请求，创窗后重放。
                            self._show_requested_pending = True
                    if window is not None:
                        window._show_requested.emit()
                else:
                    self._dispatcher.dispatch(tag, event)
            except Exception:
                logger.exception(f"Failed to dispatch event '{tag}'")

    # ═══════════════════════════════════════════════════════════════════
    # 插件管理
    # ═══════════════════════════════════════════════════════════════════

    def add_plugin_dir(self, path: str | Path) -> None:
        self._loader.add_plugin_dir(path)

    def _load_plugins(self) -> None:
        plugins = self._loader.load_all()
        self._register_plugins(plugins)
        logger.info(f"Loaded {len(plugins)} plugin(s)")

    def _register_plugins(self, plugins: list[BasePlugin]) -> None:
        with self._plugins_lock:
            for plugin in plugins:
                self._plugins[plugin.name] = plugin
                plugin.set_client(self._client)
                plugin.set_event_dispatcher(self._dispatcher)
                stopped = getattr(plugin, "stopped", None)
                if stopped is not None:
                    stopped.connect(self._on_plugin_stopped)

    def load_installed_package(self, package: Path, prepare: Callable[[BasePlugin], None]) -> str:
        """Load one newly installed package on the Qt application thread."""
        if not self._started or self._shutdown_requested:
            return "restart"
        if (dependency_environment_requires_restart()
                or SettingsManager(get_data_dir()).plugin_lib_dir != self._settings.plugin_lib_dir
                or self._loader.was_imported(package.name)):
            return "restart"
        if not is_managed_plugin(package):
            return "failed"
        try:
            with self._plugins_lock:
                registered = set(self._plugins)
            plugins = self._loader.load_new_package(package.resolve(), registered)
            if not plugins:
                return "failed"
            with self._plugins_lock:
                if self._shutdown_requested:
                    return "restart"
                self._register_plugins(plugins)
            for plugin in plugins:
                self._apply_saved_plugin_state(plugin)
                prepare(plugin)
            self._refresh_plugin_translations()
            results = [self._initialize_plugin(plugin) for plugin in plugins]
        except Exception:
            logger.exception("Could not load newly installed plugin package {}", package)
            return "failed"
        return "loaded" if all(results) else "failed"

    def _on_plugin_stopped(self, plugin: BasePlugin) -> None:
        if not self._shutdown_requested and not plugin.is_enabled:
            self._refresh_plugin_translations()

    def _apply_saved_plugin_states(self) -> None:
        """在创建窗口、启动插件线程之前应用持久化启用状态。"""
        for plugin in self._plugins.values():
            self._apply_saved_plugin_state(plugin)

    def _apply_saved_plugin_state(self, plugin: BasePlugin) -> None:
        info = plugin.info
        state = self.state_manager.get_effective(plugin.name, PluginState(
            enabled=info.enabled, show_window=info.show_window,
            window_mode=info.window_mode, log_level=info.log_level,
        ))
        info.enabled = state.enabled
        try:
            plugin.set_log_level(state.log_level)
        except (ValueError, TypeError):
            logger.warning(f"Invalid saved log level for {plugin.name}: {state.log_level}")
            plugin.set_log_level(info.log_level)

    def _initialize_plugins(self) -> None:
        with self._plugins_lock:
            for plugin in self._plugins.values():
                if self._shutdown_requested:
                    break
                self._initialize_plugin(plugin)

    def _initialize_plugin(self, plugin: BasePlugin) -> bool:
        try:
            if plugin.is_enabled:
                plugin.initialize()
                logger.info(f"Initialized plugin: {plugin.name}")
        except Exception:
            logger.exception("Failed to initialize plugin {}", plugin.name)
            return False
        return True

    def _shutdown_plugins(self) -> None:
        with self._plugins_lock:
            for plugin in self._plugins.values():
                try:
                    plugin.shutdown()
                    logger.info(f"Shutdown plugin: {plugin.name}")
                except Exception as e:
                    logger.error(
                        f"Failed to shutdown plugin {plugin.name}: {e}", exc_info=True)

    def get_plugin(self, name: str) -> BasePlugin | None:
        return self._plugins.get(name)

    def export_plugin_data(self, output: Path, *,
                           progress: Callable[[str], None] | None = None) -> DataTransferResult:
        """Export every loaded plugin into one manager-level ZIP archive."""
        with self._plugins_lock:
            plugins = dict(self._plugins)
        return export_plugins(plugins, output, progress=progress)

    def import_plugin_data(self, source: Path, *,
                           progress: Callable[[str], None] | None = None) -> DataTransferResult:
        """Import plugin data from a manager-level ZIP archive."""
        with self._plugins_lock:
            plugins = dict(self._plugins)
        return import_plugins(plugins, source, progress=progress)

    def export_single_plugin_data(
            self, name: str, output: Path,
            *, progress: Callable[[str], None] | None = None) -> DataTransferResult:
        """Export one plugin's own ZIP for its list context menu."""
        with self._plugins_lock:
            plugin = self._plugins.get(name)
        if plugin is None:
            raise KeyError(f"Unknown plugin: {name}")
        if progress:
            progress(f"导出插件数据：{name}")
        return export_plugin(plugin, name, output)

    def import_single_plugin_data(
            self, name: str, source: Path,
            *, progress: Callable[[str], None] | None = None) -> DataTransferResult:
        """Import one plugin's own ZIP for its list context menu."""
        with self._plugins_lock:
            plugin = self._plugins.get(name)
        if plugin is None:
            raise KeyError(f"Unknown plugin: {name}")
        if progress:
            progress(f"导入插件数据：{name}")
        return import_plugin(plugin, name, source)

    @property
    def module_dependency_statuses(self) -> dict[str, PluginDependencyStatus]:
        """所有已扫描模块的状态快照，包括导入失败的模块。"""
        return self._loader.module_dependency_statuses

    def get_module_dependency_status(self, module_name: str) -> PluginDependencyStatus | None:
        return self._loader.get_module_dependency_status(module_name)

    def get_plugin_dependency_status(self, plugin_name: str) -> PluginDependencyStatus | None:
        return self._loader.get_plugin_dependency_status(plugin_name)

    def enable_plugin(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        if plugin:
            # enable() 会立即创建窗口，先安装对应翻译。
            self._refresh_plugin_translations(include=name)
            try:
                plugin.enable()
            finally:
                self._refresh_plugin_translations()
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        if plugin:
            plugin.disable()
            self._refresh_plugin_translations()
            return True
        return False

    # ═══════════════════════════════════════════════════════════════════
    # 界面管理
    # ═══════════════════════════════════════════════════════════════════

    def get_plugin_widgets(self) -> dict[str, QWidget]:
        widgets = {}
        with self._plugins_lock:
            for name, plugin in self._plugins.items():
                if plugin.widget:
                    widgets[name] = plugin.widget
        return widgets

    # ═══════════════════════════════════════════════════════════════════
    # ZMQ 回调
    # ═══════════════════════════════════════════════════════════════════

    def _on_language_change(self, event: LanguageChangeEvent) -> bool:
        # TranslationManager 在应用线程同步完成；无 GUI / 测试适配器也可异步完成。
        # 用握手区分两者，避免连续语言快照递归调用 drain 而耗尽调用栈。
        completion_lock = threading.Lock()
        installing = True
        completed = False

        def finished() -> None:
            nonlocal completed
            try:
                if not self._shutdown_requested:
                    self._dispatcher.dispatch(get_event_tag(LanguageChangeEvent), event)
            except Exception:
                logger.exception("Failed to dispatch language change")
            finally:
                with completion_lock:
                    completed = True
                    resume = not installing
                if resume:
                    self._post_gui(self._drain_zmq_events)

        try:
            if self._translator_installer is None:
                finished()
            else:
                self._translator_installer.install(event.language, finished)
        except BaseException:
            with completion_lock:
                installing = False
            raise
        with completion_lock:
            installing = False
            return completed

    def _start_language_sync(self) -> None:
        with self._events_lock:
            if self._shutdown_requested or self._language_sync_thread is not None:
                return
            worker = threading.Thread(
                target=self._language_sync_loop, name="PluginLanguageSync", daemon=True,
            )
            worker.start()
            self._language_sync_thread = worker

    def _language_sync_loop(self) -> None:
        """复用 __sync__，修复失败快照或订阅建立期间遗漏的 PUB 更新。

        单个后台线程等待响应，I/O 线程和 GUI 线程均不阻塞；重复版本在入口丢弃。
        连接回调立即唤醒，之后每 5 秒校准一次。关闭时 disconnect 会取消等待中的请求。
        """
        tag = get_event_tag(LanguageChangeEvent)
        while not self._language_sync_stop.is_set():
            self._language_sync_wakeup.wait(timeout=self._LANGUAGE_SYNC_INTERVAL)
            self._language_sync_wakeup.clear()
            if self._language_sync_stop.is_set():
                return
            if not self._client.is_connected:
                continue
            try:
                response = self._client.request(
                    SyncCommand(topic=tag), timeout=self._LANGUAGE_SYNC_TIMEOUT)
                if response.success and response.data:
                    event = msgspec.msgpack.decode(response.data, type=LanguageChangeEvent)
                    self._queue_zmq_event(tag, event)
            except Exception:
                if not self._language_sync_stop.is_set():
                    logger.debug("Language snapshot unavailable; will retry")

    def _set_connection_state(self, connected: bool) -> None:
        if not self._shutdown_requested and self._main_window:
            self._main_window.set_connected(connected)

    def _on_connected(self) -> None:
        logger.info("Connected to main process")
        self._language_sync_wakeup.set()
        self._post_gui(lambda: self._set_connection_state(True))

    def _on_disconnected(self) -> None:
        logger.warning("Disconnected from main process")
        self._post_gui(lambda: self._set_connection_state(False))

    def __repr__(self) -> str:
        return f"<PluginManager: {len(self._plugins)} plugins, started={self._started}>"


def run_plugin_manager_process(
    endpoint: str,
    plugin_dirs: list[str] | None = None,
    with_gui: bool = True,
    show_main_window: bool = True,
    pub_endpoint: str | None = None,
    ctrl_endpoint: str | None = None,
    host_pid: int | None = None,
    restart_view: RestartView | None = None,
) -> int:
    """
    在独立进程中运行插件管理器

    Args:
        endpoint: ZMQ Server 基准地址（用于显示/兼容）
        plugin_dirs: 插件目录列表
        with_gui: 是否显示界面（False 为完全无界面后台模式）
        show_main_window: 是否显示主窗口（False 时 GUI 仅显示托盘图标）
        pub_endpoint: 主进程实际绑定的 PUB 端点（随机端口模式由命令行传入）
        ctrl_endpoint: 主进程实际绑定的 CTRL 端点（随机端口模式由命令行传入）
        restart_view: 接替进程需要恢复的界面状态

    Returns:
        退出代码
    """
    manager = PluginManager(
        endpoint=endpoint, plugin_dirs=plugin_dirs, log_handler=_LogHandler(),  # type: ignore
        pub_endpoint=pub_endpoint, ctrl_endpoint=ctrl_endpoint,
    )

    from .host_lifetime import HostLifetime
    host = HostLifetime(host_pid) if host_pid else None
    timer = None
    try:
        if host is not None and not host.is_alive():
            return 0
        if with_gui:
            restoration = {"restart_view": restart_view} if restart_view is not None else {}
            if host is not None:
                manager.start_with_gui(show_main_window=show_main_window, **restoration)
                from PySide6.QtCore import QTimer
                timer = QTimer(manager._app)
                timer.timeout.connect(lambda: manager._app.quit() if not host.is_alive() else None)
                timer.start(500)
            return manager.exec_gui(show_main_window=show_main_window, **restoration)
        else:
            manager.start()
            while host is None or host.is_alive():
                import time
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if timer is not None:
            timer.stop()
        manager.stop()
        if host is not None:
            host.close()

    return 0
