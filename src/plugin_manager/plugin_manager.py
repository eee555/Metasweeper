"""
插件管理器主类

作为独立进程运行，管理所有插件的加载、生命周期和通信
所有插件共享同一个 ZMQClient，事件通过 EventDispatcher 内部分发
"""
from __future__ import annotations

import atexit
import signal
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import loguru
from lib_zmq_plugins.client.zmq_client import ZMQClient
from lib_zmq_plugins.log import LogHandler
from lib_zmq_plugins.shared.base import BaseEvent, get_event_tag
from PySide6.QtCore import QObject, Qt, Signal

from shared_types import EVENT_TYPES, COMMAND_TYPES
from shared_types.events import LanguageChangeEvent

from .event_dispatcher import EventDispatcher
from plugin_sdk.plugin_base import BasePlugin
from .plugin_loader import PluginLoader
from .app_paths import get_all_plugin_dirs, patch_sys_path_for_frozen

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QWidget

logger = loguru.logger.bind(name="PluginManager")


class _TranslatorInstaller(QObject):
    """线程安全地在主线程安装 QTranslator"""
    _signal = Signal(str)

    def __init__(self):
        super().__init__()
        self._translator = None
        self._signal.connect(self._install, Qt.QueuedConnection)

    def install(self, language: str) -> None:
        self._signal.emit(language)

    def _install(self, language: str) -> None:
        from PySide6.QtCore import QCoreApplication, QTranslator
        app = QCoreApplication.instance()
        if app is None:
            return
        if self._translator is not None:
            app.removeTranslator(self._translator)
            self._translator = None
        if language != "zh_CN":
            qm_path = Path(__file__).resolve().parent.parent / f"{language}.qm"
            if qm_path.exists():
                self._translator = QTranslator()
                self._translator.load(str(qm_path))
                app.installTranslator(self._translator)


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

    def __init__(
        self,
        endpoint: str,
        plugin_dirs: list[Path] | None = None,
        log_handler: LogHandler | None = None,
    ):
        self._endpoint = endpoint
        self._log = log_handler

        # 打包模式路径补丁
        patch_sys_path_for_frozen()

        # 默认插件目录
        if plugin_dirs is None:
            plugin_dirs = get_all_plugin_dirs()

        # 共享的 Client
        self._client = ZMQClient(
            endpoint=endpoint,
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
            log_handler=log_handler,
        )
        self._dispatcher = EventDispatcher()
        self._loader = PluginLoader(plugin_dirs)

        # 插件管理
        self._plugins: dict[str, BasePlugin] = {}
        self._plugins_lock = threading.RLock()

        # 主窗口
        self._main_window = None
        self._app = None
        self._translator_installer = None

        # 注册类型
        self._client.register_event_types(*EVENT_TYPES)
        self._client.register_command_types(*COMMAND_TYPES)

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

        # 注册 SIGTERM 信号处理（父进程 terminate() 会发送此信号）
        signal.signal(signal.SIGTERM, handle_signal)

        # 注册 SIGINT 信号处理（Ctrl+C）
        signal.signal(signal.SIGINT, handle_signal)

        # 注册 atexit 回调作为兜底
        atexit.register(self._graceful_shutdown)

    def _graceful_shutdown(self) -> None:
        """优雅关闭：调用所有插件的 shutdown 方法，然后清理资源"""
        if self._shutdown_requested:
            return
        self._shutdown_requested = True

        logger.info("开始优雅关闭...")

        # 1. 关闭所有插件（让插件保存状态等）
        self._shutdown_plugins()

        # 2. 断开 ZMQ 连接
        try:
            self._client.disconnect()
        except Exception as e:
            logger.error(f"断开 ZMQ 连接失败: {e}")

        # 3. 清理事件分发器
        self._dispatcher.clear()

        self._started = False
        logger.info("优雅关闭完成")

    def start(self) -> None:
        """启动插件管理器（后台模式，无界面）"""
        if self._started:
            return

        # 在主线程创建，确保 QueuedConnection 投递到主线程事件循环
        self._translator_installer = _TranslatorInstaller()

        self._load_plugins()
        self._client.connect()
        self._setup_zmq_subscriptions()
        self._initialize_plugins()
        self._validate_control_authorizations()

        self._started = True
        logger.info("Plugin manager started")

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

    def start_with_gui(self, app: QApplication = None, *, show_main_window: bool = True) -> None:  # type: ignore
        """
        启动插件管理器并显示主界面

        Args:
            app: QApplication 实例，如果不提供则创建新的
            show_main_window: 是否显示主窗口（False 时仅在托盘运行）
        """
        from PySide6.QtWidgets import QApplication
        from .main_window import PluginManagerWindow

        # 创建或使用现有的 QApplication
        if app is None:
            app = QApplication.instance()
            if app is None:
                app = QApplication([])

        self._app = app

        # 启动核心功能
        self.start()

        # 创建主窗口（始终创建以支持托盘图标）
        self._main_window = PluginManagerWindow(self)
        self._main_window.setWindowTitle(f"插件管理器 - {self._endpoint}")
        if show_main_window:
            self._main_window.show()

        logger.info(
            f"Plugin manager started with GUI (window={show_main_window})")

    def exec_gui(self, *, show_main_window: bool = True) -> int:
        """
        启动 GUI 事件循环

        Args:
            show_main_window: 是否显示主窗口（False 时仅在托盘运行）

        Returns:
            退出代码
        """
        if self._app is None:
            self.start_with_gui(show_main_window=show_main_window)

        result = self._app.exec()
        self.stop()
        return result

    # ═══════════════════════════════════════════════════════════════════
    # ZMQ 订阅（使用事件类）
    # ═══════════════════════════════════════════════════════════════════

    def _install_translator(self, language: str) -> None:
        """在插件进程的 QApplication 上安装对应语言的翻译器（线程安全）"""
        if self._translator_installer is None:
            self._translator_installer = _TranslatorInstaller()
        self._translator_installer.install(language)

    def _setup_zmq_subscriptions(self) -> None:
        """设置 ZMQ 事件订阅"""
        from shared_types.events import ShowPluginManagerEvent
        for event_type in EVENT_TYPES:
            if event_type is ShowPluginManagerEvent or event_type is LanguageChangeEvent:
                continue
            tag = get_event_tag(event_type)
            # 订阅 ZMQ 事件，收到后分发给内部插件
            self._client.subscribe(
                event_type,
                lambda event, t=tag: self._dispatcher.dispatch(t, event),
            )
        self._client.subscribe(
            ShowPluginManagerEvent,
            lambda _: self._main_window._show_requested.emit() if self._main_window else None,
        )
        self._client.subscribe(
            LanguageChangeEvent,
            self._on_language_change,
        )

    # ═══════════════════════════════════════════════════════════════════
    # 插件管理
    # ═══════════════════════════════════════════════════════════════════

    def add_plugin_dir(self, path: str | Path) -> None:
        self._loader.add_plugin_dir(path)

    def _load_plugins(self) -> None:
        plugins = self._loader.load_all()

        with self._plugins_lock:
            for plugin in plugins:
                self._plugins[plugin.name] = plugin
                plugin.set_client(self._client)
                plugin.set_event_dispatcher(self._dispatcher)

        logger.info(f"Loaded {len(plugins)} plugin(s)")

    def _initialize_plugins(self) -> None:
        with self._plugins_lock:
            for plugin in self._plugins.values():
                try:
                    if plugin.is_enabled:
                        plugin.initialize()
                        logger.info(f"Initialized plugin: {plugin.name}")
                except Exception as e:
                    logger.error(
                        f"Failed to initialize plugin {plugin.name}: {e}", exc_info=True)

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

    def enable_plugin(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        if plugin:
            plugin.enable()
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        if plugin:
            plugin.disable()
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

    def _on_language_change(self, event: LanguageChangeEvent) -> None:
        self._install_translator(event.language)
        tag = get_event_tag(LanguageChangeEvent)
        self._dispatcher.dispatch(tag, event)

    def _on_connected(self) -> None:
        logger.info("Connected to main process")
        if self._main_window:
            self._main_window.set_connected(True)

    def _on_disconnected(self) -> None:
        logger.warning("Disconnected from main process")
        if self._main_window:
            self._main_window.set_connected(False)

    def __repr__(self) -> str:
        return f"<PluginManager: {len(self._plugins)} plugins, started={self._started}>"


def run_plugin_manager_process(
    endpoint: str,
    plugin_dirs: list[str] | None = None,
    with_gui: bool = True,
    show_main_window: bool = True,
) -> int:
    """
    在独立进程中运行插件管理器

    Args:
        endpoint: ZMQ Server 地址
        plugin_dirs: 插件目录列表
        with_gui: 是否显示界面（False 为完全无界面后台模式）
        show_main_window: 是否显示主窗口（False 时 GUI 仅显示托盘图标）

    Returns:
        退出代码
    """
    manager = PluginManager(
        endpoint=endpoint, plugin_dirs=plugin_dirs, log_handler=_LogHandler()  # type: ignore
    )

    try:
        if with_gui:
            return manager.exec_gui(show_main_window=show_main_window)
        else:
            manager.start()
            while True:
                import time
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop()

    return 0
