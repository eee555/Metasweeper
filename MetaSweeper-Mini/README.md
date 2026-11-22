# MetaSweeper-Mini

元扫雷迷你版，包含两个前端，共用同一套固定版本的 ms_toollib 和同一份 `gameSetting.ini` 规则。

## 目录

- `win/` — Windows WinForms 端，单文件体积最小，是 Windows 上的推荐方案。详见 `win/README.md`。
- `Linux/` — SDL3 + Rust 端，Linux 原生运行，同一份源码也能在 Windows 上编译。详见 `Linux/README.md`。
- `obj/ms-toollib/` — 两端共用的固定提交 ms_toollib 缓存，属于构建依赖，不随源码提交。

## 共同约定

- 只支持标准初级 `8×8×10`、中级 `16×16×40`、高级 `16×30×99`。
- 配置使用运行目录的 `gameSetting.ini`，录像写入运行目录的 `replay/`。
- 三个难度分别保存 `pixsize`，范围 `5–255`。
- EVF 录像文件名与元扫雷一致，并带 HMAC-SHA256 校验。

## 快速构建

Windows WinForms：

```powershell
cd win
.\build.ps1
```

SDL3（Linux）：

```bash
cd Linux
./build.sh
```

SDL3（Windows PowerShell）：

```powershell
cd Linux
$env:CARGO_TARGET_DIR="..\obj\win-sdl3"
cargo build --release
```
