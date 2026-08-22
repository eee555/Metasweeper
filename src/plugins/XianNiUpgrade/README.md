# 雷修境界 · 排行上传

本文说明本插件如何把修为传到排行站：身份、配置、手动/自动上传、请求格式。玩法数值（经验公式、境界表）见插件内「天地法则」，此处不重复。

首次打开雷修境界 Tab 时会自动弹出一次「天地法则」；关闭后不再打扰，复习可看界面「天地法则」第六节。

排行站协议与 KV 设计见兄弟目录 [`leixiu-rank/docs/ARCHITECTURE.md`](../../../../leixiu-rank/docs/ARCHITECTURE.md)（仓库根：`e:\Games\leixiu-rank`）。

## 身份：两套东西不要混

| 概念 | 从哪来 | 作用 |
|------|--------|------|
| `player_identifier` | 游戏设置里的玩家标识（插件存档按它分身） | **主键**。KV、令牌、成功写限流都绑它。公开榜 / `GET /api/rank` **不返回**这个字段。 |
| `display_name` | 上传时由 **SaoleiWebsite** 插件按标识查开源扫雷网 | **仅展示**。有 `realname` 且非「匿名」则用姓名，否则用 user_id；未绑定或服务不可用时回退为游戏标识。 |
| `upload_token` | 首次上传前自动生成，存在插件配置 | **所有权**。站点只存 `sha256` 哈希。换电脑必须把令牌拷过去，才能继续更新同一标识。 |

默认匿名名 `匿名玩家(anonymous player)` 以及空标识、短名 `匿名玩家` **不能上榜**。请先在游戏设置里改玩家标识，并在开源扫雷网个人主页绑定相同标识。

## 依赖

上传排行时通过 `wait_for_service(SaoleiWebsiteService)` 解析公开道号。请在插件管理器中启用 **SaoleiWebsite**（无窗口插件）。未启用时 `display_name` 回退为游戏标识，不阻断 leixiu-rank 上传。

两个站点地址独立配置：

- `SaoleiWebsite.api_base_url` → 开源扫雷网（默认 `https://openms.top`）
- `XianNiUpgrade.api_url` → 雷修排行站（默认 `https://leixiu-rank.pages.dev`）

## 配置项

定义在 `config.py`，设置页点确定时先跑字段 `validator`，再跑插件 `validate_config`。失败不关窗。联网超时约 **5 秒**。

| 字段 | 默认 | 说明 |
|------|------|------|
| `api_url` | `https://leixiu-rank.pages.dev` | 排行站**根地址**。实际上传 POST `{api_url}/api/upload`。空地址按默认域名检查。 |
| `auto_upload` | `false` | 每局公平胜利后静默上传。 |
| `upload_token` | `""` | 密码框 +「复制」按钮。空则第一次实际上传前用 `secrets.token_urlsafe(32)` 生成并 `save_config()`。 |
| `open_site_after_upload` | `false` | **仅手动上传**成功后用系统浏览器打开 `api_url`。自动上传忽略此项。 |

### 设置页何时打 health / verify

点「确定」时，插件管理器用控件**当前值**校验（等待光标）：

1. **`api_url` 字段 validator** → `GET {url}/api/health`。须 **2xx**，正文为 JSON，且 `ok === true`、`service === "leixiu-rank"`。只回 `{ok:true}` 不够。非 loopback 地址必须是 **https**（默认官方域名与 `http://127.0.0.1` / `localhost` 照常）。超时、连不上、跳转到别的源、或不是雷修排行站 → 对应错误文案。空地址会改用默认域名再请求。UA 为 `MetaSweeper-XianNiUpgrade`（无版本号）。自建且跑同一套 leixiu-rank 的站点因 `service` 相同仍可用。
2. 字段都通过后 → **`validate_config`**：
   - `upload_token` 非空，且当前游戏标识**不是**匿名：`POST {url}/api/verify`，body 为当前标识 + 令牌。UA 为 `MetaSweeper-XianNiUpgrade/{插件版本}`。
     - **403**：错误挂在 `upload_token`（令牌与该标识不匹配）。
     - **2xx**（含尚未上榜的 `registered: false`）：通过。插件不解析 `registered`，只要 HTTP 成功即可。
     - 网络失败 / 其它 HTTP：无法保存，提示检查网络。
   - 勾了 `auto_upload` 且当前仍是匿名标识：错误挂在 `auto_upload`，要求先改游戏标识。

`upload_token` 为空时不做 verify（尚未生成令牌，允许先保存其它项）。config.json **仍存明文令牌**（换电脑靠拷贝）；DEBUG 日志会对密码字段打码。

**本地配置路径**（随安装目录 / `--data-dir` 变化，设置里会动态显示完整路径）：

`<数据目录>/plugin_data/XianNiUpgradePlugin/雷修境界/config.json`

建议生成后立即在设置里点「复制」备份令牌；误改且已保存后，只有旧备份或旧 config 能恢复。

## 手动上传 vs 自动上传

两者都走同一套后台 POST，差别在触发、限流和弹窗。

### 手动：「上传排行」按钮

- `widgets.py` 点按钮 → `plugin.upload_ranking()` → `_start_upload(silent=False, bypass_throttle=True)`。
- **不受**客户端 60 秒跳过限制。若撞上站点写限流，会收到 **429** 并弹窗。
- 进行中会禁用按钮；结束（成功或失败）再启用。
- 匿名标识：**弹窗**说明无法上传，不发请求。
- 若已有一次上传线程在跑：直接返回并恢复按钮（不排队）。

### 自动：公平胜利之后

`_on_game_finished` 在存档并刷新 UI 之后调用 `_maybe_auto_upload()`（公平胜利：`game_state == 6` 且 `is_fair`）。

| 条件 | 行为 |
|------|------|
| `auto_upload` 关闭 | 不传，清掉 pending |
| 匿名 / 空标识 | **跳过、不弹窗**，只打日志 |
| `_upload_in_progress` | 记 dirty（`_pending_upload = True`），等当前请求结束再调度 |
| 距上次**实际上传尝试**不足间隔 | 记 dirty，单次 `QTimer` 到期后再传 |
| 否则 | `_start_upload(silent=True, …)` |

Dirty 补传用的是到期时的**当前** level / `total_xp`（连胜时不会卡在中间一局）。

客户端间隔默认 **60 秒**（对齐站点「同一 identifier 成功更新每分钟 1 次」）。自动上传连续失败会按 `60 × 2^min(失败次数, 3)` 拉长，上限 **600 秒**；成功清零。失败只记日志，不打断游戏。

### 弹窗与开浏览器

| | 成功 | 失败 |
|--|------|------|
| 手动 | `QMessageBox.information`；若勾了 `open_site_after_upload` 再 `webbrowser.open(api_url)` | `QMessageBox.warning`（含 400/403/429/超时等文案） |
| 自动（`silent=True`） | 只打日志，**不弹窗、不打开浏览器** | 只打日志 |

## 请求

Payload **始终带** `display_name`（由 SaoleiWebsite 解析，或回退为游戏标识）：

```json
{
  "identifier": "<当前游戏标识>",
  "level": 42,
  "total_xp": 270541,
  "plugin_version": "1.0.0",
  "upload_token": "<令牌>",
  "display_name": "<网内昵称或标识>"
}
```

- URL：`{api_url 去尾斜杠}/api/upload`
- 后台 **daemon 线程**（名 `xianni-upload`），禁止在线程里碰 GUI；结果用 `run_on_gui` 回来。
- 超时 **10 秒**。
- 头：`Content-Type: application/json; charset=utf-8`，`Accept: application/json`，`User-Agent: MetaSweeper-XianNiUpgrade/{version}`。不要用 urllib 默认 UA（Cloudflare Bot Fight 可能报 1010，插件会提示去 Pages 关掉 Bot Fight Mode）。

`level` / `total_xp` 取自当前分身存档（`_build_update_data()`），不是这一局增量。

## 文件地图

| 文件 | 上传相关职责 |
|------|----------------|
| [`plugin.py`](plugin.py) | `validate_config` / verify；手动 `upload_ranking`；胜利后自动上传、60s dirty 补传、backoff；SaoleiWebsite 昵称解析；payload 与后台 POST |
| [`config.py`](config.py) | 四个配置项；`api_url` health（JSON `ok`+`service`、非 loopback 须 https） |
| [`widgets.py`](widgets.py) | 「上传排行」按钮；「天地法则」第六节（标识/openms 绑定/自动上传/令牌） |

## 与本地排行站联调

1. 在 `e:\Games\leixiu-rank` 执行 `npm run dev`（默认 `http://127.0.0.1:8788`）。
2. 插件设置把 **排行站地址** 设为 `http://127.0.0.1:8788`（不要尾斜杠，也不要写成 `/api/upload`）。
3. 游戏设置里把玩家标识改成非匿名名，否则无法上传、也无法开启自动上传。
4. 点确定时应能通过 health；填了已有令牌时会走 verify。

站点怎么跑、curl 速查见 [`leixiu-rank/README.md`](../../../../leixiu-rank/README.md)；改 Functions 看 [ARCHITECTURE](../../../../leixiu-rank/docs/ARCHITECTURE.md)。
