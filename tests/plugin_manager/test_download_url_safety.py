from __future__ import annotations

import pytest

from plugin_manager.plugin_download import PluginDownloader
from plugin_manager.plugin_repositories import PluginRepository, RepositoryTag


TAG = RepositoryTag("v1", "a" * 40)
REPOSITORY = PluginRepository.from_url("https://github.com/example/plugin")


class FakeResponse:
    def __init__(self, *, data=None, status=200, headers=None):
        self.data = data
        self.status_code = status
        self.headers = dict(headers or {})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


def downloader(*responses):
    return PluginDownloader(FakeSession(*responses), lambda: False, lambda *_: None)


def test_safe_get_rejects_https_redirect_to_http_or_untrusted_host():
    client = downloader(
        FakeResponse(status=302, headers={"Location": "http://api.github.com/zip"}),
    )

    with pytest.raises(ValueError, match="HTTPS"):
        client._safe_get(REPOSITORY, "https://api.github.com/repos/example/plugin/tags")


def test_safe_get_rejects_redirect_to_private_ip():
    client = downloader(
        FakeResponse(status=302, headers={"Location": "https://192.168.1.1/zip"}),
    )

    with pytest.raises(ValueError):
        client._safe_get(REPOSITORY, "https://api.github.com/repos/example/plugin/tags")


def test_safe_get_rejects_unapproved_port_on_allowed_host():
    client = downloader(
        FakeResponse(status=302, headers={"Location": "https://api.github.com:8443/zip"}),
    )

    with pytest.raises(ValueError, match="端口"):
        client._safe_get(REPOSITORY, "https://api.github.com/repos/example/plugin/tags")


def test_safe_get_follows_allowed_github_archive_redirect():
    final = FakeResponse(data=[])
    client = downloader(
        FakeResponse(status=302, headers={
            "Location": "https://codeload.github.com/example/plugin/legacy.zip/" + TAG.commit,
        }),
        final,
    )

    with client._safe_get(
        REPOSITORY, "https://api.github.com/repos/example/plugin/zipball/" + TAG.commit,
    ) as response:
        assert response is final

    calls = client.session.calls
    assert len(calls) == 2
    assert calls[0][1]["allow_redirects"] is False
    assert calls[1][0].startswith("https://codeload.github.com/")


def test_safe_get_rejects_private_self_hosted_repository_before_request():
    repository = PluginRepository.from_url(
        "https://192.168.1.10:8443/team/plugin", "gitea",
    )
    client = downloader(FakeResponse(data=[]))
    url, params = repository.provider.tags_request(repository, 1)

    with pytest.raises(ValueError, match="内网"):
        client._safe_get(repository, url, params=params)
    assert client.session.calls == []


def test_archive_request_rejects_mutable_commit_names():
    for platform_url, platform in (
        ("https://github.com/team/plugin", "auto"),
        ("https://gitlab.com/team/plugin", "auto"),
        ("https://gitee.com/team/plugin", "auto"),
        ("https://codeberg.org/team/plugin", "auto"),
    ):
        repository = PluginRepository.from_url(platform_url, platform)
        with pytest.raises(ValueError, match="commit"):
            repository.provider.archive_request(
                repository, RepositoryTag("v1", "main"),
            )
