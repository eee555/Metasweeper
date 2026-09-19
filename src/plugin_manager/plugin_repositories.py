"""Hosting-specific repository URLs, tag responses and archive requests."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit

import requests
from PyQt5.QtCore import QCoreApplication


def _tr(text: str) -> str:
    return QCoreApplication.translate("PluginDownloadDialog", text)


@dataclass(frozen=True)
class RepositoryTag:
    name: str
    commit: str


@dataclass(frozen=True)
class PluginRepository:
    platform: str
    origin: str
    path: str

    @classmethod
    def from_url(cls, value: str, platform: str = "auto") -> PluginRepository:
        url = urlsplit(value.strip())
        if (
            url.scheme != "https" or not url.hostname or url.username or url.password
            or re.search(r"[\s\\]", url.netloc)
        ):
            raise ValueError(_tr("请输入有效的仓库 HTTPS 链接。"))
        port = url.port
        known_platform = PUBLIC_HOSTS.get(url.hostname.lower())
        if platform == "auto":
            if known_platform is None:
                raise ValueError(_tr("无法自动识别此站点，请选择托管平台。"))
            platform = known_platform
        if platform not in PROVIDERS:
            raise ValueError(_tr("不支持此托管平台。"))
        if known_platform and platform != known_platform:
            raise ValueError(_tr("链接与所选托管平台不匹配。"))
        if platform in ("github", "gitee") and (known_platform != platform or port not in (None, 443)):
            raise ValueError(_tr("链接与所选托管平台不匹配。"))
        raw_path = unquote(url.path).strip("/")
        path = PROVIDERS[platform].repository_path(raw_path).removesuffix(".git")
        parts = path.split("/")
        if len(parts) < 2 or any(
            part in ("", ".", "..") or not re.fullmatch(r"[\w.-]+", part, re.ASCII)
            for part in parts
        ):
            raise ValueError(_tr("请输入有效的仓库 HTTPS 链接。"))
        host = url.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        authority = f"{host}:{port}" if port not in (None, 443) else host
        return cls(platform, f"https://{authority}", path)

    @property
    def url(self) -> str:
        return f"{self.origin}/{self.path}"

    @property
    def provider(self) -> HostingProvider:
        return PROVIDERS[self.platform]

    @property
    def module_name(self) -> str:
        host = urlsplit(self.origin).netloc
        if host == "codeberg.org":
            prefix = "codeberg"
        elif host in ("github.com", "gitlab.com", "gitee.com"):
            prefix = self.platform
        else:
            prefix = f"{self.platform}_{host}"
        return re.sub(r"[^a-z0-9_]", "_", f"{prefix}_{self.path}".lower())


class HostingProvider:
    api_prefix = ""
    page_size_key = "per_page"
    page_size = 100
    headers = {"Accept": "application/json"}

    def repository_path(self, path: str) -> str:
        return "/".join(path.split("/")[:2])

    def api_url(self, repository: PluginRepository) -> str:
        return repository.origin + self.api_prefix + quote(repository.path, safe="/")

    def tags_request(self, repository: PluginRepository, page: int) -> tuple[str, dict]:
        return self.api_url(repository) + "/tags", {self.page_size_key: self.page_size, "page": page}

    def parse_tag(self, item: dict) -> RepositoryTag:
        return RepositoryTag(item["name"], item["commit"]["sha"])

    def has_next_page(self, response: requests.Response, items: list) -> bool:
        if "Link" in response.headers or response.links:
            return "next" in response.links
        # Some installations cap the requested page size or omit pagination headers.
        return bool(items)

    def archive_request(self, repository: PluginRepository, tag: RepositoryTag) -> tuple[str, dict]:
        raise NotImplementedError


class GitHubProvider(HostingProvider):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

    def api_url(self, repository: PluginRepository) -> str:
        return "https://api.github.com/repos/" + repository.path

    def has_next_page(self, response: requests.Response, items: list) -> bool:
        return "next" in response.links

    def archive_request(self, repository: PluginRepository, tag: RepositoryTag) -> tuple[str, dict]:
        return self.api_url(repository) + "/zipball/" + quote(tag.commit, safe=""), {}


class GitLabProvider(HostingProvider):
    def repository_path(self, path: str) -> str:
        return path.split("/-/", 1)[0]

    def api_url(self, repository: PluginRepository) -> str:
        return repository.origin + "/api/v4/projects/" + quote(repository.path, safe="") + "/repository"

    def parse_tag(self, item: dict) -> RepositoryTag:
        return RepositoryTag(item["name"], item["commit"]["id"])

    def has_next_page(self, response: requests.Response, items: list) -> bool:
        if "X-Next-Page" in response.headers:
            return bool(response.headers["X-Next-Page"])
        return super().has_next_page(response, items)

    def archive_request(self, repository: PluginRepository, tag: RepositoryTag) -> tuple[str, dict]:
        return self.api_url(repository) + "/archive.zip", {"sha": tag.commit}


class GiteeProvider(HostingProvider):
    api_prefix = "/api/v5/repos/"

    def archive_request(self, repository: PluginRepository, tag: RepositoryTag) -> tuple[str, dict]:
        return self.api_url(repository) + "/zipball", {"ref": tag.commit}


class GiteaProvider(HostingProvider):
    api_prefix = "/api/v1/repos/"
    page_size_key = "limit"
    page_size = 50

    def archive_request(self, repository: PluginRepository, tag: RepositoryTag) -> tuple[str, dict]:
        return self.api_url(repository) + "/archive/" + quote(tag.commit, safe="") + ".zip", {}


PUBLIC_HOSTS = {"github.com": "github", "gitlab.com": "gitlab", "gitee.com": "gitee", "codeberg.org": "gitea"}
PROVIDERS = {
    "github": GitHubProvider(),
    "gitlab": GitLabProvider(),
    "gitee": GiteeProvider(),
    "gitea": GiteaProvider(),
}
