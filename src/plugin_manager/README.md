# 插件管理器

## 操作图标资源

`resources/actions.qrc` 登记 `resources/icons/*.svg`：18 个原创线性操作图标和一个
`app.svg` 应用身份图标。操作图标统一用于菜单、工具栏、右键菜单、托盘菜单、日志、
插件详情、设置、README 与安装插件入口；`app.svg` 只用于管理器窗口/托盘和对话框标题。
插件列表、标签页和插件独立窗口仍使用 `plugin.plugin_icon`（插件包内 `icon.svg`
或 SDK 默认图标），不得用操作图标或应用身份图标覆盖。

操作 SVG 均为 `24x24` viewBox、`#526b86` 线条；`app.svg` 是
`src/media/plugin_manager.svg` 的同源副本（仅调整声明尺寸），
与 PyInstaller/Nuitka 的 `.ico` 应用图标保持同一视觉标识。
`icons.py` 导入生成的 `actions_rc.py`，通过 `action_icon(name)` /
`set_action_icon(widget, name)` 统一加载；
`QIconEngine` 在 16/24/32px 和禁用/选中状态按当前应用调色板着色，适合高 DPI 与深浅主题。
新增图标时同步维护 SVG、`ICON_NAMES`、`actions.qrc`，然后重新生成并校验：

```powershell
.\.venv\Scripts\pyside6-rcc.exe src/plugin_manager/resources/actions.qrc -o src/plugin_manager/actions_rc.py
.\.venv\Scripts\python.exe -m pytest tests/test_plugin_manager_icons.py
```

`actions_rc.py` 是生成文件，需纳入版本管理并随源码提交，不要手改。
它把 SVG 字节编译进 Python 模块，Windows PyInstaller/Nuitka 与 macOS PyInstaller
均会随 `plugin_manager.icons` 导入注册资源，
无需把 SVG 作为外部 `datas` 复制；打包必须显式包含 `PySide6.QtSvg`
（`build.bat`、CI、`plugin_manager_mac.spec`、Nuitka 脚本与 `plugin_manager.spec`
已列出该 hidden import，现有裁剪脚本不会删除它）。
图标为本项目原创几何图形，遵循仓库 `LICENSE`，不引入额外第三方图标授权。

## 插件下载与平台适配

`plugin_repositories.py` 定义仓库、标签及托管平台接口。各适配器负责 URL 解析、
标签请求、响应字段、分页规则与源码归档请求。
`plugin_download.py` 负责通用 HTTP、取消、进度、解压与安装。
`plugin_download_dialog.py` 在工作线程中调用下载器，界面提供平台选择和 tag 选择。

| 平台 | 标签接口 | 提交字段 | ZIP 接口 |
| --- | --- | --- | --- |
| GitHub | `/repos/{owner}/{repo}/tags` | `commit.sha` | `/repos/{owner}/{repo}/zipball/{sha}` |
| GitLab | `/api/v4/projects/{encoded_path}/repository/tags` | `commit.id` | `/api/v4/projects/{encoded_path}/repository/archive.zip?sha={sha}` |
| Gitee | `/api/v5/repos/{owner}/{repo}/tags` | `commit.sha` | `/api/v5/repos/{owner}/{repo}/zipball?ref={sha}` |
| Gitea / Forgejo | `/api/v1/repos/{owner}/{repo}/tags` | `commit.sha` | `/api/v1/repos/{owner}/{repo}/archive/{sha}.zip` |

GitHub API 使用 `api.github.com`，其他平台使用仓库所在站点。
GitLab 保留并整体编码多级群组路径，通过 `/-/` 区分仓库路径与页面路径。
Codeberg 使用 Gitea/Forgejo 适配器。未知域名必须手动选择平台，不尝试猜测站点类型。
自建站点支持 HTTPS、自定义端口和域名根路径部署，暂不支持部署前缀或认证令牌。

GitHub 使用 Link 分页；GitLab 优先使用 `X-Next-Page`；其他平台使用 Link，缺失时逐页请求到空页。
不以请求的页大小判断结束，避免自建实例限制页大小时漏掉后续标签。
所有归档请求都固定到标签响应中的提交 ID，不使用会移动的 tag 名或默认分支。

## 接口调查与验证（2026-09-18）

- [GitLab 官方标签文档](https://docs.gitlab.com/api/tags/) 和
  [归档文档](https://docs.gitlab.com/api/repositories/#retrieve-file-archive-from-a-repository)
  确认公开仓库可匿名访问、完整路径编码与 `sha` 参数。
- [Gitee 官方机器可读规范](https://gitee.com/api/v5/swagger_doc.json) 确认 `zipball?ref=`、
  标签分页参数；但规范中 `Tag.commit` 标为字符串，与真实响应不一致。
  `mirrors/requests` 的匿名标签请求实际返回 `commit: {sha, date}`，适配器按实际结构读取 `commit.sha`。
- [Codeberg 的 Forgejo 规范](https://codeberg.org/swagger.v1.json) 确认 `limit` 分页和 `{sha}.zip` 归档格式。
- 真实查询和 ZIP 下载通过：GitHub `eee555/ms-toollib`、GitLab `gitlab-org/cli`、
  Codeberg `Codeberg/pages-server`。仅检查归档，未将这些非插件仓库安装为插件。
- Gitee 标签小页请求曾成功，后续完整分页与 ZIP 请求返回 HTTP 403。
  未能实网验证完整安装，不能据此承诺所有 Gitee 公开仓库均可匿名下载；保留平台错误提示，不绕过限制。
- 自建站点通过模拟响应验证 URL、端口、GitLab 多级群组、分页和下载流程，未连接真实私有实例。

安装继续使用根目录 `__init__.py` 的插件包格式。下载过程不导入插件，不覆盖已有目录，
成功后重启插件管理器加载；原有 GitHub 安装目录名保持兼容。

相关测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_plugin_download.py
```

## 测试覆盖率

`tests/test_cov_pm_a_*.py` ~ `tests/test_cov_pm_f_*.py` 按模块分组覆盖插件管理器：
入口与路径（A）、配置与信息对话框（B）、插件加载与管理器核心（C）、主窗口辅助组件（D）、
`PluginManagerWindow`（E）、下载对话框（F）。全部使用桩替代 ZMQ、网络、子进程与真实应用，
仅在 `tmp_path` 中写文件，不修改全局日志配置与 Qt 资源注册状态。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ --cov=src/plugin_manager --cov-report=term-missing
```

当前 `src/plugin_manager` 语句覆盖率为 100%。新增模块或分支时应同步补充对应分组的测试，
并在完整测试套件（而非单分组）下复核，避免全局状态污染导致的用例互相干扰。
