# 插件独立翻译

插件包将编译好的 Qt 翻译文件放在包根目录的 `translations/<locale>.qm`，例如 `my_plugin/translations/en_US.qm`。即使插件类从子模块导出，也以包根目录为准。兼容单文件插件：`my_plugin.py` 使用同级的 `my_plugin.translations/<locale>.qm`，不会读取插件搜索目录中共用的 `translations`。

插件可以继续使用 `QObject.tr()` 或 `QCoreApplication.translate()`。Qt 的翻译器在插件管理器进程内共享，因此每个插件必须使用全局唯一的翻译上下文，例如包含插件名称的窗口类名；不同插件使用相同上下文和源文本时无法按调用者自动隔离。应用及 SDK 使用的公共上下文（如 `Form`、`Dialog`、`Commands`）由管理器保留，插件文件中这些上下文不会生效。

管理器根据语言事件加载已启用插件的翻译文件，在通知插件前完成切换；缺失或无法加载的文件回退至其他可用翻译器或源文本。禁用插件、语言变更和管理器关闭时移除相应翻译器。启用插件前会加载当前语言，以便新建窗口使用。应用语言为 `zh_CN` 时也可以提供插件自己的中文翻译文件。

主进程在启动插件管理器前缓存当前语言并注册快照提供器，因此首次连接即可取得语言快照；语言事件带版本号并用于重连后的补偿同步，旧发送端仍可正常解码。

## 维护翻译

- 插件翻译源文件为 `translations/<locale>.ts`，由 `develop_tools/update_plugin_translations.py` 更新；该脚本用 `pyside6-lupdate` 把插件全部源码提取到唯一上下文，不会导入插件模块。
- 运行 `develop_tools/compile_plugin_translations.py` 生成 `.qm`。`.qm` 由 `.gitignore` 忽略，构建脚本与 CI 会在打包前重新生成。
- 每个插件必须使用与其他插件及宿主不同的上下文（见各插件源码中的 `PluginTranslate(...)`）；公共上下文和 Qt 标准控件上下文不会由插件翻译覆盖。
- 增删或重命名用户可见文本后，请重跑更新与编译脚本，并检查 `develop_tools/audit_plugin_translations.py` 对完整性、上下文唯一性的检查。
