import base64
import hashlib
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
        self.text = body.decode("utf-8", errors="replace")
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.closed = True

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


GITEE_REPOSITORY = PluginRepository.from_url("https://gitee.com/example/my-plugin")


def readme_client(*responses, cancelled=lambda: False):
    session = FakeSession(*responses)
    return PluginDownloader(session, cancelled, lambda *_: None), session


def test_fetch_github_readme_uses_api_branch_and_file_directory():
    response = FakeResponse(body=json.dumps({
        "path": "docs/ReadMe.markdown",
        "html_url": "https://github.com/Example/my-plugin/blob/release%2Fdocs/docs/ReadMe.markdown",
        "encoding": "base64",
        "content": base64.encodebytes("\ufeff# 文档\n[图片](images/example.png)".encode()).decode(),
    }).encode())
    client, session = readme_client(response)
    assert client.fetch_readme(REPOSITORY) == (
        "# 文档\n[图片](images/example.png)",
        "https://github.com/example/my-plugin/tree/release%2Fdocs/docs/",
    )
    [(url, options)] = session.calls
    assert url == "https://api.github.com/repos/example/my-plugin/readme"
    assert options["stream"] and options["timeout"] == (3, 8)
    assert response.closed


def test_fetch_github_readme_returns_none_for_404():
    missing = FakeResponse(status=404)
    client, session = readme_client(missing)
    assert client.fetch_readme(REPOSITORY) is None
    assert len(session.calls) == 1
    assert missing.closed


def test_fetch_github_readme_uses_head_on_rate_limit():
    limited = FakeResponse(status=403, headers={"X-RateLimit-Remaining": "0"})
    client, session = readme_client(limited, FakeResponse(body=b"# Default branch"))
    assert client.fetch_readme(REPOSITORY) == (
        "# Default branch", REPOSITORY.url + "/tree/HEAD/",
    )
    assert session.calls[1][0] == "https://raw.githubusercontent.com/example/my-plugin/HEAD/README.md"
    assert limited.closed


def test_fetch_gitee_readme_uses_default_branch_and_allows_official_cdn():
    metadata = FakeResponse(body=b'{"default_branch":"docs/v2"}')
    missing = FakeResponse(status=404)
    cdn_url = "https://raw.giteeusercontent.com/example/my-plugin/raw/docs%2Fv2/Readme.md"
    redirect = FakeResponse(status=302, headers={"Location": cdn_url})
    document = FakeResponse(body=b"# Gitee\n")
    client, session = readme_client(metadata, missing, redirect, document)
    assert client.fetch_readme(GITEE_REPOSITORY) == (
        "# Gitee\n", GITEE_REPOSITORY.url + "/tree/docs%2Fv2/",
    )
    assert [call[0] for call in session.calls] == [
        "https://gitee.com/api/v5/repos/example/my-plugin",
        GITEE_REPOSITORY.url + "/raw/docs%2Fv2/README.md",
        GITEE_REPOSITORY.url + "/raw/docs%2Fv2/Readme.md",
        cdn_url,
    ]
    assert all(response.closed for response in (metadata, missing, redirect, document))


def test_fetch_gitee_readme_resolves_head_on_api_rejection():
    head = b"a" * 40 + b" HEAD\0multi_ack symref=HEAD:refs/heads/trunk agent=gitee\n"
    refs = b"001e# service=git-upload-pack\n0000" + f"{len(head) + 4:04x}".encode() + head + b"0000"
    client, session = readme_client(
        FakeResponse(status=403),
        FakeResponse(body=refs, headers={"Content-Type": "application/x-git-upload-pack-advertisement"}),
        FakeResponse(body=b"# Trunk"),
    )
    assert client.fetch_readme(GITEE_REPOSITORY) == ("# Trunk", GITEE_REPOSITORY.url + "/tree/trunk/")
    assert session.calls[1][0] == GITEE_REPOSITORY.url + ".git/info/refs"
    assert session.calls[1][1]["params"] == {"service": "git-upload-pack"}
    assert session.calls[2][0] == GITEE_REPOSITORY.url + "/raw/trunk/README.md"


def test_fetch_gitee_readme_tries_common_names_and_returns_none_if_missing():
    missing = [FakeResponse(status=404) for _ in download._README_FILENAMES]
    client, session = readme_client(FakeResponse(body=b'{"default_branch":"trunk"}'), *missing)
    assert client.fetch_readme(GITEE_REPOSITORY) is None
    candidates = {url.rsplit("/", 1)[-1] for url, _ in session.calls[1:]}
    assert {"README.md", "Readme.md", "ReadMe.md", "readme.MD", "README.markdown", "README.txt", "README"} <= candidates
    assert all(response.closed for response in missing)


@pytest.mark.parametrize("location", [
    "http://raw.giteeusercontent.com/file",
    "https://raw.giteeusercontent.com:8443/file",
    "https://untrusted.example/file",
    "https://127.0.0.1/file",
])
def test_fetch_readme_rejects_unsafe_redirects(location):
    redirect = FakeResponse(status=302, headers={"Location": location})
    client, session = readme_client(FakeResponse(body=b'{"default_branch":"main"}'), redirect)
    with pytest.raises(ValueError):
        client.fetch_readme(GITEE_REPOSITORY)
    assert len(session.calls) == 2
    assert redirect.closed


@pytest.mark.parametrize("body, headers", [
    (b"", {"Content-Length": str(download._MAX_README_BYTES + 1)}),
    (b"x" * (download._MAX_README_BYTES + 1), {"Content-Length": "1"}),
    (b"<html>challenge</html>", {"Content-Type": "text/html; charset=UTF-8"}),
    (b"\xff", {}),
], ids=["declared-size", "streamed-size", "html", "invalid-utf8"])
def test_fetch_readme_rejects_invalid_or_oversized_content(body, headers):
    document = FakeResponse(body=body, headers=headers)
    client, _ = readme_client(FakeResponse(body=b'{"default_branch":"main"}'), document)
    with pytest.raises(ValueError):
        client.fetch_readme(GITEE_REPOSITORY)
    assert document.closed


def test_fetch_github_readme_rejects_offsite_api_file_link():
    response = FakeResponse(body=b'{"path":"README.md","html_url":"https://untrusted.example/example/my-plugin/blob/main/README.md"}')
    client, session = readme_client(response)
    with pytest.raises(ValueError):
        client.fetch_readme(REPOSITORY)
    assert len(session.calls) == 1
    assert response.closed


def test_fetch_readme_does_not_treat_server_failure_as_missing():
    response = FakeResponse(status=502)
    client, _ = readme_client(response)
    with pytest.raises(requests.HTTPError):
        client.fetch_readme(REPOSITORY)
    assert response.closed


def test_fetch_readme_closes_response_when_cancelled_during_stream():
    interrupted = Event()

    class CancelledResponse(FakeResponse):
        def iter_content(self, chunk_size):
            interrupted.set()
            yield b"# Partial"

    document = CancelledResponse()
    client, _ = readme_client(
        FakeResponse(body=b'{"default_branch":"main"}'), document, cancelled=interrupted.is_set)
    with pytest.raises(DownloadCancelled):
        client.fetch_readme(GITEE_REPOSITORY)
    assert document.closed


def test_fetch_readme_rejects_unsupported_repository_before_request():
    client, session = readme_client()
    with pytest.raises(ValueError):
        client.fetch_readme(PluginRepository.from_url("https://gitlab.com/example/my-plugin"))
    assert session.calls == []


def test_tags_pagination_and_pinned_commit():
    session = FakeSession(
        FakeResponse(data=[{"name": TAG.name, "commit": {"sha": TAG.commit}}], links={"next": {}}),
        FakeResponse(data=[{"name": "v0", "commit": {"sha": "b" * 40}}]),
    )
    client = PluginDownloader(session, lambda: False, lambda *_: None)
    assert client.list_tags(REPOSITORY) == [TAG, RepositoryTag("v0", "b" * 40)]
    assert [call[1]["params"]["page"] for call in session.calls] == [1, 2]


def test_discover_plugins_falls_back_to_public_search_page_when_api_is_limited():
    payload = {
        "payload": {"blackbirdSearchRoute": {
            "results": [{
                "repo": {"repository": {
                    "name": "my-plugin", "owner_login": "example"}},
                "hl_trunc_description": "<em>Sample</em> &amp; plugin",
            }],
            "page_count": 1,
        }},
    }
    html = (
        '<script type="application/json" data-target="react-app.embeddedData">'
        + json.dumps(payload)
        + "</script>"
    ).encode()
    session = FakeSession(
        FakeResponse(status=403, headers={"X-RateLimit-Remaining": "0"}),
        FakeResponse(body=html),
    )
    client = PluginDownloader(session, lambda: False, lambda *_: None)

    entries = client.discover_plugins()

    assert len(entries) == 1
    assert entries[0].repository.url == "https://github.com/example/my-plugin"
    assert entries[0].description == "Sample & plugin"
    assert session.calls[1][0] == "https://github.com/search"


def test_list_tags_falls_back_to_public_html_when_github_api_is_limited():
    commit = "a" * 40
    html = (
        '<h2><a href="/example/my-plugin/releases/tag/metasweeper-v1.0.0">'
        'metasweeper-v1.0.0</a></h2>'
        f'<a href="/example/my-plugin/commit/{commit}">commit</a>'
    ).encode()
    session = FakeSession(
        FakeResponse(status=403, headers={"X-RateLimit-Remaining": "0"}),
        FakeResponse(body=html),
        FakeResponse(body=b"no more tags"),
    )
    repository = PluginRepository.from_url("https://github.com/example/my-plugin")
    client = PluginDownloader(session, lambda: False, lambda *_: None)

    assert client.list_tags(repository) == [RepositoryTag("metasweeper-v1.0.0", commit)]
    assert len(session.calls) == 3
    assert session.calls[1][0] == "https://github.com/example/my-plugin/tags"
    assert session.calls[2][0] == "https://github.com/example/my-plugin/tags?page=2"


def test_install_does_not_publish_when_preparation_fails(tmp_path):
    body = make_archive([
        ("repo-sha/training_stats/__init__.py", ""),
        ("repo-sha/training_stats/requirements.txt", "pandas>=2"),
    ])
    client = PluginDownloader(
        FakeSession(FakeResponse(body=body)), lambda: False, lambda *_: None)
    root = tmp_path / "user_plugins"

    def fail_preparation(package):
        assert (package / "requirements.txt").is_file()
        raise RuntimeError("dependency installation failed")

    with pytest.raises(RuntimeError, match="dependency installation failed"):
        client.install(
            REPOSITORY, TAG, root, [], before_publish=fail_preparation)

    assert not (root / REPOSITORY.module_name).exists()
    assert list(root.iterdir()) == []


def test_install_accepts_single_plugin_subdirectory(tmp_path):
    body = make_archive([
        ("repo-sha/README.md", "project readme"),
        ("repo-sha/tests/test_sample.py", ""),
        ("repo-sha/training_stats/__init__.py", ""),
        ("repo-sha/training_stats/plugin.py", ""),
    ])
    client = PluginDownloader(FakeSession(FakeResponse(body=body)), lambda: False, lambda *_: None)
    root = tmp_path / "user_plugins"
    path = client.install(REPOSITORY, TAG, root, [])
    assert (path / "__init__.py").is_file()
    assert (path / "plugin.py").is_file()
    assert not (path / "README.md").exists()
    assert PluginLoader([root]).discover_plugins() == [
        (path / "__init__.py", REPOSITORY.module_name)]


@pytest.mark.parametrize(("prefix", "name"), [
    ("", "example_zip"),
    ("sample/", "sample"),
    ("source-main/sample/", "sample"),
])
def test_import_zip_publishes_one_local_package(tmp_path, prefix, name):
    from plugin_manager.plugin_catalog import read_installed_metadata, read_installed_plugin

    archive = tmp_path / "example-zip.zip"
    archive.write_bytes(make_archive([
        (prefix + "__init__.py", ""),
        (prefix + "assets/example.txt", "asset"),
        (prefix + ".metasweeper-plugin.json", '{"repository":"https://github.com/example/other"}'),
    ]))
    root = tmp_path / "user_plugins"
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)

    def prepare(package, module_name):
        assert module_name == name
        assert (package / "__init__.py").is_file()
        assert not (root / name).exists()

    installed = downloader.import_zip(archive, root, [], before_publish=prepare)
    assert installed == root / name
    assert (installed / "assets/example.txt").read_text() == "asset"
    assert read_installed_metadata(installed) == {"source": "local_zip"}
    assert read_installed_plugin(installed) is None
    assert PluginLoader([root]).discover_plugins() == [(installed / "__init__.py", name)]
    (installed / "obsolete.py").write_text("old file", encoding="utf-8")
    assert downloader.import_zip(archive, root, [], before_publish=lambda *_: None) == installed
    assert not (installed / "obsolete.py").exists()
    assert list(root.iterdir()) == [installed]


def plugin_source(version="1.0", name="stable_demo"):
    return f'''
raise RuntimeError("must not execute during import")
class Demo:
    @classmethod
    def plugin_info(cls):
        return PluginInfo(name={name!r}, version={version!r})
'''


@pytest.mark.parametrize("prefix", ["", "demo/", "demo-metasweeper-v2.0/", "demo-sha/demo/"])
def test_import_zip_updates_across_archive_names_and_layouts(tmp_path, prefix):
    archive = tmp_path / "demo-1.0.zip"
    archive.write_bytes(make_archive([("demo/plugin.py", plugin_source()), ("demo/__init__.py", "")]))
    root = tmp_path / "user_plugins"
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)
    installed = downloader.import_zip(archive, root, [], before_publish=lambda *_: None)
    assert installed == root / "stable_demo"
    (installed / "obsolete.py").write_text("old file", encoding="utf-8")
    data = tmp_path / "data/plugin_data/stable_demo/settings.json"
    data.parent.mkdir(parents=True)
    data.write_text('{"user_id":23}', encoding="utf-8")
    archive = tmp_path / "demo-2.0.zip"
    archive.write_bytes(make_archive([
        (prefix + "__init__.py", ""), (prefix + "plugin.py", plugin_source("2.0")),
    ]))
    prepared = []

    def prepare(package, name):
        assert "1.0" in (installed / "plugin.py").read_text()
        assert "2.0" in (package / "plugin.py").read_text()
        prepared.append(name)

    assert downloader.import_zip(archive, root, [root], before_publish=prepare) == installed
    assert prepared == ["stable_demo"]
    assert "2.0" in (installed / "plugin.py").read_text()
    assert not (installed / "obsolete.py").exists()
    assert data.read_text() == '{"user_id":23}'
    assert list(root.iterdir()) == [installed]


def test_zip_can_update_market_install_without_duplicate_or_stale_metadata(tmp_path):
    from plugin_manager.plugin_catalog import read_installed_metadata, scan_installed

    body = make_archive([("repo-sha/__init__.py", ""), ("repo-sha/plugin.py", plugin_source())])
    root = tmp_path / "user_plugins"
    downloader = PluginDownloader(FakeSession(FakeResponse(body=body)), lambda: False, lambda *_: None)
    installed = downloader.install(REPOSITORY, TAG, root, [], plugin_version="1.0", tag_prefix="release/v")
    archive = tmp_path / "downloaded-release.zip"
    archive.write_bytes(make_archive([
        ("my-plugin-metasweeper-v2.0/__init__.py", ""),
        ("my-plugin-metasweeper-v2.0/plugin.py", plugin_source("2.0")),
    ]))

    assert downloader.import_zip(archive, root, [], before_publish=lambda *_: None) == installed
    metadata = read_installed_metadata(installed)
    assert metadata == {"source": "local_zip", "repository": REPOSITORY.url,
                        "platform": REPOSITORY.platform, "tag_prefix": "release/v", "version": "2.0"}
    assert scan_installed([root])[REPOSITORY.url].version.public == "2.0"
    assert list(root.iterdir()) == [installed]


@pytest.mark.parametrize("failure", ["prepare", "publish", "cancel"])
def test_zip_update_failure_preserves_installed_package(tmp_path, monkeypatch, failure):
    archive = tmp_path / "demo.zip"
    archive.write_bytes(make_archive([("demo/__init__.py", "# old")]))
    root = tmp_path / "user_plugins"
    cancelled = Event()
    downloader = PluginDownloader(FakeSession(), cancelled.is_set, lambda *_: None)
    installed = downloader.import_zip(archive, root, [], before_publish=lambda *_: None)
    old_metadata = (installed / ".metasweeper-plugin.json").read_bytes()
    archive.write_bytes(make_archive([("demo/__init__.py", "# new")]))
    rename = download.Path.rename

    def fail_publish(path, destination):
        if path.name == "demo" and path != installed and destination == installed:
            raise OSError("publish failed")
        return rename(path, destination)

    def prepare(*_):
        if failure == "prepare":
            raise RuntimeError("preparation failed")
        if failure == "cancel":
            cancelled.set()

    if failure == "publish":
        monkeypatch.setattr(download.Path, "rename", fail_publish)
    with pytest.raises((RuntimeError, OSError, DownloadCancelled)):
        downloader.import_zip(archive, root, [], before_publish=prepare)
    assert (installed / "__init__.py").read_text() == "# old"
    assert (installed / ".metasweeper-plugin.json").read_bytes() == old_metadata
    assert list(root.iterdir()) == [installed]


@pytest.mark.parametrize("location", ["user_plugins", "plugins"])
def test_zip_does_not_overwrite_unmanaged_or_bundled_plugin(tmp_path, location):
    archive = tmp_path / "demo.zip"
    archive.write_bytes(make_archive([("demo/__init__.py", plugin_source("2.0"))]))
    root = tmp_path / "user_plugins"
    existing = tmp_path / location / "different_module"
    existing.mkdir(parents=True)
    (existing / "__init__.py").write_text(plugin_source(), encoding="utf-8")
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)
    with pytest.raises(FileExistsError, match="不能覆盖"):
        downloader.import_zip(archive, root, [existing.parent], before_publish=lambda *_: pytest.fail("unsafe update"))
    assert "1.0" in (existing / "__init__.py").read_text()


def test_zip_refuses_ambiguous_installed_matches(tmp_path):
    root = tmp_path / "user_plugins"
    for name in ["first", "second"]:
        package = root / name
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(plugin_source(), encoding="utf-8")
    archive = tmp_path / "demo.zip"
    archive.write_bytes(make_archive([("demo/__init__.py", plugin_source("2.0"))]))
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)
    with pytest.raises(ValueError, match="多个同名插件"):
        downloader.import_zip(archive, root, [], before_publish=lambda *_: pytest.fail("ambiguous update"))


def test_zip_refuses_same_directory_with_different_plugin_identity(tmp_path):
    root = tmp_path / "user_plugins"
    package = root / "stable_demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(plugin_source(name="other"), encoding="utf-8")
    (package / ".metasweeper-plugin.json").write_text('{"source":"local_zip"}')
    archive = tmp_path / "demo.zip"
    archive.write_bytes(make_archive([("demo/__init__.py", plugin_source())]))
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)
    with pytest.raises(FileExistsError, match="标识不匹配"):
        downloader.import_zip(archive, root, [], before_publish=lambda *_: pytest.fail("identity conflict"))
    assert "other" in (package / "__init__.py").read_text()


def test_zip_update_does_not_reuse_market_version_when_new_version_is_unknown(tmp_path):
    from plugin_manager.plugin_catalog import read_installed_plugin, read_installed_metadata

    root = tmp_path / "user_plugins"
    package = root / "stable_demo"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(plugin_source(), encoding="utf-8")
    (package / ".metasweeper-plugin.json").write_text(json.dumps({
        "repository": REPOSITORY.url, "tag": "metasweeper-v1.0", "version": "1.0",
    }))
    archive = tmp_path / "demo.zip"
    archive.write_bytes(make_archive([("demo/__init__.py", plugin_source().replace("version='1.0'", "version=VERSION"))]))
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)
    assert downloader.import_zip(archive, root, [], before_publish=lambda *_: None) == package
    assert read_installed_plugin(package).version is None
    assert read_installed_metadata(package) == {"source": "local_zip", "repository": REPOSITORY.url}


def test_zip_statically_matches_positional_plugin_info_name(tmp_path):
    archive = tmp_path / "source-2.0.zip"
    source = plugin_source().replace("name='stable_demo'", "'stable_demo'")
    archive.write_bytes(make_archive([("source-2.0/__init__.py", source)]))
    root = tmp_path / "user_plugins"
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)
    assert downloader.import_zip(archive, root, [], before_publish=lambda *_: None) == root / "stable_demo"


@pytest.mark.parametrize("contents", [
    b"not a zip",
    make_archive([("../outside.py", ""), ("sample/__init__.py", "")]),
    make_archive([("first/__init__.py", ""), ("second/__init__.py", "")]),
])
def test_import_zip_rejects_invalid_archives_and_cleans_staging(tmp_path, contents):
    archive = tmp_path / "invalid.zip"
    archive.write_bytes(contents)
    root = tmp_path / "user_plugins"
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)
    with pytest.raises(ValueError):
        downloader.import_zip(archive, root, [], before_publish=lambda *_: pytest.fail("invalid archive"))
    assert list(root.iterdir()) == []
    assert not (tmp_path / "outside.py").exists()


def test_import_zip_does_not_publish_when_preparation_fails(tmp_path):
    archive = tmp_path / "sample.zip"
    archive.write_bytes(make_archive([("__init__.py", "")]))
    root = tmp_path / "user_plugins"
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)

    def prepare(*args):
        raise RuntimeError("dependency preparation failed")

    with pytest.raises(RuntimeError, match="dependency preparation failed"):
        downloader.import_zip(archive, root, [], before_publish=prepare)
    assert list(root.iterdir()) == []


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
    assert session.calls[0][0] == "https://codeload.github.com/example/my-plugin/zip/" + TAG.commit
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
    archive = make_archive([("repo-sha/__init__.py", "")])
    session = FakeSession(
        FakeResponse(data=[{"name": TAG.name, "commit": {key: TAG.commit}}], headers={"Link": ""}),
        FakeResponse(body=archive),
    )
    client = PluginDownloader(session, lambda: False, lambda *_: None)
    tags = client.list_tags(repository)
    assert tags == [TAG]
    path = client.install(repository, tags[0], tmp_path, [])
    assert session.calls[0][0] == api + "/tags"
    assert session.calls[0][1]["params"] == {**page_size, "page": 1}
    expected_archive = (
        f"https://codeload.github.com/{repository.path}/zip/{TAG.commit}"
        if repository.platform == "github" else api + archive_suffix)
    assert session.calls[1][0] == expected_archive
    assert session.calls[1][1]["params"] == archive_params
    assert ("X-GitHub-Api-Version" in session.calls[1][1]["headers"]) == (repository.platform == "github")
    metadata = json.loads((path / ".metasweeper-plugin.json").read_text())
    assert metadata == {
        "repository": repository.url,
        "platform": repository.platform,
        "tag": TAG.name,
        "commit": TAG.commit,
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
    }


@pytest.mark.parametrize("status", [403, 429])
def test_gitee_tags_fall_back_to_public_http_refs(status):
    repository = PluginRepository.from_url("https://gitee.com/team/plugin")
    packets = [
        b"# service=git-upload-pack\n", b"",
        b"a" * 40 + b" HEAD\0symref=HEAD:refs/heads/main\n",
        b"b" * 40 + b" refs/tags/v1\n",
        b"c" * 40 + b" refs/tags/v2\n",
        b"d" * 40 + b" refs/tags/v2^{}\n", b"",
    ]
    body = b"".join(f"{len(packet) + 4:04x}".encode() + packet if packet else b"0000"
                    for packet in packets)
    session = FakeSession(
        FakeResponse(status=status),
        FakeResponse(body=body, headers={
            "Content-Type": "application/x-git-upload-pack-advertisement",
        }),
    )
    client = PluginDownloader(session, lambda: False, lambda *_: None)

    assert client.list_tags(repository) == [
        RepositoryTag("v1", "b" * 40), RepositoryTag("v2", "d" * 40),
    ]
    url, kwargs = session.calls[-1]
    assert url == "https://gitee.com/team/plugin.git/info/refs"
    assert kwargs["params"] == {"service": "git-upload-pack"}


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
