# MetaSweeper-Mini

元扫雷迷你版以 SDL3 + Rust 为主实现，同一份源码支持 Windows 和 Linux。

## 目录

- `src/` 存放 Windows 和 Linux 共用的 SDL3 源码。平台差异集中在 `src/platform.rs`。
- `assets/` 存放 LED 位图和 EVF 校验资源。
- `Cargo.toml`、`build.ps1` 和 `build.sh` 位于本目录。
- `win/` 存放旧版 WinForms 源码。
- `obj/ms-toollib/` 存放固定提交的 ms_toollib 构建缓存。

## 共同约定

- 只支持标准初级 `8×8×10`、中级 `16×16×40`、高级 `16×30×99`。
- 配置使用 `gameSetting.ini`，录像写入同目录的 `replay/`。Windows 使用工作目录，Linux 使用可执行文件所在目录。
- 三个难度分别保存 `pixsize`，范围 `5–255`。
- EVF 录像文件名与元扫雷一致，并带 HMAC-SHA256 校验。
- 正常结束的对局标记为公平，标准模式的胜局同时标记为官方。对局中检测到计时偏差超过 100 毫秒时会重开。
- Mini 的版本号在 `Cargo.toml` 的 `[package].version` 中维护。EVF 的 `software` 随编译版本和目标平台生成，例如 `迷你元1.0.0-windows` 和 `迷你元1.0.0-linux`。

## 快速构建

需要 Rust 1.94 或更新版本、CMake、Python 3 和 C 编译器。Windows 使用 MSVC 和 Windows SDK，Linux 需要 X11 或 Wayland 开发头。首次构建需要联网，脚本会准备 `ms-toollib.rev` 锁定的依赖版本。

Windows PowerShell：

```powershell
cd MetaSweeper-Mini
.\build.ps1
```

产物在 `obj/win-sdl3/release/MetaSweeper-Mini.exe`。可用 `-OutputPath` 指定打包路径、`-PythonPath` 指定 Python，或用 `-Offline` 复用已有缓存。

Linux：

```bash
cd MetaSweeper-Mini
bash ./build.sh
```

产物复制到仓库的 `dist/linux-sdl3/MetaSweeper-Mini`。已有依赖缓存时可传入 `--offline`。

在 GitHub Actions 手动运行 **Build MetaSweeper-Mini** 可以下载 Windows x64 版和 CentOS 7 x64 兼容包。CentOS 7 包在 manylinux2014 环境中构建，使用 X11，并检查可执行文件所需的 glibc 版本不高于 2.17。

## 运行

按 `F4` 切换并保存鼠标锁定设置。EVF 记录开局时是否启用，或本局进行中是否启用过。Windows 切出主窗口时暂时释放鼠标，返回时恢复。Linux 可用 `SDL_VIDEO_DRIVER=x11` 选择 X11。Wayland 下光标不会被实际限制，EVF 仍按设置状态记录。

字体从系统读取并按字符回退。Windows 优先 SimHei 和 Segoe UI，Linux 优先 Noto Sans CJK 和 DejaVu Sans。
