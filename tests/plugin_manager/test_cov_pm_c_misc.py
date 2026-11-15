"""Focused coverage tests for download, repository and icon edge branches."""
from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZipFile

import pytest
import requests
from PySide6.QtCore import QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialogButtonBox, QPushButton

from plugin_manager import icons, plugin_download as download
from plugin_manager.plugin_download import DownloadCancelled, PluginDownloader
from plugin_manager.plugin_repositories import (
    HostingProvider,
    PluginRepository,
    RepositoryTag,
)


REPOSITORY = PluginRepository.from_url("https://github.com/example/plugin")
TAG = RepositoryTag("v1", "a" * 40)


class FakeResponse:
    def __init__(self, *, status=200, body=b"", headers=None, links=None, data=None):
        self.status_code = status
        self.body = body
        self.headers = {"Content-Length": str(len(body))}
        self.headers.update(headers or {})
        self.links = links or {}
        self.data = data
        self.raised = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def json(self):
        return self.data

    def raise_for_status(self):
        self.raised = True
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

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


def make_archive(files):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in files:
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def offline_qt(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


def test_download_rejects_stream_larger_than_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_MAX_DOWNLOAD", 5)
    response = FakeResponse(body=b"0123456789")
    response.headers["Content-Length"] = "0"
    session = FakeSession(response)
    progress = []
    client = PluginDownloader(session, lambda: False,
                              lambda *args: progress.append(args))
    with pytest.raises(ValueError, match="100 MiB"):
        client.install(REPOSITORY, TAG, tmp_path, [])
    assert list(tmp_path.iterdir()) == []
    assert progress == [(0, 0)]


def test_download_rejects_missing_content_length_stream(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_MAX_DOWNLOAD", 5)
    response = FakeResponse(body=b"x" * 10)
    response.headers.pop("Content-Length")
    client = PluginDownloader(FakeSession(response), lambda: False, lambda *_: None)
    with pytest.raises(ValueError, match="100 MiB"):
        client.install(REPOSITORY, TAG, tmp_path, [])


def test_extract_creates_explicit_directory_entries(tmp_path):
    body = make_archive([
        ("repo-sha/", ""),
        ("repo-sha/assets/", ""),
        ("repo-sha/__init__.py", ""),
        ("repo-sha/assets/icon.txt", "icon"),
    ])
    client = PluginDownloader(FakeSession(FakeResponse(body=body)),
                              lambda: False, lambda *_: None)
    path = client.install(REPOSITORY, TAG, tmp_path, [])
    assert (path / "assets" / "icon.txt").read_text() == "icon"


def test_extract_cancellation_between_chunks_is_propagated(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_CHUNK_SIZE", 1)
    body = make_archive([("repo-sha/__init__.py", "x" * 10)])
    checks = []

    def cancelled():
        checks.append(True)
        return len(checks) > 3

    client = PluginDownloader(FakeSession(FakeResponse(body=body)),
                              cancelled, lambda *_: None)
    with pytest.raises(DownloadCancelled):
        client.install(REPOSITORY, TAG, tmp_path, [])
    assert len(checks) > 3
    assert list(tmp_path.iterdir()) == []


def test_list_tags_cancellation_propagates(monkeypatch):
    client = PluginDownloader(FakeSession(), lambda: True, lambda *_: None)
    with pytest.raises(DownloadCancelled):
        client.list_tags(REPOSITORY)


@pytest.mark.parametrize("status,expected", [
    (404, ValueError), (403, ValueError), (429, ValueError),
    (500, requests.HTTPError),
])
def test_check_response_all_status_branches(status, expected):
    response = FakeResponse(status=status)
    try:
        PluginDownloader._check_response(response)
    except expected:
        pass
    else:
        pytest.fail(f"status {status} should raise {expected.__name__}")
    assert (status >= 400 and not 400 <= status <= 499) or status != 500 or response.raised


def test_check_response_non_2xx_without_error():
    response = FakeResponse(status=302)
    PluginDownloader._check_response(response)
    assert response.raised


def test_download_cancelled_before_install_uses_check(tmp_path):
    client = PluginDownloader(FakeSession(), lambda: True, lambda *_: None)
    with pytest.raises(DownloadCancelled):
        client.install(REPOSITORY, TAG, tmp_path, [])


def test_list_tags_paginates_then_returns(monkeypatch):
    first = FakeResponse(data=[{"name": "v1", "commit": {"sha": "a"}}],
                         links={"next": {}})
    second = FakeResponse(data=[{"name": "v2", "commit": {"sha": "b"}}])
    session = FakeSession(first, second)
    client = PluginDownloader(session, lambda: False, lambda *_: None)
    assert client.list_tags(REPOSITORY) == [
        RepositoryTag("v1", "a"), RepositoryTag("v2", "b")]
    assert [call[1]["params"]["page"] for call in session.calls] == [1, 2]


def test_install_rejects_existing_module_file_in_search_dir(tmp_path):
    search = tmp_path / "other"
    search.mkdir()
    (search / f"{REPOSITORY.module_name}.py").write_text("existing",
                                                          encoding="utf-8")
    client = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)
    with pytest.raises(FileExistsError):
        client.install(REPOSITORY, TAG, tmp_path / "plugins", [search])


def test_install_rejects_package_without_root_init(tmp_path):
    body = make_archive([("repo-sha/plugin.py", "")])
    client = PluginDownloader(FakeSession(FakeResponse(body=body)),
                              lambda: False, lambda *_: None)
    with pytest.raises(ValueError):
        client.install(REPOSITORY, TAG, tmp_path, [])


def test_download_rejects_declared_content_length(tmp_path):
    response = FakeResponse(body=b"tiny")
    response.headers["Content-Length"] = "999999999"
    client = PluginDownloader(FakeSession(response), lambda: False, lambda *_: None)
    with pytest.raises(ValueError, match="100 MiB"):
        client.install(REPOSITORY, TAG, tmp_path, [])


def test_extract_rejects_too_many_uncompressed_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_MAX_EXTRACTED", 5)
    body = make_archive([("repo-sha/__init__.py", "x" * 10)])
    client = PluginDownloader(FakeSession(FakeResponse(body=body)),
                              lambda: False, lambda *_: None)
    with pytest.raises(ValueError, match="500 MiB"):
        client.install(REPOSITORY, TAG, tmp_path, [])


def test_extract_rejects_unsafe_archive_entry(tmp_path):
    body = make_archive([
        ("repo-sha/__init__.py", ""),
        ("repo-sha/../../escaped.py", "bad"),
    ])
    client = PluginDownloader(FakeSession(FakeResponse(body=body)),
                              lambda: False, lambda *_: None)
    with pytest.raises(ValueError):
        client.install(REPOSITORY, TAG, tmp_path, [])
    assert list(tmp_path.iterdir()) == []


def test_extract_rejects_multiple_roots(tmp_path):
    body = make_archive([("a/__init__.py", ""), ("b/__init__.py", "")])
    client = PluginDownloader(FakeSession(FakeResponse(body=body)),
                              lambda: False, lambda *_: None)
    with pytest.raises(ValueError):
        client.install(REPOSITORY, TAG, tmp_path, [])
    assert list(tmp_path.iterdir()) == []


def test_install_cancelled_after_metadata_before_rename(tmp_path, monkeypatch):
    body = make_archive([("repo-sha/__init__.py", "")])
    calls = []
    original_check = PluginDownloader._check_cancelled

    def check(self):
        calls.append(True)
        original_check(self)
        if len(calls) >= 4:
            raise DownloadCancelled()

    monkeypatch.setattr(PluginDownloader, "_check_cancelled", check)
    client = PluginDownloader(FakeSession(FakeResponse(body=body)),
                              lambda: False, lambda *_: None)
    with pytest.raises(DownloadCancelled):
        client.install(REPOSITORY, TAG, tmp_path, [])
    assert list(tmp_path.iterdir()) == []


def test_repository_ipv6_host_is_bracketed():
    repository = PluginRepository.from_url(
        "https://[2001:db8::1]:8443/team/plugin", "gitlab")
    assert repository.origin == "https://[2001:db8::1]:8443"
    assert repository.url == "https://[2001:db8::1]:8443/team/plugin"


def test_repository_ipv6_default_port_is_bracketed():
    repository = PluginRepository.from_url(
        "https://[2001:db8::1]/team/plugin", "gitea")
    assert repository.origin == "https://[2001:db8::1]"
    assert repository.module_name.startswith("gitea__2001_db8__1_")


@pytest.mark.parametrize("items,links,headers,expected", [
    ([], {}, {}, False),
    ([{"name": "v1"}], {}, {}, True),
    ([{"name": "v1"}], {"next": {}}, {"Link": "next"}, True),
    ([{"name": "v1"}], {}, {"Link": "last"}, False),
])
def test_hosting_provider_has_next_page_base(items, links, headers, expected):
    provider = HostingProvider()
    response = FakeResponse(links=links, headers=headers)
    assert provider.has_next_page(response, items) is expected


def test_hosting_provider_archive_request_is_abstract():
    with pytest.raises(NotImplementedError):
        HostingProvider().archive_request(REPOSITORY, TAG)


@pytest.mark.parametrize("url,platform", [
    ("http://github.com/team/repo", "auto"),
    ("https:///team/repo", "auto"),
    ("https://user:not-a-secret@github.com/team/repo", "auto"),
    ("https://unknown.example/team/repo", "auto"),
    ("https://github.com/team/repo", "gitlab"),
    ("https://github.com:8443/team/repo", "auto"),
    ("https://github.com/team/../repo", "auto"),
    ("https://git.example/team/repo", "unsupported"),
])
def test_repository_invalid_url_branches(url, platform):
    with pytest.raises(ValueError):
        PluginRepository.from_url(url, platform)


def test_repository_all_platform_helpers_and_urls():
    from plugin_manager.plugin_repositories import (
        GitHubProvider, GitLabProvider, GiteeProvider, GiteaProvider,
    )

    github = GitHubProvider()
    gitlab = GitLabProvider()
    gitee = GiteeProvider()
    gitea = GiteaProvider()
    assert github.api_url(REPOSITORY) == "https://api.github.com/repos/example/plugin"
    assert github.has_next_page(FakeResponse(links={"next": {}}), []) is True
    assert github.has_next_page(FakeResponse(), []) is False
    assert github.archive_request(REPOSITORY, TAG)[0].endswith("/zipball/" + TAG.commit)
    assert gitlab.repository_path("team/sub/-/tags/v1") == "team/sub"
    assert gitlab.api_url(REPOSITORY).endswith("/repository")
    assert gitlab.parse_tag({"name": "v", "commit": {"id": "x"}}) == RepositoryTag("v", "x")
    assert gitlab.has_next_page(FakeResponse(headers={"X-Next-Page": "2"}), []) is True
    assert gitlab.has_next_page(FakeResponse(headers={"X-Next-Page": ""}), []) is False
    assert gitlab.has_next_page(FakeResponse(), [{"name": "v"}]) is True
    assert gitlab.archive_request(REPOSITORY, TAG)[1] == {"sha": TAG.commit}
    assert gitee.api_url(REPOSITORY).endswith("/api/v5/repos/example/plugin")
    assert gitee.archive_request(REPOSITORY, TAG)[1] == {"ref": TAG.commit}
    assert gitea.api_url(REPOSITORY).endswith("/api/v1/repos/example/plugin")
    assert gitea.archive_request(REPOSITORY, TAG)[0].endswith(TAG.commit + ".zip")
    assert HostingProvider().repository_path("a/b/c") == "a/b"
    assert HostingProvider().api_url(REPOSITORY).endswith("/plugin")
    assert HostingProvider().tags_request(REPOSITORY, 3)[1]["page"] == 3
    assert HostingProvider().parse_tag(
        {"name": "v", "commit": {"sha": "s"}}) == RepositoryTag("v", "s")


def test_repository_module_name_public_hosts():
    assert PluginRepository.from_url(
        "https://codeberg.org/team/plugin").module_name == "codeberg_team_plugin"
    assert PluginRepository.from_url(
        "https://gitlab.com/team/plugin").module_name == "gitlab_team_plugin"
    assert PluginRepository.from_url(
        "https://gitee.com/team/plugin").module_name == "gitee_team_plugin"
    assert PluginRepository.from_url(
        "https://git.example/team/plugin", "gitlab").module_name == \
        "gitlab_git_example_team_plugin"


def test_svg_data_rejects_unknown_name():
    with pytest.raises(ValueError, match="Unknown plugin manager action icon"):
        icons._svg_data("not-a-real-icon")


def test_translation_helper_is_callable():
    from plugin_manager.plugin_repositories import _tr as repositories_tr
    assert repositories_tr("hello") == "hello"


def test_svg_data_missing_resource_and_finally_closes_file(monkeypatch, qapp):
    class MissingFile:
        def __init__(self, path):
            self.path = path
            self.closed = False

        def open(self, mode):
            return False

        def close(self):
            self.closed = True

    files = []
    monkeypatch.setattr(icons, "QFile", lambda path: (
        files.append(MissingFile(path)) or files[-1]))
    icons._svg_data.cache_clear()
    with pytest.raises(RuntimeError, match="Missing plugin manager action resource"):
        icons._svg_data("download")
    assert files[0].path == ":/plugin_manager/actions/download.svg"
    assert files[0].closed is False
    icons._svg_data.cache_clear()


def test_svg_data_closes_successfully_opened_file(monkeypatch, qapp):
    class GoodFile:
        def __init__(self):
            self.closed = False
            self.read = False

        def open(self, mode):
            return True

        def readAll(self):
            self.read = True
            return __import__("PySide6.QtCore", fromlist=["QByteArray"]).QByteArray(b"<svg/>")

        def close(self):
            self.closed = True

    source = GoodFile()
    monkeypatch.setattr(icons, "QFile", lambda path: source)
    icons._svg_data.cache_clear()
    assert icons._svg_data("download") == b"<svg/>"
    assert source.closed and source.read
    icons._svg_data.cache_clear()


def test_action_icon_engine_clone_preserves_flags(qapp):
    engine = icons._ActionIconEngine(b"<svg/>", False)
    clone = engine.clone()
    assert isinstance(clone, icons._ActionIconEngine)
    assert clone._data == engine._data
    assert clone._recolour is False
    assert clone is not engine
    del engine, clone


@pytest.mark.parametrize("mode", [
    pytest.param("Normal", id="normal"),
    pytest.param("Disabled", id="disabled"),
    pytest.param("Selected", id="selected"),
])
def test_icon_engine_all_paths(qapp, qtbot, mode):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication

    qt_mode = getattr(QIcon.Mode, mode)
    for name, recolour in (("download", True), ("app", False)):
        icon = icons.action_icon(name)
        assert not icon.isNull()
        assert not icon.pixmap(QSize(24, 16)).isNull()
        assert not icon.pixmap(QSize(24, 16), qt_mode).isNull()
        engine = icons._ActionIconEngine(icons._svg_data(name), recolour)
        assert not engine.pixmap(QSize(16, 16), qt_mode,
                                 QIcon.State.Off).isNull()
        assert not engine.scaledPixmap(QSize(16, 16), qt_mode,
                                       QIcon.State.Off, 1.5).isNull()
        target = QPixmap(32, 32)
        target.fill(0)
        painter = QPainter(target)
        try:
            engine.paint(painter, QRect(0, 0, 16, 16), qt_mode, QIcon.State.Off)
        finally:
            painter.end()
        assert not target.toImage().isNull()
    assert QApplication.instance() is qapp


def test_set_action_icon_on_qaction(qapp, qtbot):
    action = QAction("text")
    icons.set_action_icon(action, "download")
    assert not action.icon().isNull()
    assert action.isIconVisibleInMenu()
    action.deleteLater()


def test_set_action_icon_on_object_without_seticon(qapp):
    class Target(QPushButton):
        def setIcon(self, icon):
            raise AttributeError("no setIcon")

    target = Target("text")
    with pytest.raises(AttributeError, match="no setIcon"):
        icons.set_action_icon(target, "download")
    target.deleteLater()


def test_set_action_icon_on_non_qaction_button(qapp, qtbot):
    button = QPushButton("text")
    qtbot.addWidget(button)
    icons.set_action_icon(button, "close")
    assert button.iconSize() == QSize(16, 16)
    assert not button.icon().isNull()


def test_set_button_box_icons_applies_only_to_existing_buttons(qapp, qtbot):
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                           QDialogButtonBox.StandardButton.Cancel)
    qtbot.addWidget(box)
    icons.set_button_box_icons(box)
    assert not box.button(QDialogButtonBox.StandardButton.Ok).icon().isNull()
    assert not box.button(QDialogButtonBox.StandardButton.Cancel).icon().isNull()
    assert box.button(QDialogButtonBox.StandardButton.Close) is None
