"""
统计插件主体
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt5.QtCore import QCoreApplication, QUrl, QLibraryInfo, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtQuickWidgets import QQuickWidget
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from plugin_sdk import BasePlugin, PluginInfo, make_plugin_icon, WindowMode, IntConfig
from plugin_sdk.config_types import OtherInfoBase
from plugins.services.history import HistoryService
from shared_types.events import GameFinishedEvent, LanguageChangeEvent

from .bridge import StatsBridge

_translate = QCoreApplication.translate


class StatsConfig(OtherInfoBase):
    """统计插件配置"""
    top_n = IntConfig(
        default=10,
        label=_translate("Form", "前N名平均（0=全部平均）"),
        min_value=0,
        max_value=999,
        step=1,
        description=_translate("Form", "设置0则显示全部平均，设置N则显示前N名的平均值"),
    )
    bv_beginner_min = IntConfig(
        default=2,
        label=_translate("Form", "初级BV最小值"),
        min_value=1,
        max_value=999,
        step=1,
    )
    bv_beginner_max = IntConfig(
        default=54,
        label=_translate("Form", "初级BV最大值"),
        min_value=1,
        max_value=999,
        step=1,
    )
    bv_intermediate_min = IntConfig(
        default=30,
        label=_translate("Form", "中级BV最小值"),
        min_value=1,
        max_value=999,
        step=1,
    )
    bv_intermediate_max = IntConfig(
        default=128,
        label=_translate("Form", "中级BV最大值"),
        min_value=1,
        max_value=999,
        step=1,
    )
    bv_expert_min = IntConfig(
        default=100,
        label=_translate("Form", "高级BV最小值"),
        min_value=1,
        max_value=999,
        step=1,
    )
    bv_expert_max = IntConfig(
        default=288,
        label=_translate("Form", "高级BV最大值"),
        min_value=1,
        max_value=999,
        step=1,
    )


class StatsPlugin(BasePlugin[StatsConfig]):
    """
    统计插件

    - 从 HistoryService 获取历史数据
    - 使用 QML + Qt Charts 绘制统计图表
    - 支持按难度/模式筛选
    """

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name=_translate("Form", "统计"),
            description=_translate("Form", "游戏数据统计与可视化"),
            author="ljzloser",
            version="1.0.0",
            icon=make_plugin_icon("#00897b", "\U0001F4CA"),
            window_mode=WindowMode.TAB,  # type: ignore
            other_info=StatsConfig,
        )

    def __init__(self, info):
        super().__init__(info)
        self._bridge: StatsBridge = None  # type: ignore
        self._quick_widget: QQuickWidget = None  # type: ignore

    def _setup_subscriptions(self) -> None:
        self.subscribe(GameFinishedEvent, self._on_game_finished)
        self.subscribe(LanguageChangeEvent, self._on_language_change)

    def _create_widget(self) -> QWidget:
        # 创建数据桥
        self._bridge = StatsBridge()

        # 创建容器 QWidget
        container = QWidget()
        container.setMinimumSize(600, 400)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建 QQuickWidget
        self._quick_widget = QQuickWidget()
        self._quick_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self._quick_widget.setClearColor(QColor("transparent"))

        # 设置 QML 引擎导入路径
        engine = self._quick_widget.engine()
        qml_import_path = QLibraryInfo.location(QLibraryInfo.Qml2ImportsPath)
        engine.addImportPath(qml_import_path)

        # 注入数据桥到 QML 上下文
        self._quick_widget.rootContext().setContextProperty("bridge", self._bridge)

        # 加载 QML 文件
        qml_dir = Path(__file__).parent / "qml"
        qml_path = qml_dir / "StatsView.qml"
        self._quick_widget.setSource(QUrl.fromLocalFile(str(qml_path)))

        # 检查加载错误
        if self._quick_widget.status() == QQuickWidget.Error:
            for err in self._quick_widget.errors():
                self.logger.error(f"QML 加载错误: {err.toString()}")

        layout.addWidget(self._quick_widget)
        return container

    def on_initialized(self) -> None:
        # 等待 HistoryService 就绪
        history = self.wait_for_service(HistoryService, timeout=15.0)
        if history is None:
            self.logger.warning("HistoryService 未就绪，统计功能不可用")
            return

        # 必须在 GUI 线程设置 history service，因为 dataChanged 信号会触发 QML 刷新
        self.run_on_gui(lambda: self._bridge.set_history_service(history))
        # 同步配置到 bridge
        self._sync_config()
        self.logger.info("统计插件已初始化，HistoryService 已连接")

    def _sync_config(self) -> None:
        """将插件配置同步到 bridge。"""
        if self._bridge:
            top_n = self.other_info.top_n
            self.run_on_gui(lambda: self._bridge.setTopN(top_n))
            cfg = self.other_info
            self.run_on_gui(
                lambda: self._bridge.setBvBeginnerMin(cfg.bv_beginner_min))
            self.run_on_gui(
                lambda: self._bridge.setBvBeginnerMax(cfg.bv_beginner_max))
            self.run_on_gui(lambda: self._bridge.setBvIntermediateMin(
                cfg.bv_intermediate_min))
            self.run_on_gui(lambda: self._bridge.setBvIntermediateMax(
                cfg.bv_intermediate_max))
            self.run_on_gui(
                lambda: self._bridge.setBvExpertMin(cfg.bv_expert_min))
            self.run_on_gui(
                lambda: self._bridge.setBvExpertMax(cfg.bv_expert_max))

    def _on_config_changed(self, name: str, value: Any) -> None:
        """配置变化时同步到 bridge 并刷新。"""
        if not self._bridge:
            return
        mapping = {
            "top_n": self._bridge.setTopN,
            "bv_beginner_min": self._bridge.setBvBeginnerMin,
            "bv_beginner_max": self._bridge.setBvBeginnerMax,
            "bv_intermediate_min": self._bridge.setBvIntermediateMin,
            "bv_intermediate_max": self._bridge.setBvIntermediateMax,
            "bv_expert_min": self._bridge.setBvExpertMin,
            "bv_expert_max": self._bridge.setBvExpertMax,
        }
        setter = mapping.get(name)
        if setter:
            self.run_on_gui(lambda v=value: setter(v))
            self.run_on_gui(self._bridge.refresh)

    def _on_game_finished(self, event: GameFinishedEvent) -> None:
        """游戏结束后延迟刷新统计数据，等待录像保存完成"""
        if self._bridge:
            self.run_on_gui(lambda: QTimer.singleShot(
                2000, self._bridge.refresh))

    def _on_language_change(self, event: LanguageChangeEvent) -> None:
        """语言变化时重新加载 QML"""
        if self._quick_widget:
            def _reload():
                source = self._quick_widget.source()
                self._quick_widget.setSource(QUrl())
                self._quick_widget.setSource(source)
            self.run_on_gui(_reload)
