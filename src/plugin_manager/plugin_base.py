"""
插件基类定义

每个插件同时具备：
|- 后台数据处理能力（订阅事件、处理数据）
|- 界面交互能力（可选的 PyQt 界面）

注意：插件共享同一个 ZMQClient，事件通过 EventDispatcher 内部分发
每个插件运行在独立线程中（QThread），通过内部队列串行消费事件，保证线程安全
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import Future
import threading
from abc import abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, ClassVar, TypeVar, cast

_E = TypeVar("_E", bound="BaseEvent")
_T = TypeVar("_T")  # 用于服务获取方法的泛型

if TYPE_CHECKING:
    from .config_types import OtherInfoBase

if TYPE_CHECKING:
    from PyQt5.QtGui import QIcon

from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QBrush, QFont

from lib_zmq_plugins.shared.base import BaseEvent, get_event_tag

from .service_registry import ServiceNotFoundError

if TYPE_CHECKING:
    from PyQt5.QtWidgets import QWidget
    from lib_zmq_plugins.client.zmq_client import ZMQClient
    from .event_dispatcher import EventDispatcher


def make_plugin_icon(
    color: str = "#1976d2",
    symbol: str = "?",
    size: int = 64,
) -> QIcon:
    """
    生成插件默认图标的工厂函数

    Args:
        color: 圆形背景颜色（十六进制）
        symbol: 圆心显示的文字/符号
        size: 图标像素尺寸

    Returns:
        生成的 QIcon

    Usage::

        PLUGIN_INFO = PluginInfo(..., icon=make_plugin_icon("#e65100", "📝"))
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)  # type: ignore[attr-defined]

    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    # 圆形背景
    p.setPen(Qt.NoPen)  # type: ignore[attr-defined]
    p.setBrush(QBrush(QColor(color)))
    p.drawEllipse(pix.rect().adjusted(3, 3, -3, -3))

    # 符号文字
    pen = QPen(QColor("white"), 2)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)  # type: ignore[attr-defined]
    font = QFont("Segoe UI Emoji", int(size * 0.44), QFont.Bold)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignCenter | Qt.AlignVCenter, symbol)  # type: ignore[attr-defined]
    p.end()

    return QIcon(pix)


class WindowMode(str):
    """窗口加载方式枚举"""
    TAB = "tab"           # 标签页内加载
    DETACHED = "detached"  # 独立窗口加载
    CLOSED = "closed"      # 不自动加载

    @classmethod
    def _values(cls) -> list[str]:
        return [cls.TAB, cls.DETACHED, cls.CLOSED]

    # 用于 QComboBox 的显示标签映射
    LABELS = {
        TAB: "标签页内",
        DETACHED: "独立窗口",
        CLOSED: "不自动加载",
    }


class _ServiceProxy:
    """
    服务代理对象（内部使用）
    
    拦截属性访问，将方法调用转换为 call_service 调用。
    让插件开发者可以直接通过属性访问方式调用服务方法。
    """
    
    def __init__(self, plugin: "BasePlugin", protocol: type):
        object.__setattr__(self, "_plugin", plugin)
        object.__setattr__(self, "_protocol", protocol)
    
    def __getattr__(self, name: str) -> Any:
        # 返回一个可调用对象，调用时转发到 _call_service
        def _method_call(*args, timeout: float = 10.0, **kwargs) -> Any:
            if kwargs:
                # 如果有 kwargs，不支持（服务方法通常只有位置参数）
                raise TypeError(
                    f"Service method call with keyword arguments is not supported. "
                    f"Use positional arguments: {self._protocol.__name__}.{name}(*args)"
                )
            return self._plugin._call_service(
                self._protocol, name, *args, timeout=timeout
            )
        return _method_call
    
    def __repr__(self) -> str:
        return f"<ServiceProxy: {self._protocol.__name__}>"


class PluginLifecycle(str, Enum):
    """插件生命周期状态"""
    NEW = "NEW"                     # 刚创建，未初始化
    INITIALIZING = "INITIALIZING"   # 线程已启动，on_initialized() 正在执行
    READY = "READY"                 # on_initialized() 完成，正常运行
    SHUTTING_DOWN = "SHUTTING_DOWN" # shutdown() 调用中
    STOPPED = "STOPPED"             # 已停止


class LogLevel(str):
    """日志级别枚举"""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    @classmethod
    def _values(cls) -> list[str]:
        return [cls.TRACE, cls.DEBUG, cls.INFO, cls.WARNING, cls.ERROR]

    # 用于 QComboBox 的显示标签（中文友好）
    LABELS = {
        TRACE: "TRACE (最详细)",
        DEBUG: "DEBUG",
        INFO: "INFO (常规)",
        WARNING: "WARNING",
        ERROR: "ERROR (仅错误)",
    }


@dataclass
class PluginInfo:
    """插件元信息"""

    name: str  # 插件名称
    version: str = "1.0.0"  # 版本号
    author: str = ""  # 作者
    description: str = ""  # 描述
    enabled: bool = True  # 是否启用
    priority: int = 100  # 优先级（数值越小越先执行）
    show_window: bool = True  # 初始化时是否显示窗口
    window_mode: WindowMode = cast(WindowMode, "tab")  # 窗口加载方式
    log_level: LogLevel = cast(LogLevel, "DEBUG")  # 默认日志级别
    icon: QIcon | None = None  # 插件图标，None 使用默认蓝色问号
    log_config: "LogConfig | None" = None  # 日志轮转配置，None 使用全局默认值
    # 插件自定义配置类（继承自 OtherInfoBase）
    other_info: type["OtherInfoBase"] | None = None


class BasePlugin(QThread):
    """
    插件基类（继承 QThread，每个插件运行在独立线程中）

    每个插件同时具备后台数据处理和界面交互能力：
    - 后台部分：订阅事件、处理数据、发送控制指令（在独立线程中执行）
    - 界面部分：可选的 PyQt 界面组件（需通过 run_on_gui 安全访问）

    所有插件共享同一个 ZMQClient，事件通过 EventDispatcher 投递到各插件的队列。
    每个插件的 handler 在自己的线程中**串行**执行，天然线程安全。

    子类必须实现 ``plugin_info()`` 类方法来声明元信息::

        class MyPlugin(BasePlugin):
            @classmethod
            def plugin_info(cls) -> PluginInfo:
                return PluginInfo(
                    name="my_plugin",
                    description="我的插件",
                    icon=make_plugin_icon("#e65100", "📝"),
                )
    """

    # ── GUI 跨线程信号（类级别，所有实例共享连接到各自 slot）──
    gui_call = pyqtSignal(object, object, object)
    ready = pyqtSignal(object)  # 插件就绪信号（参数：插件实例）
    config_changed = pyqtSignal(str, object)  # 配置变化信号（参数：字段名, 新值）

    # 队列最大容量（背压控制）
    MAX_QUEUE_SIZE = 4096

    @classmethod
    @abstractmethod
    def plugin_info(cls) -> PluginInfo:
        """返回插件元信息。子类必须重写此方法。"""

    def __init__(self, info: PluginInfo):
        QThread.__init__(self)

        # 抽象检查：确保子类实现了 plugin_info()
        if type(self).plugin_info is BasePlugin.plugin_info:
            raise TypeError(
                f"Can't instantiate abstract class {type(self).__name__} "
                f"without implementing 'plugin_info()' classmethod"
            )

        self.setObjectName(f"plugin-{info.name}")
        # 保存线程名，在 run() 启动时设到底层 Python 线程
        self._thread_name = f"plugin-{info.name}"

        self._info = info
        self._client: ZMQClient | None = None
        self._event_dispatcher: EventDispatcher | None = None
        self._widget: QWidget | None = None
        self._lifecycle = PluginLifecycle.NEW

        # ── 队列基础设施 ──
        self._event_queue: deque[tuple[Callable[[Any], None], Any]] = deque()
        self._queue_lock = threading.Lock()
        self._queue_event = threading.Event()   # 用于通知新事件入队
        self._stop_requested = threading.Event()
        self._resource_lock = threading.RLock()  # 保护内部共享状态

        # 连接 gui_call 信号到槽（QueuedConnection 跨线程安全）
        self.gui_call.connect(self._on_gui_call, Qt.ConnectionType.QueuedConnection)

        # 每个插件拥有独立的 loguru logger（日志写入 plugins/<name>.log）
        from .logging_setup import get_plugin_logger
        self.logger, self._log_sink_id = get_plugin_logger(
            info.name,
            log_config=info.log_config,
        )
        self._log_level: LogLevel = info.log_level
        
        # 记录本插件注册的服务（用于 shutdown 时自动注销）
        self._registered_protocols: list[type] = []

        # ── 插件自定义配置 ──
        self._other_info: OtherInfoBase | None = None
        self._config_manager: PluginConfigManager | None = None
        if info.other_info is not None:
            from .config_manager import PluginConfigManager
            from .app_paths import get_plugin_data_dir

            # 实例化配置对象
            self._other_info = info.other_info()
            # 设置配置变化回调
            self._other_info.set_on_change(self._on_config_changed)
            # 创建配置管理器
            data_dir = get_plugin_data_dir(type(self))
            self._config_manager = PluginConfigManager(data_dir)
            # 加载配置
            self._config_manager.load(info.name, self._other_info)

    def _on_config_changed(self, name: str, value: Any) -> None:
        """配置变化回调（在配置对象中触发，需转发到主线程发射信号）"""
        # 使用 run_on_gui 确保信号在主线程发射
        self.run_on_gui(self._emit_config_changed, name, value)

    def _emit_config_changed(self, name: str, value: Any) -> None:
        """在主线程发射 config_changed 信号"""
        self.config_changed.emit(name, value)

    # ═══════════════════════════════════════════════════════════════════
    # 属性
    # ═══════════════════════════════════════════════════════════════════

    @property
    def info(self) -> PluginInfo:
        return self._info

    @property
    def name(self) -> str:
        return self._info.name

    @property
    def is_enabled(self) -> bool:
        return self._info.enabled

    @property
    def is_ready(self) -> bool:
        """插件是否真正初始化完成（on_initialized 已执行完毕）"""
        return self._lifecycle == PluginLifecycle.READY

    @property
    def lifecycle(self) -> PluginLifecycle:
        """当前生命周期状态"""
        return self._lifecycle

    @property
    def widget(self) -> QWidget | None:
        return self._widget

    @property
    def client(self) -> ZMQClient | None:
        return self._client

    @property
    def data_dir(self) -> "Path":
        """插件专属数据目录（可写），自动根据插件类名创建"""
        from pathlib import Path
        from .app_paths import get_plugin_data_dir

        if not hasattr(self, "_data_dir"):
            self._data_dir = get_plugin_data_dir(type(self))
        return self._data_dir

    @property
    def log_level(self) -> LogLevel:
        """当前日志级别"""
        return self._log_level

    @property
    def other_info(self) -> OtherInfoBase | None:
        """插件自定义配置对象"""
        return self._other_info

    def save_config(self) -> None:
        """保存插件配置到文件"""
        if self._config_manager and self._other_info:
            self._config_manager.save(self._info.name, self._other_info)
            self.logger.debug(f"Config saved: {self._other_info.to_dict()}")

    def set_log_level(self, level: LogLevel | str) -> None:
        """动态设置插件的日志级别"""
        from .logging_setup import set_plugin_log_level
        if isinstance(level, str):
            level = LogLevel(level.upper())
        self._log_level = level
        set_plugin_log_level(self._log_sink_id, level)
        self.logger.debug(f"Log level changed to {level}")

    @property
    def plugin_icon(self) -> QIcon:
        """返回插件图标（使用 PluginInfo.icon，未设置则生成默认图标）"""
        if self._info.icon:
            return self._info.icon
        return make_plugin_icon()

    # ═══════════════════════════════════════════════════════════════════
    # 线程安全工具
    # ═══════════════════════════════════════════════════════════════════

    @contextmanager
    def locked(self):
        """
        保护内部状态的上下文管理器

        用法::

            with self.locked():
                self._internal_counter += 1
                self._cache.clear()
        """
        with self._resource_lock:
            yield

    def run_on_gui(self, func: Callable[..., None], *args, **kwargs) -> None:
        """
        将函数调用安全地投递到 Qt GUI 主线程执行

        从插件的工作线程（handler）中调用此方法来更新 GUI。
        通过 QueuedConnection 保证跨线程安全。

        Args:
            func: 要在主线程执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        用法::

            def _on_video_save(self, event):
                self._save_to_db(event)           # IO — 直接做
                self.run_on_gui(self.table.refresh)  # GUI — 投递到主线程
        """
        self.gui_call.emit(func, args, kwargs)

    @pyqtSlot(object, object, object)
    def _on_gui_call(
        self,
        func: Callable[..., None],
        args: tuple,
        kwargs: dict,
    ) -> None:
        """GUI 主线程执行的槽：接收来自工作线程的回调请求"""
        try:
            func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"GUI callback error: {e}", exc_info=True)

    # ═══════════════════════════════════════════════════════════════════
    # 线程入口（子类不应覆写）
    # ═══════════════════════════════════════════════════════════════════

    def run(self) -> None:
        """
        插件线程主循环：从队列中取出事件并调用对应的 handler

        此方法由 QThread.start() 调用，子类不应覆写。
        循环逻辑：等待事件 → 取出 → 执行 handler → 异常隔离 → 继续等待
        """
        # 设置 Python 线程名（调试时在 IDE 线程面板/日志中可见）
        threading.current_thread().name = self._thread_name

        self.logger.debug(f"Plugin thread started: {self.name}")

        # 在插件线程中执行初始化回调（可能包含耗时操作：DB、网络等）
        try:
            self.on_initialized()
            self._lifecycle = PluginLifecycle.READY
            self.ready.emit(self)  # 通知 UI 刷新
        except Exception as e:
            self.logger.error(
                f"on_initialized error in '{self.name}': {e}",
                exc_info=True,
            )

        # 初始化期间可能已收到关闭请求，提前退出
        if self._stop_requested.is_set():
            try:
                self.on_shutdown()
            except Exception as e:
                self.logger.error(
                    f"on_shutdown error in '{self.name}': {e}",
                    exc_info=True,
                )
            return

        while not self._stop_requested.is_set():
            # 等待新事件入队或停止信号
            self._queue_event.wait(timeout=0.5)

            # 批量处理队列中的所有事件
            while not self._stop_requested.is_set():
                with self._queue_lock:
                    if not self._event_queue:
                        break
                    handler, event = self._event_queue.popleft()

                try:
                    handler(event)
                except Exception as e:
                    self.logger.error(
                        f"Handler error in '{self.name}': {e}",
                        exc_info=True,
                    )

            self._queue_event.clear()

        # 在插件线程中执行清理回调（可能包含耗时操作：DB 关闭、保存数据等）
        try:
            self.on_shutdown()
        except Exception as e:
            self.logger.error(
                f"on_shutdown error in '{self.name}': {e}",
                exc_info=True,
            )

        self.logger.debug(f"Plugin thread stopped: {self.name}")

    # ═══════════════════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════════════════

    def set_client(self, client: ZMQClient) -> None:
        self._client = client

    def set_event_dispatcher(self, dispatcher: EventDispatcher) -> None:
        self._event_dispatcher = dispatcher

    def initialize(self) -> None:
        """初始化插件并启动事件处理线程（主线程调用，快速返回）"""
        if self._lifecycle not in (PluginLifecycle.NEW, PluginLifecycle.STOPPED):
            return

        self._setup_subscriptions()
        self._widget = self._create_widget()
        self._lifecycle = PluginLifecycle.INITIALIZING

        # 启动插件的事件处理线程（on_initialized 在 run 中执行）
        self._stop_requested.clear()
        self.start()
        self.logger.debug(f"Plugin thread launched: {self.name}")

    def shutdown(self) -> None:
        """关闭插件并停止事件处理线程"""
        if self._lifecycle == PluginLifecycle.STOPPED:
            return

        with self._resource_lock:
            self._lifecycle = PluginLifecycle.SHUTTING_DOWN

        # 通知线程退出
        self._stop_requested.set()
        self._queue_event.set()  # 唤醒可能阻塞的 wait()

        # 等待线程结束（最多 2 秒）
        # on_shutdown 已在 run() 末尾的插件线程中执行
        if not self.wait(2000):
            self.logger.warning(f"Plugin thread did not stop in time: {self.name}")
            self.terminate()  # 强制终止
            # 注意：强制终止可能导致未完成的 Future 永久阻塞
            # 调用方应设置超时并处理 TimeoutError 异常

        if self._event_dispatcher:
            self._event_dispatcher.unsubscribe_all(self)
            
            # 注销本插件注册的所有服务
            for protocol in self._registered_protocols:
                try:
                    self._event_dispatcher.services.unregister(protocol)
                    self.logger.debug(f"Unregistered service: {protocol.__name__}")
                except Exception as e:
                    self.logger.warning(f"Failed to unregister service {protocol.__name__}: {e}")
            self._registered_protocols.clear()

        if self._widget:
            self._widget.deleteLater()
            self._widget = None

        # 清空队列残留事件
        with self._queue_lock:
            self._event_queue.clear()

        # 保存插件配置
        self.save_config()

        with self._resource_lock:
            self._lifecycle = PluginLifecycle.STOPPED

    # ═══════════════════════════════════════════════════════════════════
    # 内部事件投递（由 EventDispatcher 调用）
    # ═══════════════════════════════════════════════════════════════════

    def _enqueue_event(self, handler: Callable[[Any], None], event: Any) -> bool:
        """
        将事件投递到插件队列（由 EventDispatcher 调用）

        此方法是非阻塞的，立即返回。

        Returns:
            True 表示成功入队，False 表示队列已满被丢弃
        """
        with self._queue_lock:
            if len(self._event_queue) >= self.MAX_QUEUE_SIZE:
                self.logger.warning(
                    f"Event queue full ({self.MAX_QUEUE_SIZE}), dropping event"
                )
                return False
            self._event_queue.append((handler, event))

        self._queue_event.set()
        return True

    # ═══════════════════════════════════════════════════════════════════
    # 抽象方法
    # ═══════════════════════════════════════════════════════════════════

    @abstractmethod
    def _setup_subscriptions(self) -> None:
        """
        设置事件订阅

        子类实现此方法，订阅感兴趣的事件：
            self.subscribe(GameStartedEvent, self._on_game_started)
            self.subscribe(BoardUpdateEvent, self._on_board_update)
        """
        pass

    # ═══════════════════════════════════════════════════════════════════
    # 可选重写
    # ═══════════════════════════════════════════════════════════════════

    def _create_widget(self) -> QWidget | None:
        """创建界面组件，返回 None 表示无界面"""
        return None

    def on_initialized(self) -> None:
        """插件初始化完成回调"""
        pass

    def on_shutdown(self) -> None:
        """插件关闭前回调"""
        pass

    # ═══════════════════════════════════════════════════════════════════
    # 事件订阅（使用事件类）
    # ═══════════════════════════════════════════════════════════════════

    def subscribe(
        self,
        event_class: type[_E],
        handler: Callable[[_E], None],
    ) -> None:
        """订阅事件"""
        if self._event_dispatcher:
            tag = get_event_tag(event_class)
            self._event_dispatcher.subscribe(tag, handler, self._info.priority, self)

    def unsubscribe(self, event_class: type[BaseEvent]) -> None:
        """取消订阅事件"""
        if self._event_dispatcher:
            tag = get_event_tag(event_class)
            self._event_dispatcher.unsubscribe(tag, self)

    # ═══════════════════════════════════════════════════════════════════
    # 指令发送
    # ═══════════════════════════════════════════════════════════════════

    def send_command(self, command: Any) -> None:
        """发送控制指令到主进程（异步）"""
        if self._client:
            self._client.send_command(command)

    def request(self, command: Any, timeout: float = 5.0) -> Any:
        """发送请求并等待响应（同步）"""
        if self._client:
            return self._client.request(command, timeout)
        return None

    # ═══════════════════════════════════════════════════════════════════
    # 服务注册（插件间通讯）
    # ═══════════════════════════════════════════════════════════════════

    def register_service(
        self,
        provider: object,
        *,
        protocol: type | None = None,
    ) -> None:
        """
        注册服务（供其他插件调用）
        
        Args:
            provider: 服务提供者实例（通常是 self）
            protocol: 服务接口类型（可选，自动推断）
            
        Raises:
            TypeError: 未实现 Protocol 的所有方法
            
        用法::
        
            class MyPlugin(BasePlugin):
                def on_initialized(self):
                    # 显式指定 protocol
                    self.register_service(self, protocol=MyService)
        """
        if self._event_dispatcher is None:
            self.logger.warning("Cannot register service: no dispatcher")
            return
        
        # 自动推断 protocol
        if protocol is None:
            # 从 provider 的基类中找到 Protocol 子类
            for base in type(provider).__mro__:
                if (
                    base is not object
                    and hasattr(base, "_is_protocol")
                    and base._is_protocol
                ):
                    protocol = base
                    break
        
        if protocol is None:
            self.logger.warning(
                "Cannot register service: no protocol found. "
                "Specify protocol= explicitly or inherit from a Protocol."
            )
            return
        
        # 验证 provider 实现了 Protocol 的所有方法
        missing_methods = self._check_protocol_implementation(provider, protocol)
        if missing_methods:
            raise TypeError(
                f"Cannot register service: {type(provider).__name__} does not implement "
                f"{protocol.__name__}. Missing methods: {', '.join(missing_methods)}"
            )
        
        # 注册服务
        self._event_dispatcher.services.register(protocol, provider, self.name)
        
        # 记录已注册的 protocol（用于 shutdown 时自动注销）
        if protocol not in self._registered_protocols:
            self._registered_protocols.append(protocol)

    def _check_protocol_implementation(
        self,
        provider: object,
        protocol: type,
    ) -> list[str]:
        """
        检查 provider 是否实现了 Protocol 的所有方法
        
        Returns:
            缺失的方法名列表（空列表表示全部实现）
        """
        missing = []
        
        # 获取 Protocol 中定义的所有方法（不包括继承自 object 的）
        for name in dir(protocol):
            if name.startswith('_'):
                continue
            
            attr = getattr(protocol, name, None)
            if attr is None:
                continue
            
            # 检查是否是方法（Callable）
            if callable(attr) or isinstance(attr, property):
                # 检查 provider 是否有该方法
                provider_attr = getattr(type(provider), name, None)
                if provider_attr is None:
                    missing.append(name)
        
        return missing

    def _get_service(self, protocol: type[_T]) -> _T:
        """
        获取服务实例（内部使用）
        
        注意：直接调用服务方法会在调用方线程执行，可能有线程安全问题。
        推荐使用 get_service_proxy() 获取代理对象。
        """
        if self._event_dispatcher is None:
            raise ServiceNotFoundError(protocol)
        
        return self._event_dispatcher.services.get(protocol)

    def _try_get_service(self, protocol: type[_T]) -> _T | None:
        """
        尝试获取服务实例（内部使用）
        
        注意：直接调用服务方法会在调用方线程执行，可能有线程安全问题。
        推荐使用 get_service_proxy() 获取代理对象。
        """
        if self._event_dispatcher is None:
            return None
        
        return self._event_dispatcher.services.try_get(protocol)

    def has_service(self, protocol: type) -> bool:
        """
        检查服务是否可用
        
        Args:
            protocol: 服务接口类型
            
        Returns:
            True 表示服务已注册
        """
        if self._event_dispatcher is None:
            return False
        
        return self._event_dispatcher.services.has(protocol)

    def _call_service(
        self,
        protocol: type,
        method: str,
        *args,
        timeout: float = 10.0,
    ) -> Any:
        """
        调用服务方法（内部实现）
        
        由 _ServiceProxy 调用，插件开发者应使用 get_service_proxy()。
        
        WARNING - 死锁风险:
            如果两个插件互相调用对方的服务（A 调 B 的同时 B 调 A），
            会产生死锁，因为双方队列都在等待对方响应。
            
            避免方法：
            - 使用 call_service_async() 异步调用
            - 设计单向依赖关系，避免循环调用
            - 不要在服务方法实现中调用其他插件的服务
        """
        if self._event_dispatcher is None:
            raise ServiceNotFoundError(protocol)
        
        provider = self._event_dispatcher.services.get(protocol)
        
        # 创建 Future 用于接收结果
        future: Future[Any] = Future()
        
        # 定义在服务提供者线程执行的函数
        def _execute_in_provider_thread(_: Any) -> None:
            try:
                result = getattr(provider, method)(*args)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
        
        # 投递到服务提供者的队列
        success = provider._enqueue_event(_execute_in_provider_thread, None)
        if not success:
            raise RuntimeError(
                f"Failed to enqueue service call: {protocol.__name__}.{method} "
                "(provider queue full)"
            )
        
        # 等待结果
        return future.result(timeout=timeout)

    def call_service_async(
        self,
        protocol: type,
        method: str,
        *args,
    ) -> Future[Any]:
        """
        异步调用服务方法（非阻塞，返回 Future）
        
        Args:
            protocol: 服务接口类型
            method: 方法名
            *args: 方法参数
            
        Returns:
            Future 对象，可调用 result() 获取结果
            
        用法::
        
            future = self.call_service_async(MyService, "some_method", arg1)
            # 做其他事情...
            result = future.result(timeout=5.0)  # 阻塞等待结果
        """
        if self._event_dispatcher is None:
            future: Future[Any] = Future()
            future.set_exception(ServiceNotFoundError(protocol))
            return future
        
        try:
            provider = self._event_dispatcher.services.get(protocol)
        except ServiceNotFoundError as e:
            future = Future()
            future.set_exception(e)
            return future
        
        future: Future[Any] = Future()
        
        def _execute_in_provider_thread(_: Any) -> None:
            try:
                result = getattr(provider, method)(*args)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
        
        success = provider._enqueue_event(_execute_in_provider_thread, None)
        if not success:
            future.set_exception(RuntimeError(
                f"Failed to enqueue service call: {protocol.__name__}.{method} "
                "(provider queue full)"
            ))
        
        return future

    def get_service_proxy(self, protocol: type[_T]) -> _T:
        """
        获取服务代理对象（类型安全，IDE 友好）
        
        返回一个代理对象，通过属性访问方式调用服务方法。
        所有方法调用都会在服务提供者线程执行，线程安全。
        
        Args:
            protocol: 服务接口类型
            
        Returns:
            服务代理对象（IDE 可推断类型，支持方法补全）
            
        用法::
        
            # 获取代理对象
            service = self.get_service_proxy(MyService)
            
            # 直接调用方法（IDE 完整补全）
            result = service.some_method(arg1, arg2)
            count = service.get_count()
            
            # 以上调用等同于：
            # result = self.call_service(MyService, "some_method", arg1, arg2)
            # count = self.call_service(MyService, "get_count")
        """
        return _ServiceProxy(self, protocol)  # type: ignore[return-value]

    # ═══════════════════════════════════════════════════════════════════
    # 辅助
    # ═══════════════════════════════════════════════════════════════════

    def enable(self) -> None:
        """启用插件"""
        self._info.enabled = True
        if self._lifecycle == PluginLifecycle.STOPPED or not self.isRunning():
            self.initialize()

    def disable(self) -> None:
        """禁用插件"""
        self._info.enabled = False
        if self._lifecycle != PluginLifecycle.STOPPED:
            self.shutdown()

    def __repr__(self) -> str:
        return f"<Plugin {self._info.name} v{self._info.version} [{self._lifecycle.value}]>"
