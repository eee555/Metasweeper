"""
XianNiUpgrade - 配置定义
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PyQt5.QtCore import QCoreApplication
from plugin_sdk import OtherInfoBase, BoolConfig, TextConfig

_translate = QCoreApplication.translate

DEFAULT_API_URL = "https://leixiu-rank.pages.dev"
DEFAULT_IDENTIFIER = "匿名玩家(anonymous player)"
HEALTH_SERVICE = "leixiu-rank"
VALIDATE_TIMEOUT_SEC = 5
_HEALTH_UA = "MetaSweeper-XianNiUpgrade"
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_HEALTH_MAX_BYTES = 4096


def resolve_api_url(url: str) -> str:
    return (url or "").strip() or DEFAULT_API_URL


def is_loopback_hostname(hostname: str | None) -> bool:
    if not hostname:
        return False
    return hostname.strip("[]").lower() in _LOOPBACK_HOSTS


def _effective_port(parsed: urllib.parse.ParseResult) -> int:
    if parsed.port is not None:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    if parsed.scheme == "http":
        return 80
    return -1


def _origin_key(url: str) -> tuple[str, str, int] | None:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if not parsed.scheme or not host:
        return None
    return (parsed.scheme.lower(), host, _effective_port(parsed))


def api_url_transport_error(url: str) -> str | None:
    """非 loopback 必须 https。格式不对或协议不对时返回文案。"""
    raw = resolve_api_url(url)
    try:
        parsed = urllib.parse.urlparse(raw)
    except ValueError:
        return _translate("Form", "排行站地址无效")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return _translate("Form", "排行站地址无效")
    if not is_loopback_hostname(parsed.hostname) and parsed.scheme != "https":
        return _translate("Form", "排行站地址须使用 HTTPS")
    return None


def is_rank_health_payload(data: object) -> bool:
    return (
        isinstance(data, dict)
        and data.get("ok") is True
        and data.get("service") == HEALTH_SERVICE
    )


def _validate_api_url(url: str) -> str | None:
    """GET {url}/api/health；空地址用默认域名。须 2xx + JSON + ok + service。"""
    transport_error = api_url_transport_error(url)
    if transport_error:
        return transport_error

    raw = resolve_api_url(url)
    health_url = raw.rstrip("/") + "/api/health"
    req = urllib.request.Request(
        health_url,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": _HEALTH_UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=VALIDATE_TIMEOUT_SEC) as resp:
            status = int(getattr(resp, "status", 200))
            if not (200 <= status < 300):
                return _translate("Form", "无法连接排行站")
            final_url = str(getattr(resp, "geturl", lambda: health_url)())
            if _origin_key(final_url) != _origin_key(health_url):
                return _translate("Form", "无法连接排行站")
            raw_body = resp.read(_HEALTH_MAX_BYTES)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return _translate("Form", "无法连接排行站")

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return _translate("Form", "无法连接排行站")
    if not is_rank_health_payload(data):
        return _translate("Form", "该地址不是雷修排行站")
    return None


class XianNiUpgradeConfig(OtherInfoBase):
    """雷修境界插件配置"""

    api_url = TextConfig(
        default=DEFAULT_API_URL,
        label=_translate("Form", "排行站地址"),
        description=_translate("Form", "官方排行站地址（固定），上传时会 POST 到 {地址}/api/upload"),
        placeholder="https://leixiu-rank.pages.dev",
        validator=_validate_api_url,
        readonly=True,
    )

    auto_upload = BoolConfig(
        default=False,
        label=_translate("Form", "自动上传排行"),
        description=_translate(
            "Form",
            "每局胜利后静默上传。60 秒内不连发；成功不弹窗、不打开浏览器",
        ),
    )

    upload_token = TextConfig(
        default="",
        label=_translate("Form", "上传令牌"),
        password=True,
        copy_button=True,
        description=_translate(
            "Form",
            "首次上传前自动生成。换电脑请点击右侧「复制」，在新电脑设置里粘贴。"
            "建议生成后立即备份；误改且已保存后，只有旧备份或旧 config 能恢复",
        ),
        placeholder=_translate("Form", "首次上传前自动生成"),
    )

    @classmethod
    def settings_extra_hints(cls, config_path: Path) -> list[str]:
        """插件设置对话框底部显示的动态说明。"""
        return [
            _translate("Form", "配置文件：{path}").format(path=str(config_path)),
            _translate(
                "Form",
                "建议生成后立即点「复制」备份；误改且已保存后，只有旧备份或旧 config 能恢复。",
            ),
        ]

    open_site_after_upload = BoolConfig(
        default=False,
        label=_translate("Form", "上传成功后打开排行页"),
        description=_translate("Form", "成功上传后用系统浏览器打开排行站（仅手动上传）"),
    )

    rules_dialog_seen = BoolConfig(
        default=False,
        visible=False,
    )
