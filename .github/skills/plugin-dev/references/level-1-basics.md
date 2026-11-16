# Level 1: 基础概念

## BasePlugin 基类

所有插件都必须继承 `BasePlugin` 类：

```python
from plugin_sdk import BasePlugin, PluginInfo


class MyPlugin(BasePlugin):
    ...
```

## 必须实现的方法

### 1. `plugin_info()` - 插件元信息

```python
@classmethod
def plugin_info(cls) -> PluginInfo:
    return PluginInfo(
        name="my_plugin",           # 唯一标识（必填）
        version="1.0.0",            # 版本号
        description="插件描述",      # 描述
        author="author",            # 作者
        enabled=True,               # 默认是否启用
        priority=100,               # 优先级（越小越先处理事件）
        show_window=True,           # 初始化时显示窗口
        window_mode=WindowMode.TAB, # 窗口模式
    )
```

### 2. `_setup_subscriptions()` - 事件订阅

```python
def _setup_subscriptions(self) -> None:
    from shared_types.events import VideoSaveEvent
    self.subscribe(VideoSaveEvent, self._on_video_save)
```

## 可选实现的方法

### `_create_widget()` - 创建 GUI

```python
def _create_widget(self) -> QWidget | None:
    """返回插件界面，None 表示无界面"""
    self._widget = MyWidget()
    return self._widget
```

### `on_initialized()` - 初始化回调

```python
def on_initialized(self) -> None:
    """在插件线程中执行，可做耗时操作"""
    self.logger.info("插件已初始化")
    # 数据库初始化、网络连接等
```

### `on_shutdown()` - 关闭清理

```python
def on_shutdown(self) -> None:
    """插件关闭前执行清理"""
    self.logger.info("插件正在关闭...")
    # 释放资源、保存数据等
```

## 插件生命周期

```
plugin_info()           # 返回元信息
    ↓
实例化 BasePlugin
    ↓
initialize()            # 启动插件线程
    ↓
_setup_subscriptions()  # 注册事件订阅
    ↓
_create_widget()        # 创建 UI（主线程）
    ↓
_thread.start()         # QThread 事件循环开始运行
    ↓
on_initialized()        # 【工作线程】初始化回调
    ↓
═══ 进入事件循环 ═══
    ↓
shutdown()              # 请求停止
    ↓
on_shutdown()           # 【工作线程】清理回调
    ↓
STOPPED
```

## BasePlugin 核心属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.info` | `PluginInfo` | 插件元信息 |
| `self.name` | `str` | 插件名称 |
| `self.data_dir` | `Path` | **插件专属数据目录** |
| `self.logger` | `Logger` | **已绑定的日志器** |
| `self.widget` | `QWidget` | UI 组件（如果有） |
| `self.other_info` | `OtherInfoBase` | 配置对象（如果有） |

## WindowMode 窗口模式

| 模式 | 行为 |
|------|------|
| `WindowMode.TAB` | 嵌入主窗口标签页 |
| `WindowMode.DETACHED` | 独立窗口（可拖回标签页） |
| `WindowMode.CLOSED` | 不自动创建窗口 |
