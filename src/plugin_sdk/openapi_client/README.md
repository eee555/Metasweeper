# openapi_client - OpenAPI 客户端共享库

供插件对接 OpenAPI 网站（当前内置 openms 站点）使用的共享库。

## 一键生成

一条命令完成：下载/刷新 openapi.json → 生成模型 → 生成端点门面 → 生成包入口 → import 自检。

```bash
# 方式一（推荐，在 src 目录或项目根下均可）
python -m plugin_sdk.openapi_client.generate_openms

# 方式二：直接运行脚本
python src/plugin_sdk/openapi_client/generate_openms.py
```

脚本幂等，重复运行会覆盖旧生成物。默认内置 openms 站点参数（spec URL、base_url、输出目录），如需对接其他站点，复制脚本修改顶部常量即可。

## 生成物清单

全部集中在 `src/plugin_sdk/openapi_client/openms/` 子包（自动生成，勿手改）：

| 文件 | 说明 |
|------|------|
| `openapi.json` | spec 缓存基线（随包分发，运行期只读） |
| `models_gen.py` | datamodel-code-generator 生成的 msgspec.Struct 模型 |
| `models_requests.py` | 内联 requestBody 合成的命名请求模型（见下） |
| `api_endpoints.py` | 端点门面 `OpenmsApi`（带完整类型注解，IDE 补全友好） |
| `__init__.py` | 薄封装：导出 `create_client()` / `OpenmsApi` / 全部模型类 |

### 内联请求体模型

datamodel-code-generator 只为 `$ref` 指向的命名模型生成 Struct；若端点的
requestBody schema 是内联定义（properties 直接挂在 schema 上，无 `$ref`），
body 会回退成 `dict[str, Any]`。生成脚本会自动扫描这类端点，按
`operationId`（去掉 `_api` 段后 PascalCase + `In` 后缀，如
`tournament_api_set_tournament` → `TournamentSetTournamentIn`）合成命名
请求模型，输出到 `models_requests.py`，并在门面方法签名上使用。
命名与既有 `components/schemas` 冲突或字段名不合法的端点仍回退 dict 并
打印警告。

## 运行期用法

```python
from plugin_sdk.openapi_client.openms import create_client, OpenmsApi

client = create_client()          # base_url 默认 https://openms.top，可传参覆盖
api = OpenmsApi(client)           # 端点门面

# 匿名只读端点示例
user = api.userprofile_get_user_info(user_id=1)   # -> UserProfile 模型实例
```

也支持从库顶层懒加载导入（不会在 import 时强制加载 openms 子包）：

```python
from plugin_sdk.openapi_client import OpenmsApi
```

上述类/异常/传输层也可直接从 `plugin_sdk` 顶层导入（同样为惰性转发，
首次访问才加载 openapi_client，不影响包导入速度）：

```python
from plugin_sdk import create_client, OpenmsApi, SpecDrivenClient, QtNetworkTransport
```

认证：`client.set_token(token)`（Bearer 头，具体站点认证方式需实测确认）。

## 依赖说明

- **运行期**：`requests` + `msgspec`（随 plugin_sdk 整体分发，已进 requirements.txt）
- **生成期**：`datamodel-code-generator`（不进 requirements.txt，仅本地生成时需要；脚本检测到缺失时会给出安装提示）

```bash
pip install datamodel-code-generator
```
