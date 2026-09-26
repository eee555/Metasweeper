# 插件模板代码

## 最小可行插件（无 GUI）

```python
"""插件描述"""
from __future__ import annotations

from plugin_sdk import BasePlugin, PluginInfo
from shared_types.events import VideoSaveEvent


class MyPlugin(BasePlugin):
    """插件描述"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="my_plugin",
            version="1.0.0",
            description="插件描述",
            window_mode=WindowMode.CLOSED,  # 无界面
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._on_video_save)

    def on_initialized(self) -> None:
        self.logger.info("MyPlugin 已初始化")

    def _on_video_save(self, event: VideoSaveEvent):
        self.logger.info(f"游戏结束: 用时={event.rtime}s")
```

## 带 GUI 的插件模板

```python
"""插件描述"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal

from plugin_sdk import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from shared_types.events import VideoSaveEvent


class MyPluginWidget(QWidget):
    """插件 UI"""
    
    _update_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        self._title = QLabel("插件标题")
        self._title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self._title)
        
        self._info = QLabel("等待数据...")
        layout.addWidget(self._info)
        
        self._update_signal.connect(self._on_update)

    def _on_update(self, text: str):
        self._info.setText(text)


class MyPlugin(BasePlugin):
    """插件描述"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="my_plugin",
            version="1.0.0",
            author="author",
            description="插件描述",
            window_mode=WindowMode.TAB,
            icon=make_plugin_icon("#4CAF50", "M"),
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._on_video_save)

    def _create_widget(self) -> QWidget | None:
        self._widget = MyPluginWidget()
        return self._widget

    def on_initialized(self) -> None:
        self.logger.info("MyPlugin 已初始化")

    def _on_video_save(self, event: VideoSaveEvent):
        self.logger.info(f"收到游戏数据: 用时={event.rtime}s")
        self._widget._update_signal.emit(f"用时: {event.rtime:.2f}s")
```

## 包形式插件结构

```
plugins/my_plugin/
├── __init__.py     # 插件类定义
├── models.py       # 数据模型
├── widgets.py      # UI 组件
└── utils.py        # 工具函数
```

### `__init__.py` 示例

```python
"""插件包入口"""
from __future__ import annotations

from plugin_sdk import BasePlugin, PluginInfo
from .widgets import MyPluginWidget
from .models import MyDataModel


class MyPlugin(BasePlugin):
    """插件主类"""
    
    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="my_plugin",
            version="1.0.0",
            description="复杂插件示例",
        )
    
    def _setup_subscriptions(self) -> None:
        from shared_types.events import VideoSaveEvent
        self.subscribe(VideoSaveEvent, self._on_video_save)
    
    def _create_widget(self):
        self._widget = MyPluginWidget()
        return self._widget
    
    def on_initialized(self) -> None:
        self._model = MyDataModel(self.data_dir)
        self.logger.info("MyPlugin 已初始化")
    
    def _on_video_save(self, event):
        data = self._model.process(event)
        self._widget.update_data(data)
```

## 带配置的插件模板

```python
from plugin_sdk import BasePlugin, PluginInfo, OtherInfoBase, BoolConfig, IntConfig


class MyConfig(OtherInfoBase):
    """插件配置"""
    
    enable_feature = BoolConfig(
        default=True,
        label="启用功能",
        description="是否启用某功能",
    )
    
    max_count = IntConfig(
        default=100,
        label="最大数量",
        min_value=1,
        max_value=1000,
    )


class MyPlugin(BasePlugin):
    
    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="my_plugin",
            description="带配置的插件",
            other_info=MyConfig,  # 👈 绑定配置类
        )
    
    def on_initialized(self) -> None:
        if self.other_info:
            max_count = self.other_info.max_count
            self.logger.info(f"配置: max_count={max_count}")
    
    def _on_config_changed(self, name: str, value):
        """配置变化时调用"""
        self.logger.info(f"配置变化: {name} = {value}")
```

## 带控制权限的插件模板

```python
from shared_types.commands import NewGameCommand


class MyPlugin(BasePlugin):
    
    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="my_plugin",
            description="需要控制权限的插件",
            required_controls=[NewGameCommand],  # 👈 声明需要的权限
        )
    
    def on_initialized(self) -> None:
        # 检查是否有权限
        if self.has_control_auth(NewGameCommand):
            self.logger.info("已获得 NewGameCommand 权限")
        else:
            self.logger.warning("未获得 NewGameCommand 权限")
    
    def on_control_auth_changed(self, cmd_type, granted: bool):
        """权限变更回调"""
        if cmd_type == NewGameCommand:
            if granted:
                self.logger.info("获得了控制权限")
            else:
                self.logger.warning("失去了控制权限")
    
    def _start_new_game(self):
        if self.has_control_auth(NewGameCommand):
            self.send_command(NewGameCommand(rows=16, cols=30, mines=99))
```
