"""插件市场扫描与安装流程测试（使用假 HTTP 层，不访问网络）。"""
from __future__ import annotations

import json

import pytest

from plugin_manager import plugin_market_dialog as market
from plugin_manager.plugin_catalog import InstalledPlugin, parse_index, rank_versions

INDEX = json.dumps({
    "schema_version": 1,
    "plugins": [{
        "name": "training_stats",
        "repository": "https://github.com/example/training-stats",
        "description": "训练统计",
        "author": "example",
    }],
})
TAGS = [
    {"name": "metasweeper-v1.0.0", "commit": {"sha": "a" * 40}},
    {"name": "metasweeper-v1.2.0", "commit": {"sha": "b" * 40}},
    {"name": "docs", "commit": {"sha": "c" * 40}},
]


class FakeResponse:
    def __init__(self, *, data=None, body: bytes = b"", status: int = 200):
        self.data = data
        self.body = body
        self.status_code = status
        self.headers = {"Content-Length": str(len(body))}
        self.links: dict = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(str(self.status_code))

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]


class FakeSession:
    def __init__(self, *args, **kwargs):
        self.headers: dict = {}
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, url, **kwargs):
        self.calls.append(url)
        if "search/repositories" in url:
            return FakeResponse(data={"items": [{"name": "training_stats", "html_url": "https://github.com/example/training-stats", "owner": {"login": "example"}}]})
        return FakeResponse(data=TAGS)

    def close(self):
        return None


@pytest.fixture()
def fake_network(monkeypatch):
    import requests

    monkeypatch.setattr(requests, "Session", FakeSession)


def test_github_discovery_requests_topic():
    from plugin_manager.plugin_download import PluginDownloader

    session = FakeSession()
    downloader = PluginDownloader(session, lambda: False, lambda *_: None)
    entries = downloader.discover_plugins()
    assert [entry.repository.url for entry in entries] == [
        "https://github.com/example/training-stats"]
    assert session.calls == ["https://api.github.com/search/repositories"]


def test_scan_collects_versions_and_state(qtbot, fake_network, monkeypatch):
    monkeypatch.setattr(market, "scan_installed", lambda dirs: {})
    captured = []
    task = market._MarketTask("https://github.com/example/plugins", None, None, None)
    task.snapshot.connect(captured.append)
    task.run()

    assert task.error == ""
    assert len(captured) == 1
    (row,) = captured[0].rows
    assert row.entry.name == "training_stats"
    assert row.latest_version == "1.2.0"
    assert row.state == market._tr(market.STATE_NOT_INSTALLED)


def test_scan_marks_update_available(qtbot, fake_network, monkeypatch):
    from pathlib import Path

    entry = parse_index(json.loads(INDEX))[0]
    installed = InstalledPlugin(
        name="training_stats",
        directory=Path("."),
        version=rank_versions(entry, [("metasweeper-v1.0.0", "a" * 40)])[0][0],
    )
    monkeypatch.setattr(
        market, "scan_installed", lambda dirs: {"https://github.com/example/training-stats": installed})
    captured = []
    task = market._MarketTask("https://github.com/example/plugins", None, None, None)
    task.snapshot.connect(captured.append)
    task.run()

    (row,) = captured[0].rows
    assert row.installed_version == "1.0.0"
    assert row.state == market._tr(market.STATE_UPDATE)


def test_install_installs_dependencies_before_publishing_package(
        qtbot, fake_network, monkeypatch, tmp_path):
    from types import SimpleNamespace

    entry = parse_index(json.loads(INDEX))[0]
    releases = market.PluginRelease(
        entry, rank_versions(entry, [("metasweeper-v1.2.0", "b" * 40)]))
    row = market.MarketRow(entry=entry, releases=releases)
    events = []

    monkeypatch.setattr(
        market, "scan_plugin_dependencies",
        lambda *_: SimpleNamespace(status="missing"))

    def install_deps(data_dir, requirements, *, output_callback=None):
        events.append(("dependencies", requirements.name))
        if output_callback:
            output_callback("Installing packages")
        return None

    monkeypatch.setattr(market, "install_plugin_requirements", install_deps)

    class FakeDownloader:
        def __init__(self, *args, **kwargs):
            pass

        def install(self, repository, tag, plugin_dir, search_dirs, **kwargs):
            package = tmp_path / "staging" / "training_stats"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "requirements.txt").write_text("pandas>=2", encoding="utf-8")
            events.append(("download", tag.name))
            kwargs["before_publish"](package)
            events.append(("publish", package.name))
            return "installed-path"

    monkeypatch.setattr(market, "PluginDownloader", FakeDownloader)
    installed_signals = []
    task = market._MarketTask("", row, None, None)
    task.installed.connect(installed_signals.append)
    task.run()

    assert task.error == ""
    assert events == [
        ("download", "metasweeper-v1.2.0"),
        ("dependencies", "requirements.txt"),
        ("publish", "training_stats"),
    ]
    assert installed_signals == ["installed-path"]


def test_install_completion_uses_cached_catalog_and_local_metadata(qtbot, monkeypatch, tmp_path):
    from types import SimpleNamespace

    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    entry = parse_index(json.loads(INDEX))[0]
    releases = market.PluginRelease(
        entry, rank_versions(entry, [("metasweeper-v1.2.0", "b" * 40)]))
    row = market.MarketRow(entry=entry, releases=releases)
    dialog = market.PluginMarketDialog("")
    qtbot.addWidget(dialog)
    dialog._rows = [row]
    installed = InstalledPlugin(
        name="installed", directory=tmp_path, version=releases.latest_version,
        repository=entry.repository.url)
    monkeypatch.setattr(market, "scan_installed", lambda *_: {
        entry.repository.url.lower(): installed})
    monkeypatch.setattr(market, "get_all_plugin_dirs", lambda: [tmp_path])
    monkeypatch.setattr(dialog, "start_scan", lambda: pytest.fail("unexpected remote scan"))
    complete = []
    monkeypatch.setattr(dialog, "_show_install_complete", lambda error="": complete.append(error))
    dialog._task = SimpleNamespace(target=row, error="", deleteLater=lambda: None)
    dialog._show_installed(str(tmp_path))

    dialog._task_finished()

    assert row.releases is releases
    assert row.installed == installed
    assert dialog.table.item(0, 1).text() == "1.2.0"
    assert dialog.table.item(0, 2).text() == "1.2.0"
    assert complete == [""]


def test_market_restart_is_connected_to_window(monkeypatch):
    from types import SimpleNamespace
    from plugin_manager import main_window

    connected = []
    calls = []
    class Dialog:
        def __init__(self, index_url, parent):
            self.restart_requested = SimpleNamespace(connect=connected.append)
        def exec(self):
            connected[0]()
        def deleteLater(self):
            calls.append("closed")

    monkeypatch.setattr(main_window, "PluginMarketDialog", Dialog)
    window = SimpleNamespace(restart_plugin_manager=lambda: calls.append("restart"))
    main_window.PluginManagerWindow._open_plugin_market(window)
    assert calls == ["restart", "closed"]


def test_batch_failure_reports_partial_success(qtbot, monkeypatch, tmp_path):
    from types import SimpleNamespace

    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    dialog = market.PluginMarketDialog("")
    qtbot.addWidget(dialog)
    monkeypatch.setattr(market, "get_all_plugin_dirs", lambda: [])
    monkeypatch.setattr(market, "scan_installed", lambda *_: {})
    outcomes = []
    monkeypatch.setattr(dialog, "_show_install_complete", outcomes.append)
    dialog._installed_paths.append(str(tmp_path))
    dialog._queue.append(object())
    dialog._task = SimpleNamespace(target=object(), error="dependency failed",
                                   deleteLater=lambda: None)

    dialog._task_finished()

    assert outcomes == ["dependency failed"]
    assert dialog._queue == []


@pytest.mark.parametrize("button, expected_restart", [("确认", False), ("重启", True)])
def test_completion_dialog_buttons(qtbot, monkeypatch, button, expected_restart):
    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    dialog = market.PluginMarketDialog("")
    qtbot.addWidget(dialog)
    requests = []
    dialog.restart_requested.connect(lambda: requests.append(True))

    def choose(box):
        target = next(item for item in box.buttons() if item.text() == button)
        target.click()
        return 0

    monkeypatch.setattr(market.QMessageBox, "exec", choose)
    dialog._show_install_complete()
    assert bool(requests) is expected_restart


@pytest.mark.parametrize("selected", ["1.0.0", "1.2.0"])
def test_install_confirmation_matches_selected_version(qtbot, monkeypatch, tmp_path, selected):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    entry = parse_index(json.loads(INDEX))[0]
    releases = market.PluginRelease(entry, rank_versions(entry, [
        ("metasweeper-v1.0.0", "a" * 40),
        ("metasweeper-v1.2.0", "b" * 40),
    ]))
    row = market.MarketRow(entry, releases, InstalledPlugin(
        name=entry.name, directory=tmp_path, version=releases.latest_version))
    dialog = market.PluginMarketDialog("")
    qtbot.addWidget(dialog)
    dialog._rows = [row]
    dialog._populate()
    dialog.table.selectRow(0)
    dialog.version.setCurrentIndex(next(
        i for i in range(dialog.version.count())
        if str(dialog.version.itemData(i)) == selected))
    questions, starts = [], []
    monkeypatch.setattr(market.QMessageBox, "question", lambda *args: (
        questions.append(args[2]) or QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(dialog, "_start_task", lambda *args: starts.append(args))

    dialog._install_selected()

    assert f"更新到 {selected}" in questions[0]
    assert str(starts[0][2]) == selected


@pytest.mark.parametrize("installing", [False, True])
def test_tray_quit_waits_for_market_worker(qtbot, monkeypatch, installing):
    from threading import Event
    from types import SimpleNamespace
    from plugin_manager import main_window
    from tests.plugin_manager.test_cov_pm_e_helpers import shell

    entered, release = Event(), Event()
    def run(task):
        entered.set()
        release.wait(5)
    monkeypatch.setattr(market._MarketTask, "run", run)
    window = shell(qtbot)
    calls = []
    window._tray_icon = None
    window._state_mgr = SimpleNamespace(save=lambda: calls.append("save"))
    window._manager = SimpleNamespace(stop=lambda: calls.append("stop"))
    monkeypatch.setattr(main_window, "QApplication", SimpleNamespace(
        instance=lambda: SimpleNamespace(quit=lambda: calls.append("quit"))))
    dialog = market.PluginMarketDialog("", window)
    qtbot.addWidget(dialog)
    window._market_dialog = dialog
    target = object() if installing else None
    try:
        dialog._start_task("", target, None)
        qtbot.waitUntil(entered.is_set)
        task = dialog._task
        window._really_quit()
        window._really_quit()
        assert task.isInterruptionRequested()
        assert calls == []
        release.set()
        qtbot.waitUntil(lambda: calls == ["save", "stop", "quit"])
        assert dialog._task is None
    finally:
        release.set()
        if dialog._task is not None:
            dialog._task.wait(5000)


def test_tray_quit_runs_after_market_modal_loop_returns(qtbot, monkeypatch):
    from threading import Event
    from types import SimpleNamespace
    from PySide6.QtCore import QTimer
    from plugin_manager import main_window
    from tests.plugin_manager.test_cov_pm_e_helpers import shell

    entered, release = Event(), Event()
    def run(task):
        entered.set()
        release.wait(5)
    monkeypatch.setattr(market._MarketTask, "run", run)
    window = shell(qtbot)
    window._tray_icon = None
    calls = []
    window._state_mgr = SimpleNamespace(save=lambda: calls.append("save"))
    window._manager = SimpleNamespace(stop=lambda: calls.append("stop"))
    monkeypatch.setattr(main_window, "QApplication", SimpleNamespace(
        instance=lambda: SimpleNamespace(quit=lambda: calls.append("quit"))))

    def quit_while_running():
        if not entered.is_set():
            QTimer.singleShot(10, quit_while_running)
            return
        window._really_quit()
        release.set()

    QTimer.singleShot(0, quit_while_running)
    try:
        window._open_plugin_market()
        calls.append("dialog returned")
        qtbot.waitUntil(lambda: "quit" in calls)
        assert calls == ["dialog returned", "save", "stop", "quit"]
    finally:
        release.set()


def test_scan_survives_single_repository_failure(qtbot, fake_network, monkeypatch):
    from plugin_manager import plugin_download

    def boom(self, repository):
        raise ValueError("仓库不可用")

    monkeypatch.setattr(plugin_download.PluginDownloader, "list_tags", boom)
    monkeypatch.setattr(market, "scan_installed", lambda dirs: {})
    captured = []
    task = market._MarketTask("https://github.com/example/plugins", None, None, None)
    task.snapshot.connect(captured.append)
    task.run()

    (row,) = captured[0].rows
    assert row.releases is not None and row.releases.error == "仓库不可用"
    assert row.state == market._tr(market.STATE_FAILED)


def test_update_download_failure_preserves_installed(tmp_path, monkeypatch):
    from plugin_manager.plugin_download import PluginDownloader
    from plugin_manager.plugin_repositories import PluginRepository, RepositoryTag

    repo = PluginRepository.from_url("https://github.com/example/training-stats")
    destination = tmp_path / repo.module_name
    destination.mkdir()
    (destination / "__init__.py").write_text("old", encoding="utf-8")
    (destination / ".metasweeper-plugin.json").write_text(
        json.dumps({"repository": repo.url}), encoding="utf-8")
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)
    def fail(*args, **kwargs):
        raise OSError("network failure")
    monkeypatch.setattr(downloader, "_download", fail)
    with pytest.raises(OSError):
        downloader.update(repo, RepositoryTag("v2", "a" * 40), tmp_path)
    assert (destination / "__init__.py").read_text(encoding="utf-8") == "old"
