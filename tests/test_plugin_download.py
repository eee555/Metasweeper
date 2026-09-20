import io
import json
import stat
from threading import Event
from zipfile import ZipFile, ZipInfo

import pytest
import requests

from plugin_manager import plugin_download as download
from plugin_manager.plugin_download import DownloadCancelled, PluginDownloader
from plugin_manager.plugin_repositories import PluginRepository, RepositoryTag
from plugin_manager.plugin_loader import PluginLoader


REPOSITORY = PluginRepository.from_url("https://github.com/example/my-plugin")
TAG = RepositoryTag("release/v1.0", "a" * 40)


def make_archive(files):
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        for name, content in files:
            archive.writestr(name, content)
    return data.getvalue()


class FakeResponse:
    def __init__(self, *, data=None, body=b"", links=None, status=200, headers=None):
        self.data = data
        self.body = body
        self.links = links or {}
        self.status_code = status
        self.headers = {"Content-Length": str(len(body))}
        self.headers.update(headers or {})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]


class FakeSession:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.headers = {}
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


@pytest.mark.parametrize("url", [
    "https://github.com/example/my-plugin",
    " https://github.com/example/my-plugin.git/ ",
    "https://github.com/example/my-plugin/releases/tag/v1.0",
])
def test_repository_url(url):
    assert PluginRepository.from_url(url) == REPOSITORY
    assert REPOSITORY.module_name == "github_example_my_plugin"


@pytest.mark.parametrize("url", [
    "http://github.com/example/repo", "https://github.com/owner",
    "https://github.com.evil.test/owner/repo", "https://github.com@evil.test/a/b",
    "https://github.com/owner/..", "https://github.com/owner/%2e%2e",
    "https://github.com/owner/.git",
])
def test_invalid_repository_url(url):
    with pytest.raises(ValueError):
        PluginRepository.from_url(url)


def test_tags_pagination_and_pinned_commit():
    session = FakeSession(
        FakeResponse(data=[{"name": TAG.name, "commit": {"sha": TAG.commit}}], links={"next": {}}),
        FakeResponse(data=[{"name": "v0", "commit": {"sha": "b" * 40}}]),
    )
    client = PluginDownloader(session, lambda: False, lambda *_: None)
    assert client.list_tags(REPOSITORY) == [TAG, RepositoryTag("v0", "b" * 40)]
    assert [call[1]["params"]["page"] for call in session.calls] == [1, 2]


def test_install_is_discoverable_without_executing_plugin(tmp_path):
    body = make_archive([
        ("repo-sha/__init__.py", "raise RuntimeError('must not execute during download')"),
        ("repo-sha/assets/icon.txt", "asset"),
    ])
    session = FakeSession(FakeResponse(body=body))
    progress = []
    client = PluginDownloader(session, lambda: False, lambda *args: progress.append(args))
    root = tmp_path / "user_plugins"
    path = client.install(REPOSITORY, TAG, root, [])
    assert path == root / REPOSITORY.module_name
    assert (path / "assets/icon.txt").read_text() == "asset"
    assert json.loads((path / ".metasweeper-plugin.json").read_text())["tag"] == TAG.name
    assert session.calls[0][0].endswith("/zipball/" + TAG.commit)
    assert progress[-1] == (len(body), len(body))
    assert list(root.iterdir()) == [path]
    assert PluginLoader([root]).discover_plugins() == [(path / "__init__.py", REPOSITORY.module_name)]


@pytest.mark.parametrize("entry", [
    "repo-sha/../../escaped.py", "/escaped.py", "repo-sha/C:/escaped.py",
    "repo-sha/..\\escaped.py", "repo-sha/file:stream", "repo-sha/name. /bad.py",
])
def test_unsafe_archive_is_not_installed(tmp_path, entry):
    body = make_archive([("repo-sha/__init__.py", ""), (entry, "bad")])
    client = PluginDownloader(FakeSession(FakeResponse(body=body)), lambda: False, lambda *_: None)
    root = tmp_path / "user_plugins"
    with pytest.raises(ValueError):
        client.install(REPOSITORY, TAG, root, [])
    assert list(root.iterdir()) == []
    assert not (tmp_path / "escaped.py").exists()


def test_symlink_is_rejected(tmp_path):
    link = ZipInfo("repo-sha/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    body = make_archive([("repo-sha/__init__.py", ""), (link, "../../outside")])
    client = PluginDownloader(FakeSession(FakeResponse(body=body)), lambda: False, lambda *_: None)
    with pytest.raises(ValueError):
        client.install(REPOSITORY, TAG, tmp_path, [])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("files", [
    [("repo-sha/plugin.py", "")],
    [("repo-a/__init__.py", ""), ("repo-b/__init__.py", "")],
])
def test_invalid_package_layout(tmp_path, files):
    client = PluginDownloader(FakeSession(FakeResponse(body=make_archive(files))), lambda: False, lambda *_: None)
    with pytest.raises(ValueError):
        client.install(REPOSITORY, TAG, tmp_path, [])
    assert list(tmp_path.iterdir()) == []


def test_existing_plugin_is_not_overwritten(tmp_path):
    existing = tmp_path / REPOSITORY.module_name
    existing.mkdir()
    (existing / "__init__.py").write_text("original")
    session = FakeSession()
    client = PluginDownloader(session, lambda: False, lambda *_: None)
    with pytest.raises(FileExistsError):
        client.install(REPOSITORY, TAG, tmp_path, [])
    assert (existing / "__init__.py").read_text() == "original"
    assert session.calls == []


def test_cancel_download_removes_partial_files(tmp_path):
    cancelled = False

    def progress(received, total):
        nonlocal cancelled
        if received:
            cancelled = True

    body = make_archive([("repo-sha/__init__.py", "x" * 100000)])
    client = PluginDownloader(FakeSession(FakeResponse(body=body)), lambda: cancelled, progress)
    with pytest.raises(DownloadCancelled):
        client.install(REPOSITORY, TAG, tmp_path, [])
    assert list(tmp_path.iterdir()) == []


def test_size_limits(tmp_path, monkeypatch):
    body = make_archive([("repo-sha/__init__.py", "x" * 100)])
    for limit in ("_MAX_DOWNLOAD", "_MAX_EXTRACTED"):
        with monkeypatch.context() as patch:
            patch.setattr(download, limit, 10)
            client = PluginDownloader(FakeSession(FakeResponse(body=body)), lambda: False, lambda *_: None)
            with pytest.raises(ValueError):
                client.install(REPOSITORY, TAG, tmp_path, [])
            assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("status", [404, 403, 429, 500])
def test_http_error(tmp_path, status):
    client = PluginDownloader(FakeSession(FakeResponse(status=status)), lambda: False, lambda *_: None)
    with pytest.raises((ValueError, requests.HTTPError)):
        client.install(REPOSITORY, TAG, tmp_path, [])
    assert list(tmp_path.iterdir()) == []


def test_dialog_downloads_selected_tag_and_clears_stale_tags(qtbot, monkeypatch, tmp_path):
    from plugin_manager import plugin_download_dialog as ui

    session = FakeSession(
        FakeResponse(data=[
            {"name": "v2", "commit": {"sha": "b" * 40}},
            {"name": TAG.name, "commit": {"sha": TAG.commit}},
        ]),
        FakeResponse(body=make_archive([("repo-sha/__init__.py", "")])),
    )
    monkeypatch.setattr(ui.requests, "Session", lambda: session)
    monkeypatch.setattr(ui, "get_executable_dir", lambda: tmp_path)
    monkeypatch.setattr(ui, "get_all_plugin_dirs", lambda: [])
    dialog = ui.PluginDownloadDialog()
    qtbot.addWidget(dialog)
    dialog.url.setText("https://github.com/example/my-plugin")
    dialog.fetch.click()
    qtbot.waitUntil(lambda: dialog.tags.count() == 2)
    dialog.tags.setCurrentIndex(1)
    dialog.install.click()
    qtbot.waitUntil(lambda: dialog._installed)
    assert session.calls[-1][0].endswith(TAG.commit)
    assert not dialog.install.isEnabled()
    assert (tmp_path / "user_plugins" / REPOSITORY.module_name / "__init__.py").exists()
    dialog.url.setText("https://github.com/example/another-plugin")
    assert dialog.tags.count() == 0
    assert not dialog.install.isEnabled()


def test_dialog_empty_tags_and_retry_after_failure(qtbot, monkeypatch):
    from plugin_manager import plugin_download_dialog as ui

    session = FakeSession(FakeResponse(status=404), FakeResponse(data=[]))
    monkeypatch.setattr(ui.requests, "Session", lambda: session)
    dialog = ui.PluginDownloadDialog()
    qtbot.addWidget(dialog)
    dialog.url.setText("https://github.com/example/my-plugin")
    for _ in range(2):
        dialog.fetch.click()
        qtbot.waitUntil(lambda: dialog._task is None)
        assert dialog.status.text()
        assert dialog.fetch.isEnabled()
        assert not dialog.install.isEnabled()
        assert dialog.tags.count() == 0


def test_closing_dialog_waits_for_download_cancellation(qtbot, monkeypatch, tmp_path):
    from plugin_manager import plugin_download_dialog as ui

    entered = Event()
    release = Event()

    class SlowResponse(FakeResponse):
        def iter_content(self, chunk_size):
            entered.set()
            assert release.wait(5)
            yield from super().iter_content(chunk_size)

    session = FakeSession(
        FakeResponse(data=[{"name": TAG.name, "commit": {"sha": TAG.commit}}]),
        SlowResponse(body=make_archive([("repo-sha/__init__.py", "")])),
    )
    monkeypatch.setattr(ui.requests, "Session", lambda: session)
    monkeypatch.setattr(ui, "get_executable_dir", lambda: tmp_path)
    monkeypatch.setattr(ui, "get_all_plugin_dirs", lambda: [])
    dialog = ui.PluginDownloadDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.url.setText("https://github.com/example/my-plugin")
    dialog.fetch.click()
    qtbot.waitUntil(lambda: dialog.tags.count() == 1)
    dialog.install.click()
    try:
        qtbot.waitUntil(entered.is_set)
        dialog.close()
        assert dialog.isVisible()
        assert not dialog.close_button.isEnabled()
    finally:
        release.set()
    qtbot.waitUntil(lambda: dialog._task is None)
    assert not dialog.isVisible()
    assert list((tmp_path / "user_plugins").iterdir()) == []


@pytest.mark.parametrize("url,platform,path,module", [
    ("https://github.com:443/example/my-plugin.git", "auto", "example/my-plugin", "github_example_my_plugin"),
    ("https://gitlab.com/team/subgroup/plugin/-/tags/v1", "auto", "team/subgroup/plugin", "gitlab_team_subgroup_plugin"),
    ("https://gitee.com/team/plugin/tree/v1", "auto", "team/plugin", "gitee_team_plugin"),
    ("https://codeberg.org/team/plugin/src/tag/v1", "auto", "team/plugin", "codeberg_team_plugin"),
    ("https://git.example.org:8443/team/sub/plugin.git", "gitlab", "team/sub/plugin", "gitlab_git_example_org_8443_team_sub_plugin"),
    ("https://forge.example.org/team/plugin", "gitea", "team/plugin", "gitea_forge_example_org_team_plugin"),
])
def test_hosting_urls(url, platform, path, module):
    repository = PluginRepository.from_url(url, platform)
    assert repository.path == path
    assert repository.module_name == module


@pytest.mark.parametrize("url,platform", [
    ("https://unknown.example/team/repo", "auto"),
    ("https://github.com/team/repo", "gitlab"),
    ("https://gitlab.com/team/repo", "github"),
    ("https://unknown.example/team/repo", "gitee"),
    ("https://git.example/team/../repo", "gitlab"),
    ("https://git.example/team/%2e%2e/repo", "gitlab"),
    ("https://git.example/team/repo", "unsupported"),
    ("https://user:password@git.example/team/repo", "gitlab"),
])
def test_reject_ambiguous_or_mismatched_hosting(url, platform):
    with pytest.raises(ValueError):
        PluginRepository.from_url(url, platform)


@pytest.mark.parametrize("url,platform,api,archive_suffix,archive_params,key,page_size", [
    ("https://github.com/team/plugin", "auto", "https://api.github.com/repos/team/plugin",
     "/zipball/" + TAG.commit, {}, "sha", {"per_page": 100}),
    ("https://gitlab.com/team/sub/plugin", "auto", "https://gitlab.com/api/v4/projects/team%2Fsub%2Fplugin/repository",
     "/archive.zip", {"sha": TAG.commit}, "id", {"per_page": 100}),
    ("https://gitee.com/team/plugin", "auto", "https://gitee.com/api/v5/repos/team/plugin",
     "/zipball", {"ref": TAG.commit}, "sha", {"per_page": 100}),
    ("https://codeberg.org/team/plugin", "auto", "https://codeberg.org/api/v1/repos/team/plugin",
     "/archive/" + TAG.commit + ".zip", {}, "sha", {"limit": 50}),
    ("https://lab.example:8443/team/sub/plugin", "gitlab", "https://lab.example:8443/api/v4/projects/team%2Fsub%2Fplugin/repository",
     "/archive.zip", {"sha": TAG.commit}, "id", {"per_page": 100}),
    ("https://forge.example/team/plugin", "gitea", "https://forge.example/api/v1/repos/team/plugin",
     "/archive/" + TAG.commit + ".zip", {}, "sha", {"limit": 50}),
])
def test_each_provider_downloads_selected_commit(tmp_path, url, platform, api, archive_suffix, archive_params, key, page_size):
    repository = PluginRepository.from_url(url, platform)
    session = FakeSession(
        FakeResponse(data=[{"name": TAG.name, "commit": {key: TAG.commit}}], headers={"Link": ""}),
        FakeResponse(body=make_archive([("repo-sha/__init__.py", "")])),
    )
    client = PluginDownloader(session, lambda: False, lambda *_: None)
    tags = client.list_tags(repository)
    assert tags == [TAG]
    path = client.install(repository, tags[0], tmp_path, [])
    assert session.calls[0][0] == api + "/tags"
    assert session.calls[0][1]["params"] == {**page_size, "page": 1}
    assert session.calls[1][0] == api + archive_suffix
    assert session.calls[1][1]["params"] == archive_params
    assert ("X-GitHub-Api-Version" in session.calls[1][1]["headers"]) == (repository.platform == "github")
    metadata = json.loads((path / ".metasweeper-plugin.json").read_text())
    assert metadata == {"repository": repository.url, "platform": repository.platform, "tag": TAG.name, "commit": TAG.commit}


def test_gitlab_pagination_header():
    repository = PluginRepository.from_url("https://gitlab.com/team/plugin")
    session = FakeSession(
        FakeResponse(data=[{"name": "v2", "commit": {"id": "b" * 40}}], headers={"X-Next-Page": "2"}),
        FakeResponse(data=[{"name": TAG.name, "commit": {"id": TAG.commit}}], headers={"X-Next-Page": ""}),
    )
    client = PluginDownloader(session, lambda: False, lambda *_: None)
    assert client.list_tags(repository) == [RepositoryTag("v2", "b" * 40), TAG]
    assert [call[1]["params"]["page"] for call in session.calls] == [1, 2]


@pytest.mark.parametrize("url,platform", [
    ("https://gitee.com/team/plugin", "auto"),
    ("https://forge.example/team/plugin", "gitea"),
])
def test_paginate_without_headers_or_assuming_server_page_size(url, platform):
    repository = PluginRepository.from_url(url, platform)
    session = FakeSession(
        FakeResponse(data=[{"name": "v2", "commit": {"sha": "b" * 40}}]),
        FakeResponse(data=[{"name": TAG.name, "commit": {"sha": TAG.commit}}]),
        FakeResponse(data=[]),
    )
    client = PluginDownloader(session, lambda: False, lambda *_: None)
    assert client.list_tags(repository) == [RepositoryTag("v2", "b" * 40), TAG]
    assert [call[1]["params"]["page"] for call in session.calls] == [1, 2, 3]


def test_self_hosted_names_do_not_collide():
    urls = ["https://a.example/team/repo", "https://b.example/team/repo", "https://a.example:8443/team/repo"]
    names = {PluginRepository.from_url(url, "gitea").module_name for url in urls}
    assert len(names) == 3


def test_dialog_requires_platform_for_self_hosted_and_clears_old_selection(qtbot, monkeypatch):
    from plugin_manager import plugin_download_dialog as ui

    session = FakeSession(FakeResponse(data=[{"name": TAG.name, "commit": {"id": TAG.commit}}], headers={"X-Next-Page": ""}))
    monkeypatch.setattr(ui.requests, "Session", lambda: session)
    dialog = ui.PluginDownloadDialog()
    qtbot.addWidget(dialog)
    dialog.url.setText("https://git.example/team/sub/plugin")
    dialog.fetch.click()
    assert session.calls == []
    assert not dialog.install.isEnabled()
    dialog.platform.setCurrentIndex(dialog.platform.findData("gitlab"))
    dialog.fetch.click()
    assert not dialog.platform.isEnabled()
    qtbot.waitUntil(lambda: dialog.tags.count() == 1)
    assert dialog.platform.isEnabled()
    assert dialog.install.isEnabled()
    dialog.platform.setCurrentIndex(dialog.platform.findData("gitea"))
    assert dialog.tags.count() == 0
    assert not dialog.install.isEnabled()
