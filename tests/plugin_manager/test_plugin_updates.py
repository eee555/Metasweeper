"""自动更新仅从已安装的来源检查并发布稳定版本。"""
from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
import requests

from plugin_manager import plugin_updates as updates
from plugin_manager.dependency_scan import PluginDependencyStatus
from plugin_manager.plugin_catalog import META_FILENAME, read_installed_metadata
from plugin_manager.plugin_repositories import RepositoryTag

GITHUB = "https://github.com/example/metasweeper-demo"
GITEE = "https://gitee.com/another-owner/metasweeper-demo"
STABLE = RepositoryTag("metasweeper-v2.0", "a" * 40)


@pytest.fixture
def managed_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(updates, "get_executable_dir", lambda: tmp_path)
    directory = tmp_path / "user_plugins"
    directory.mkdir()
    return directory


def _install_old(root, name, *, repository=GITHUB, **metadata):
    package = root / name
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# old plugin", encoding="utf-8")
    (package / META_FILENAME).write_text(
        json.dumps({"repository": repository, **metadata}), encoding="utf-8")
    return package


def _run_task(qtbot, task=None):
    if task is None:
        task = updates.PluginAutoUpdateTask()
    with qtbot.waitSignal(task.finished, timeout=5000):
        task.start()
    assert task.wait(5000)
    return task.updated


def _fake_download(monkeypatch, requirements=None):
    downloads = []

    def download(self, repository, tag, archive):
        with ZipFile(archive, "w") as package:
            package.writestr("source/__init__.py", "# new plugin")
            if requirements is not None:
                package.writestr("source/requirements.txt", requirements)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        downloads.append((repository.url, tag, digest))
        return digest

    monkeypatch.setattr(updates.PluginDownloader, "_download", download)
    return downloads


def test_updates_exact_saved_source_and_preserves_module_and_prefix(managed_dir, monkeypatch, qtbot):
    package = _install_old(
        managed_dir, "old_module_name", repository=GITEE, platform="gitee",
        tag="custom-1.0", tag_prefix="custom-")
    data_dir = managed_dir.parent / "data" / "plugin_data" / "DemoPlugin"
    data_dir.mkdir(parents=True)
    plugin_data = data_dir / "save.txt"
    plugin_data.write_text("saved", encoding="utf-8")
    checked = []
    prepared = []
    target = RepositoryTag("custom-1.10", "b" * 40)

    def list_tags(self, repository):
        checked.append(repository.url)
        return [RepositoryTag("custom-3.0rc1", "c" * 40),
                RepositoryTag("custom-1.2", "d" * 40), target]

    def prepare(staged, module_name, report):
        assert (staged / "__init__.py").read_text(encoding="utf-8") == "# new plugin"
        assert (package / "__init__.py").read_text(encoding="utf-8") == "# old plugin"
        prepared.append(module_name)

    monkeypatch.setattr(updates.PluginDownloader, "list_tags", list_tags)
    monkeypatch.setattr(updates, "prepare_plugin_dependencies", prepare)
    downloads = _fake_download(monkeypatch)

    assert _run_task(qtbot) == [package]
    assert checked == [GITEE]
    assert prepared == ["old_module_name"]
    assert downloads[0][:2] == (GITEE, target)
    assert read_installed_metadata(package) == {
        "repository": GITEE, "platform": "gitee", "version": "1.10",
        "tag_prefix": "custom-", "tag": target.name, "commit": target.commit,
        "archive_sha256": downloads[0][2],
    }
    assert plugin_data.read_text(encoding="utf-8") == "saved"
    assert list(managed_dir.iterdir()) == [package]


@pytest.mark.parametrize("tags", [
    [],
    [STABLE, RepositoryTag("v9.0rc1", "b" * 40)],
    [RepositoryTag("v1.9", "c" * 40)],
])
def test_skips_when_no_newer_stable_version(managed_dir, monkeypatch, qtbot, tags):
    package = _install_old(managed_dir, "module", version="2.0.0")
    monkeypatch.setattr(updates.PluginDownloader, "list_tags", lambda *_: tags)
    downloads = _fake_download(monkeypatch)

    assert _run_task(qtbot) == []
    assert downloads == []
    assert read_installed_metadata(package)["version"] == "2.0.0"


def test_skips_unmanaged_and_unsuitable_targets(managed_dir, monkeypatch, qtbot):
    _install_old(managed_dir.parent / "plugins", "unmanaged", version="1.0")
    _install_old(managed_dir, "_update_temporary", version="1.0")
    _install_old(managed_dir, "unknown_version", version="dev", tag="nightly")
    manual = _install_old(managed_dir, "manual", version="1.0")
    (manual / META_FILENAME).unlink()
    invalid = _install_old(managed_dir, "invalid_encoding", version="1.0")
    (invalid / META_FILENAME).write_bytes(b"\xff")
    no_entry = _install_old(managed_dir, "data_directory", version="1.0")
    (no_entry / "__init__.py").unlink()
    (managed_dir / "single.py").touch()
    linked = _install_old(managed_dir, "junction", version="1.0")
    original_lstat = Path.lstat

    def lstat(path):
        if path == linked:
            return SimpleNamespace(st_mode=stat.S_IFDIR,
                                   st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return original_lstat(path)

    sessions = []
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(updates.requests, "Session", lambda: sessions.append(True))

    assert _run_task(qtbot) == []
    assert sessions == []


def test_tag_and_dependency_failures_leave_old_files_and_continue(managed_dir, monkeypatch, qtbot):
    unreachable = _install_old(managed_dir, "a_unreachable", repository=GITEE, version="1.0")
    broken = _install_old(managed_dir, "b_broken", version="1.0")
    healthy = _install_old(managed_dir, "c_healthy", version="1.0")
    reports = []
    logs = []
    monkeypatch.setattr(updates, "get_data_dir", lambda: managed_dir.parent / "data")
    monkeypatch.setattr(updates.logger, "exception", lambda message, path: logs.append(path))
    _fake_download(monkeypatch, requirements="example>=2")

    def list_tags(self, repository):
        if repository.url == GITEE:
            raise requests.ConnectionError("tag lookup failed")
        return [STABLE]

    def scan(module_path, module_name):
        status = "missing" if module_name == broken.name else "satisfied"
        return PluginDependencyStatus(module_name, module_path, None, status)

    def install_requirements(data_dir, requirements_file, *, output_callback):
        reports.append((data_dir, requirements_file.read_text(encoding="utf-8")))
        output_callback("pip output")
        return "dependency installation failed"

    monkeypatch.setattr(updates.PluginDownloader, "list_tags", list_tags)
    monkeypatch.setattr(updates, "scan_plugin_dependencies", scan)
    monkeypatch.setattr(updates, "install_plugin_requirements", install_requirements)

    assert _run_task(qtbot) == [healthy]
    assert logs == [unreachable, broken]
    assert reports == [(managed_dir.parent / "data", "example>=2")]
    assert (broken / "__init__.py").read_text(encoding="utf-8") == "# old plugin"
    assert read_installed_metadata(broken)["version"] == "1.0"
    assert read_installed_metadata(healthy)["version"] == "2.0"
    assert sorted(managed_dir.iterdir()) == [unreachable, broken, healthy]


@pytest.mark.parametrize("stage", ["metadata", "tags", "dependencies"])
def test_interruption_prevents_next_stage_and_publication(managed_dir, monkeypatch, qtbot, stage):
    package = _install_old(managed_dir, "module", version="1.0")
    task = updates.PluginAutoUpdateTask()
    events = []
    downloads = _fake_download(monkeypatch)
    read_installed_plugin = updates.read_installed_plugin

    def read_metadata(path):
        events.append("metadata")
        if stage == "metadata":
            task.requestInterruption()
        return read_installed_plugin(path)

    def list_tags(self, repository):
        events.append("tags")
        if stage == "tags":
            task.requestInterruption()
        return [STABLE]

    def prepare(staged, module_name, report):
        events.append("dependencies")
        task.requestInterruption()

    monkeypatch.setattr(updates, "read_installed_plugin", read_metadata)
    monkeypatch.setattr(updates.PluginDownloader, "list_tags", list_tags)
    monkeypatch.setattr(updates, "prepare_plugin_dependencies", prepare)

    assert _run_task(qtbot, task) == []
    stages = ["metadata", "tags", "dependencies"]
    assert events == stages[:stages.index(stage) + 1]
    assert len(downloads) == (1 if stage == "dependencies" else 0)
    assert read_installed_metadata(package)["version"] == "1.0"
    assert list(managed_dir.iterdir()) == [package]
