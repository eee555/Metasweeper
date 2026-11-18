# 问题诊断

## 插件未被加载

按顺序排查：

### 1. 检查文件位置
确认 `.py` 文件在正确的目录：
- `plugins/` - 用户插件主目录
- `user_plugins/` - 备用用户插件目录

### 2. 检查命名规则
- 文件名不能以 `_` 开头（如 `_test.py` 会被跳过）
- `services` 目录会被跳过（它是服务接口定义，不是插件）

### 3. 检查基类继承
确认类继承了 `BasePlugin`：
```python
from plugin_sdk import BasePlugin

class MyPlugin(BasePlugin):  # 必须继承 BasePlugin
    ...
```

### 4. 检查必须方法
确认实现了 `plugin_info()` 和 `_setup_subscriptions()`：
```python
@classmethod
def plugin_info(cls) -> PluginInfo:
    return PluginInfo(name="my_plugin", ...)

def _setup_subscriptions(self) -> None:
    ...
```

### 5. 查看错误日志
检查 `data/logs/plugin_manager.log` 中的错误：
```
Failed to load module: xxx
SyntaxError: xxx
ImportError: xxx
```

## GUI 更新导致崩溃

### 症状
- 界面卡死
- 随机崩溃
- "QObject: Cannot create children for a parent that is in a different thread" 错误

### 原因
在事件处理器（工作线程）中直接操作 GUI。

### 解决方案
使用信号槽或 `run_on_gui()`：
```python
# ❌ 错误
def _on_event(self, event):
    self._widget.label.setText("text")  # 崩溃！

# ✅ 正确
def _on_event(self, event):
    self._widget._signal.emit("text")  # 通过信号
    # 或
    self.run_on_gui(self._widget.label.setText, "text")
```

## 事件未触发

### 排查步骤

1. 确认已订阅事件：
```python
def _setup_subscriptions(self) -> None:
    self.subscribe(VideoSaveEvent, self._on_video_save)
```

2. 确认事件类型正确：
```python
from shared_types.events import VideoSaveEvent  # 不是其他名字
```

3. 检查插件是否启用：
- 在插件管理器中查看插件状态
- 确认 `PluginInfo(enabled=True)`

4. 查看日志：
```python
def _on_video_save(self, event):
    self.logger.info("收到事件")  # 确认是否被调用
```

## 导入错误

### 症状
```
ImportError: No module named 'xxx'
ModuleNotFoundError: No module named 'xxx'
```

### 解决方案

**方案 A：使用已安装的库**
只使用 `requirements.txt` 中的依赖：
- PySide6, msgspec, loguru, pyzmq 等

**方案 B：重新打包**
1. 在 `requirements.txt` 中添加依赖
2. 在 `plugin_manager.spec` 的 `hiddenimports` 中添加模块名
3. 重新执行 PyInstaller 打包

**方案 C：放在插件目录**
某些纯 Python 库可以直接放入插件目录中。

**方案 D：手动安装插件依赖（最终用户）**
插件管理器启动时只使用已配置的依赖目录并检查各插件的 `requirements.txt`，不会自动创建虚拟环境或安装包。默认的 `<data_dir>/plugin_libs` 会在启动时创建并启用，可在「设置 → 插件依赖环境」选择其他目录。向普通库目录安装时只接受兼容 wheel。需要安装依赖时，在插件列表右键选择「查看依赖详情」，然后点击「手动安装此插件依赖」。

- `debugpy` 不包含在应用包中；首次启动调试功能时会询问是否安装。
- 插件列表只提示有问题的依赖；详情会显示每项依赖的版本约束、安装版本和状态。用户点击手动安装后，会在非阻塞弹窗中看到 pip 下载输出和结果。
- 依赖环境设置中的「查看已安装的包」会列出当前选定目录的包名和版本，并支持刷新。
- 下载源在依赖环境设置中按行配置；默认是官方 PyPI 和清华镜像，第一行作为主源，其余作为额外源。配置只影响之后由用户手动发起的安装。
- 每个插件自己的 `requirements.txt` 只列应用没有提供的额外第三方依赖。应用和 SDK 已提供的库不要重复列入。
- 所有插件共享该目录；含原生扩展的库需与管理器 Python 版本和系统架构一致。安装依赖需要网络。

## 服务调用失败

### 症状
```
Service not found: MyService
Timeout waiting for service: MyService
```

### 解决方案

1. 确认服务提供者已加载：
```python
def on_initialized(self):
    # 使用 wait_for_service 等待
    self._service = self.wait_for_service(MyService, timeout=10.0)
```

2. 确认服务已注册：
```python
# 服务提供者
def on_initialized(self):
    self.register_service(self, protocol=MyService)
```

3. 检查 Protocol 定义正确：
```python
@runtime_checkable
class MyService(Protocol):
    def method(self) -> ReturnType: ...
```

## 配置不生效

### 症状
- `self.other_info` 为 None
- 配置值没有更新

### 解决方案

1. 确认绑定了配置类：
```python
@classmethod
def plugin_info(cls) -> PluginInfo:
    return PluginInfo(
        name="my_plugin",
        other_info=MyConfig,  # 👈 必须绑定
    )
```

2. 确认访问方式正确：
```python
if self.other_info:  # 先检查是否为 None
    value = self.other_info.some_config
```

3. 检查配置文件：
```
data/plugin_data/<plugin_name>/config.json
```
