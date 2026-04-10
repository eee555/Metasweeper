"""
Hello World 示例插件

演示基本的事件订阅、pyqtSignal 跨线程 GUI 更新。
"""
from __future__ import annotations

from typing import Any

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QDial
from PyQt5.QtCore import pyqtSignal, Qt

from plugin_manager import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from plugin_manager.config_types import (
    OtherInfoBase,
    BoolConfig,
    IntConfig,
    FloatConfig,
    ChoiceConfig,
    TextConfig,
    ColorConfig,
    FileConfig,
    PathConfig,
    LongTextConfig,
    RangeConfig,
    BaseConfig,
)
from shared_types.events import VideoSaveEvent


# ═══════════════════════════════════════════════════════════════════
# 自定义配置类型示例
# ═══════════════════════════════════════════════════════════════════


class DialConfig(BaseConfig[int]):
    """
    自定义配置类型: 旋钮控件 → QDial
    
    演示如何继承 BaseConfig 创建自定义配置类型
    """
    widget_type = "dial"
    
    def __init__(
        self,
        default: int = 50,
        label: str = "",
        min_value: int = 0,
        max_value: int = 100,
        notch_step: int = 10,
        **kwargs,
    ):
        super().__init__(default, label, **kwargs)
        self.min_value = min_value
        self.max_value = max_value
        self.notch_step = notch_step
    
    def create_widget(self):
        """创建 QDial 控件，返回 (控件, getter, setter, 信号)"""
        from PyQt5.QtCore import QObject
        
        widget = QDial()
        widget.setRange(self.min_value, self.max_value)
        widget.setValue(int(self.default))
        widget.setNotchesVisible(True)
        widget.setSingleStep(self.notch_step)
        widget.setPageStep(self.notch_step * 2)
        widget.setMinimumSize(60, 60)
        widget.setMaximumSize(100, 100)
        
        if self.description:
            widget.setToolTip(self.description)
        
        # 返回控件、getter、setter、以及 valueChanged 信号
        return widget, widget.value, widget.setValue, widget.valueChanged
    
    def to_storage(self, value: int) -> int:
        return int(value)
    
    def from_storage(self, data: Any) -> int:
        try:
            return int(data)
        except (ValueError, TypeError):
            return int(self.default)


# ═══════════════════════════════════════════════════════════════════
# 插件配置 - 包含所有配置类型示例
# ═══════════════════════════════════════════════════════════════════


class HelloPluginConfig(OtherInfoBase):
    """
    Hello World 插件配置
    
    包含所有支持的配置类型示例
    """

    # ── BoolConfig: 布尔值 → QCheckBox ────────────────
    enable_auto_log = BoolConfig(
        default=True,
        label="自动记录日志",
        description="收到事件时自动记录到日志",
    )
    show_timestamp = BoolConfig(
        default=True,
        label="显示时间戳",
        description="在日志中显示时间戳",
    )

    # ── IntConfig: 整数 → QSpinBox ────────────────────
    max_log_lines = IntConfig(
        default=100,
        label="最大日志行数",
        description="保留的最大日志行数",
        min_value=10,
        max_value=1000,
        step=10,
    )
    refresh_interval = IntConfig(
        default=5,
        label="刷新间隔(秒)",
        description="自动刷新的间隔时间",
        min_value=1,
        max_value=60,
    )

    # ── FloatConfig: 浮点数 → QDoubleSpinBox ──────────
    min_rtime_filter = FloatConfig(
        default=0.0,
        label="最小时间筛选(秒)",
        description="只记录大于此时间的游戏",
        min_value=0.0,
        max_value=999.0,
        decimals=2,
    )
    zoom_factor = FloatConfig(
        default=1.0,
        label="缩放因子",
        description="UI 缩放比例",
        min_value=0.5,
        max_value=2.0,
        step=0.1,
        decimals=1,
    )

    # ── ChoiceConfig: 选择 → QComboBox ────────────────
    log_level = ChoiceConfig(
        default="INFO",
        label="日志级别",
        description="日志显示级别",
        choices=[
            ("DEBUG", "DEBUG"),
            ("INFO", "INFO"),
            ("WARNING", "WARNING"),
            ("ERROR", "ERROR"),
        ],
    )
    display_mode = ChoiceConfig(
        default="compact",
        label="显示模式",
        choices=[
            ("compact", "紧凑"),
            ("detailed", "详细"),
            ("minimal", "极简"),
        ],
    )

    # ── TextConfig: 文本 → QLineEdit ──────────────────
    player_name = TextConfig(
        default="",
        label="玩家名称",
        placeholder="输入玩家名称...",
    )
    api_token = TextConfig(
        default="",
        label="API Token",
        description="用于远程同步的认证令牌",
        password=True,
        placeholder="输入密钥...",
    )

    # ── ColorConfig: 颜色 → 颜色选择按钮 ──────────────
    theme_color = ColorConfig(
        default="#4CAF50",
        label="主题颜色",
        description="插件的主题颜色",
    )
    highlight_color = ColorConfig(
        default="#FF5722",
        label="高亮颜色",
        description="重要信息的高亮颜色",
    )

    # ── FileConfig: 文件 → 文件选择器 ────────────────
    export_file = FileConfig(
        default="",
        label="导出文件",
        description="日志导出文件路径",
        filter="Text Files (*.txt);;JSON Files (*.json)",
        save_mode=True,
    )
    import_file = FileConfig(
        default="",
        label="导入文件",
        description="导入配置文件",
        filter="JSON Files (*.json)",
    )

    # ── PathConfig: 目录 → 目录选择器 ────────────────
    log_directory = PathConfig(
        default="",
        label="日志目录",
        description="日志文件保存目录",
    )
    cache_directory = PathConfig(
        default="",
        label="缓存目录",
        description="临时缓存文件目录",
    )

    # ── LongTextConfig: 多行文本 → QTextEdit ────────
    welcome_message = LongTextConfig(
        default="欢迎使用 Hello World 插件！",
        label="欢迎消息",
        placeholder="输入欢迎消息...",
        max_height=80,
    )
    custom_script = LongTextConfig(
        default="",
        label="自定义脚本",
        description="自定义处理脚本（Python 代码）",
        placeholder="# 在此输入 Python 代码...",
        max_height=120,
    )

    # ── RangeConfig: 数值范围 → 两个 QSpinBox ──────
    rtime_range = RangeConfig(
        default=(0, 300),
        label="时间范围(秒)",
        description="只记录此时间范围内的游戏",
        min_value=0,
        max_value=999,
    )
    bbbv_range = RangeConfig(
        default=(0, 999),
        label="3BV 范围",
        description="只记录此 3BV 范围内的游戏",
        min_value=0,
        max_value=9999,
    )

    # ── 自定义配置类型: DialConfig → QDial ─────────────
    volume = DialConfig(
        default=50,
        label="音量",
        description="自定义旋钮控件示例",
        min_value=0,
        max_value=100,
        notch_step=10,
    )
    sensitivity = DialConfig(
        default=5,
        label="灵敏度",
        description="响应灵敏度设置",
        min_value=1,
        max_value=10,
        notch_step=1,
    )


# ═══════════════════════════════════════════════════════════════════
# UI 组件
# ═══════════════════════════════════════════════════════════════════


class HelloWidget(QWidget):
    """简单的 UI 界面"""

    _update_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0

        layout = QVBoxLayout(self)

        self._title = QLabel("Hello World Plugin")
        self._title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(self._title)

        self._info = QLabel("Waiting for game data...")
        layout.addWidget(self._info)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)

        self._update_signal.connect(self._append_log)

    def _append_log(self, text: str):
        """Slot: executed on main thread"""
        self._log.append(text)
        self._count += 1
        self._info.setText(f"Received {self._count} record(s)")


# ═══════════════════════════════════════════════════════════════════
# 插件主体
# ═══════════════════════════════════════════════════════════════════


class HelloPlugin(BasePlugin):

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="hello_world",
            version="1.0.0",
            author="Example",
            description="Hello World - demonstrates event subscription and pyqtSignal GUI update",
            icon=make_plugin_icon("#4CAF50", "H", 64),
            window_mode=WindowMode.TAB,
            other_info=HelloPluginConfig,
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._on_video_save)

    def _create_widget(self) -> QWidget:
        self._widget = HelloWidget()
        return self._widget

    def on_initialized(self) -> None:
        self.logger.info("HelloPlugin initialized")
        if self.other_info:
            self.logger.info(f"配置: {self.other_info.to_dict()}")
            # 连接配置变化信号
            self.config_changed.connect(self._on_config_changed)

    def _on_config_changed(self, name: str, value) -> None:
        """配置变化时的回调"""
        self.logger.info(f"配置变化: {name} = {value}")

    def on_shutdown(self) -> None:
        self.logger.info("HelloPlugin shutting down")

    def _on_video_save(self, event: VideoSaveEvent):
        self.logger.info(
            f"Game: time={event.rtime}s, level={event.level}, "
            f"3BV={event.bbbv}, L={event.left} R={event.right}"
        )
        info_text = (
            f"[{event.rtime:.2f}s] {event.level} | "
            f"3BV={event.bbbv} | L={event.left} R={event.right}"
        )
        # pyqtSignal emit -> auto QueuedConnection cross-thread to main thread
        self._widget._update_signal.emit(info_text)