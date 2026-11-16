# 插件系统架构

## 整体架构

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
│   BasePlugin(QObject + moveToThread) × N
│     ├─ HistoryPlugin (内置)          │
│     ├─ 你的插件A (用户)              │
│     └─ 你的插件B (用户)              │
│                                      │
│   PluginManagerWindow (Qt GUI)       │
└──────────────────────────────────────┘
```

## 关键点

- 每个插件运行在**独立的线程**中（QObject + moveToThread），互不阻塞
- 主进程和插件管理器通过 **ZeroMQ** 通信
- 插件通过**事件订阅**接收游戏数据，通过**指令发送**控制主进程

## 目录结构

```
<安装目录>/
├── metaminsweeper.exe          # 主程序
├── plugin_manager.exe          # 插件管理器
├── plugins/                    # 👈 用户插件放这里！
│   ├── my_complex/             # 包形式插件（唯一支持的插件结构）
│   │   ├── __init__.py
│   │   └── utils.py
│   └── services/               # 👈 服务接口定义
│       └── history.py          # HistoryService 接口
├── plugin_sdk/                 # 插件开发 SDK
│   ├── plugin_base.py          # 👈 BasePlugin 基类
│   ├── service_registry.py     # 服务注册表
│   └── config_types/           # 配置类型
├── shared_types/               # 共享类型定义
│   ├── events.py               # 事件类型
│   ├── commands.py             # 指令类型
│   └── enums.py                # 枚举类型
├── plugin_manager/             # 插件管理器内部模块
├── user_plugins/               # 备用用户插件目录
├── data/
│   ├── logs/                   # 日志输出（自动创建）
│   │   └── <插件名>.log        # 各插件独立日志
│   └── plugin_data/            # 各插件的独立数据目录（自动创建）
│       ├── HistoryPlugin/
│       └── MyHelloPlugin/      # 你的插件数据会在这里自动创建
└── _internal/                  # PyInstaller 解压的内部文件（只读）
```

## 插件发现机制

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

## 插件形式

插件一律以**包形式（目录结构）**组织：

```
plugins/
└── my_plugin/
    ├── __init__.py       # 插件类定义在此处
    ├── models.py         # 数据模型
    └── widgets.py        # UI 组件
```

## 自动发现规则

- 文件/目录名以 `_` 开头的会被跳过（如 `_template.py`）
- `services` 目录会被跳过（它是服务接口定义，不是插件）
- 包形式插件中，只有 `__init__.py` 中导出的 `BasePlugin` 子类会被发现
- 单个 `__init__.py` 文件中可以定义多个继承 `BasePlugin` 的类，都会被加载
