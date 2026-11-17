from __future__ import annotations

import re
from urllib.parse import urlencode

from ..download import ReplayDownloadHandler
from utils.plugin_i18n import PluginTranslate

_translate = PluginTranslate("ClipboardReplay")


def find_replay_code(text: str) -> str | None:
    if len(text) > 256:
        return None
    match = re.fullmatch(
        r"\s*95经典扫雷\s*\|\s*([0-9]{1,20})\s*-\s*([0-9]{1,20})"
        r"\s*-\s*([0-9]{1,20})\s*", text)
    if match is None:
        return None
    uid, season, replay_id = int(match[1]), int(match[2]), int(match[3])
    if uid <= 0 or season <= 0 or replay_id <= 0:
        return None
    return f"{uid}-{season}-{replay_id}"


class Classic95Handler(ReplayDownloadHandler):
    handler_id = "classic95"
    display_name = _translate("ClipboardReplay", "95经典扫雷小程序")

    def match(self, text: str) -> str | None:
        return find_replay_code(text)

    def build_download_url(self, video_id: str) -> str:
        uid, season, replay_id = video_id.split("-")
        query = urlencode({"season": season, "id": replay_id, "uid": uid})
        return f"https://mg.xiean.net:6789/v1/replay/open?{query}"
