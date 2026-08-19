---
name: metasweeper-dev
description: >-
  元扫雷核心开发助手。当需要修改核心游戏逻辑、导入导出、录像回放、stats.dat 格式、
  窗口行为、游戏状态机、计分板/计数器、UI 菜单、游戏模式时使用此 skill。
  涵盖架构详解、模块文档、常见修改场景、调试指南。
---

# 元扫雷核心开发助手

## 何时使用

- 修改核心游戏逻辑（游戏状态、雷区交互、胜利/失败判定）
- 修改导入导出（stats.dat、CSV、meta.dat）
- 修改录像回放功能
- 修改计分板/计数器
- 修改 UI 菜单栏、对话框
- 添加新的游戏模式或约束
- 调试窗口行为、事件响应
- 修改打包/构建流程

## 架构详解

### 继承链

```
ui.ui_main_board.Ui_MainWindow         # 自动生成的 UI 表单
  └─ superGUI.Ui_MainWindow             # 基类：路径、配置、设置读写
      └─ MineSweeperGUIEvent             # 鼠标/键盘/滚轮事件
          └─ MineSweeperVideoPlayer       # 录像回放控制器
              └─ MainWindowGUIImportExport  # 导入/导出
                  └─ MineSweeperGUI         # ★ 主游戏控制器
```

`MainWindow`（`mainWindowGUI.py`）是独立的 `QMainWindow` 实例，不作为继承的一部分，而是作为 `self.mainWindow` 属性传入。

### 游戏状态机

状态定义在 `src/config/constants.py`：

```
READY → PLAYING → WIN / FAIL
                   ↘ JOKING → JOWIN / JOFAIL
DISPLAY / SHOW_DISPLAY（录像回放）
SHOW（概率显示）
STUDY（研究/分析模式）
MODIFY（修改模式）
```

状态变更入口：`mineSweeperGUI.py` 中 `game_state` 的 setter（line ~240-300）。

### 数据流

```
用户操作（鼠标/键盘）
  → MineSweeperGUIEvent（事件转换）
    → ms_toollib（实际游戏逻辑，.pyd）
      → board_renderer / mineLabel（界面绘制）
      → gameScoreBoard（计数器刷新）
      → （游戏结束时）→ stats.dat 加密写入
```

### stats.dat 读写

| 操作 | 位置 | 方法 |
|---|---|---|
| 写入单条记录 | `mineSweeperGUI.py:415-432` | `gameFinished()` 中调用 |
| 读取所有 short_md5 | `mineSweeperGUI.py:1486-1514` | `_read_stats_dat_short_md5s()` |
| 导入 3.2.2 evf | `mainWindowGUIImportExport.py:44-233` | 旧 exe 验证 → dedup → 写入 |
| 导入旧版 stats.dat | `mainWindowGUIImportExport.py:241-277` | 直接解密 → dedup → 写入 |
| 导出 CSV | `mainWindowGUIImportExport.py:349-435` | 解密 → 过滤 → csv.writer |
| 导出 meta.dat | `mainWindowGUIImportExport.py:437-509` | 解密 → 过滤 → 重新加密写入 |

AES-128-GCM 密钥在 `superGUI.STATS_DAT_KEY`（`src/superGUI.py:27`）。

## 常见修改场景

### 1. 新增导出菜单项

```
步骤：
  1. uiFiles/main_board.ui  → 添加 action（设 text、font）
  2. uiFiles/ → 执行 ui转py.bat → 自动编译到 src/ui/
  3. MainWindowGUIImportExport.__init__  → trigger 连线
  4. 实现导出方法
```

**严禁直接修改 `src/ui/` 下的生成文件**，所有界面改动必须先改 `uiFiles/` 下的 `.ui` 源文件，再执行 `ui转py.bat`。

### 2. 修改去重逻辑

去重 key 目前是 `short_md5`（md5[:8]）。如需加入 `mine_num/row/column`：
- 改 `_read_stats_dat_short_md5s()` 返回 `set[tuple]`
- 改两处 import（evf 和 dat）的对比逻辑

### 3. 新增游戏模式

```
步骤：
  1. src/config/constants.py  → 加 MODE_xxx 常量
  2. src/utils/helpers.py     → trans_game_mode 翻译
  3. src/superGUI.py          → predefinedBoardPara 配置
  4. src/mineSweeperGUI.py    → 约束逻辑
```

### 4. 修改计数器 namespace

变量通过 `score_board_manager.with_namespace({...})` 注入。
name 到公式别名的映射在 `utils/helpers.py:trans_expression()`。
如需刷新 UI 记得调 `score_board_manager.show(ms_board, index_type)`。

## 调试指南

- 窗口行为问题：检查 `mainWindowGUI.py:closeEvent` + `superGUI.py:read_or_create_game_setting` + 配置 key 大小写
- stats.dat 解密失败：确认 `STATS_DAT_KEY` 一致、nonce/tag/ciphertext 长度正确
- 菜单不显示：运行 `uiFiles/ui转py.bat` 重新生成 .py，检查 action 连线
- 插件不加载：`plugin_manager\_run.py` 入口，`plugin_loader.py` 扫描路径

## 构建

构建由 **GitHub Actions CI** 完成（`.github/workflows/python-app.yml`），不在本地构建。
触发方式：推送到 main/master 自动构建；也可在 Actions 页面手动 `workflow_dispatch`。

CI 流程：
1. 安装 Qt + Python 3.12
2. `pyinstaller` 打包 `metasweeper.exe`（含 `--runtime-hook hook-debugpy-pyinstaller.py`）
3. `pyinstaller` 打包 `plugin_manager.exe`
4. 合并资源到 `dist/metasweeper/`
5. 上传 Artifact（zip 包）
