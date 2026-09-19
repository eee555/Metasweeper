# 插件下载与平台适配

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
