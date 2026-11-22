"""后台检查并更新管理器安装的用户插件。"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import loguru
import requests
from PySide6.QtCore import QCoreApplication, QThread

from .app_paths import get_data_dir, get_executable_dir
from .dependency_scan import scan_plugin_dependencies
from .plugin_catalog import CatalogEntry, rank_versions, read_installed_plugin
from .plugin_download import DownloadCancelled, PluginDownloader, is_plain_plugin_directory
from .plugin_lib_env import install_plugin_requirements
from .plugin_repositories import PluginRepository, RepositoryTag

logger = loguru.logger.bind(name="PluginAutoUpdate")


def prepare_plugin_dependencies(
    package: Path, module_name: str, report: Callable[[str], None],
) -> None:
    """检查并安装暂存插件的依赖；失败时阻止发布插件文件。"""
    requirements = package / "requirements.txt"
    if not requirements.is_file():
        return
    dependency = scan_plugin_dependencies(package / "__init__.py", module_name)
    if dependency.status in {"no_requirements", "satisfied"}:
        return
    report(QCoreApplication.translate("PluginMarketDialog", "正在安装插件依赖…"))
    error = install_plugin_requirements(
        get_data_dir(), requirements, output_callback=report)
    if error:
        raise RuntimeError(QCoreApplication.translate(
            "PluginMarketDialog", "插件依赖安装失败；插件文件尚未发布：{error}",
        ).format(error=error))
    report(QCoreApplication.translate("PluginMarketDialog", "插件依赖安装完成。"))


class PluginAutoUpdateTask(QThread):
    """更新已安装的插件；finished 后可读取成功更新的目录。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.updated: list[Path] = []

    def run(self) -> None:
        self.updated.clear()
        plugin_dir = get_executable_dir() / "user_plugins"
        try:
            if not is_plain_plugin_directory(plugin_dir):
                return
            packages = sorted(plugin_dir.iterdir())
        except (FileNotFoundError, NotADirectoryError):
            return
        except OSError:
            logger.exception("无法扫描插件更新目录：{}", plugin_dir)
            return

        for package in packages:
            if self.isInterruptionRequested():
                return
            try:
                if package.name.startswith("_") or package.name == "services":
                    continue
                if is_plain_plugin_directory(package):
                    self._update_plugin(package)
            except DownloadCancelled:
                return
            except Exception:
                logger.exception("自动更新插件失败：{}", package)

    def _update_plugin(self, package: Path) -> None:
        installed = read_installed_plugin(package)
        if installed is None or installed.version is None:
            return
        repository = PluginRepository.from_url(installed.repository, installed.platform or "auto")
        entry = CatalogEntry(installed.name, repository, tag_prefix=installed.tag_prefix)

        def report(message: str) -> None:
            logger.debug("{}: {}", package.name, message)

        def prepare_dependencies(staged: Path) -> None:
            prepare_plugin_dependencies(staged, package.name, report)

        with requests.Session() as session:
            downloader = PluginDownloader(
                session, self.isInterruptionRequested, lambda *_: None)
            if self.isInterruptionRequested():
                raise DownloadCancelled()
            tags = downloader.list_tags(repository)
            versions = rank_versions(entry, ((tag.name, tag.commit) for tag in tags))
            if not versions or versions[0][0] <= installed.version:
                return
            version, tag_name, commit = versions[0]
            if self.isInterruptionRequested():
                raise DownloadCancelled()
            # The downloader also checks after dependency preparation and before replacing the directory.
            self.updated.append(downloader.update(
                repository, RepositoryTag(tag_name, commit), package.parent,
                plugin_version=str(version), tag_prefix=installed.tag_prefix,
                destination_name=installed.name, before_publish=prepare_dependencies,
            ))
