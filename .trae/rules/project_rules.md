# 元扫雷 Metasweeper v3.3.4

## 项目概述
PySide6（Qt 6）实现的扫雷游戏，支持多种游戏模式、录像回放、插件系统。
只能在 Windows 上开发（依赖 PySide6、pywin32、ms_toollib.pyd，后两者为 Windows 原生依赖）。

## 架构

### 继承链（MRO）
```
MineSweeperGUI
  -> MainWindowGUIImportExport  (src/mainWindowGUIImportExport.py)
    -> MineSweeperVideoPlayer   (src/mineSweeperVideoPlayer.py)
      -> MineSweeperGUIEvent    (src/mineSweeperGUIEvent.py)
        -> superGUI.Ui_MainWindow  (src/superGUI.py)
          -> ui.ui_main_board.Ui_MainWindow  (src/ui/ui_main_board.py)
```
`MainWindow`（`src/mainWindowGUI.py`）是独立的 QMainWindow，作为参数传入。

### 关键文件
| 文件 | 职责 |
|---|---|
| `src/main.py` | 入口：Qt 应用、单例、插件进程、命令处理器 |
| `src/superGUI.py` | 基类：路径、配置、IniConfig、STATS_DAT_KEY、版本号 |
| `src/mineSweeperGUI.py` | 主控制器：游戏状态、定时器、存档 |
| `src/mineSweeperGUIEvent.py` | 鼠标/键盘事件处理 |
| `src/mineSweeperVideoPlayer.py` | 录像回放 (.evf/.avf/.rmv/.mvf/.evfs) |
| `src/mainWindowGUIImportExport.py` | stats.dat/CSV 导入导出、去重 |
| `src/app/game_engine.py` | 埋雷、UPK 首击等引擎逻辑 |
| `src/config/constants.py` | 游戏状态、模式、常量 |
| `src/utils/protocol.py` | StatsRecord 编解码 |
| `src/utils/board_funcs.py` | 棋盘 bytes 转换 |
| `src/utils/helpers.py` | trans_expression、trans_game_mode |
| `src/dialogs/gameScoreBoard.py` | 计数器/计分板系统 |
| `src/dialogs/videoControl.py` | 录像控制面板 |
| `src/plugin_sdk/` | 插件 SDK（BasePlugin、GameServerBridge） |
| `src/plugin_manager/` | 插件管理器子进程 |

### 游戏模式（EVF 标准模式码）
0 标准、1 UPK、4 Win7、5 经典无猜、6 强无猜、7 弱无猜、8 准无猜、9 强可猜、10 弱可猜、
11 双击递归、12 标雷递归、13 双击标雷递归、14 无猜双击递归、15 无猜标雷递归、16 无猜双击标雷递归。

**模式推衍（重排雷局、判负、递归连锁）由局面状态机在 ms_toollib（Rust，仓库 F:\GitHub\ms_toollib）内部实现**。
GUI 侧的职责只有：埋雷时执行 `ms_board.mode = gameMode`（见 `mineSweeperGUI.py::layMine`）。
禁止在 Python 侧重复实现模式逻辑。例外：UPK 预设局面的首击重排仍在 `app/game_engine.py::ai()`。
修改 ms_toollib 后需在 `ms_toollib/python_package` 执行 `cargo build --release`，
再把 `target/release/ms_toollib.dll` 复制为 `src/ms_toollib.pyd`。
模式语义改动必须同步维护 `ms_toollib/base/tests/test_modes.rs`。

### 数据存储
- **stats.dat**：AES-128-GCM 加密，版本字节 + 记录列表
  - Key: `superGUI.STATS_DAT_KEY`（`src/superGUI.py:26`）
  - 格式：`[1B version][2B len][12B nonce][16B tag][ciphertext]`
  - 去重：`short_md5 = md5(file/raw_data)[:8]`
- **gameSetting.ini**：ConfigParser（大小写敏感，`optionxform = str`）
- **录像文件**：`.evf`（原生）、`.avf`、`.rmv`、`.mvf`、`.evfs`（合集）

## 常用命令

```powershell
# 运行
python src/main.py

# UI 生成（修改 .ui 后）——从 uiFiles/ 目录执行
.\ui转py.bat

# 国际化——从 src/ui/ 目录执行此脚本，禁止手动单跑 pyside6-lupdate
.\生成ts文件.bat
# 之后编译 .qm：
pyside6-lrelease en_US.ts -qm ../en_US.qm
pyside6-lrelease de_DE.ts -qm ../de_DE.qm
pyside6-lrelease pl_PL.ts -qm ../pl_PL.qm
pyside6-lrelease ja_JP.ts -qm ../ja_JP.qm

# 测试
pytest

# 类型检查
mypy src

# 构建：GitHub Actions（.github/workflows/python-app.yml）
# 推送到 main/master 自动构建；产物为 dist/ 下的 zip
```

## 代码规范
- 字符串用单引号（已有代码风格）
- dat 文件版本号：当前 `version=0`，新增版本在 `_read_dat_records` 加 handler
- 去重 key 用 `short_md5`（8 bytes md5）

## UI 修改守则

**所有界面修改必须从修改 `.ui` 文件开始**，位于 `uiFiles/`。然后执行 `ui转py.bat`（该目录下），
`pyside6-uic` 会将 `.ui` 编译为 `src/ui/` 下的 `.py` 文件。**禁止直接修改 `src/ui/` 下的生成文件**。

## 国际化守则

**新增/修改含 `_translate()`、`self.tr()`、`QCoreApplication.translate` 的源文件时，必须同步检查
`src/ui/生成ts文件.bat` 的扫描清单是否覆盖该文件**——清单不全时 `-noobsolete` 会把清单外文件的
翻译词条误删。清单以
`git grep -l -E "_translate\(|self\.tr\(|QCoreApplication\.translate" -- "src/*.py"`
的结果为准，外加 `uiFiles/` 下全部 `.ui` 文件。改完 `.ts` 后用 `pyside6-lrelease` 重新编译 `.qm`。

## 插件系统
- ZMQ 通信，主进程 `GameServerBridge`（单例）
- 插件管理器作为独立子进程运行
- `src/plugin_sdk/` 定义 BasePlugin API
- 插件模板与参考文档在 `.claude/skills/plugin-dev/`（历史资源，可直接使用）
