"""
开源扫雷网 HTTP API 服务接口

供插件间调用，查询标识绑定与用户信息。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SaoleiUserInfo:
    id: int
    username: str
    realname: str
    firstname: str
    lastname: str


@runtime_checkable
class SaoleiWebsiteService(Protocol):
    """开源扫雷网 API 服务接口"""

    def get_user_info(self, user_id: int) -> SaoleiUserInfo | None: ...

    def get_user_info_bulk(self, user_ids: list[int]) -> list[SaoleiUserInfo]: ...

    def resolve_user_id(self, identifier: str) -> int | None: ...

    def get_rank_display_name(self, identifier: str) -> str: ...


def format_rank_display_name(
    user_info: SaoleiUserInfo | None,
    user_id: int | None = None,
    identifier: str = "",
) -> str:
    """对齐 openms userprofile 昵称规则。"""
    if user_info is not None:
        realname = (user_info.realname or "").strip()
        if realname and realname != "匿名":
            return realname
        return str(user_info.id)
    if user_id is not None:
        return str(user_id)
    return identifier
