"""Download tagged plugin packages without requiring a Git installation."""
from __future__ import annotations

import json
import re
import stat
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Callable
from zipfile import ZipFile

import requests
from PyQt5.QtCore import QCoreApplication

from .plugin_repositories import PluginRepository, RepositoryTag


_MAX_DOWNLOAD = 100 * 1024 * 1024
_MAX_EXTRACTED = 500 * 1024 * 1024
_CHUNK_SIZE = 64 * 1024


def _tr(text: str) -> str:
    return QCoreApplication.translate("PluginDownloadDialog", text)


class DownloadCancelled(Exception):
    pass


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
        if response.status_code in (403, 429):
            raise ValueError(_tr("托管平台拒绝请求或请求次数已达上限，请稍后重试。"))
        response.raise_for_status()

    def list_tags(self, repository: PluginRepository) -> list[RepositoryTag]:
        tags = []
        page = 1
        while True:
            self._check_cancelled()
            url, params = repository.provider.tags_request(repository, page)
            with self.session.get(
                url, params=params, headers=repository.provider.headers, timeout=(5, 30),
            ) as response:
                self._check_response(response)
                items = response.json()
                tags.extend(repository.provider.parse_tag(item) for item in items)
                if not repository.provider.has_next_page(response, items):
                    return tags
            page += 1

    def install(
        self,
        repository: PluginRepository,
        tag: RepositoryTag,
        plugin_dir: Path,
        search_dirs: list[Path],
    ) -> Path:
        destination = plugin_dir / repository.module_name
        for directory in [plugin_dir, *search_dirs]:
            if (directory / repository.module_name).exists() or (directory / f"{repository.module_name}.py").exists():
                raise FileExistsError(_tr("插件目录已存在，不会覆盖：{path}").format(path=directory / repository.module_name))
        self._check_cancelled()
        plugin_dir.mkdir(parents=True, exist_ok=True)
        # Hidden from PluginLoader until the complete package is ready.
        with TemporaryDirectory(prefix="_download_", dir=plugin_dir) as temporary:
            work_dir = Path(temporary)
            archive = work_dir / "source.zip"
            self._download(repository, tag, archive)
            package = self._extract(archive, work_dir / "source")
            if not (package / "__init__.py").is_file():
                raise ValueError(_tr("仓库根目录缺少 __init__.py 插件入口。"))
            metadata = {"repository": repository.url, "platform": repository.platform,
                        "tag": tag.name, "commit": tag.commit}
            (package / ".metasweeper-plugin.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            self._check_cancelled()
            # Same filesystem: publish only after download and extraction succeed.
            package.rename(destination)
        return destination

    def _download(self, repository: PluginRepository, tag: RepositoryTag, archive: Path) -> None:
        url, params = repository.provider.archive_request(repository, tag)
        with self.session.get(url, params=params, headers=repository.provider.headers, stream=True, timeout=(5, 30)) as response:
            self._check_response(response)
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
                    output.write(chunk)
                    self.progress(received, total)

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
