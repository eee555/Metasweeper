from __future__ import annotations

import re
from urllib.parse import urlsplit

from ..download import ReplayDownloadHandler


def find_video_id(text: str) -> str | None:
    for candidate in re.findall(r"https?://[^\s<>\"'\u3000-\u303f\uff00-\uffef]+", text[:65536], re.IGNORECASE):
        try:
            parsed = urlsplit(candidate.rstrip(".,;:!?)]}"))
        except ValueError:
            continue
        if parsed.netloc.lower() != "www.saolei.wang":
            continue
        match = re.fullmatch(r"/video/(?:download/)?([0-9]{1,20})/?", parsed.path)
        if match and int(match[1]) > 0:
            return str(int(match[1]))
    return None


class SaoleiHandler(ReplayDownloadHandler):
    handler_id = "saolei"
    display_name = "扫雷网录像"
    download_url_template = "https://www.saolei.wang/video/download/{video_id}"

    def match(self, text: str) -> str | None:
        return find_video_id(text)
