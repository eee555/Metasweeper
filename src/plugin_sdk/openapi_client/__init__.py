"""
openapi_client - spec 驱动通用 OpenAPI 客户端

供插件对接任意 OpenAPI 网站使用的共享库：
- SpecDrivenClient: 按 openapi spec 动态发现端点并执行请求的通用客户端
- build_model_registry: 从生成的模型模块构建模型注册表
- codegen: 生成期工具（datamodel-codegen 调用、端点门面生成）
- 异常层次: ApiClientError / AuthError / RateLimitError / ValidationError / SpecError

典型用法（插件生成脚本 + 运行期）::

    # 生成期（见 codegen.py）: 下载 spec -> 生成 models_gen.py -> 生成端点门面
    # 运行期:
    from plugin_sdk.openapi_client import SpecDrivenClient, build_model_registry
    from .api import models_gen

    client = SpecDrivenClient(
        spec=json.loads(Path("openapi.json").read_text(encoding="utf-8")),
        model_registry=build_model_registry(models_gen),
        base_url="https://example.com",
    )
    result = client.call("some_operation_id", param1=1)

openms 子包（由 generate_openms.py 一键生成）通过模块级 __getattr__ 懒加载导出，
不会在本包 import 时强制加载::

    from plugin_sdk.openapi_client import OpenmsApi  # 等价于从 .openms 导入
"""
from __future__ import annotations

from typing import TYPE_CHECKING

# 静态检查用: openms 子包的符号通过下方 __getattr__ 懒加载提供
if TYPE_CHECKING:
    from .openms import OpenmsApi, create_client
    from .transport import (
        QtNetworkTransport,
        RequestsTransport,
        Transport,
        TransportError,
        TransportResponse,
    )
from .client import SpecDrivenClient, build_model_registry
from .errors import (
    ApiClientError,
    AuthError,
    RateLimitError,
    SpecError,
    ValidationError,
)
from .transport import (
    QtNetworkTransport,
    RequestsTransport,
    Transport,
    TransportError,
    TransportResponse,
)
from .codegen import (
    download_spec,
    generate_endpoints_facade,
    run_model_codegen,
)

__all__ = [
    # 客户端
    "SpecDrivenClient",
    "build_model_registry",
    # 异常层次
    "ApiClientError",
    "AuthError",
    "RateLimitError",
    "ValidationError",
    "SpecError",
    # 生成期工具
    "run_model_codegen",
    "generate_endpoints_facade",
    "download_spec",
    # 传输层
    "Transport",
    "TransportResponse",
    "TransportError",
    "RequestsTransport",
    "QtNetworkTransport",
    # openms 子包（懒加载，见下方 __getattr__）
    "OpenmsApi",
    "create_client",
]

# openms 生成子包的懒加载导出: 仅在首次访问时导入，避免包 import 即加载 openms
_LAZY_OPENMS_ATTRS = ("OpenmsApi", "create_client")


def __getattr__(name: str):
    if name in _LAZY_OPENMS_ATTRS:
        from . import openms as _openms

        return getattr(_openms, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
