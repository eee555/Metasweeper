# MetaSweeper-Mini（SDL3 端）

SDL3 + Rust 的跨平台实现，游戏逻辑和界面布局与 Windows WinForms 端保持一致。绘制使用纯软件光栅化，文字使用纯 Rust 的 `fontdue`，不依赖 Cairo、Pango、GLib 或 X11 链接库。

## 依赖

- Rust 1.94 或更新版本
- CMake（SDL3 以静态方式从源码构建）
- Python 3（构建时从 WinForms 端提取语言、精灵、LED 位图和校验密钥）
- Linux 需要 C 编译器和 X11/Wayland 开发头
- Windows 需要 MSVC 和 Windows SDK

首次构建需要网络下载 crate。`sdl3` 固定为 0.20.0，内置 SDL 3.4.20 源码。

## 共享的 ms_toollib

`Cargo.toml` 通过路径依赖使用 `../obj/ms-toollib/base`，锁定的提交记录在 `win/Build/ms-toollib.rev`。首次运行 `build.sh` 会拉取这个提交。如果先构建过 WinForms 端，则直接复用同一份缓存。

## 构建

Linux：

```bash
cd MetaSweeper-Mini/Linux
./build.sh
```

`build.sh` 会拉取固定提交的 ms_toollib、构建 Release，并把可执行文件复制到 `dist/linux-sdl3/MetaSweeper-Mini`。

Windows PowerShell：

```powershell
cd MetaSweeper-Mini\Linux
$env:CARGO_TARGET_DIR="..\obj\win-sdl3"
cargo build --release
```

Windows 会把 SDL3 静态编译进 exe，产物位于 `obj/win-sdl3/release/MetaSweeper-Mini.exe`。如果自动探测不到 Python，可以显式指定：

```powershell
$env:MINI_PYTHON="C:\Path\To\python.exe"
```

## 运行

程序读取自身所在目录的 `gameSetting.ini`，录像写入同目录的 `replay/`，与 WinForms 端共用相同的文件名和键。

Linux 若同时存在 X11 与 Wayland，可用 `SDL_VIDEO_DRIVER=x11` 强制使用 X11。Wayland 下系统不允许程序把鼠标锁定在棋盘内，此时鼠标限制会关闭。

字体在运行期从系统查找。Windows 优先 SimHei、微软雅黑、宋体，Linux 优先 Noto Sans CJK、文泉驿。没有可用字体时程序仍可启动，但文字不会绘制。
