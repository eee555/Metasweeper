"""Download tagged plugin packages without requiring a Git installation."""
from __future__ import annotations

import base64
import hashlib
import html
import ipaddress
import json
import re
import stat
import time
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Callable
from urllib.parse import quote, unquote, urljoin, urlsplit
from zipfile import ZipFile

import requests
from PySide6.QtCore import QCoreApplication

from .plugin_repositories import PluginRepository, RepositoryTag


_MAX_DOWNLOAD = 100 * 1024 * 1024
_MAX_EXTRACTED = 500 * 1024 * 1024
_MAX_INDEX_BYTES = 1024 * 1024
_MAX_README_BYTES = 1024 * 1024
_MAX_README_API_BYTES = 2 * _MAX_README_BYTES  # Base64, line breaks and metadata.
_README_FILENAMES = tuple(
    stem + suffix
    for suffix in (".md", ".MD", ".markdown", ".MARKDOWN", ".txt", ".TXT", "")
    for stem in ("README", "Readme", "readme", "ReadMe")
)
_GIT_REFS_MEDIA_TYPE = "application/x-git-upload-pack-advertisement"
_GIT_REFS_PREAMBLE = b"001e# service=git-upload-pack\n0000"
_CHUNK_SIZE = 64 * 1024
_MAX_REDIRECTS = 5
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

# 「原始仓库主机 + 平台官方 API / 归档 CDN 主机」白名单。
# 只用于校验请求地址与每一跳重定向目标，不参与 URL 拼接。
_PLATFORM_CDN_HOSTS: dict[str, frozenset[str]] = {
    "github": frozenset({
        "github.com", "api.github.com", "codeload.github.com",
        "objects.githubusercontent.com", "raw.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }),
    "gitlab": frozenset({"gitlab.com"}),
    "gitee": frozenset({"gitee.com", "so.gitee.com"}),
    "gitea": frozenset({"codeberg.org"}),
}


def _tr(text: str) -> str:
    return QCoreApplication.translate("PluginDownloadDialog", text)


def is_plain_plugin_directory(path: Path) -> bool:
    try:
        info = path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return False
    # Windows junctions are directories with the reparse-point flag.
    return stat.S_ISDIR(info.st_mode) and not (
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _allowed_hosts(repository: PluginRepository) -> frozenset[str]:
    """仓库允许的主机集合 = 原始 origin 主机 + 平台官方 API/CDN 主机。"""
    origin_host = (urlsplit(repository.origin).hostname or "").lower()
    return frozenset({origin_host, *_PLATFORM_CDN_HOSTS.get(repository.platform, ())})


def _allowed_ports(repository: PluginRepository) -> dict[str, frozenset[int]]:
    """只允许自建 origin 使用其配置端口，平台/CDN 主机使用标准 HTTPS 端口。"""
    origin = urlsplit(repository.origin)
    origin_host = (origin.hostname or "").lower()
    ports = {host: frozenset({443}) for host in _allowed_hosts(repository)}
    ports[origin_host] = frozenset({origin.port or 443})
    return ports


def _host_is_forbidden_ip(host: str) -> bool:
    """IP 字面量若属于环回 / 链路本地 / 私有 / 保留网段则禁止。"""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False  # 域名：静态检查无法覆盖 DNS 解析结果
    return any((address.is_loopback, address.is_link_local,
                address.is_private, address.is_reserved))


def _validate_url(
    url: str,
    *,
    allowed_hosts: frozenset[str],
    allowed_ports: dict[str, frozenset[int]],
) -> None:
    """校验单跳 URL 的 scheme / host / port / IP 类别。"""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    try:
        port = parts.port or 443
    except ValueError as exc:
        raise ValueError(_tr("下载链接包含无效端口，已拒绝。")) from exc
    if not host or parts.username or parts.password or re.search(r"[\s\\]", parts.netloc):
        raise ValueError(_tr("下载链接包含非法主机，已拒绝。"))
    if parts.scheme != "https":
        raise ValueError(_tr("下载链接不是 HTTPS，已拒绝。"))
    if host not in allowed_hosts:
        raise ValueError(_tr("下载重定向到未授权的主机，已拒绝。"))
    if port not in allowed_ports.get(host, frozenset()):
        raise ValueError(_tr("下载链接使用未授权的端口，已拒绝。"))
    if _host_is_forbidden_ip(host):
        raise ValueError(_tr("自建站点不允许使用内网或保留 IP 地址。"))


class DownloadCancelled(Exception):
    pass


class HostingRequestRejected(ValueError):
    """A hosting endpoint refused or rate-limited a request."""


class GitHubApiRateLimit(HostingRequestRejected):
    """GitHub REST API anonymous quota exhausted; callers may use web fallback."""


class _GitHubSearchPageParser(HTMLParser):
    """Read the embedded repository search payload from GitHub's public HTML page."""

    def __init__(self) -> None:
        super().__init__()
        self._capture = False
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self._capture = (
            tag == "script"
            and attributes.get("type") == "application/json"
            and attributes.get("data-target") == "react-app.embeddedData"
        )

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._capture = False

    def handle_data(self, data: str) -> None:
        if self._capture:
            self.chunks.append(data)


class _GitHubTagPageParser(HTMLParser):
    """Extract version tag names and full commit hashes from GitHub's tag page."""

    def __init__(self, repository_path: str) -> None:
        super().__init__()
        self.repository_path = "/" + repository_path.strip("/")
        self.current_tag: str | None = None
        self.tags: list[RepositoryTag] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        href = attributes.get("href") or ""
        tag_prefix = self.repository_path + "/releases/tag/"
        commit_prefix = self.repository_path + "/commit/"
        if tag == "a" and href.startswith(tag_prefix):
            self.current_tag = unquote(href[len(tag_prefix):].split("/", 1)[0])
        elif tag == "a" and self.current_tag and href.startswith(commit_prefix):
            commit = href[len(commit_prefix):].split("/", 1)[0]
            if re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit):
                self.tags.append(RepositoryTag(self.current_tag, commit))
                self.current_tag = None


class PluginDownloader:
    def __init__(
        self,
        session: requests.Session,
        cancelled: Callable[[], bool],
        progress: Callable[[int, int], None],
    ):
        self.session = session
        self.cancelled = cancelled
        self.progress = progress
        self.session.headers.update({
            "User-Agent": "Metasweeper-PluginManager",
        })

    def _check_cancelled(self) -> None:
        if self.cancelled():
            raise DownloadCancelled()

    @staticmethod
    def _check_response(response: requests.Response) -> None:
        if response.status_code == 404:
            raise ValueError(_tr("仓库或版本不存在，或仓库不是公开仓库。"))
        if response.status_code == 403 and response.headers.get(
            "X-RateLimit-Remaining") == "0":
            raise GitHubApiRateLimit(_tr(
                "GitHub API 匿名请求额度已用完；尝试从标签网页读取版本。"))
        if response.status_code in (403, 429):
            raise HostingRequestRejected(_tr("托管平台拒绝请求或请求次数已达上限，请稍后重试。"))
        response.raise_for_status()

    def _safe_get(
        self,
        repository: PluginRepository,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        stream: bool = False,
        timeout: tuple[int, int] = (5, 30),
        allow_not_found: bool = False,
        extra_hosts: frozenset[str] = frozenset(),
    ) -> requests.Response:
        """Issue a request while validating every redirect hop.

        A response without ``url`` is accepted for lightweight test doubles; its
        effective URL is the request URL. Real requests responses always expose it.
        The caller owns and must close the returned response.
        """
        allowed_ports = _allowed_ports(repository)
        for host in extra_hosts:
            allowed_ports.setdefault(host, frozenset({443}))
        allowed_hosts = frozenset(allowed_ports)
        current_url = url
        request_params = params

        for redirect_count in range(_MAX_REDIRECTS + 1):
            self._check_cancelled()
            _validate_url(
                current_url,
                allowed_hosts=allowed_hosts,
                allowed_ports=allowed_ports,
            )
            for attempt in range(3):
                self._check_cancelled()
                try:
                    response = self.session.get(
                        current_url,
                        params=request_params,
                        headers=headers,
                        stream=stream,
                        timeout=timeout,
                        allow_redirects=False,
                    )
                    break
                except (requests.ConnectionError, requests.Timeout):
                    if attempt == 2:
                        raise
                    time.sleep(0.25 * (attempt + 1))
            request_params = None

            try:
                response_url = getattr(response, "url", None) or current_url
                _validate_url(
                    response_url,
                    allowed_hosts=allowed_hosts,
                    allowed_ports=allowed_ports,
                )
                if response.status_code not in _REDIRECT_STATUSES:
                    if not (allow_not_found and response.status_code == 404):
                        self._check_response(response)
                    return response

                location = response.headers.get("Location")
                if not location:
                    raise ValueError(_tr("下载服务器返回了不完整的重定向。"))
                if redirect_count >= _MAX_REDIRECTS:
                    raise ValueError(_tr("下载重定向次数超过限制。"))
                next_url = urljoin(response_url, location)
                _validate_url(
                    next_url, allowed_hosts=allowed_hosts, allowed_ports=allowed_ports,
                )
            except Exception:
                close = getattr(response, "close", None)
                if callable(close):
                    close()
                raise

            close = getattr(response, "close", None)
            if callable(close):
                close()
            current_url = next_url

        raise ValueError(_tr("下载重定向次数超过限制。"))

    def discover_plugins(self, source: str = "github"):
        """Discover public plugins from GitHub topics or Gitee repository search."""
        if source == "gitee":
            return self._discover_gitee_plugins()
        if source != "github":
            raise ValueError(_tr("不支持的插件搜索源：{source}").format(source=source))

        origin = PluginRepository.from_url("https://github.com/github/github")
        entries = []
        seen = set()
        try:
            for page in range(1, 11):
                with self._safe_get(
                    origin, "https://api.github.com/search/repositories",
                    params={"q": "topic:metasweeper-plugin archived:false",
                            "per_page": 100, "page": page},
                    headers=origin.provider.headers,
                    timeout=(3, 12),
                ) as response:
                    data = response.json()
                    if data.get("incomplete_results"):
                        raise GitHubApiRateLimit(
                            _tr("GitHub 搜索结果不完整，改用公开搜索页面。"))
                    entries.extend(self._catalog_entries(data.get("items", []), seen))
                    if not response.links.get("next"):
                        return entries
        except GitHubApiRateLimit:
            return self._discover_github_topic_page(origin)
        return entries

    def _gitee_search_page(self, origin: PluginRepository, offset: int) -> dict:
        url = "https://so.gitee.com/v1/search/widget/wong1slagnlmzwvsu5ya"
        with self._safe_get(
            origin, url,
            params={"q": "metasweeper", "from": offset, "size": 100},
            headers={"Accept": "application/json"},
            timeout=(3, 12),
        ) as response:
            return response.json()

    def _discover_gitee_plugins(self):
        """Search Gitee's public repository index for conventionally named plugins."""
        from .plugin_catalog import CatalogEntry

        origin = PluginRepository.from_url("https://gitee.com/example/example")
        entries = []
        seen: set[str] = set()
        for offset in range(0, 1000, 100):
            self._check_cancelled()
            data = self._gitee_search_page(origin, offset)
            hits = (data.get("hits") or {}).get("hits") or []
            for hit in hits:
                fields = hit.get("fields") or {}
                repository_url = self._gitee_search_field(fields, "url")
                path = self._gitee_search_field(fields, "path")
                if not path.lower().startswith("metasweeper-") or not repository_url:
                    continue
                try:
                    repository = PluginRepository.from_url(repository_url, "gitee")
                except ValueError:
                    continue
                key = repository.url.lower()
                if key in seen:
                    continue
                seen.add(key)
                entries.append(CatalogEntry(
                    name=path,
                    repository=repository,
                    description=self._gitee_search_field(fields, "description"),
                    author=self._gitee_search_field(fields, "owner.path.keyword"),
                ))
            if offset + len(hits) >= int((data.get("hits") or {}).get(
                    "total", {}).get("value", 0)) or not hits:
                break
        return entries

    @staticmethod
    def _gitee_search_field(fields: dict, name: str) -> str:
        value = fields.get(name, "")
        if isinstance(value, list):
            value = value[0] if value else ""
        return str(value or "")

    @staticmethod
    def _catalog_entries(items: list[dict], seen: set[str]):
        from .plugin_catalog import CatalogEntry

        entries = []
        for item in items:
            try:
                if item.get("private") or item.get("archived"):
                    continue
                html_url = item.get("html_url")
                owner = item.get("owner") or {}
                if not html_url and item.get("repo"):
                    data = item["repo"].get("repository") or {}
                    html_url = f"https://github.com/{data['owner_login']}/{data['name']}"
                    owner = {"login": data.get("owner_login")}
                repo = PluginRepository.from_url(html_url, "github")
                key = repo.url.lower()
                if key in seen:
                    continue
                seen.add(key)
                description = item.get("description") or item.get("hl_trunc_description") or ""
                description = html.unescape(re.sub(r"<[^>]*>", "", description))
                entries.append(CatalogEntry(
                    name=item.get("name") or repo.path.split("/")[-1],
                    repository=repo, description=description,
                    author=owner.get("login") or ""))
            except (KeyError, TypeError, ValueError):
                continue
        return entries

    def _discover_github_topic_page(self, origin: PluginRepository):
        """Use GitHub's public search page when the Search REST quota is exhausted."""
        entries = []
        seen: set[str] = set()
        for page in range(1, 11):
            self._check_cancelled()
            with self._safe_get(
                origin, "https://github.com/search",
                params={"q": "topic:metasweeper-plugin archived:false",
                        "type": "repositories", "page": page},
                headers={"Accept": "text/html"},
                timeout=(3, 12),
            ) as response:
                parser = _GitHubSearchPageParser()
                parser.feed(response.text)
                parser.close()
            if not parser.chunks:
                if page == 1:
                    raise ValueError(_tr(
                        "GitHub 搜索 API 已限流，且公开搜索页面无法解析。"))
                break
            try:
                payload = json.loads("".join(parser.chunks))
                route = payload["payload"]["blackbirdSearchRoute"]
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ValueError(_tr("无法解析 GitHub 插件搜索结果。")) from exc
            results = route.get("results", [])
            entries.extend(self._catalog_entries(results, seen))
            if page >= int(route.get("page_count", 1)) or not results:
                break
        return entries

    def list_tags(self, repository: PluginRepository) -> list[RepositoryTag]:
        tags: list[RepositoryTag] = []
        page = 1
        try:
            while True:
                self._check_cancelled()
                url, params = repository.provider.tags_request(repository, page)
                with self._safe_get(
                    repository, url, params=params,
                    headers=repository.provider.headers,
                    timeout=(3, 12),
                ) as response:
                    self._check_response(response)
                    items = response.json()
                    tags.extend(repository.provider.parse_tag(item)
                                for item in items)
                    if not repository.provider.has_next_page(response, items):
                        return tags
                page += 1
        except HostingRequestRejected as exc:
            if repository.platform == "gitee":
                return self._list_gitee_tag_refs(repository)
            if repository.platform == "github" and isinstance(exc, GitHubApiRateLimit):
                return self._list_github_tags_page(repository)
            raise

    def _list_gitee_tag_refs(self, repository: PluginRepository) -> list[RepositoryTag]:
        media_type = "application/x-git-upload-pack-advertisement"
        invalid = _tr("无法读取 Gitee 仓库的版本标签。")
        data = bytearray()
        with self._safe_get(
            repository, repository.url + ".git/info/refs",
            params={"service": "git-upload-pack"}, headers={"Accept": media_type},
            stream=True, timeout=(3, 12),
        ) as response:
            if response.headers.get("Content-Type", "").split(";", 1)[0] != media_type:
                raise ValueError(invalid)
            for chunk in response.iter_content(_CHUNK_SIZE):
                self._check_cancelled()
                data.extend(chunk)
                if len(data) > _MAX_INDEX_BYTES:
                    raise ValueError(invalid)

        preamble = b"001e# service=git-upload-pack\n0000"
        if not data.startswith(preamble):
            raise ValueError(invalid)
        refs: dict[str, str] = {}
        peeled: dict[str, str] = {}
        offset = len(preamble)
        while offset + 4 <= len(data):
            size = data[offset:offset + 4]
            if size == b"0000" and offset + 4 == len(data):
                return [RepositoryTag(name, peeled.get(name, sha))
                        for name, sha in refs.items()]
            if not re.fullmatch(rb"[0-9a-fA-F]{4}", size):
                break
            length = int(size, 16)
            end = offset + length
            if length < 4 or end > len(data):
                break
            packet = data[offset + 4:end].split(b"\0", 1)[0].rstrip(b"\n")
            offset = end
            match = re.fullmatch(rb"([0-9a-fA-F]{40}|[0-9a-fA-F]{64}) refs/tags/(.+)", packet)
            if match is None:
                continue
            name = match[2].decode("utf-8", errors="surrogateescape")
            sha = match[1].decode("ascii")
            if name.endswith("^{}"):
                peeled[name[:-3]] = sha
            else:
                refs[name] = sha
        raise ValueError(invalid)

    def _list_github_tags_page(
        self, repository: PluginRepository,
    ) -> list[RepositoryTag]:
        """Fallback to GitHub's public HTML tags page when REST quota is exhausted."""
        tags: list[RepositoryTag] = []
        base = repository.url.rstrip("/") + "/tags"
        seen: set[tuple[str, str]] = set()
        for page in range(1, 11):
            self._check_cancelled()
            url = base if page == 1 else f"{base}?page={page}"
            with self._safe_get(repository, url, stream=True) as response:
                parser = _GitHubTagPageParser(repository.path)
                for chunk in response.iter_content(_CHUNK_SIZE):
                    self._check_cancelled()
                    parser.feed(chunk.decode("utf-8", errors="replace"))
                parser.close()
            new_tags = [tag for tag in parser.tags
                        if (tag.name, tag.commit) not in seen]
            if not new_tags:
                break
            tags.extend(new_tags)
            seen.update((tag.name, tag.commit) for tag in new_tags)
        if not tags:
            raise ValueError(_tr(
                "GitHub API 已限流，且无法从公开标签网页读取版本。"))
        return tags

    def fetch_readme(self, repository: PluginRepository) -> tuple[str, str] | None:
        """Return the default-branch README and its directory URL for browser links."""
        if repository.platform not in {"github", "gitee"}:
            raise ValueError(_tr("仅支持读取 GitHub 和 Gitee 仓库的 README。"))
        if PluginRepository.from_url(repository.url, repository.platform) != repository:
            raise ValueError(_tr("请输入有效的仓库 HTTPS 链接。"))

        if repository.platform == "github":
            try:
                return self._fetch_github_readme(repository)
            except GitHubApiRateLimit:
                # GitHub resolves HEAD in both the raw and browser routes.
                return self._fetch_raw_readme(repository, "HEAD")
        return self._fetch_raw_readme(repository, self._gitee_default_branch(repository))

    def _read_readme_response(
        self, response: requests.Response, *, limit: int = _MAX_README_BYTES,
    ) -> bytes:
        self._check_cancelled()
        if response.status_code != 200:
            raise ValueError(_tr("托管平台返回了意外的 README 响应。"))
        if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() in {
            "text/html", "application/xhtml+xml",
        }:
            raise ValueError(_tr("托管平台返回了意外的 README 响应。"))
        too_large = _tr("README 文件超过 1 MiB 或响应超过大小限制。")
        if int(response.headers.get("Content-Length") or 0) > limit:
            raise ValueError(too_large)
        body = bytearray()
        for chunk in response.iter_content(_CHUNK_SIZE):
            self._check_cancelled()
            if len(body) + len(chunk) > limit:
                raise ValueError(too_large)
            body.extend(chunk)
        self._check_cancelled()
        return bytes(body)

    @staticmethod
    def _readme_base_url(repository: PluginRepository, branch: str, path: str) -> str:
        if not branch or any(
            part in {"", ".", ".."} for part in branch.split("/")
        ) or re.search(r"[\x00-\x20\x7f~^:?*\[\\]|\.\.", branch):
            raise ValueError(_tr("无法识别 README 所在的仓库分支。"))
        directory = path.rpartition("/")[0]
        base = f"{repository.url}/tree/{quote(branch, safe='')}/"
        return base + f"{quote(directory, safe='/')}/" if directory else base

    @staticmethod
    def _decode_readme(content: bytes) -> str:
        if len(content) > _MAX_README_BYTES:
            raise ValueError(_tr("README 文件超过 1 MiB 或响应超过大小限制。"))
        if b"\0" in content:
            raise ValueError(_tr("README 不是有效的 UTF-8 文本。"))
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(_tr("README 不是有效的 UTF-8 文本。")) from exc

    def _fetch_github_readme(self, repository: PluginRepository) -> tuple[str, str] | None:
        with self._safe_get(
            repository, repository.provider.api_url(repository) + "/readme",
            headers=repository.provider.headers, stream=True, timeout=(3, 8),
            allow_not_found=True,
        ) as response:
            self._check_cancelled()
            if response.status_code == 404:
                return None
            body = self._read_readme_response(response, limit=_MAX_README_API_BYTES)

        invalid = _tr("无法解析 GitHub README 响应。")
        try:
            data = json.loads(body)
            link = urlsplit(data["html_url"])
            path = data["path"]
            link_path = unquote(link.path)
            prefix = f"/{repository.path}/blob/"
            suffix = "/" + path
            if (
                link.scheme != "https" or link.netloc.lower() != "github.com"
                or link.query or link.fragment
                or not link_path.casefold().startswith(prefix.casefold())
                or not link_path.endswith(suffix)
                or any(part in {"", ".", ".."} for part in path.split("/"))
                or re.search(r"[\x00-\x1f\x7f\\]", path)
                or data["encoding"] != "base64"
            ):
                raise ValueError(invalid)
            content = base64.b64decode("".join(data["content"].split()), validate=True)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(invalid) from exc
        branch = link_path[len(prefix):-len(suffix)]
        return self._decode_readme(content), self._readme_base_url(repository, branch, path)

    def _gitee_default_branch(self, repository: PluginRepository) -> str:
        try:
            with self._safe_get(
                repository, repository.provider.api_url(repository),
                headers=repository.provider.headers, stream=True, timeout=(3, 8),
            ) as response:
                body = self._read_readme_response(response)
        except HostingRequestRejected:
            # The public smart HTTP advertisement identifies HEAD when REST is limited.
            with self._safe_get(
                repository, repository.url + ".git/info/refs",
                params={"service": "git-upload-pack"},
                headers={"Accept": _GIT_REFS_MEDIA_TYPE}, stream=True, timeout=(3, 8),
            ) as response:
                body = self._read_readme_response(response)
                media_type = response.headers.get("Content-Type", "").split(";", 1)[0]
            if media_type == _GIT_REFS_MEDIA_TYPE and body.startswith(_GIT_REFS_PREAMBLE):
                offset = len(_GIT_REFS_PREAMBLE)
                size = body[offset:offset + 4]
                if re.fullmatch(rb"[0-9a-fA-F]{4}", size):
                    end = offset + int(size, 16)
                    if offset + 4 < end <= len(body):
                        packet = body[offset + 4:end].removesuffix(b"\n")
                        match = re.fullmatch(
                            rb"(?:[0-9a-f]{40}|[0-9a-f]{64}) HEAD\x00"
                            rb"(?:[^ ]+ )*symref=HEAD:refs/heads/([^ ]+)(?: .*)?", packet,
                        )
                        if match:
                            return match[1].decode("utf-8")
        else:
            data = json.loads(body)
            if isinstance(data, dict) and isinstance(data.get("default_branch"), str):
                return data["default_branch"]
        raise ValueError(_tr("无法识别 README 所在的仓库分支。"))

    def _fetch_raw_readme(
        self, repository: PluginRepository, branch: str,
    ) -> tuple[str, str] | None:
        base = self._readme_base_url(repository, branch, "")
        extra_hosts = (frozenset({"raw.giteeusercontent.com"})
                       if repository.platform == "gitee" else frozenset())
        for filename in _README_FILENAMES:
            url = repository.provider.raw_branch_file_url(repository, branch, filename)
            with self._safe_get(
                repository, url, stream=True, timeout=(3, 8),
                allow_not_found=True, extra_hosts=extra_hosts,
            ) as response:
                self._check_cancelled()
                if response.status_code == 404:
                    continue
                content = self._read_readme_response(response)
            return self._decode_readme(content), base
        return None

    def fetch_index(self, index_repository: PluginRepository) -> str:
        """读取索引仓库根目录的 metasweeper-plugins.json。"""
        from .plugin_catalog import INDEX_FILENAME

        url, params = index_repository.provider.raw_file_request(
            index_repository, INDEX_FILENAME)
        with self._safe_get(
            index_repository, url, params=params,
            headers=index_repository.provider.headers, stream=True,
        ) as response:
            self._check_response(response)
            total = int(response.headers.get("Content-Length", 0))
            if total > _MAX_INDEX_BYTES:
                raise ValueError(_tr("插件索引文件超过 1 MiB。"))
            chunks: list[bytes] = []
            received = 0
            for chunk in response.iter_content(_CHUNK_SIZE):
                self._check_cancelled()
                received += len(chunk)
                if received > _MAX_INDEX_BYTES:
                    raise ValueError(_tr("插件索引文件超过 1 MiB。"))
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8")

    def install(
        self,
        repository: PluginRepository,
        tag: RepositoryTag,
        plugin_dir: Path,
        search_dirs: list[Path],
        *,
        plugin_version: str = "",
        tag_prefix: str = "",
        before_publish: Callable[[Path], None] | None = None,
    ) -> Path:
        destination = plugin_dir / repository.module_name
        for directory in [plugin_dir, *search_dirs]:
            if (directory / repository.module_name).exists() or (directory / f"{repository.module_name}.py").exists():
                raise FileExistsError(_tr("插件目录已存在，不会覆盖：{path}").format(
                    path=directory / repository.module_name))
        self._check_cancelled()
        plugin_dir.mkdir(parents=True, exist_ok=True)
        # Hidden from PluginLoader until the complete package is ready.
        with TemporaryDirectory(prefix="_download_", dir=plugin_dir) as temporary:
            work_dir = Path(temporary)
            archive = work_dir / "source.zip"
            archive_sha256 = self._download(repository, tag, archive)
            extracted = self._extract(archive, work_dir / "source")
            if (extracted / "__init__.py").is_file():
                package = extracted
            else:
                candidates = [
                    child for child in extracted.iterdir()
                    if child.is_dir() and (child / "__init__.py").is_file()
                ]
                if len(candidates) != 1:
                    raise ValueError(_tr(
                        "仓库根目录必须含 __init__.py，或只包含一个插件包目录。"))
                package = candidates[0]
            metadata = {"repository": repository.url, "platform": repository.platform,
                        "tag": tag.name, "commit": tag.commit,
                        "archive_sha256": archive_sha256}
            if plugin_version:
                metadata["version"] = plugin_version
                metadata["tag_prefix"] = tag_prefix
            (package / ".metasweeper-plugin.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            self._check_cancelled()
            if before_publish is not None:
                before_publish(package)
            self._check_cancelled()
            # Same filesystem: publish only after download and preparation succeed.
            package.rename(destination)
        return destination

    def update(self, repository: PluginRepository, tag: RepositoryTag, plugin_dir: Path,
               *, plugin_version: str = "", tag_prefix: str = "",
               destination_name: str | None = None,
               before_publish: Callable[[Path], None] | None = None) -> Path:
        """完整下载并校验后再替换；失败时恢复旧目录。"""
        destination_name = destination_name or repository.module_name
        if Path(destination_name).name != destination_name or destination_name in (".", ".."):
            raise ValueError(_tr("不能更新非普通插件目录。"))
        destination = plugin_dir / destination_name
        if not is_plain_plugin_directory(destination):
            raise ValueError(_tr("不能更新非普通插件目录。"))
        from .plugin_catalog import read_installed_metadata
        metadata = read_installed_metadata(destination)
        try:
            installed_repository = PluginRepository.from_url(
                str(metadata.get("repository") or ""),
                str(metadata.get("platform") or "auto"))
        except ValueError:
            installed_repository = None
        if (installed_repository is None
                or installed_repository.plugin_identity != repository.plugin_identity):
            raise ValueError(_tr("插件来源不匹配，不能自动更新。"))
        with TemporaryDirectory(prefix="_update_", dir=plugin_dir) as temporary:
            work = Path(temporary)
            package = self.install(
                repository, tag, work, [], plugin_version=plugin_version,
                tag_prefix=tag_prefix, before_publish=before_publish)
            self._check_cancelled()
            backup = work / "backup"
            destination.rename(backup)
            try:
                package.rename(destination)
            except BaseException:
                backup.rename(destination)
                raise
        return destination

    def _download(self, repository: PluginRepository, tag: RepositoryTag, archive: Path) -> str:
        url, params = repository.provider.archive_request(repository, tag)
        digest = hashlib.sha256()
        with self._safe_get(
            repository, url, params=params,
            headers=repository.provider.headers, stream=True,
        ) as response:
            total = int(response.headers.get("Content-Length", 0))
            if total > _MAX_DOWNLOAD:
                raise ValueError(_tr("插件压缩包超过 100 MiB。"))
            received = 0
            self.progress(0, total)
            with archive.open("wb") as output:
                for chunk in response.iter_content(_CHUNK_SIZE):
                    self._check_cancelled()
                    received += len(chunk)
                    if received > _MAX_DOWNLOAD:
                        raise ValueError(_tr("插件压缩包超过 100 MiB。"))
                    digest.update(chunk)
                    output.write(chunk)
                    self.progress(received, total)
        return digest.hexdigest()

    def _extract(self, archive: Path, target: Path) -> Path:
        with ZipFile(archive) as source:
            entries = source.infolist()
            if sum(entry.file_size for entry in entries) > _MAX_EXTRACTED:
                raise ValueError(_tr("插件解压后超过 500 MiB。"))
            roots = set()
            for entry in entries:
                self._check_cancelled()
                path = PurePosixPath(entry.filename)
                if (
                    path.is_absolute() or ".." in path.parts or not path.parts
                    or re.search(r'[\\:<>"|?*\x00-\x1f]', entry.filename)
                    or any(part.endswith((".", " ")) or Path(part).is_reserved() for part in path.parts)
                    or stat.S_ISLNK(entry.external_attr >> 16)
                ):
                    raise ValueError(_tr("压缩包包含不安全的路径或符号链接。"))
                roots.add(path.parts[0])
                destination = target.joinpath(*path.parts)
                if entry.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(entry) as input_file, destination.open("xb") as output:
                        while chunk := input_file.read(_CHUNK_SIZE):
                            self._check_cancelled()
                            output.write(chunk)
            if len(roots) != 1:
                raise ValueError(_tr("压缩包必须包含一个仓库根目录。"))
            return target / roots.pop()
