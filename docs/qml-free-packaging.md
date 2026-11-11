# 不含 QML 的发布包

内置统计插件已移除，发布包不再支持依赖 QML、Qt Quick、Qt Charts 的插件。
历史记录插件、历史数据库与 `HistoryService` 保留。

## 收集配置

- Windows PyInstaller 入口为 `build.bat` 和 `.github/workflows/python-app.yml`。
- macOS PyInstaller 配置位于 `package_tool/macos/`。
- PyInstaller 主程序和插件管理器均排除 `PySide6.QtQuickWidgets`、
  `PySide6.QtQuick`、`PySide6.QtQml`、`PySide6.QtCharts`。
- 插件源码作为数据文件分发，不会自动分析其导入。插件管理器显式收集
  `shared_types.aes_gcm`、`config.constants`、`utils.app_logger`，供内置插件使用。
- `package_tool/build_nuitka_main.bat` 同样停止显式包含 QML 模块和插件。

`PySide6` 仍是必需依赖。Widgets、Network、Svg、Multimedia 分别用于
界面、网络、皮肤和音效；不能整体删除 `PySide6_Addons`。
`.qm` 是翻译文件，必须保留，与 `.qml` 无关。

## Windows Nuitka 构建

在项目根目录执行 `package_tool\build_nuitka_main.bat`。脚本使用 `.venv` 中的
Python、Nuitka 和 `pyside6-lrelease`，先更新四种语言的翻译，再依次编译主程序和
插件管理器，合并到 `dist\metasweeper-nuitka\package`。内置插件保留为源码，放在
`internal\plugins`；插件管理器显式收集 `plugin_sdk`、`shared_types`、
`config.constants` 和 `utils.app_logger`，覆盖插件源码中的动态导入依赖。

两个编译步骤均默认使用 `--jobs=4`，限制并行编译任务数。可以在 PowerShell 中覆盖：

```powershell
$env:NUITKA_JOBS = '8'
.\package_tool\build_nuitka_main.bat
```

`NUITKA_JOBS` 必须为正整数。还可设置 `NUITKA_OUTPUT_DIR` 修改输出根目录、
`NUITKA_CONSOLE_MODE` 修改控制台模式。默认包含 `debugpy` 及其随包调试器源码。
同时把 pydevd 的 `_pydevd_bundle` 等模块分发到包根目录，满足调试器运行时使用
顶层模块名的动态导入；设置 `NUITKA_INCLUDE_DEBUGPY=0` 可以不包含调试支持。
未找到 `dumpbin.exe` 时，脚本通过 `vswhere.exe` 定位 Visual Studio C++ 工具链并
加载 `vcvars64.bat`；工具链缺失会在编译前报错。

## Windows 产物裁剪

主程序和插件管理器合并后调用 `package_tool/trim_qt_runtime.ps1`。
脚本支持 PyInstaller 的 `_internal/PySide6` 和 Nuitka 的扁平 DLL 布局。

脚本会删除整个 QML 导入目录、QML 调试插件以及 Qt 屏幕虚拟键盘插件。
虚拟键盘会间接引用 Quick/QML，即使排除了 Python 模块也可能被 Qt hook 收集。
其他输入法插件保留。支持 PyInstaller 的 `plugins` 和 Nuitka 的 `qt-plugins`
目录布局。如果包内没有 `Qt6Pdf.dll`，同时移除无法加载的 `imageformats/qpdf.dll`；
已分发 PDF 运行库的包保留该插件。

本地源码中遗留的统计插件 `__pycache__` 可能被目录复制带入产物，
因此脚本也清除发布包内旧的统计插件目录，不改动用户历史数据库。

Qt DLL 按原生依赖关系筛选，保留仍被引用的模块。裁剪后若仍存在
QML/Quick/Charts/VirtualKeyboard 运行时，构建会报错，需检查剩余引用方。
未指定 `-Apply` 时只报告计划；指定后执行删除。脚本需要 Visual Studio 的
`dumpbin.exe`，CI 会自动定位该工具。

## 验收

1. 分别构建主程序和插件管理器，合并后执行裁剪。
2. 确认 QML/Quick/Charts 运行时和统计插件目录均不存在。
3. 检查所有保留二进制的普通与延迟导入，确认 Qt DLL 无缺失。
4. 确认 Widgets、Network、Svg、Multimedia 的 Python 扩展及原生库保留。
5. 验证冻结程序启动、内置插件加载和 `HistoryService` 注册；检查日志中的导入错误。
6. 运行现有音效与历史查询测试。真实设备的声音输出、可见界面交互及 macOS
   发布包仍需在对应环境验收，不能仅凭构建成功判定。