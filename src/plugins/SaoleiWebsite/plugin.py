"""
SaoleiWebsite - 插件主类
"""
from __future__ import annotations

from plugin_sdk import BasePlugin, PluginInfo, WindowMode

from plugins.services.saolei_website import SaoleiUserInfo, SaoleiWebsiteService

from .client import SaoleiWebsiteClient
from .config import DEFAULT_API_BASE_URL, DEFAULT_TIMEOUT_SEC, SaoleiWebsiteConfig


class SaoleiWebsitePlugin(BasePlugin[SaoleiWebsiteConfig]):
    """开源扫雷网 HTTP API 客户端"""

    @classmethod
    def plugin_info(cls) -> PluginInfo:
        return PluginInfo(
            name="SaoleiWebsite",
            version="1.0.0",
            description="开源扫雷网 HTTP API 客户端",
            window_mode=WindowMode.CLOSED,
            other_info=SaoleiWebsiteConfig,
        )

    def _setup_subscriptions(self) -> None:
        pass

    def on_initialized(self) -> None:
        self._client = self._build_client()
        self.register_service(self, protocol=SaoleiWebsiteService)
        self.logger.info("SaoleiWebsiteService 已注册")
        self.config_changed.connect(self._on_config_changed)

    def _build_client(self) -> SaoleiWebsiteClient:
        base_url = DEFAULT_API_BASE_URL
        timeout_sec = float(DEFAULT_TIMEOUT_SEC)
        if self.other_info:
            base_url = (self.other_info.api_base_url or "").strip() or DEFAULT_API_BASE_URL
            timeout_sec = float(self.other_info.timeout_sec or DEFAULT_TIMEOUT_SEC)
        return SaoleiWebsiteClient(
            base_url=base_url,
            timeout_sec=timeout_sec,
            user_agent=f"MetaSweeper-SaoleiWebsite/{self.info.version}",
        )

    def _on_config_changed(self, name: str, value) -> None:
        self.logger.info(f"配置变化: {name} = {value}")
        self._client = self._build_client()

    def resolve_user_id(self, identifier: str) -> int | None:
        return self._client.resolve_user_id(identifier)

    def get_user_info(self, user_id: int) -> SaoleiUserInfo | None:
        return self._client.get_user_info(user_id)

    def get_user_info_bulk(self, user_ids: list[int]) -> list[SaoleiUserInfo]:
        return self._client.get_user_info_bulk(user_ids)

    def get_rank_display_name(self, identifier: str) -> str:
        return self._client.get_rank_display_name(identifier)
