# 元扫雷 macOS 版（Apple Silicon）

在 macOS 上从源码打包元扫雷为原生 `.app` 的工具链。上游项目官方仅发布 Windows
版本；本目录提供等价的 macOS 构建方案（PyInstaller 双进程打包，架构与 Windows
版 Nuitka 方案一致：`Metasweeper.app`（主程序）内嵌 `plugin_manager.app`（插件管理器））。

## 环境要求

- macOS 11+（Apple Silicon 已验证；理论上 Intel 亦可，`ms_toollib` 有 x86_64 wheel）
- Python 3.10–3.12（推荐 3.12；首次运行自动创建 `.venv` 并安装依赖）
- Xcode 命令行工具（`iconutil` 用于生成 icns 图标）

## 构建

```sh
bash package_tool/macos/build_mac.sh
```

产物：`package_tool/macos/dist/Metasweeper.app`，直接双击或 `open` 启动。

## 与 Windows 版的差异

| 能力 | Windows | macOS |
| --- | --- | --- |
| 游戏本体、无猜/可猜模式、录像播放、计数器 | ✅ | ✅ |
| 插件系统（ZMQ 事件总线 + 独立进程） | ✅ | ✅ |
| 界面风格 | windowsvista | Fusion |
| 录像官方签名（`metaminesweeper_checksum` 闭源模块） | ✅ | ❌ 与所有自打包版本一致，录像无法通过官方签名校验 |
| OBR 截屏识别（Ctrl+Space） | ✅ | 首次使用需在 系统设置 → 隐私与安全性 → 屏幕录制 中授权 |
| 限制鼠标不超出棋盘（Win32 ClipCursor） | ✅ | ❌ macOS 无公开等价 API，该设置不生效 |
| 防截屏（SetWindowDisplayAffinity） | ✅ | ❌ macOS 无公开等价 API，高级设置中开关不生效 |

## 文件说明

- `build_mac.sh` —— 一键构建入口
- `metasweeper_mac.spec` —— 主程序 PyInstaller 配置
- `plugin_manager_mac.spec` —— 插件管理器 PyInstaller 配置（`LSUIElement` 托盘应用）
- `make_assets.py` —— 从 `package_tool/cat.svg` 生成 `Metasweeper.icns` 与 `src/media/cat.ico`
- `.orig/` —— 打兼容补丁前的源文件备份（`app/board_renderer.py`、`main.py`、
  `superGUI.py`、`mineSweeperGUI.py`、`plugin_manager/app_paths.py`）

## 对源码的兼容性改动（均不影响 Windows 行为）

1. `src/app/board_renderer.py` —— win32 导入与 `limit_cursor` / `unlimit_cursor` /
   `_clip_mouse` 均加 `sys.platform == "win32"` 分支（`unlimit_cursor` 在每次
   游戏结束/关窗时都会被调用，漏改会导致踩雷即崩溃）
2. `src/main.py` —— 界面样式、插件管理器互斥体、防截屏 API、内嵌 `plugin_manager.app`
   的启动路径、冻结模式下工作目录修正
3. `src/mineSweeperGUI.py` —— `disable_screenshot` / `enable_screenshot` 默认空实现
   （原先只在 `main.py` 主分支注入，CLI/插件构造路径会缺属性）
4. `src/superGUI.py` —— 无写权限时的回退目录：`%APPDATA%` → `~/Library/Application Support`
5. `src/plugin_manager/app_paths.py` —— 指针文件目录按平台选择
6. `src/main.py` `_cleanup` —— 插件管理器对 SIGTERM 的优雅关闭依赖其 Qt 事件循环
   （`plugin_manager/plugin_manager.py` 注册的信号处理器在 macOS 上不会被执行），
   主程序退出时 `wait(5)` 超时后升级 `kill()`，异常不再外泄（Windows 不受影响）
7. `src/media/cat.ico` —— 由 `cat.svg` 生成（发布版资源，源码仓库缺失；已存在则不覆盖）

## 验证

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python package_tool/macos/gameplay_smoke_test.py
QT_QPA_PLATFORM=offscreen .venv/bin/python package_tool/macos/quit_cleanup_test.py
```

- `gameplay_smoke_test.py`：离屏模拟完整对局（标旗/踩雷失败/胜利/重开/高级盘/关窗）
- `quit_cleanup_test.py`：对真实插件管理器子进程复现 SIGTERM 超时并验证 kill 升级

改动源码后建议先跑这两个测试再打包。

## 注意事项

- `AI_AGENT_POLICY.md` 参与 `policy_guard` 启动校验，构建与分发时**不得修改**该文件
- 产物为 ad-hoc 签名且未公证：拷贝到其他 Mac 首次打开若被 Gatekeeper 拦截，
  右键 App 选"打开"，或 `xattr -cr /path/to/Metasweeper.app`
- 界面语言文件（`*.qm`）为发布版资源，源码仓库缺失时界面回退为中文
- 分发 `.app` 前请确认符合项目 LICENSE（GPLv3 + 附加条款）的要求
