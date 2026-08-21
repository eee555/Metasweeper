"""
SaoleiWebsite - 配置定义
"""
from __future__ import annotations

from PyQt5.QtCore import QCoreApplication

from plugin_sdk import OtherInfoBase, IntConfig, TextConfig

_translate = QCoreApplication.translate

DEFAULT_API_BASE_URL = "https://openms.top"
DEFAULT_TIMEOUT_SEC = 10


class SaoleiWebsiteConfig(OtherInfoBase):
    """开源扫雷网 API 客户端配置"""

    api_base_url = TextConfig(
        default=DEFAULT_API_BASE_URL,
        label=_translate("Form", "API 根地址"),
        description=_translate(
            "Form",
            "开源扫雷网站点根地址，用于查询标识绑定与用户信息",
        ),
        placeholder=DEFAULT_API_BASE_URL,
    )

    timeout_sec = IntConfig(
        default=DEFAULT_TIMEOUT_SEC,
        label=_translate("Form", "请求超时（秒）"),
        description=_translate("Form", "HTTP 请求超时时间"),
        min_value=1,
        max_value=120,
    )
