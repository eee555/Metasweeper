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

## 日志清理

菜单「工具 → 清理全部日志...」清空 `<data>/logs` 下的所有 `*.log`（含
`main.log`、`plugins/*.log` 与轮转备份）。日志文件被 loguru 的文件 sink 以追加模式
持有，Windows 下无法删除，因此实现上统一截断为空（`logging_setup.clear_all_logs`），
清理后 sink 会继续从新文件末尾写入。目录中非 `.log` 文件（例如截图）不会被误删；
单个文件被其它程序占用时跳过并在结果提示中报告。清理前有确认对话框，
清理成功后若日志查看器已打开则同步清屏。

## 插件下载与平台适配

`plugin_repositories.py` 定义仓库、标签及托管平台接口。各适配器负责 URL 解析、
标签请求、响应字段、分页规则与源码归档请求。
`plugin_download.py` 负责通用 HTTP、取消、进度、解压与安装。
插件市场在工作线程中调用下载器，界面提供搜索源和版本选择。

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
  标签 REST API 返回 403 或 429 时，通过 HTTPS 查询同一公开仓库公布的 Git refs。ZIP 下载沿用归档 API，归档请求被拒绝时显示平台错误。
- 自建站点通过模拟响应验证 URL、端口、GitLab 多级群组、分页和下载流程，未连接真实私有实例。

安装继续使用根目录 `__init__.py` 的插件包格式。下载过程不导入插件，不覆盖已有目录，
成功后重启插件管理器加载；原有 GitHub 安装目录名保持兼容。

相关测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_plugin_download.py
```

## 插件市场搜索源

插件市场允许切换 GitHub 和 Gitee。GitHub 搜索带有 `metasweeper-plugin` Topic 的公开仓库，优先使用 GitHub API，匿名额度耗尽时回退到 GitHub 公开搜索页；下载归档固定到 tag 对应的 commit SHA。

Gitee 搜索通过其公开仓库搜索服务查询 `metasweeper`，并只展示仓库名以 `metasweeper-` 开头的结果。Gitee 搜索没有 Topic 筛选，因此 Gitee 上的插件镜像需保留此命名前缀；搜索索引延迟时，仓库不会立即显示。搜索遇到临时连接重置时会有限重试，版本 tag 查询和下载沿用 Gitee API 适配器。

GitHub 与 Gitee 使用各自的搜索和下载接口；同名的 `metasweeper-` 镜像按同一插件身份识别。切换搜索源会显示已有安装并沿用原安装目录更新，避免因托管平台不同而安装出第二份插件。

市场安装会先下载插件、检查并安装其 `requirements.txt` 中未满足的依赖，再发布插件目录。安装完成后使用已有的搜索结果和本地元数据更新列表，不重新联网；完成提示提供「确认」和「重启」按钮。也可通过「插件 → 重启」重启插件管理器。重启保留启动参数与数据目录，等待旧进程退出并释放单实例锁后启动新进程。重启前可见的主窗口会恢复到前台，并重新选中当时的插件标签页。手动复制的插件仍通过右键「查看依赖详情」安装依赖。

插件管理器会记住主窗口关闭时的宽高，位置由桌面系统决定。最大化时保存普通窗口的宽高。

插件市场会记住上次选择的 GitHub 或 Gitee 搜索源。双击市场中的插件行，或点击最后一列的「查看详情」，可查看作者、说明、仓库链接和 README。README 在打开详情后从该仓库读取，正文和链接颜色会随深浅色主题切换。

插件列表右键的「启用」和「禁用」会立即保存，供下次启动使用。

「插件 → 自动更新插件」默认开启，取消勾选后会记住关闭状态。开启时会立即检查，以后每次启动及连续运行期间每 24 小时检查一次。系统按 `.metasweeper-plugin.json` 记录的安装仓库检查受管理的插件，后台安装更高的稳定版本及所需依赖，并保留插件数据。更新完成后通过「插件 → 重启」加载新版本。手工复制且没有来源信息的插件不会被自动覆盖。

相关测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/plugin_manager/test_plugin_catalog.py tests/plugin_manager/test_plugin_market.py
```

## 本地 ZIP 安装与更新

「插件 → 从 ZIP 导入插件…」支持直接打包的插件、单个插件包目录，以及插件市场使用的
GitHub / Gitee 等仓库源码 ZIP（外层仓库目录中直接放插件，或再包含一个插件包目录）。
本地导入与市场安装共用包目录识别和安全解压逻辑，仍只接受一个插件包。

再次导入会更新 `user_plugins` 中由管理器安装的同一个插件。管理器静态读取
`plugin_info()` 中 `PluginInfo` 声明的字符串 `name`，用于识别不同文件名、版本号和
外层目录下的同一个插件，识别过程不执行插件代码；无法静态读取时按包目录名匹配
（ZIP 中没有外层目录时按 ZIP 文件名匹配）。
市场安装使用的模块目录名会保留，因此从市场安装后也可以通过 ZIP 更新。
普通手工目录、内置插件、符号链接和存在多个匹配目标的安装不会被覆盖。

新包先在临时目录准备依赖，成功后完整替换旧代码（包括移除旧包已不再提供的文件）；
替换失败会恢复旧代码。插件配置、授权、启用状态和独立数据目录保持原样。
插件已经加载时，界面会提示重启管理器后生效。
通过 ZIP 更新市场插件时保留仓库来源，清除不再对应新代码的旧标签、提交和校验值，
可静态读取的新版版本号继续用于市场更新检查；无法确定版本时不自动猜测版本。
没有已有市场来源的 ZIP 安装仍作为本地插件管理，不从压缩包中任意声明的仓库地址启用自动更新。

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
