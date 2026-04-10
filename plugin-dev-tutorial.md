# Meta-Minesweeper 插件开发教程（PyInstaller 打包版 + VS Code）

> 本教程面向 **PyInstaller 打包后** 的插件管理器，使用 **VS Code** 作为开发/调试工具。

---

## 目录

- [一、系统架构概览](#一系统架构概览)
- [二、环境准备](#二环境准备)
- [三、理解插件发现机制](#三理解插件发现机制)
- [四、编写第一个插件（Hello World）](#四编写第一个插件hello-world)
- [五、核心 API 详解](#五核心-api-详解)
- [六、插件自定义配置系统](#六插件自定义配置系统)
- [七、实战：带 GUI 的完整插件示例](#七实战带-gui-的完整插件示例)
- [八、VS Code 调试指南](#八vs-code-调试指南)
- [九、常见问题与最佳实践](#九常见问题与最佳实践)

---

## 一、系统架构概览

Meta-Minesweeper 采用 **ZMQ 多进程插件架构**：

```
┌──────────────────────────────────────┐
│          主进程 (metaminsweeper.exe)   │
│   GameServerBridge (ZMQ Server :5555)│
└──────────────┬───────────────────────┘
               │ ZMQ PUB/SUB + REQ/REP
┌──────────────▼───────────────────────┐
│     插件管理器进程 (plugin_manager)    │
│                                      │
│   PluginLoader ──→ 发现 & 加载 .py   │
│        │                             │
│   EventDispatcher ──→ 事件分发       │
│        │                             │
│   BasePlugin(QThread) × N            │
│     ├─ HistoryPlugin (内置)          │
│     ├─ 你的插件A (用户)              │
│     └─ 你的插件B (用户)              │
│                                      │
│   PluginManagerWindow (Qt GUI)       │
└──────────────────────────────────────┘
```

**关键点：**
- 每个插件运行在**独立的 QThread** 中，互不阻塞
- 主进程和插件管理器通过 **ZeroMQ** 通信
- 插件通过**事件订阅**接收游戏数据，通过**指令发送**控制主进程

---

## 二、环境准备

### 2.1 目录结构（打包后）

打包完成后，目录结构如下：

```
<安装目录>/
├── metaminsweeper.exe          # 主程序
├── plugin_manager.exe          # 插件管理器
├── plugins/                    # 👈 用户插件放这里！
│   ├── my_hello.py             # 你的插件（单文件）
│   └── my_complex/             # 或包形式插件
│       ├── __init__.py
│       └── utils.py
├── shared_types/               # 共享类型定义
│   ├── events.py               # 事件类型
│   ├── commands.py             # 指令类型
│   └── services/               # 👈 服务接口定义
│       └── history.py          # HistoryService 接口
├── plugin_manager/             # 插件管理器模块
│   ├── plugin_base.py          # 👈 BasePlugin 基类
│   └── service_registry.py     # 服务注册表
├── user_plugins/               # 备用用户插件目录
├── data/
│   ├── logs/                   # 日志输出（自动创建）
│   │   └── <插件名>.log        # 各插件独立日志
│   └── plugin_data/            # 各插件的独立数据目录（自动创建）
│       ├── HistoryPlugin/
│       └── MyHelloPlugin/      # 你的插件数据会在这里自动创建
└── _internal/                  # PyInstaller 解压的内部文件（只读）
```

### 2.2 用 VS Code 打开项目

```bash
# 方式一：直接打开安装目录作为工作区
code "D:\你的安装目录"

# 方式二：在其他位置创建插件开发文件夹，写好后复制到安装目录
mkdir D:\my-plugins
code D:\my-plugins
```

### 2.3 推荐 VS Code 扩展

| 扩展 | 用途 |
|------|------|
| Python (Microsoft) | 智能补全、调试 |
| Python Debugger | 远程 debugpy 调试 |

### 2.4 Python 解释器（可选）

如果需要代码补全，在 VS Code 右下角选择一个装了 PyQt5 / msgspec 的 Python 解释器即可。不配也能正常写插件。

---

## 三、理解插件发现机制

### 3.1 插件加载流程

```
plugin_manager 启动
  → PluginLoader 初始化
  → 扫描以下目录：
      ① <bundle>/plugins/          (内置插件，打包时包含)
      ② <exe_dir>/plugins/         (👈 用户插件主目录)
      ③ <exe_dir>/user_plugins/    (备用用户插件目录)
  → 对每个 .py 文件（不含 _ 开头）动态导入
  → 查找继承了 BasePlugin 的类
  → 实例化并注册到 PluginManager
```

### 3.2 支持两种形式

**单文件插件**（推荐新手使用）：
```
plugins/
└── my_plugin.py          # 一个 .py 文件 = 一个插件
```

**包形式插件**（适合复杂插件）：
```
plugins/
└── my_plugin/
    ├── __init__.py       # 插件类定义在此处
    ├── models.py         # 数据模型
    └── widgets.py        # UI 组件
```

### 3.3 自动发现规则

- 文件/目录名以 `_` 开头的会被跳过（如 `_template.py`）
- 单个 `.py` 文件中可以定义多个继承 `BasePlugin` 的类，都会被加载
- 包形式插件中，只有 `__init__.py` 中导出的 `BasePlugin` 子类会被发现

---

## 四、编写第一个插件（Hello World）

### 4.1 创建插件文件

在 `<安装目录>/plugins/` 下创建 `hello_world.py`：

```python
"""
Hello World 示例插件

功能：监听每局游戏结束事件，在界面显示统计信息。
"""
from __future__ import annotations

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PyQt5.QtCore import Qt, pyqtSignal

# 导入插件基类和辅助类型
from plugin_manager import BasePlugin, PluginInfo, make_plugin_icon, WindowMode

# 导入可用的事件类型
from shared_types.events import VideoSaveEvent


class HelloWidget(QWidget):
    """简单的 UI 界面"""

    # 自定义信号：用于跨线程安全更新 UI
    _update_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0

        layout = QVBoxLayout(self)

        self._title = QLabel("👋 Hello World 插件")
        self._title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(self._title)

        self._info = QLabel("等待游戏数据...")
        layout.addWidget(self._info)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)

        # 连接信号
        self._update_signal.connect(self._append_log)

    def update_game_info(self, text: str):
        """线程安全地更新 UI（通过信号槽）"""
        self._update_signal.emit(text)

    def _append_log(self, text: str):
        """槽函数：在主线程执行 UI 更新"""
        self._log.append(text)
        self._count += 1
        self._info.setText(f"已收到 {self._count} 条游戏记录")


class HelloPlugin(BasePlugin):
    """Hello World 示例插件"""

    # ════════════════════════════════════════
    # 1. 定义插件元信息（必须实现）
    # ════════════════════════════════════════
    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="hello_world",           # 唯一名称（用于日志文件名、数据目录名等）
            version="1.0.0",              # 版本号
            author="Your Name",           # 作者
            description="Hello World 示例插件——演示基本的事件订阅和 UI 显示",
            enabled=True,                 # 是否默认启用
            priority=100,                 # 优先级（数字越小越先处理事件）
            show_window=True,             # 初始化时是否显示窗口
            window_mode=WindowMode.TAB,   # 窗口模式: TAB=标签页 / DETACHED=独立窗口 / CLOSED=不显示
            icon=make_plugin_icon(        # 图标（可选，None 则用默认）
                color="#4CAF50",          # 绿色背景
                symbol="H",               # 显示字母 H
                size=64
            ),
        )

    # ════════════════════════════════════════
    # 2. 订阅事件（必须实现）
    # ════════════════════════════════════════
    def _setup_subscriptions(self) -> None:
        """
        在此方法中调用 self.subscribe() 订阅你感兴趣的事件。
        
        可用事件类型（定义在 shared_types/events.py）：
          - VideoSaveEvent: 游戏结束时触发（含完整统计数据 + 录像数据）
          - BoardUpdateEvent: 棋盘更新时触发（每步操作都会触发）
        """
        self.subscribe(VideoSaveEvent, self._on_video_save)

    # ════════════════════════════════════════
    # 3. 创建 UI 界面（可选覆写，返回 None 表示无界面）
    # ════════════════════════════════════════
    def _create_widget(self) -> QWidget | None:
        """
        创建插件的 GUI 组件。
        
        注意：
        - 此方法在主线程中调用
        - 可以使用 self.data_dir 获取插件专属的可写数据目录
        - 返回的 widget 会被嵌入标签页或独立窗口
        """
        self._widget = HelloWidget()
        return self._widget

    # ════════════════════════════════════════
    # 4. 初始化回调（可选覆写）
    # ════════════════════════════════════════
    def on_initialized(self) -> None:
        """
        线程启动后执行此回调。
        
        适用场景：
        - 数据库初始化 / 建表
        - 网络连接建立
        - 加载配置文件
        - 任何耗时操作（在此执行不会卡住 UI）
        
        注意：此方法在插件工作线程中执行，不要直接操作 GUI 对象！
        """
        self.logger.info("HelloPlugin 已初始化！")

    # ════════════════════════════════════════
    # 5. 关闭清理回调（可选覆写）
    # ════════════════════════════════════════
    def on_shutdown(self) -> None:
        """插件关闭前执行清理"""
        self.logger.info("HelloPlugin 正在关闭...")

    # ════════════════════════════════════════
    # 6. 事件处理方法
    # ════════════════════════════════════════
    def _on_video_save(self, event: VideoSaveEvent):
        """
        VideoSaveEvent 事件处理器
        
        重要：此方法在插件的工作线程中执行（非主线程），
        所以可以直接做 IO 操作（数据库写入、文件读写等）。
        
        但如果要更新 GUI，必须通过 run_on_gui() 或信号槽机制。
        """
        # 直接使用 loguru logger 记录日志（已为每个插件配置独立的日志文件）
        self.logger.info(
            f"收到游戏录像: 用时={event.rtime}s, "
            f"难度={event.level}, 3BV={event.bbbv}, "
            f"左键={event.left}, 右键={event.right}"
        )

        # 构建显示文本
        info_text = (
            f"[{event.rtime:.2f}s] {event.level} | "
            f"3BV={event.bbbv} | L={event.left} R={event.right} D={event.double}"
        )

        # ✅ 推荐：直接 emit 信号（自动 QueuedConnection 跨线程到主线程）
        self._widget._update_signal.emit(info_text)

        # 备选（一次性调用时可用）：
        # self.run_on_gui(self._widget.update_game_info, info_text)
```

### 4.2 验证插件加载

1. 将 `hello_world.py` 放入 `<安装目录>/plugins/` 目录
2. 启动 `metaminsweeper.exe`（主程序）
3. 启动 `plugin_manager.exe`（插件管理器）
4. 如果一切正常，你应该能在左侧列表看到绿色的 "H" 图标插件
5. 玩一局游戏结束后，插件界面应显示游戏统计信息

---

## 五、核心 API 详解

### 5.1 BasePlugin 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `self.info` | `PluginInfo` | 插件的元信息对象 |
| `self.name` | `str` | 插件名称（来自 `info.name`） |
| `self.is_enabled` | `bool` | 当前是否启用 |
| `self.is_ready` | `bool` | 是否已完成初始化 |
| `self.lifecycle` | `PluginLifecycle` | 当前生命周期状态 |
| `self.widget` | `QWidget \| None` | `_create_widget()` 返回的界面组件 |
| `self.client` | `ZMQClient` | ZMQ 客户端（一般不直接使用） |
| `self.data_dir` | `Path` | **插件专属可写数据目录**（重要！） |
| `self.log_level` | `LogLevel` | 当前的日志级别 |
| `self.plugin_icon` | `QIcon` | 插件图标 |
| `self.logger` | `loguru.Logger` | **已绑定插件名称的日志器**（直接用！） |
| `self.other_info` | `OtherInfoBase \| None` | 插件自定义配置对象 |
| `self.config_changed` | `pyqtSignal` | 配置变化信号，参数 `(name, value)` |

### 5.2 事件订阅 API

```python
# 订阅事件（在 _setup_subscriptions 中调用）
self.subscribe(event_class, handler_function)

# 取消订阅
self.unsubscribe(event_class)
```

**当前可用的事件类型：**

| 事件类 | 触发时机 | 关键字段 |
|--------|----------|----------|
| `VideoSaveEvent` | 一局游戏结束时 | `rtime`(用时), `level`(难度), `bbbv`, `left`, `right`, `double`, `mode`, `raw_data`(base64录像), 以及约30+其他字段 |
| `BoardUpdateEvent` | 每步棋盘更新时 | 棋盘状态信息 |

### 5.3 向主进程发送指令

```python
# 异步发送（发完即返回，不等响应）
self.send_command(NewGameCommand(rows=16, cols=30, mines=99))

# 同步请求-响应（等待最多 timeout 秒）
result = self.request(some_query_command, timeout=5.0)
```

**当前可用的指令类型：**

| 指令类 | 说明 | 参数 |
|--------|------|------|
| `NewGameCommand` | 开始新游戏 | `rows`, `cols`, `mines` |
| `MouseClickCommand` | 模拟鼠标点击 | `row`, `col`, `button`, `modifiers` |

### 5.4 线程安全的 GUI 更新（重要！）

> **为什么需要跨线程机制？**
>
> `BasePlugin` 继承自 `QThread`，它本身就是一个 `QObject`。事件处理器运行在**插件工作线程**中，
> 但 PyQt 的 GUI 操作只能在**主线程**执行。直接跨线程操作 GUI 会导致未定义行为或崩溃。
>
> **推荐：使用 `pyqtSignal`（信号槽）**

因为插件类本身就是 `QObject`（QThread 的父类），所以可以直接在 Widget 或 Plugin 类上定义信号：
Qt 会自动用 **QueuedConnection** 跨线程投递，安全且高效。

```python
# ════ 推荐方式：pyqtSignal（声明式、类型清晰） ════

# Step 1: 在 QWidget 子类上定义信号
class MyWidget(QWidget):
    new_data = pyqtSignal(dict)       # 自定义参数类型

    def __init__(self):
        super().__init__()
        self.new_data.connect(self._on_new_data)   # 连接到槽函数

    def _on_new_data(self, data: dict):            # 槽函数在主线程执行
        self.label.setText(data["text"])

# Step 2: 在事件处理器中 emit 信号
def _on_video_save(self, event):
    # 此代码在工作线程执行 → emit 自动跨线程投递到主线程的 _on_new_data
    self._widget.new_data.emit({"text": f"用时 {event.rtime}s"})
```

**也可以把信号定义在 Plugin 类上**（因为 BasePlugin 本身就是 QObject）：

```python
class MyPlugin(BasePlugin):
    _sig_update = pyqtSignal(str)

    def _create_widget(self):
        self._sig_update.connect(self._do_update)   # 槽可以是 Plugin 的方法
        return SomeWidget()

    @pyqtSlot(str)
    def _do_update(self, text: str):                # 主线程执行
        if self.widget:
            self.widget.label.setText(text)

    def _handle_event(self, event):
        self._sig_update.emit(f"数据: {event.rtime}")  # 工作线程 emit → 自动跨线程
```

```python
# ════ 备选方式：self.run_on_gui() ════
# 适用于一次性调用、不需要重复连接的场景
self.run_on_gui(some_function, arg1, arg2, keyword_arg=value)
```

| 方式 | 适用场景 | 特点 |
|------|----------|------|
| **`pyqtSignal` + 槽** | 有固定 UI 需反复更新 | **推荐**。声明式，类型签名清晰，Qt 原生惯用法 |
| **`self.run_on_gui()`** | 临时/一次性 UI 调用 | 通用封装，无需预先定义信号，灵活但可读性略差 |

两种方式的底层原理相同 —— 都是通过 QueuedConnection 将调用投递到 Qt 主线程的事件循环。

### 5.5 服务通讯 API（插件间调用）

插件间通过**服务接口**进行类型安全的调用，服务方法会在**服务提供者线程**执行，线程安全。

```python
# ════════════════════════════════════════
# 1. 注册服务（服务提供者）
# ════════════════════════════════════════
def on_initialized(self):
    # 注册服务，显式指定 Protocol 类型
    self.register_service(self, protocol=MyService)

# ════════════════════════════════════════
# 2. 检查服务是否存在
# ════════════════════════════════════════
if self.has_service(MyService):
    # 服务可用
    pass

# ════════════════════════════════════════
# 3. 获取服务代理（推荐）
# ════════════════════════════════════════
service = self.get_service_proxy(MyService)

# 调用服务方法（IDE 完整补全，在服务提供者线程执行）
data = service.get_data(123)        # 同步调用，阻塞等待结果
all_data = service.list_data(100)   # 超时默认 10 秒

# ════════════════════════════════════════
# 4. 异步调用（非阻塞）
# ════════════════════════════════════════
future = self.call_service_async(MyService, "get_data", 123)
# 做其他事情...
result = future.result(timeout=5.0)  # 阻塞等待结果
```

**服务相关方法：**

| 方法 | 说明 |
|------|------|
| `register_service(self, protocol=MyService)` | 注册服务（在 `on_initialized` 中调用） |
| `has_service(MyService)` | 检查服务是否可用 |
| `get_service_proxy(MyService)` | 获取服务代理对象（推荐） |
| `call_service_async(MyService, "method", *args)` | 异步调用，返回 Future |

**注意事项：**
- 服务方法在**服务提供者线程**执行，调用方无需关心线程安全
- **死锁风险**：不要让两个插件互相调用对方的服务
- 服务接口中不要暴露删除等敏感操作

### 5.6 日志记录

```python
# 每个 BasePlugin 实例都有绑定好的 logger，直接使用即可
self.logger.debug("详细调试信息")
self.logger.info("常规信息")
self.logger.warning("警告")
self.logger.error("错误信息")

# 日志会自动输出到：
#   <data_dir>/logs/<plugin_name>.log    （插件专属日志）
#   <data_dir>/logs/plugin_manager.log   （主日志）
```

### 5.7 PluginInfo 配置项

```python
@dataclass
class PluginInfo:
    name: str                              # 必填，唯一标识
    version: str = "1.0.0"                 # 版本号
    author: str = ""                       # 作者
    description: str = ""                  # 描述
    enabled: bool = True                   # 默认是否启用
    priority: int = 100                    # 优先级（越小越先处理事件）
    show_window: bool = True               # 初始化时显示窗口
    window_mode: WindowMode = "tab"        # tab/detached/closed
    log_level: LogLevel = "DEBUG"          # 默认日志级别
    icon: QIcon | None = None             # 图标
    log_config: LogConfig | None = None    # 高级日志配置
    other_info: type[OtherInfoBase] | None = None  # 👈 自定义配置类
```

**WindowMode 含义：**

| 模式 | 行为 |
|------|------|
| `WindowMode.TAB` | 插件 UI 嵌入主窗口的标签页内 |
| `WindowMode.DETACHED` | 插件 UI 以独立窗口弹出（可拖回标签页） |
| `WindowMode.CLOSED` | 不自动创建 UI 窗口（可通过右键菜单手动打开） |

---

## 六、插件自定义配置系统

插件可以定义自己的配置项，这些配置会：
- 自动生成 UI 控件（在设置对话框中）
- 自动持久化到 `data/plugin_data/<plugin_name>/config.json`
- 支持配置变化事件通知

### 6.1 配置类型一览

| 类型 | UI 控件 | 用途示例 |
|------|---------|----------|
| `BoolConfig` | QCheckBox | 开关选项（启用/禁用功能） |
| `IntConfig` | QSpinBox / QSlider | 整数设置（数量、超时时间） |
| `FloatConfig` | QDoubleSpinBox | 浮点数设置（阈值、系数） |
| `ChoiceConfig` | QComboBox | 下拉选择（主题、模式） |
| `TextConfig` | QLineEdit | 文本输入（名称、路径、密码） |
| `ColorConfig` | 颜色按钮 + QColorDialog | 颜色选择（主题颜色） |
| `FileConfig` | QLineEdit + 文件对话框 | 文件路径选择 |
| `PathConfig` | QLineEdit + 目录对话框 | 目录路径选择 |
| `LongTextConfig` | QTextEdit | 多行文本（脚本、描述） |
| `RangeConfig` | 两个 QSpinBox | 数值范围（最小/最大值） |

### 6.2 定义配置类

继承 `OtherInfoBase` 并声明配置字段：

```python
from plugin_manager.config_types import (
    OtherInfoBase, BoolConfig, IntConfig, FloatConfig,
    ChoiceConfig, TextConfig, ColorConfig, FileConfig,
    PathConfig, LongTextConfig, RangeConfig,
)

class MyPluginConfig(OtherInfoBase):
    """我的插件配置"""
    
    # ── 基础类型 ─────────────────────────
    enable_auto_save = BoolConfig(
        default=True,
        label="自动保存",
        description="游戏结束后自动保存录像",
    )
    
    max_records = IntConfig(
        default=100,
        label="最大记录数",
        min_value=10,
        max_value=10000,
        step=10,
    )
    
    min_rtime = FloatConfig(
        default=0.0,
        label="最小用时筛选",
        min_value=0.0,
        max_value=999.0,
        decimals=2,
    )
    
    theme = ChoiceConfig(
        default="dark",
        label="主题",
        choices=[
            ("light", "明亮"),
            ("dark", "暗黑"),
            ("auto", "跟随系统"),
        ],
    )
    
    player_name = TextConfig(
        default="",
        label="玩家名称",
        placeholder="输入名称...",
    )
    
    api_token = TextConfig(
        default="",
        label="API Token",
        password=True,           # 密码模式
        placeholder="输入密钥...",
    )
    
    # ── 高级类型 ─────────────────────────
    theme_color = ColorConfig(
        default="#1976d2",
        label="主题颜色",
    )
    
    export_file = FileConfig(
        default="",
        label="导出文件",
        filter="JSON (*.json)",   # 文件过滤器
        save_mode=True,           # 保存文件模式
    )
    
    log_directory = PathConfig(
        default="",
        label="日志目录",
    )
    
    description = LongTextConfig(
        default="",
        label="描述",
        placeholder="输入描述...",
        max_height=100,
    )
    
    time_range = RangeConfig(
        default=(0, 300),
        label="时间范围(秒)",
        min_value=0,
        max_value=999,
    )
```

### 6.3 绑定配置到插件

在 `PluginInfo` 中通过 `other_info` 属性绑定：

```python
class MyPlugin(BasePlugin):
    
    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="my_plugin",
            version="1.0.0",
            description="我的插件",
            other_info=MyPluginConfig,  # 👈 绑定配置类
        )
```

### 6.4 访问配置值

```python
class MyPlugin(BasePlugin):
    
    def on_initialized(self):
        # 访问配置值
        if self.other_info:
            max_records = self.other_info.max_records
            theme = self.other_info.theme
            self.logger.info(f"配置: max_records={max_records}, theme={theme}")
    
    def _handle_event(self, event):
        # 使用配置
        if self.other_info and self.other_info.enable_auto_save:
            self._save_record(event)
```

### 6.5 监听配置变化

```python
class MyPlugin(BasePlugin):
    
    def on_initialized(self):
        # 连接配置变化信号
        self.config_changed.connect(self._on_config_changed)
    
    def _on_config_changed(self, name: str, value: Any):
        """配置变化时调用（在主线程执行）"""
        self.logger.info(f"配置变化: {name} = {value}")
        
        if name == "theme":
            self._apply_theme(value)
        elif name == "max_records":
            self._resize_buffer(value)
```

### 6.6 配置相关属性和方法

| 属性/方法 | 说明 |
|-----------|------|
| `self.other_info` | 配置对象实例（可能为 None） |
| `self.config_changed` | 配置变化信号，参数 `(name, value)` |
| `self.save_config()` | 手动保存配置到文件 |
| `self.other_info.to_dict()` | 导出配置为字典 |
| `self.other_info.from_dict(data)` | 从字典加载配置 |
| `self.other_info.reset_to_defaults()` | 重置为默认值 |

### 6.7 配置存储位置

配置自动保存到：
```
data/plugin_data/<plugin_name>/config.json
```

示例：
```json
{
  "enable_auto_save": true,
  "max_records": 100,
  "theme": "dark",
  "player_name": "Player1",
  "theme_color": "#1976d2"
}
```

### 6.8 自定义配置类型

如果预定义的配置类型不满足需求，可以继承 `BaseConfig` 创建自定义类型：

```python
from plugin_manager.config_types.base_config import BaseConfig
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QDial
from PyQt5.QtCore import Qt

class DialConfig(BaseConfig[int]):
    """旋钮配置 → QDial 控件"""
    widget_type = "dial"
    
    def __init__(
        self,
        default: int = 0,
        label: str = "",
        min_value: int = 0,
        max_value: int = 100,
        **kwargs,
    ):
        super().__init__(default, label, **kwargs)
        self.min_value = min_value
        self.max_value = max_value
    
    def create_widget(self):
        """创建自定义 UI 控件，返回 (控件, getter, setter, 信号)"""
        widget = QDial()
        widget.setRange(self.min_value, self.max_value)
        widget.setValue(int(self.default))
        widget.setNotchesVisible(True)
        
        if self.description:
            widget.setToolTip(self.description)
        
        # 返回控件、getter、setter、以及 valueChanged 信号
        return widget, widget.value, widget.setValue, widget.valueChanged
    
    def to_storage(self, value: int) -> int:
        return int(value)
    
    def from_storage(self, data) -> int:
        return int(data)

# 使用自定义配置类型
class MyConfig(OtherInfoBase):
    volume = DialConfig(50, "音量", min_value=0, max_value=100)
    sensitivity = DialConfig(5, "灵敏度", min_value=1, max_value=10)
```

**自定义配置类型要点：**

| 方法/属性 | 说明 |
|-----------|------|
| `widget_type` | 控件类型标识 |
| `create_widget()` | 返回 `(控件, getter, setter, 信号)` 四元组 |
| `to_storage(value)` | 将值转换为 JSON 可序列化格式 |
| `from_storage(data)` | 从 JSON 数据恢复值 |

**信号对象说明：**

信号对象可以是：
- Qt 控件的内置信号（如 `widget.valueChanged`、`widget.textChanged`）
- 自定义 `pyqtSignal`（需要通过 QObject 子类定义）

```python
# 方式一：使用控件的内置信号
return widget, widget.value, widget.setValue, widget.valueChanged

# 方式二：自定义信号（复杂控件）
from PyQt5.QtCore import QObject, pyqtSignal

class MySignal(QObject):
    changed = pyqtSignal()

signal_emitter = MySignal(parent=container)  # parent 防止垃圾回收
# ... 控件变化时调用 signal_emitter.changed.emit()
return container, get_value, set_value, signal_emitter.changed
```

---

## 七、实战：带 GUI 的完整插件示例

下面是一个更完整的示例——**实时统计面板插件**，展示计数器、表格等常见 UI 元素的用法：

```python
"""
实时游戏统计面板

功能：统计当前游戏的各种数据，实时显示在界面上。
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QGroupBox, QHeaderView, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from plugin_manager import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from shared_types.events import VideoSaveEvent, BoardUpdateEvent


class StatsPanel(QWidget):
    """统计面板 UI"""

    _signal_update_stats = pyqtSignal(dict)
    _signal_add_record = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total_games = 0
        self._stats_by_level = defaultdict(lambda: {"count": 0, "best_time": float('inf')})

        self._setup_ui()
        self._signal_update_stats.connect(self._do_update_stats)
        self._signal_add_record.connect(self._do_add_record)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # === 顶部统计卡片 ===
        cards_layout = QHBoxLayout()

        self._lbl_total = self._make_stat_card("总局数", "0", "#1976D2")
        self._lbl_today = self._make_stat_card("今日", "0", "#388E3C")
        self._lbl_best = self._make_stat_card("最佳", "--", "#F57C00")
        self._lbl_avg = self._make_stat_card("平均", "--", "#7B1FA2")

        for card in [self._lbl_total, self._lbl_today, self._lbl_best, self._lbl_avg]:
            cards_layout.addWidget(card)

        main_layout.addLayout(cards_layout)

        # === 历史记录表格 ===
        group = QGroupBox("最近对局")
        group_layout = QVBoxLayout(group)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["难度", "用时(s)", "3BV", "操作数"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        group_layout.addWidget(self._table)

        main_layout.addWidget(group)

    def _make_stat_card(self, title: str, value: str, color: str) -> QWidget:
        """创建统计卡片"""
        card = QWidget()
        card.setStyleSheet(f"""
            background: {color}; border-radius: 8px; padding: 8px;
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px;")
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)
        return card

    def update_from_event(self, event_data: dict):
        """线程安全：从事件数据更新统计"""
        self._signal_update_stats.emit(event_data)
        self._signal_add_record.emit(event_data)

    def _do_update_stats(self, data: dict):
        """槽：在主线程更新统计数据"""
        level = data.get("level", "?")
        rtime = data.get("rtime", 0)

        self._total_games += 1
        self._lbl_total.findChild(QLabel).setText(str(self._total_games))

        stats = self._stats_by_level[level]
        stats["count"] += 1
        if rtime > 0 and rtime < stats["best_time"]:
            stats["best_time"] = rtime
            self._lbl_best.findChild(QLabel).setText(f"{rtime:.2f}")

    def _do_add_record(self, data: dict):
        """槽：在主线程添加表格行"""
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(str(data.get("level", "?"))))
        self._table.setItem(row, 1, QTableWidgetItem(f"{data.get('rtime', 0):.2f}"))
        self._table.setItem(row, 2, QTableWidgetItem(str(data.get("bbbv", 0))))
        ops = int(data.get("left", 0)) + int(data.get("right", 0))
        self._table.setItem(row, 3, QTableWidgetItem(str(ops)))


class StatsPlugin(BasePlugin):
    """实时游戏统计插件"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="stats_panel",
            version="1.0.0",
            author="Developer",
            description="实时统计面板——展示游戏数据和历史记录",
            icon=make_plugin_icon("#E91E63", "S", 64),
            window_mode=WindowMode.TAB,
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._on_video_save)

    def _create_widget(self) -> QWidget:
        self._panel = StatsPanel()
        return self._panel

    def on_initialized(self) -> None:
        # 尝试从持久化文件恢复之前的数据
        saved = self.data_dir / "saved_stats.json"
        if saved.exists():
            try:
                data = json.loads(saved.read_text(encoding='utf-8'))
                self.logger.info(f"已恢复 {len(data)} 条历史记录")
            except Exception as e:
                self.logger.warning(f"无法读取存档: {e}")

    def on_shutdown(self) -> None:
        # 退出时保存关键数据
        self.logger.info("StatsPlugin 正在保存数据...")

    def _on_video_save(self, event: VideoSaveEvent):
        self.logger.info(
            f"[{event.level}] {event.rtime:.2f}s | 3BV={event.bbbv}"
        )

        # 将事件转为字典传给 UI
        event_dict = {
            "level": event.level,
            "rtime": event.rtime,
            "bbbv": event.bbbv,
            "left": event.left,
            "right": event.right,
        }
        # ✅ 推荐：直接 emit 信号（自动跨线程）
        self._panel._signal_update_stats.emit(event_dict)
        self._panel._signal_add_record.emit(event_dict)

        # 备选（一次性调用时可用）：
        # self.run_on_gui(self._panel.update_from_event, event_dict)
```
---

## 八、VS Code 调试指南

### 最简开发方式（推荐）

只需 5 步，无需配置 launch.json：

```bash
# 1️⃣ 安装 Python 3.12（如果没有的话）
#    从 python.org 下载安装

# 2️⃣ 在扫雷安装目录下创建虚拟环境并安装依赖
cd <安装目录>
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3️⃣ 用 VS Code 打开安装目录
code <安装目录>
#    右下角选择 .venv 中的 Python 解释器（会自动识别）
```

```
4️⃣ 运行 metaminsweeper.exe          （启动主进程）
5️⃣ plugin_manager.exe会跟随主进程启动         （启动插件管理器）
6️⃣ 点击界面上的 🐛 Debug 按钮       （变绿 = debugpy 已监听 5678 端口）
7️⃣ VS Code → 运行和调试 → 附加到进程 → 选 plugin_manager.exe
8️⃣ 在插件代码打断点 → 触发事件 → 命中断点 ✅
```

> 前提条件：`plugin_manager.spec` 的 `hiddenimports` 需包含 `debugpy`。

### 开发模式调试

有源码时直接 F5 调试 `main.py` 即可，无需额外配置。

---

## 九、常见问题与最佳实践

### Q1: 我的插件为什么没有被加载？

按顺序排查：

1. **文件位置**：确认 `.py` 文件在 `plugins/` 或 `user_plugins/` 目录下
2. **命名规则**：文件名不能以 `_` 开头（如 `_test.py` 会被跳过）
3. **语法错误**：查看 `data/logs/plugin_manager.log` 中有无 `Failed to load module` 错误
4. **基类继承**：确认类继承了 `BasePlugin` 并实现了 `plugin_info()` 和 `_setup_subscriptions()`
5. **导入错误**：如果使用了第三方库（如 requests），需联系作者添加该库；或临时将同版本的第三方库放到 `_internal/` 目录中

### Q2: 如何让插件使用额外的第三方库？

打包后的环境只有 `requirements.txt` 中的依赖。如果你的插件需要额外的库：

**方案 A：重新打包**（推荐）
1. 在 `requirements.txt` 中添加依赖
2. 在 `plugin_manager.spec` 的 `hiddenimports` 中添加模块名
3. 重新执行 PyInstaller 打包

**方案 B：放在插件旁边**
某些纯 Python 库可以直接将源码放入插件的目录中（包形式插件），然后正常 import。但这不是长久之计。

### Q3: 如何存储插件的持久化数据？

**方式一：使用配置系统（推荐）**

定义配置类并绑定到插件，配置会自动保存和加载：

```python
class MyConfig(OtherInfoBase):
    setting1 = BoolConfig(True, "设置1")
    setting2 = IntConfig(100, "设置2")

class MyPlugin(BasePlugin):
    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(name="my_plugin", other_info=MyConfig)
    
    def on_initialized(self):
        # 访问配置
        if self.other_info:
            value = self.other_info.setting1
    
    def on_shutdown(self):
        # 配置在设置对话框确认时自动保存
        # 也可以手动保存
        self.save_config()
```

**方式二：使用 self.data_dir**

使用 `self.data_dir` —— 它指向 `<exe_dir>/data/plugin_data/<PluginClassName>/`：

```python
def on_initialized(self):
    db_path = self.data_dir / "my_data.db"
    config_path = self.data_dir / "settings.json"
    
    # 这些目录会自动创建，无需手动 mkdir
    # 打包后和开发模式下路径不同，但 self.data_dir 会自动处理
```

### Q4: 插件之间如何通信？

插件间通过**服务接口（Protocol）**进行类型安全的通讯。

#### 1. 定义服务接口

在 `shared_types/services/` 目录下创建接口定义文件：

```python
# shared_types/services/my_service.py
from typing import Protocol, runtime_checkable
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class MyData:
    """数据类型（frozen 保证不可变，线程安全）"""
    id: int
    name: str

@runtime_checkable
class MyService(Protocol):
    """服务接口定义"""
    def get_data(self, id: int) -> MyData | None: ...
    def list_data(self, limit: int = 100) -> list[MyData]: ...
```

#### 2. 服务提供者

```python
class ProviderPlugin(BasePlugin):
    def on_initialized(self):
        # 注册服务（显式指定 protocol）
        self.register_service(self, protocol=MyService)
    
    # 实现服务接口方法
    def get_data(self, id: int) -> MyData | None:
        return self._db.query(id)
    
    def list_data(self, limit: int = 100) -> list[MyData]:
        return self._db.query_all(limit)
```

#### 3. 服务使用者

```python
class ConsumerPlugin(BasePlugin):
    def on_initialized(self):
        if self.has_service(MyService):
            # 获取服务代理（推荐）
            self._service = self.get_service_proxy(MyService)
    
    def _do_something(self):
        # 调用服务方法（IDE 完整补全，在服务提供者线程执行）
        data = self._service.get_data(123)
        all_data = self._service.list_data(100)
```

#### 服务调用方式

| 方法 | 说明 | 推荐 |
|------|------|------|
| `get_service_proxy(MyService)` | 获取代理对象，方法调用在提供者线程执行 | ✅ |
| `call_service_async(MyService, "method", *args)` | 异步调用，返回 Future | 高级用法 |
| `has_service(MyService)` | 检查服务是否可用 | - |

#### 注意事项

- **死锁风险**：不要让两个插件互相调用对方的服务
- **线程安全**：服务方法在提供者线程执行，调用方无需关心
- **删除接口**：不要在服务接口中暴露删除等敏感操作

### Q5: 最佳实践清单

| 建议 | 原因 |
|------|------|
| 所有 IO 操作放在 `on_initialized()` 或事件处理器中 | 这些在插件工作线程中执行，不阻塞 UI |
| GUI 操作必须用 `run_on_gui()` 或信号槽 | Qt 的 GUI 只能在主线程操作 |
| 使用 `self.logger` 而非 `print()` | 自动按插件分文件、支持级别过滤、自动轮转 |
| 使用 `msgspec.structs.asdict(event)` 反序列化事件数据 | 事件对象是 msgspec struct，不能直接当 dict 用 |
| 长耗时操作考虑超时和取消 | 插件关闭时只有 2 秒优雅退出时间 |
| `on_shutdown()` 中释放外部资源 | 数据库连接、网络 socket、文件句柄等 |
| 不要在 `_create_widget()` 中做耗时操作 | 此方法在主线程执行，会卡住 UI 加载 |
| 给插件起一个唯一的 name | 用于日志文件、数据目录、UI 标识，避免冲突 |

### Q6: 插件生命周期图示

```
                    plugin_class.plugin_info()
                              │
                              ▼
                     PluginLoader 发现并实例化
                              │
                         set_client()  ← 注入 ZMQ 客户端
                              │
                   set_event_dispatcher()  ← 注入事件分发器
                              │
                        initialize()  ← 启动 QThread
                              │
                    ┌─► _setup_subscriptions()  ← 注册事件订阅
                    │         │
                    │    _create_widget()  ← 创建 UI（主线程）
                    │         │
                    │      start()  ← QThread 开始运行
                    │         │
                    │    on_initialized()  ← 【工作线程】初始化回调
                    │         │
                    │    ═══ 进入事件循环 ═══
                    │    │  等待事件 → 调用 handler → 处理下一个
                    │    │  ...
                    │    │
                    │    shutdown()  ← 请求停止
                    │         │
                    │    on_shutdown()  ← 【工作线程】清理回调
                    │         │
                    └───── STOPPED
```

---

## 附录：快速参考卡片

```python
# ═══ 最小可行插件模板 ═══

from plugin_manager import BasePlugin, PluginInfo, make_plugin_icon, WindowMode
from plugin_manager.config_types import OtherInfoBase, BoolConfig, IntConfig  # 可选
from shared_types.events import VideoSaveEvent  # 按需导入
from shared_types.services.my_service import MyService  # 服务接口（可选）

# ═══ 配置类定义（可选） ═══
class MyConfig(OtherInfoBase):
    enable_feature = BoolConfig(True, "启用功能")
    max_count = IntConfig(100, "最大数量", min_value=1, max_value=1000)

class MyPlugin(BasePlugin):

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="my_plugin",
            description="插件描述",
            window_mode=WindowMode.TAB,  # TAB / DETACHED / CLOSED
            icon=make_plugin_icon("#1976D2", "M"),
            other_info=MyConfig,         # 👈 绑定配置类（可选）
        )

    def _setup_subscriptions(self) -> None:
        self.subscribe(VideoSaveEvent, self._handle_event)

    def _create_widget(self):        # 可选：返回 QWidget 或 None
        pass

    def on_initialized(self):        # 可选：耗时初始化
        pass                          # self.data_dir 可存放数据
        
        # 注册服务（如果是服务提供者）
        # self.register_service(self, protocol=MyService)
        
        # 获取服务代理（如果是服务使用者）
        # if self.has_service(MyService):
        #     self._service = self.get_service_proxy(MyService)
        
        # 连接配置变化信号（可选）
        # self.config_changed.connect(self._on_config_changed)
        
        # 访问配置值（可选）
        # if self.other_info:
        #     max_count = self.other_info.max_count

    def on_shutdown(self):            # 可选：资源清理
        pass

    def _handle_event(self, event):
        self.logger.info(f"收到事件: {event}")  # 用 logger 不用 print
        # self.run_on_gui(gui_func, *args)      # GUI 更新走这
```
