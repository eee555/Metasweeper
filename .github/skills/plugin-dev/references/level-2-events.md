# Level 2: 事件系统

事件类型与字段以 `src/shared_types/events.py` 为准。本节与当前协议保持一致。

## 订阅事件

在 `_setup_subscriptions()` 中订阅感兴趣的事件：

```python
def _setup_subscriptions(self) -> None:
    from shared_types.events import GameFinishedEvent, BoardUpdateEvent

    self.subscribe(GameFinishedEvent, self._on_game_finished)
    self.subscribe(BoardUpdateEvent, self._on_board_update)
```

## 可用事件类型

### GameFinishedEvent（tag: `game_end`）

游戏结束、重开或离开游戏状态时触发。录像二进制数据位于 `raw_data`，类型为 `bytes`，不是 base64 文本。

```python
def _on_game_finished(self, event: GameFinishedEvent) -> None:
    event.rtime          # 用时（秒）
    event.level          # 难度：3 初级、4 中级、5 高级、6 自定义
    event.game_state     # 状态索引：0–10，定义见 shared_types.enums.GameBoardState
    event.left           # 左键次数
    event.right          # 右键次数
    event.double         # 双击次数
    event.cl             # 总点击数
    event.ce             # 有效点击数
    event.bbbv           # 总 3BV
    event.bbbv_solved    # 已解决 3BV
    event.raw_data       # EVF4 二进制数据（bytes）
    event.mode           # 游戏模式
```

`VideoSaveEvent` 是旧版文档中的名称；当前协议使用 `GameFinishedEvent`，tag 为 `game_end`。

### BoardUpdateEvent（tag: `board_update`）

棋盘状态更新时触发，字段为 `rows`、`cols`、`game_board`、`mines_remaining` 和 `game_time`：

```python
def _on_board_update(self, event: BoardUpdateEvent) -> None:
    board = event.game_board  # 二维数组
    rows = event.rows
    cols = event.cols
    remaining = event.mines_remaining
    elapsed = event.game_time
```

其它事件包括 `GameStatusChangeEvent`、`ButtonClickEvent`、`CloseEvent`、`ShowPluginManagerEvent` 和 `LanguageChangeEvent`。字段定义与序列化注册见 `shared_types.events.EVENT_TYPES`。

## 取消订阅

```python
def _some_method(self):
    self.unsubscribe(GameFinishedEvent)
```

## 事件处理器注意事项

**重要**: 事件处理器在**插件工作线程**中执行：

- ✅ 可以做 IO 操作（数据库、文件）
- ✅ 可以做耗时计算
- ❌ 不能直接操作 GUI（会导致崩溃）
- ✅ 更新 GUI 必须使用信号槽或 `run_on_gui()`

## 事件处理流程

```
主进程触发事件
    ↓
ZMQ 发送到插件管理器
    ↓
EventDispatcher 分发
    ↓
各插件的 handler 被调用（在工作线程）
    ↓
handler 处理数据
    ↓
（如需更新 GUI）通过信号槽投递到主线程
```
