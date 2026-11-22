# MetaSweeper-Mini

Mini 以单文件体积和基础扫雷体验为目标，玩法限于标准初级、中级和高级。界面反馈围绕开格、标雷和按压状态。

用 Visual Studio 打开 MetaSweeper-Mini.sln，选择 x64。Debug 可直接按 F5，Release 生成可独立复制的 MetaSweeper-Mini.exe。

构建需要 Git for Windows、.NET Framework 4.8 开发包、MSVC 和 Windows SDK、Rust 的 x86_64-pc-windows-msvc 工具链，以及 Python 3.10 或更新版本。Visual Studio 会在需要时编译 Rust 并打包资源，运行时使用 Windows 自带的组件。

只需克隆元扫雷仓库。首次构建会从上游获取 Build/ms-toollib.rev 锁定的提交，并缓存到 obj/ms-toollib。首次构建需要联网获取源码和 Cargo 依赖，缓存齐全后可用 build.ps1 -Offline 离线构建。

Release 产物位于 bin/x64/Release。也可运行 build.ps1 构建并复制到上一级的 dist/winforms-prototype。

## 源码结构

- Program.cs 是启动入口。
- UI/ 存放主窗、棋盘、数码管、计数器和设置窗。
- Game/ 包装一局游戏，对上提供输入和可见状态。
- Configuration/ 负责读取和保存 INI、默认难度和国家表。
- Native/ 存放 C# 到 Rust 的接口、DLL 加载和 Rust 封装。
- Build/ 负责编译本机库和生成嵌入资源。
- MetaSweeper-Mini.Tests/ 存放录像校验码和配置兼容的单元测试、覆盖率和运行脚本。
- bin/ 和 obj/ 是构建输出，不需要一起分发。

## 单文件如何打包

构建时通过 Cargo 路径依赖编译固定提交的 ms_toollib 的 Rust base crate（启用 rs feature），再把 Native/native.rs 编译成 cdylib。项目没有手选个别 Rust 源文件。发布时嵌入的是生成的 mines_core.dll 的 LZMS 压缩数据。Release 构建启用大小优化、LTO 和符号剥离，实际保留哪些机器码由编译器和链接器决定。

启动时，NativeCore 把库解压到系统临时目录并加载导出的窄接口。WinForms 使用这些接口办理开局、输入、局面、Pluck 和 EVF 保存。

## 配置兼容

程序读取运行目录中的 `gameSetting.ini`，与元扫雷使用相同的文件名。已有元扫雷配置中的玩家、比赛、国家、自动保存、鼠标限制、结束标雷、计数器、窗口位置和预设尺寸会被读取，其他键会被忽略。修改并保存已有文件时，未知键会保留，方便在同一目录继续使用元扫雷。

文件不存在时，Mini 只生成自己实际使用的键，不生成自定义模式、音效、动画、语言或其他未实现功能的占位配置。

录像默认保存到运行目录下的 `replay` 目录。持久配置和录像只使用程序所在目录，不读写用户的 AppData 或 `%LOCALAPPDATA%\MiniMines`。内嵌运行库会解压到系统临时目录，并在进程退出后自动删除。

游戏模式固定为标准。读取外部配置时，只有 `gamemode = 0` 且棋盘尺寸精确匹配 `8×8×10`、`16×16×40`、`16×30×99` 之一的难度会被采用。其他模式或自定义尺寸会回退到初级，Mini 不会据此切换到未实现的玩法。

设置窗口包含玩家标识、比赛标识、国家或地区、自动保存模式、鼠标限制、结束标雷、计数器显示和计数器缩放。快捷键由程序固定，可在“设置”菜单的“快捷键”窗口查看，不能通过设置页或配置文件修改。主窗口位置、计数器位置和三个标准难度的格子尺寸由窗口拖动操作自动保存。

## 录像校验码

每局保存的 EVF 会写入字段 27 和字段 28 的软件校验码。校验码固定 32 字节，算法是 HMAC-SHA256，覆盖从版本字节到事件结束标记的整段内容，末尾的两字节长度字段和校验码本身不参与计算。写入时长度用大端 uint16，值固定为 `0x0020`。

验签会确认签名内容以事件结束标记 `\0` 结尾，最小合法签名是 35 字节。`Sign` 会拒绝已经带有 `0x0020` 校验码字段的输入，避免重复签名。

签名在 `Game.GetReplay()` 里统一完成，自动保存和手动保存用的是同一份结果。校验实现位于 `Game/ReplayChecksum.cs`，提供 `GetChecksum`、`ValidChecksum`、`GetSelfKey`，以及直接处理 EVF 的 `Sign` 和 `Verify`。

密钥是 32 字节，内嵌在程序里，属于防篡改级别。它能发现随手修改和来源混淆，无法抵抗逆向提取。密钥泄漏后替换 `Key` 数组并重新发版即可。

元扫雷的 software 白名单只认精确字符串。当前 Mini 写入 `元3.3.4-迷你版`，`ms_toollib` 1.6.3 的内置白名单尚未包含它，官方校验是否需要识别由元扫雷作者决定。

## 测试

测试工程使用 xUnit 和 coverlet，运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\MetaSweeper-Mini.Tests\run-tests.ps1
```

报告输出到 `MetaSweeper-Mini.Tests\coverage\coverage.cobertura.xml`。配置兼容、最小配置生成、旧配置迁移和录像校验码均有自动化测试。
