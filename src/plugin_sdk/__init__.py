"""
插件 SDK

提供给插件开发者使用的模块：
- BasePlugin: 插件基类
- PluginInfo: 插件信息
- config_types: 配置类型
- service_registry: 服务注册
- server_bridge: 服务端桥接（主进程使用）
- control_auth: 控制授权管理
"""

from typing import TYPE_CHECKING

from .plugin_base import (
    BasePlugin,
    PluginInfo,
    PluginLifecycle,
    WindowMode,
    LogLevel,
    make_plugin_icon,
)
from .service_registry import (
    ServiceRegistry,
    ServiceNotFoundError,
    ServiceAlreadyRegisteredError,
)
from .server_bridge import GameServerBridge
from .control_auth import ControlAuthorizationManager

# 配置类型
from .config_types import (
    BaseConfig,
    ConfigWidgetBase,
    ConfigWidgetWrapper,
    OtherInfoBase,
    BoolConfig,
    IntConfig,
    FloatConfig,
    ChoiceConfig,
    TextConfig,
    ColorConfig,
    FileConfig,
    PathConfig,
    LongTextConfig,
    RangeConfig,
)

# ---------------------------------------------------------------------------
# openapi_client 顶层转发导出（惰性）
#
# 以下名字实际定义在 plugin_sdk.openapi_client 子包中，通过模块级 __getattr__
# 首次访问时才 import，保持 plugin_sdk 包导入轻量（不会在包 import 时加载
# openapi_client 及其依赖）。与上述既有导出经检查无命名冲突。
# ---------------------------------------------------------------------------
if TYPE_CHECKING:
    # 类型存根: 仅供静态检查/IDE 补全，运行期走下方 __getattr__ 懒加载
    from .openapi_client import (
        # 客户端
        SpecDrivenClient,
        build_model_registry,
        # openms 端点门面
        OpenmsApi,
        create_client,
        # 异常层次
        ApiClientError,
        AuthError,
        RateLimitError,
        ValidationError,
        SpecError,
        # 传输层
        Transport,
        TransportResponse,
        TransportError,
        RequestsTransport,
        QtNetworkTransport,
    )

__all__ = [
    # 插件基类
    "BasePlugin",
    "PluginInfo",
    "PluginLifecycle",
    "WindowMode",
    "LogLevel",
    "make_plugin_icon",
    # 服务注册
    "ServiceRegistry",
    "ServiceNotFoundError",
    "ServiceAlreadyRegisteredError",
    # 服务端桥接
    "GameServerBridge",
    # 控制授权
    "ControlAuthorizationManager",
    # 配置类型
    "BaseConfig",
    "ConfigWidgetBase",
    "ConfigWidgetWrapper",
    "OtherInfoBase",
    "BoolConfig",
    "IntConfig",
    "FloatConfig",
    "ChoiceConfig",
    "TextConfig",
    "ColorConfig",
    "FileConfig",
    "PathConfig",
    "LongTextConfig",
    "RangeConfig",
    # openapi_client 转发导出（通过下方 __getattr__ 惰性提供）
    "SpecDrivenClient",
    "build_model_registry",
    "OpenmsApi",
    "create_client",
    "ApiClientError",
    "AuthError",
    "RateLimitError",
    "ValidationError",
    "SpecError",
    "Transport",
    "TransportResponse",
    "TransportError",
    "RequestsTransport",
    "QtNetworkTransport",
]

# openapi_client 转发导出的白名单（首次访问时才 import 子包）
_LAZY_OPENAPI_CLIENT_ATTRS = frozenset(
    (
        "SpecDrivenClient",
        "build_model_registry",
        "OpenmsApi",
        "create_client",
        "ApiClientError",
        "AuthError",
        "RateLimitError",
        "ValidationError",
        "SpecError",
        "Transport",
        "TransportResponse",
        "TransportError",
        "RequestsTransport",
        "QtNetworkTransport",
    )
)


def __getattr__(name: str):
    """模块级 __getattr__: 惰性转发 openapi_client 的导出符号。

    仅在首次访问上述白名单内的名字时才导入 plugin_sdk.openapi_client,
    保证 `import plugin_sdk` 本身不产生任何 openapi_client 相关副作用。
    """
    if name in _LAZY_OPENAPI_CLIENT_ATTRS:
        from . import openapi_client as _openapi_client

        return getattr(_openapi_client, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
