# 元扫雷「插件打包 / 安装 / 更新」实施计划

> **版本**：v1.0（不包含网络更新/商店/依赖管理）
> **更新日期**：2026-08-28
> **范围**：定义 `.metaplugin` 打包格式、实现本地安装/卸载流程

---

## 📊 现状摘要

| 维度 | 现状 | 备注 |
|------|------|------|
| 插件元信息 | 13 字段，**缺 `min_app_version` / `dependencies` / `homepage` / `sha256`** | `plugin_base.py:165` 的 `PluginInfo` |
| 插件发现 | 扫描 `<bundle>/plugins/` + `<exe>/plugins/` + `<exe>/user_plugins/` | `plugin_loader.py:65-101` |
| 打包格式 | **无**（裸目录） | 既无 `.zip` 也无 `.metaplugin` |
| 安装入口 | **无 UI**（手动复制目录 + 点刷新） | `main_window.py:1255-1270` 工具栏 |
| 卸载 | **无** | 状态文件会有"幽灵条目" |
| 依赖管理 | **无**（插件共享主程序 `requirements.txt`） | `pycryptodome` 等被全量安装 |
| 主程序版本 | 硬编码 `src/superGUI.py:25 = "元3.3.4"` | 兼容性基线 |
| 数据目录 | `get_data_dir()` / `get_plugin_data_dir()` 已规范化 | `app_paths.py:160-220` |
| 已安装列表 | 散落在 `plugin_states.json` | 无来源 / 安装时间 / 启用历史 |

**核心结论**：基础设施（路径、状态、GUI 框架）**齐全且可复用**，缺的是**"格式 + 工作流"**。

---

## 🏛️ 整体架构（2 阶段）

```
阶段 1（基础）        阶段 2（安装/卸载）
──────────────     ─────────────────
.metaplugin        安装/卸载按钮
PluginInfo 扩展    注册表 JSON
打包 CLI           SHA256 校验
```

> **建议落地顺序**：1 → 2，每阶段独立可发布。

---

## 🟢 阶段 1：定义打包格式（最小侵入，1-2 天）

**目标**：定义 `.metaplugin` 包格式，扩展 `PluginInfo` 字段，让现有插件"无感升级"。

### 1.1 包格式定义

格式：标准 ZIP，后缀 `.metaplugin`，根目录必须含 `manifest.json`：

```json
// manifest.json 示例
{
  "format_version": 1,
  "name": "challenge_mode",
  "version": "1.2.0",
  "author": "eee555",
  "description": "挑战模式插件",
  "min_app_version": "元3.3.0",
  "homepage": "https://github.com/eee555/Metasweeper-plugins",
  "dependencies": ["pycryptodome>=3.10"],
  "sha256": "a1b2c3d4...",
  "entry": "challenge_mode/__init__.py"
}
```

**ZIP 内目录结构**（与现有插件一致）：

```
challenge_mode/
├── __init__.py
├── plugin.py
├── widgets.py
├── config.py
├── icon.png
├── manifest.json       ← 新增
└── README.md
```

### 1.2 改动清单

| 文件 | 改动 | 备注 |
|------|------|------|
| `src/plugin_sdk/plugin_base.py:165-185` | `PluginInfo` 新增 5 字段（**全部带默认值**） | `min_app_version: str = ""`、`dependencies: list[str] = []`、`homepage: str = ""`、`download_url: str = ""`、`sha256: str = ""` |
| `src/plugin_manager/plugin_manifest.py` | **新建**：定义 `PluginManifest` dataclass + `manifest_from_zip(path)` / `manifest_from_dir(path)` 解析器 | 兼容旧插件（manifest 缺失时从 `PluginInfo` 反射读取） |
| `package_tool/plugin_packager.py` | **新建**：CLI 工具 `python -m package_tool.plugin_packager pack <plugin_dir> [-o output.metaplugin]` | 扫描目录、生成 manifest、计算 sha256、打包 zip |
| `pyproject.toml` | 注册 `[project.scripts]`：`plugin-pkg = "package_tool.plugin_packager:main"` | 终端可用 `plugin-pkg pack` |

### 1.3 兼容性保证

- `PluginInfo` 新字段**全部带默认值** → 现有 8 个插件零修改
- `plugin_manifest.py` 检测到旧插件无 manifest 时**降级从 PluginInfo 读取**
- `format_version=1` 留扩展空间

### 1.4 验收标准

- [ ] 给 `src/plugins/challenge_mode/` 打一个 `.metaplugin` 文件
- [ ] `plugin_manifest.manifest_from_zip()` 能正确解析
- [ ] 现有插件无 manifest 时也能正常加载

---

## 🟡 阶段 2：安装 / 卸载 / 注册表（3-5 天）

**目标**：在插件管理器 UI 提供"导入 .metaplugin"和"卸载"功能，建立"已安装插件注册表"。

### 2.1 改动清单

| 文件 | 改动 |
|------|------|
| `src/plugin_manager/plugin_installer.py` | **新建**：`install_from_zip(zip_path) -> PluginManifest`、`uninstall(plugin_name) -> bool` |
| `src/plugin_manager/installed_registry.py` | **新建**：管理 `data/installed_plugins.json`（记录：name / version / source / installed_at / install_path / sha256） |
| `src/plugin_manager/main_window.py:1255-1270` | 工具栏 `[刷新]` 旁新增 `[📦 安装插件]` 按钮，触发 `QFileDialog.getOpenFileName(filter="Metasweeper Plugin (*.metaplugin *.zip)")` |
| `src/plugin_manager/main_window.py:1708-1768` | 右键菜单新增 `🗑 卸载` 项（仅对 `installed_plugins.json` 中有记录的插件启用） |
| `src/plugin_manager/main_window.py:1708-1768` | 右键菜单新增 `📂 打开插件目录` 项（方便用户手动管理） |
| `src/shared_types/widgets/confirm_dialog.py` | **新建子类** `UninstallConfirmDialog`：展示"将删除：X 个数据文件、Y 条日志、Z KB"，要求二次确认 |
| `src/plugin_manager/plugin_state.py` | 扩展 `PluginStateManager`：新增 `remove_state(plugin_name)` 防止幽灵条目 |

### 2.2 卸载清理范围

```python
uninstall(name) 应清理：
  1. <exe>/user_plugins/<name>/              # 插件代码
  2. data/plugin_data/<name>/                # 插件持久化数据
  3. data/logs/plugins/<name>.log            # 插件日志
  4. data/plugin_states.json 中 <name> 条目  # 启用状态
  5. data/installed_plugins.json 中 <name>   # 安装来源
```

### 2.3 校验流程

```
导入 .metaplugin
  ↓
1. 解压到临时目录
  ↓
2. 读取 manifest.json，校验：
   - format_version == 1
   - sha256 == 实际文件 hash（防篡改）
   - min_app_version <= 当前主程序版本（"元3.3.4"）
  ↓
3. 检查 name 是否已存在
   - 不存在 → 复制到 user_plugins/<name>/
   - 存在 → 弹 ConfirmDialog 询问"覆盖/取消/查看差异"
  ↓
4. 写入 installed_plugins.json
  ↓
5. 触发刷新
```

### 2.4 验收标准

- [ ] 导入 .metaplugin 后立即出现在插件列表
- [ ] 卸载后目录、状态、数据、日志全清，无残留
- [ ] SHA256 校验失败时拒绝安装并提示
- [ ] 版本不兼容时拒绝安装并提示

---

## 🛡️ 关键复用点（避免重新造轮子）

| 复用资产 | 文件 | 用法 |
|----------|------|------|
| 主程序版本号 | `src/superGUI.py:25` | `min_app_version` 校验基线 |
| 路径规范化 | `src/plugin_manager/app_paths.py` | `get_user_plugin_dirs()` / `get_plugin_data_dir()` 全程使用 |
| 状态持久化 | `src/plugin_manager/plugin_state.py` | 扩展 `remove_state()` 即可 |
| 确认对话框 | `src/shared_types/widgets/confirm_dialog.py` | 卸载确认继承它 |
| PyInstaller 流程 | `build.bat` | 不涉及（metaplugin 是用户态产物） |

---

## ⚠️ 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 旧插件无 manifest | 无法识别"已安装来源" | 阶段 2 首次启动时**为所有已加载插件自动生成 manifest**（仅本地标识用） |
| SHA256 校验慢（大插件） | 安装体验差 | 后台线程计算 + 进度条 |
| 用户手动复制到 `user_plugins/` 的插件 | 与"注册表"不一致 | `PluginLoader.discover_plugins()` 加钩子，**未注册插件显示"⚠ 未通过安装器安装"** |
| 多进程间共享 plugin_states.json | 写竞争 | `PluginStateManager` 已有文件锁（需确认） |
| 卸载时插件正在运行 | 崩溃 | 卸载前**强制调 `on_unload()`**，并要求用户先禁用 |
| InnoSetup 通配覆盖 user_plugins | 用户数据丢失 | 阶段 2 完成后，**修改 `Metaminesweeper.iss`**：`user_plugins/` 不使用 `ignoreversion` |

---

## 📅 推荐时间线

| 阶段 | 工作量 | 依赖 | 阻塞 |
|------|--------|------|------|
| **阶段 1** | 1-2 天 | 无 | 无 |
| **阶段 2** | 3-5 天 | 阶段 1 | 无 |

**总计**：5-7 天（一人）。

---

## ❓ 建议先讨论的 4 个问题

请确认以下方向后开始实施：

1. **包格式后缀**：`.metaplugin` vs `.msp` vs `.zip`？建议 `.metaplugin`（辨识度高）。
2. **内置插件是否也走 .metaplugin 流程？** 建议**暂时不走**（保持 `src/plugins/` 目录直装，避免破坏现有构建链路），只对 `user_plugins/` 强制。
3. **InnoSetup 是否同步改造 `user_plugins/` 的覆盖策略？** 建议在阶段 2 落地时一起改，避免用户升级主程序时丢失已安装插件。
4. **SHA256 校验粒度**：仅校验 zip 整体 vs 同时校验 `manifest.json` 单独签名？建议先仅校验整体，简单可靠。
