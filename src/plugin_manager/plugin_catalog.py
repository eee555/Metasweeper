"""插件索引与版本管理。

索引仓库是一个公开仓库（或任意 HTTPS JSON 地址），根目录提供
``metasweeper-plugins.json``，列出各插件所在的公开仓库。宿主据此
自动扫描插件、比较已安装版本并检测更新。

索引格式::

    {
      "schema_version": 1,
      "plugins": [
        {
          "name": "training_stats",
          "repository": "https://github.com/owner/metasweeper-training-stats",
          "platform": "auto",
          "description": "训练统计",
          "author": "owner",
          "tag_prefix": "metasweeper-v"
        }
      ]
    }

插件发布方只需按约定打 tag（默认 ``metasweeper-v1.2.3``），无需提交 PR。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from packaging.version import InvalidVersion, Version

from .plugin_repositories import PluginRepository

DEFAULT_TAG_PREFIX = "metasweeper-v"
INDEX_SCHEMA_VERSION = 1
INDEX_FILENAME = "metasweeper-plugins.json"
META_FILENAME = ".metasweeper-plugin.json"


class CatalogError(ValueError):
    """索引内容不合法。"""


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """索引中的一个插件条目。"""

    name: str
    repository: PluginRepository
    description: str = ""
    author: str = ""
    tag_prefix: str = DEFAULT_TAG_PREFIX
    homepage: str = ""

    def version_from_tag(self, tag_name: str) -> Version | None:
        """把 tag 名解析为版本号；不符合约定时返回 None。"""
        return parse_tag_version(tag_name, self.tag_prefix)


@dataclass(slots=True)
class PluginRelease:
    """一个插件仓库的版本信息。"""

    entry: CatalogEntry
    versions: list[tuple[Version, str, str]] = field(default_factory=list)
    error: str = ""

    @property
    def latest(self) -> tuple[Version, str, str] | None:
        return self.versions[0] if self.versions else None

    @property
    def latest_version(self) -> Version | None:
        latest = self.latest
        return latest[0] if latest else None


@dataclass(frozen=True, slots=True)
class InstalledPlugin:
    """已安装插件（通过市场安装时带有来源信息）。"""

    name: str
    directory: Path
    version: Version | None = None
    repository: str = ""
    tag: str = ""
    platform: str = ""

    def update_available(self, releases: PluginRelease) -> bool:
        latest = releases.latest_version
        if latest is None:
            return False
        if self.version is None:
            # 版本来源未知（手工安装或元数据缺失），不臆测为可更新。
            return False
        return latest > self.version


def parse_tag_version(tag_name: str, prefix: str = DEFAULT_TAG_PREFIX) -> Version | None:
    """解析 ``<prefix>1.2.3``、``v1.2.3`` 或 ``1.2.3`` 形式的 tag。

    返回 None 表示不是版本标签，调用方应忽略该 tag。
    """
    raw = tag_name.strip()
    if not raw:
        return None
    candidates = [raw]
    for candidate_prefix in (prefix, "v", ""):
        if candidate_prefix and raw.lower().startswith(candidate_prefix.lower()):
            candidate = raw[len(candidate_prefix):]
            if candidate:
                candidates.append(candidate)
    for candidate in candidates:
        candidate = candidate.lstrip("vV")
        try:
            version = Version(candidate)
        except InvalidVersion:
            continue
        if not version.is_prerelease:
            return version
    return None


def _parse_repository(value: Any, platform: str) -> PluginRepository:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError("插件条目缺少 repository")
    try:
        return PluginRepository.from_url(value, platform or "auto")
    except ValueError as exc:
        raise CatalogError(str(exc)) from exc


def parse_index(payload: str | bytes | dict[str, Any]) -> list[CatalogEntry]:
    """解析索引内容；忽略重复或非法条目，但对整体格式错误抛错。"""
    if isinstance(payload, (str, bytes)):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CatalogError(f"索引不是合法的 JSON：{exc}") from exc
    else:
        data = payload
    if not isinstance(data, dict):
        raise CatalogError("索引根节点必须是对象")
    schema = data.get("schema_version", INDEX_SCHEMA_VERSION)
    if not isinstance(schema, int) or schema > INDEX_SCHEMA_VERSION:
        raise CatalogError(f"不支持的索引版本：{schema}")
    raw_plugins = data.get("plugins")
    if not isinstance(raw_plugins, list):
        raise CatalogError("索引缺少 plugins 列表")

    entries: list[CatalogEntry] = []
    seen: set[str] = set()
    for item in raw_plugins:
        if not isinstance(item, dict):
            continue
        repository = item.get("repository")
        platform = item.get("platform", "auto")
        if not isinstance(platform, str):
            platform = "auto"
        try:
            parsed = _parse_repository(repository, platform)
        except CatalogError:
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            name = parsed.path.rsplit("/", 1)[-1]
        name = name.strip()
        if name in seen:
            continue
        seen.add(name)
        prefix = item.get("tag_prefix")
        entries.append(CatalogEntry(
            name=name,
            repository=parsed,
            description=str(item.get("description") or ""),
            author=str(item.get("author") or ""),
            tag_prefix=prefix if isinstance(prefix, str) and prefix else DEFAULT_TAG_PREFIX,
            homepage=str(item.get("homepage") or parsed.url),
        ))
    return entries


def rank_versions(
    entry: CatalogEntry,
    tags: Iterable[tuple[str, str]],
) -> list[tuple[Version, str, str]]:
    """把 (tag 名, commit) 列表转换为按版本倒序的 (版本, tag 名, commit)。"""
    result: list[tuple[Version, str, str]] = []
    for tag_name, commit in tags:
        version = entry.version_from_tag(tag_name)
        if version is None:
            continue
        result.append((version, tag_name, commit))
    result.sort(key=lambda item: item[0], reverse=True)
    return result


def read_installed_metadata(directory: Path) -> dict[str, Any]:
    """读取插件目录中的市场来源元数据。"""
    path = directory / META_FILENAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def find_plugin_directory(
    name: str,
    plugin_dirs: Iterable[Path],
) -> Path | None:
    """在所有插件目录中定位指定插件包目录。"""
    for directory in plugin_dirs:
        if not directory.is_dir():
            continue
        candidate = directory / name
        if candidate.is_dir() and (candidate / "__init__.py").is_file():
            return candidate
    return None


def scan_installed(plugin_dirs: Iterable[Path]) -> dict[str, InstalledPlugin]:
    """扫描已安装插件目录，返回 name → 安装信息。

    仅返回带有市场元数据的插件；手工复制的插件没有可靠版本来源。
    """
    installed: dict[str, InstalledPlugin] = {}
    for directory in plugin_dirs:
        if not directory.is_dir():
            continue
        for package in directory.iterdir():
            if not package.is_dir() or not (package / "__init__.py").is_file():
                continue
            metadata = read_installed_metadata(package)
            if not metadata:
                continue
            version: Version | None = None
            raw_version = metadata.get("version")
            if isinstance(raw_version, str):
                try:
                    version = Version(raw_version)
                except InvalidVersion:
                    version = None
            if version is None and isinstance(metadata.get("tag"), str):
                version = parse_tag_version(
                    metadata["tag"], str(metadata.get("tag_prefix") or DEFAULT_TAG_PREFIX))
            try:
                key = PluginRepository.from_url(str(metadata.get("repository") or "")).url.lower()
            except ValueError:
                continue
            installed[key] = InstalledPlugin(
                name=package.name,
                directory=package,
                version=version,
                repository=str(metadata.get("repository") or ""),
                tag=str(metadata.get("tag") or ""),
                platform=str(metadata.get("platform") or ""),
            )
    return installed
