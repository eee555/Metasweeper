# MetaSweeper-Mini

元扫雷迷你版使用 SDL3 + Rust，同一份源码支持 Windows 和 Linux。

## 目录

- `src/` 存放 Windows 和 Linux 共用的 SDL3 源码。平台差异集中在 `src/platform.rs`。
- `assets/` 存放 LED 位图和 EVF 校验资源。
- `Cargo.toml`、`build.ps1` 和 `build.sh` 位于本目录。
- `obj/ms-toollib/` 缓存 `ms-toollib.rev` 锁定的上游源码。`obj/ms-toollib-mini/` 存放打过补丁、供 Cargo 编译的副本。

## 共同约定

- 只支持标准初级 `8×8×10`、中级 `16×16×40`、高级 `16×30×99`。
- 配置使用 `gameSetting.ini`，录像写入同目录的 `replay/`。Windows 使用工作目录，Linux 使用可执行文件所在目录。
- 胜利、踩雷和进行中重开或退出的对局会追加到同目录的 `stats.dat`，可由完整版读取。默认只自动保存胜局的 `.evf` 录像，可在设置中更改。两版的数据目录不同时，可在启动 Mini 前将 `MINI_STATS_PATH` 设为完整版 `stats.dat` 的绝对路径。
- 三个难度分别保存 `pixsize`，范围 `5–255`。
- EVF 录像文件名与元扫雷一致。未配置外部签名器的构建使用内置 HMAC-SHA256 校验，默认文件名末尾加 `_fake`。
- 正常结束的对局标记为公平，标准模式的胜局同时标记为官方。对局中检测到计时偏差超过 100 毫秒时会重开。
- 对局计时使用 SDL 给输入事件记录的单调时间。计时栏按整秒更新，全屏统计表跟随显示器刷新率更新。
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

### 为什么需要 ms_toollib 补丁

Mini 使用 `ms_toollib` 的布雷、对局状态和 EVF 编码。构建使用 `ms-toollib-mini.patch` 调整两处行为：

- **缩小构建体积。** Mini 无需从截图识别棋盘。补丁从 Rust `rs` 特性中移除 `tract-onnx`，将棋盘图像识别单独放在 ONNX 特性下，避免编译和链接推理依赖。
- **让竞速计时使用输入时间。** 补丁给 `BaseVideo` 增加 `step_at`。Mini 传入 SDL 记录的单调事件时间，让对局计时和 EVF 使用鼠标事件发生的时刻，避免把事件排队的延迟算进成绩。原有 `step` 接口仍使用调用时刻。

`prepare.py` 在生成依赖副本时应用补丁，保留原始上游缓存。依赖版本或补丁内容变化时，脚本会重新生成 `obj/ms-toollib-mini/`。升级 `ms-toollib.rev` 后，需确认补丁仍能应用并通过 Mini 的测试。

## 接入录像签名

签名作者可以在仓库外提供 `replay_signer.rs`，其中实现 `pub(crate) fn sign_payload(payload: &[u8]) -> Result<[u8; 32], String>`。Mini 传入 EVF v4 去掉末尾两字节校验字段长度后的数据，并将返回值写入 EVF 校验字段。手动保存和自动保存共用此接口。

将 `MINI_REPLAY_SIGNER` 设为该 `.rs` 文件的绝对路径，再运行原有构建命令。Windows、Linux 和直接运行 `cargo build` 都读取同一个环境变量：

```powershell
$env:MINI_REPLAY_SIGNER = 'C:\private\replay_signer.rs'
.\build.ps1
```

```bash
MINI_REPLAY_SIGNER=/path/to/private/replay_signer.rs bash ./build.sh
```

未设置时使用内置签名，并在默认文件名末尾加 `_fake`。指定路径后，文件缺失或接口不匹配会使构建失败。签名函数返回 `Err` 时，该录像保存失败。正式发布前应将两平台生成的录像交给元扫雷正式版验签。

## 自定义计数器（试用）

将 Python 版的 `scoreBoardSetting.ini` 放到 Mini 的数据目录（与 `gameSetting.ini` 同级），重启 Mini 后，独立计数器和全屏计数器会使用 `[DEFAULT]` 中的指标名称、顺序和公式。没有该文件或该节为空时使用 Mini 的默认指标。Mini 只读取该文件，可与 Python 版共用。

```ini
[DEFAULT]
点击 = left + right + double
右键 = f'{right}@{right_s:.3f}'
难度 = f'{bbbv_solved}/{bbbv}'
```

该试用版支持最多 24 行，每条公式最长 512 字节。指标超过 24 行或文件读取失败时，Mini 使用默认指标。支持常见四则和比较运算、条件表达式、`min`、`max`、`round` 等函数，以及简单 f-string 格式化。未支持的语法或变量会在对应行显示「公式暂不支持」，运行错误显示 `error`，结算指标在数据就绪前显示 `--`。运行 Mini 无需安装 Python。

## 运行

按 `F11` 选择「仅棋盘」「棋盘＋计时栏」或「棋盘＋计数器」后进入独占全屏，再按一次退出。选择时可用 `←` / `→` 或 `Tab` / `Shift+Tab` 移动焦点，按 `Enter` 确认、`Esc` 取消，也可直接按 `1`、`2`、`3` 进入对应布局。计时栏包含剩余雷数、笑脸和时间。Mini 保留格子的像素大小，选择能容纳所选内容和边框的最小分辨率，同尺寸优先选较高刷新率。余下区域留黑。选了「棋盘＋计数器」时，统计表会显示在全屏内。其他布局会在计数器位于另一块屏幕时保留其独立窗口。Windows 和 Linux X11 支持切换，Wayland 下需用 `SDL_VIDEO_DRIVER=x11` 运行 Mini。

全屏时按 `1`、`2`、`3` 可以直接切换难度。Mini 保留计时栏选项和格子大小，根据新棋盘尺寸重新选择分辨率。无法应用新分辨率时保留原难度。

按 `F4` 切换并保存鼠标锁定设置。EVF 记录开局时是否启用，或本局进行中是否启用过。Windows 切出主窗口时暂时释放鼠标，返回时恢复。Linux 可用 `SDL_VIDEO_DRIVER=x11` 选择 X11。Wayland 下光标不会被实际限制，EVF 仍按设置状态记录。

字体从系统读取并按字符回退。Windows 优先 SimHei 和 Segoe UI，Linux 优先 Noto Sans CJK 和 DejaVu Sans。
