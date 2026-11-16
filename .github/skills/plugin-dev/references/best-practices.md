# 最佳实践

## 核心原则

| 实践 | 原因 |
|------|------|
| IO 操作放在 `on_initialized()` 或事件处理器 | 在工作线程执行，不阻塞 UI |
| GUI 操作用信号槽或 `run_on_gui()` | 跨线程安全，避免崩溃 |
| 使用 `self.logger` 而非 `print()` | 自动分文件、支持过滤、自动轮转 |
| 使用 `self.data_dir` 存储数据 | 自动处理打包/开发模式路径差异 |
| 在 `on_shutdown()` 释放资源 | 避免资源泄漏 |
| 给插件起唯一的 name | 用于日志、数据目录、UI 标识 |

## 日志记录

```python
# ✅ 正确：使用 self.logger
def _handle_event(self, event):
    self.logger.info(f"处理事件: {event.rtime}s")
    self.logger.debug("详细调试信息")
    self.logger.warning("警告信息")
    self.logger.error("错误信息")

# ❌ 错误：使用 print
def _handle_event(self, event):
    print("处理事件")  # 不会记录到日志文件
```

日志会自动输出到：
- `data/logs/<plugin_name>.log` - 插件专属日志
- `data/logs/main.log` - 主日志

## 数据存储

```python
def on_initialized(self):
    # ✅ 正确：使用 self.data_dir
    db_path = self.data_dir / "my_data.db"
    config_path = self.data_dir / "settings.json"
    
    # 目录会自动创建
    # 打包后和开发模式下路径不同，但 self.data_dir 会自动处理

# ❌ 错误：硬编码路径
def on_initialized(self):
    db_path = Path("data/my_plugin/my_data.db")  # 打包后路径可能不对
```

## 线程安全

```python
from PySide6.QtCore import Signal

class MyWidget(QWidget):
    # ✅ 正确：定义信号
    _update_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self._update_signal.connect(self._do_update)
    
    def _do_update(self, text):
        self.label.setText(text)


class MyPlugin(BasePlugin):
    def _handle_event(self, event):
        # ✅ 正确：通过信号更新 GUI
        self._widget._update_signal.emit(f"数据: {event.rtime}")
        
        # 或使用 run_on_gui（一次性调用）
        self.run_on_gui(self._widget.update_data, event.rtime)
```

## 资源管理

```python
class MyPlugin(BasePlugin):
    def on_initialized(self):
        # 初始化资源
        self._db = sqlite3.connect(self.data_dir / "data.db")
        self._network = NetworkClient()
    
    def on_shutdown(self):
        # ✅ 正确：释放资源
        self._db.close()
        self._network.disconnect()
        self.logger.info("资源已释放")
```

## 配置管理

```python
class MyConfig(OtherInfoBase):
    # ✅ 正确：合理的默认值
    max_records = IntConfig(
        default=100,
        label="最大记录数",
        min_value=10,
        max_value=10000,
    )

class MyPlugin(BasePlugin):
    def on_initialized(self):
        # ✅ 正确：检查配置是否存在
        if self.other_info:
            max_records = self.other_info.max_records
        
        # ✅ 正确：监听配置变化
        self.config_changed.connect(self._on_config_changed)
```

## 错误处理

```python
def _handle_event(self, event):
    try:
        result = self._process_data(event)
        self._widget._signal.emit(result)
    except Exception as e:
        # ✅ 正确：记录错误，不影响其他插件
        self.logger.error(f"处理失败: {e}", exc_info=True)
```

## 性能优化

```python
# ✅ 正确：耗时操作在工作线程
def _handle_event(self, event):
    # 这些都在工作线程执行，不阻塞 UI
    data = self._heavy_computation(event)
    self._db.insert(data)
    self._widget._signal.emit(data)

# ❌ 错误：耗时操作在主线程
def _create_widget(self):
    time.sleep(5)  # 卡住 UI 加载
    return MyWidget()
```

## 调试技巧

```python
def _handle_event(self, event):
    # 临时添加调试日志
    self.logger.debug(f"event type: {type(event)}")
    self.logger.debug(f"event data: {msgspec.structs.asdict(event)}")
    
    # 正常处理
    ...
```

VS Code 调试：
1. 点击界面上的 🐛 Debug 按钮
2. VS Code → 运行和调试 → 附加到进程 → 选 plugin_manager.exe
3. 在插件代码打断点调试
