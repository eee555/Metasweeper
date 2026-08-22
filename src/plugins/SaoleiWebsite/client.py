"""
开源扫雷网 HTTP 客户端（stdlib urllib）
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from plugins.services.saolei_website import SaoleiUserInfo, format_rank_display_name

from .config import DEFAULT_API_BASE_URL, DEFAULT_TIMEOUT_SEC

logger = logging.getLogger(__name__)


def _parse_user_info(data: dict[str, Any]) -> SaoleiUserInfo | None:
    user_id = data.get("id")
    if user_id is None:
        return None
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    return SaoleiUserInfo(
        id=uid,
        username=str(data.get("username") or ""),
        realname=str(data.get("realname") or ""),
        firstname=str(data.get("firstname") or ""),
        lastname=str(data.get("lastname") or ""),
    )


class SaoleiWebsiteClient:
    """开源扫雷网只读 API 客户端。"""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_API_BASE_URL,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        user_agent: str = "MetaSweeper-SaoleiWebsite/1.0.0",
    ) -> None:
        self._base_url = (base_url or "").strip().rstrip("/")
        self._timeout_sec = timeout_sec
        self._user_agent = user_agent
        self._identifier_cache: dict[str, int | None] = {}
        self._user_info_cache: dict[int, SaoleiUserInfo | None] = {}

    def clear_cache(self) -> None:
        self._identifier_cache.clear()
        self._user_info_cache.clear()

    def _request_json(self, url: str) -> tuple[int, Any | None]:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": self._user_agent,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_sec) as resp:
                status = int(getattr(resp, "status", 200))
                raw = resp.read()
        except urllib.error.HTTPError as e:
            return e.code, None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.warning("开源扫雷网请求失败 %s: %s", url, e)
            return -1, None
        except Exception as e:
            logger.warning("开源扫雷网请求异常 %s: %s", url, e)
            return -1, None

        if not raw:
            return status, None
        try:
            return status, json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return status, None

    def resolve_user_id(self, identifier: str) -> int | None:
        key = (identifier or "").strip()
        if not key:
            return None
        if key in self._identifier_cache:
            return self._identifier_cache[key]

        query = urllib.parse.urlencode({"identifier": key})
        url = f"{self._base_url}/identifier/get/staff/?{query}"
        status, data = self._request_json(url)
        if status == 404:
            self._identifier_cache[key] = None
            return None
        if status != 200 or not isinstance(data, dict):
            self._identifier_cache[key] = None
            return None

        user = data.get("user")
        if user is None:
            self._identifier_cache[key] = None
            return None
        try:
            user_id = int(user)
        except (TypeError, ValueError):
            self._identifier_cache[key] = None
            return None

        self._identifier_cache[key] = user_id
        return user_id

    def get_user_info(self, user_id: int) -> SaoleiUserInfo | None:
        if user_id in self._user_info_cache:
            return self._user_info_cache[user_id]

        url = f"{self._base_url}/api/userprofile/info/{user_id}"
        status, data = self._request_json(url)
        if status != 200 or not isinstance(data, dict):
            self._user_info_cache[user_id] = None
            return None

        info = _parse_user_info(data)
        self._user_info_cache[user_id] = info
        return info

    def get_user_info_bulk(self, user_ids: list[int]) -> list[SaoleiUserInfo]:
        ids = [uid for uid in user_ids if isinstance(uid, int)]
        if not ids:
            return []

        missing = [uid for uid in ids if uid not in self._user_info_cache]
        if missing:
            query = urllib.parse.urlencode({"ids": ",".join(str(i) for i in missing)})
            url = f"{self._base_url}/api/userprofile/infobulk?{query}"
            status, data = self._request_json(url)
            if status == 200 and isinstance(data, list):
                seen: set[int] = set()
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    info = _parse_user_info(item)
                    if info is None or info.id in seen:
                        continue
                    seen.add(info.id)
                    self._user_info_cache[info.id] = info
            for uid in missing:
                self._user_info_cache.setdefault(uid, None)

        result: list[SaoleiUserInfo] = []
        for uid in ids:
            info = self._user_info_cache.get(uid)
            if info is not None:
                result.append(info)
        return result

    def get_rank_display_name(self, identifier: str) -> str:
        key = (identifier or "").strip()
        if not key:
            return identifier
        try:
            user_id = self.resolve_user_id(key)
            if user_id is None:
                return key
            info = self.get_user_info(user_id)
            return format_rank_display_name(info, user_id=user_id, identifier=key)
        except Exception as e:
            logger.warning("解析排行昵称失败 identifier=%r: %s", key, e)
            return key
