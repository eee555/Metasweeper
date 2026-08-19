# 元扫雷 Metasweeper v3.3.4

## 项目概述
PyQt5 实现的扫雷游戏，支持多种游戏模式、录像回放、插件系统。

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
`MainWindow` (`src/mainWindowGUI.py`) 是独立的 QMainWindow，作为参数传入。

### 关键文件
| 文件 | 职责 |
|---|---|
| `src/main.py` | 入口：Qt 应用、单例、插件进程、命令处理器 |
| `src/superGUI.py` | 基类：路径、配置、IniConfig、STATS_DAT_KEY、版本号 |
| `src/mineSweeperGUI.py` | 主控制器：游戏状态、定时器、AI、存档 |
| `src/mineSweeperGUIEvent.py` | 鼠标/键盘事件处理 |
| `src/mineSweeperVideoPlayer.py` | 录像回放 (.evf/.avf/.rmv/.mvf/.evfs) |
| `src/mainWindowGUIImportExport.py` | stats.dat/CSV 导入导出、去重 |
| `src/mainWindowGUI.py` | QMainWindow 窗口（拖拽、关闭事件） |
| `src/config/constants.py` | 游戏状态、模式、常量 |
| `src/utils/protocol.py` | StatsRecord 编解码 |
| `src/utils/board_funcs.py` | 棋盘 bytes 转换 |
| `src/utils/helpers.py` | trans_expression、trans_game_mode |
| `src/dialogs/gameScoreBoard.py` | 计数器/计分板系统 |
| `src/dialogs/videoControl.py` | 录像控制面板 |
| `src/plugin_sdk/` | 插件 SDK（BasePlugin、GameServerBridge） |
| `src/plugin_manager/` | 插件管理器子进程 |

### 数据存储
- **stats.dat**：AES-128-GCM 加密，版本字节 + 记录列表
  - Key: `superGUI.STATS_DAT_KEY`（`src/superGUI.py:26`）
  - 格式：`[1B version][2B len][12B nonce][16B tag][ciphertext]`
  - 去重：`short_md5 = md5(file/raw_data)[:8]`
- **gameSetting.ini**：ConfigParser（大小写敏感，`optionxform = str`）
- **录像文件**：`.evf`（原生）、`.avf`、`.rmv`、`.mvf`、`.evfs`（合集）

## 常用命令

```bash
# 运行
python src/main.py

# UI 生成（修改 .ui 后）——从 uiFiles/ 目录执行
cd uiFiles
.\ui转py.bat

# 国际化——执行此脚本，不准手动执行pylupdate5
cd src/ui
.\生成ts文件.bat

# 测试
pytest

# 类型检查
mypy src

# 构建：使用 GitHub Actions（.github/workflows/python-app.yml）
# 触发方式：推送到 main/master 自动构建；也可手动 workflow_dispatch
# 产物为 dist/ 下的 zip 包，包含 metasweeper.exe + plugin_manager.exe

# 翻译文件生成
pylupdate5 ... -ts en_US.ts
```

## 代码规范
- 字符串用单引号（已有代码风格）
- dat 文件版本号：当前 `version=0`，新增版本在 `_read_dat_records` 加 handler
- 去重 key 用 `short_md5`（8 bytes md5）

## UI 修改守则

**所有界面修改必须从修改 `.ui` 文件开始**，位于 `F:\GitHub\Solvable-Minesweeper\uiFiles\`。然后执行 `ui转py.bat`（该目录下），`pyuic5` 会自动将 `.ui` 编译为 `src/ui/` 下的 `.py` 文件。**禁止直接修改 `src/ui/` 下的生成文件**。

Linux 无法开发本项目（依赖 PyQt5、pywin32、ms_toollib.pyd 等 Windows 原生库）。

## 插件系统
- ZMQ 通信，主进程 `GameServerBridge`（单例）
- 插件管理器作为独立子进程运行
- `src/plugin_sdk/` 定义 BasePlugin API
- 插件模板在 `.claude/skills/plugin-dev/`
