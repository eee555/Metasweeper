# Level 3: 跨线程 GUI 更新

## 为什么需要跨线程机制？

`BasePlugin` 是 `QObject`（通过 moveToThread 运行在独立线程），事件处理器运行在**插件工作线程**中，但 PySide6 的 GUI 操作只能在**主线程**执行。直接跨线程操作 GUI 会导致未定义行为或崩溃。

## 推荐方式：Signal + 槽函数

因为插件类本身就是 `QObject`，所以可以直接定义信号：

```python
from PySide6.QtCore import Signal

class MyWidget(QWidget):
    # 定义信号
    _update_signal = Signal(str)
    _data_signal = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 连接信号到槽函数
        self._update_signal.connect(self._on_update)
        self._data_signal.connect(self._on_data)
    
    def _on_update(self, text: str):
        """槽函数在主线程执行"""
        self.label.setText(text)
    
    def _on_data(self, data: dict):
        self.table.update_data(data)


class MyPlugin(BasePlugin):
    def _on_video_save(self, event):
        # 工作线程 emit → 自动跨线程到主线程
        self._widget._update_signal.emit(f"用时: {event.rtime:.2f}s")
        self._widget._data_signal.emit({"time": event.rtime})
```

## 备选方式：run_on_gui()

适用于一次性调用、不需要重复连接的场景：

```python
def _on_video_save(self, event):
    # 一次性更新 GUI
    self.run_on_gui(self._widget.update_label, f"用时: {event.rtime}s")
    
    # 带多个参数
    self.run_on_gui(self._widget.update_stats, event.rtime, event.bbbv)
```

## 两种方式对比

| 方式 | 适用场景 | 特点 |
|------|----------|------|
| **Signal + 槽** | 有固定 UI 需反复更新 | **推荐**。声明式，类型签名清晰 |
| **run_on_gui()** | 临时/一次性 UI 调用 | 灵活但可读性略差 |

## 错误示例

```python
# ❌ 错误：直接在事件处理器中操作 GUI
def _on_video_save(self, event):
    self._widget.label.setText(f"用时: {event.rtime}s")  # 崩溃！

# ❌ 错误：在 _create_widget 中做耗时操作
def _create_widget(self):
    time.sleep(5)  # 卡住 UI 加载
    return MyWidget()
```

## 正确示例

```python
class MyWidget(QWidget):
    _update = Signal(str)

    def __init__(self):
        super().__init__()
        self._update.connect(self._do_update)
    
    def _do_update(self, text):
        self.label.setText(text)


class MyPlugin(BasePlugin):
    def _create_widget(self):
        self._widget = MyWidget()
        return self._widget
    
    def _on_video_save(self, event):
        # ✅ 正确：通过信号更新 GUI
        self._widget._update.emit(f"用时: {event.rtime:.2f}s")
```

## 底层原理

两种方式底层原理相同 —— 都是通过 Qt 的 `QueuedConnection` 将调用投递到主线程的事件循环中，确保 GUI 操作在主线程执行。
