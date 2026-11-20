"""插件市场扫描与安装流程测试（使用假 HTTP 层，不访问网络）。"""
from __future__ import annotations

import json

import pytest

from plugin_manager import plugin_market_dialog as market
from plugin_manager.plugin_catalog import InstalledPlugin, parse_index, rank_versions
from plugin_manager.plugin_repositories import PluginRepository

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


def test_gitee_discovery_searches_public_plugin_repositories(monkeypatch):
    from plugin_manager.plugin_download import PluginDownloader

    session = FakeSession()
    calls = []
    result = {"hits": {"total": {"value": 2}, "hits": [
        {"fields": {
            "path": ["metasweeper-example-plugin"],
            "url": ["https://gitee.com/example/metasweeper-example-plugin"],
            "description": ["MetaSweeper plugin"],
            "owner.path.keyword": ["example"],
        }},
        {"fields": {
            "path": ["Metasweeper"],
            "url": ["https://gitee.com/example/Metasweeper"],
        }},
    ]}}
    monkeypatch.setattr(session, "get", lambda url, **kwargs: (
        calls.append((url, kwargs)) or FakeResponse(data=result)))
    downloader = PluginDownloader(session, lambda: False, lambda *_: None)

    entries = downloader.discover_plugins("gitee")

    assert len(entries) == 1
    assert entries[0].repository.url == "https://gitee.com/example/metasweeper-example-plugin"
    assert entries[0].repository.platform == "gitee"
    assert entries[0].description == "MetaSweeper plugin"
    assert entries[0].author == "example"
    assert calls[0][0] == "https://so.gitee.com/v1/search/widget/wong1slagnlmzwvsu5ya"
    assert calls[0][1]["params"] == {"q": "metasweeper", "from": 0, "size": 100}


def test_gitee_discovery_retries_transient_connection_reset(monkeypatch):
    import requests
    from plugin_manager import plugin_download
    from plugin_manager.plugin_download import PluginDownloader

    monkeypatch.setattr(plugin_download.time, "sleep", lambda *_: None)
    session = FakeSession()
    calls = []
    response = FakeResponse(data={"hits": {"total": {"value": 0}, "hits": []}})

    def get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise requests.ConnectionError("connection reset")
        return response

    monkeypatch.setattr(session, "get", get)
    downloader = PluginDownloader(session, lambda: False, lambda *_: None)

    assert downloader.discover_plugins("gitee") == []
    assert len(calls) == 2


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


def test_scan_matches_installed_plugin_from_other_source(qtbot, monkeypatch, tmp_path):
    github = PluginRepository.from_url(
        "https://github.com/ljzloser/metasweeper-history")
    gitee = PluginRepository.from_url(
        "https://gitee.com/Q1312358581/metasweeper-history")
    entry = market.CatalogEntry(name="metasweeper-history", repository=gitee)
    installed = InstalledPlugin(
        name=github.module_name, directory=tmp_path / github.module_name,
        version=market.Version("1.0.0"),
        repository=github.url, platform="github")
    monkeypatch.setattr(market, "scan_installed", lambda *_: {
        github.url.lower(): installed,
    })

    class GiteeTagSession(FakeSession):
        def get(self, url, **kwargs):
            response = FakeResponse(data=[{
                "name": "metasweeper-v1.1.0",
                "commit": {"sha": "a" * 40},
            }])
            response.headers["Link"] = ""
            return response

    monkeypatch.setattr(market.requests, "Session", GiteeTagSession)
    task = market._MarketTask("", None, None, None, source="gitee")
    snapshot = task._scan(None, [entry])

    assert snapshot.rows[0].installed is installed
    assert snapshot.rows[0].state == market._tr(market.STATE_UPDATE)


def test_install_installs_dependencies_before_publishing_package(
        qtbot, fake_network, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from plugin_manager import plugin_updates

    entry = parse_index(json.loads(INDEX))[0]
    releases = market.PluginRelease(
        entry, rank_versions(entry, [("metasweeper-v1.2.0", "b" * 40)]))
    row = market.MarketRow(entry=entry, releases=releases)
    events = []

    monkeypatch.setattr(
        plugin_updates, "scan_plugin_dependencies",
        lambda *_: SimpleNamespace(status="missing"))

    def install_deps(data_dir, requirements, *, output_callback=None):
        events.append(("dependencies", requirements.name))
        if output_callback:
            output_callback("Installing packages")
        return None

    monkeypatch.setattr(plugin_updates, "install_plugin_requirements", install_deps)

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


def test_market_uninstall_refreshes_selected_row(qtbot, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QWidget

    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    monkeypatch.setattr(market, "is_managed_plugin", lambda path: path == tmp_path)
    monkeypatch.setattr(market, "scan_installed", lambda *_: {})
    parent = QWidget()
    qtbot.addWidget(parent)
    calls = []

    def uninstall(package, display_name, dialog):
        calls.append((package, display_name, dialog))
        return True

    parent.uninstall_market_plugin = uninstall
    dialog = market.PluginMarketDialog("", parent)
    qtbot.addWidget(dialog)
    entry = parse_index(json.loads(INDEX))[0]
    row = market.MarketRow(entry, installed=InstalledPlugin(
        name="training_stats", directory=tmp_path, version=None,
        repository=entry.repository.url))
    dialog._rows = [row]
    dialog._populate()
    dialog.table.selectRow(0)
    assert dialog.uninstall.isEnabled()

    dialog.uninstall.click()

    assert calls == [(tmp_path, entry.name, dialog)]
    assert row.installed is None
    assert not dialog.uninstall.isEnabled()


def test_filtered_market_row_opens_same_details_from_button_and_double_click(qtbot, monkeypatch):
    from dataclasses import replace
    from PySide6.QtCore import Qt

    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    entry = parse_index(INDEX)[0]
    other = replace(entry, name="another plugin", description="different description")
    dialog = market.PluginMarketDialog("")
    qtbot.addWidget(dialog)
    dialog._rows = [market.MarketRow(entry), market.MarketRow(other)]
    dialog.search.setText("different")
    opened = []

    class Details:
        def __init__(self, row, parent):
            assert parent is dialog
            opened.append(row.entry)

        def exec(self):
            pass

        def deleteLater(self):
            pass

    monkeypatch.setattr(market, "_MarketDetailsDialog", Details)
    assert dialog.table.columnCount() == 5
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == other.name
    assert dialog.table.horizontalHeaderItem(4).text() == "详情"
    details = dialog.table.cellWidget(0, 4)
    assert details.text() == "查看详情"
    details.click()

    dialog.show()
    index = dialog.table.model().index(0, 0)
    point = dialog.table.visualRect(index).center()
    qtbot.mouseClick(dialog.table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qtbot.mouseDClick(dialog.table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert opened == [other, other]


@pytest.mark.parametrize("outcome", ["present", "missing", "error"])
def test_market_details_loads_repository_readme_asynchronously(qtbot, monkeypatch, outcome):
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QLabel

    entry = parse_index(INDEX)[0]
    main_thread = QThread.currentThread()
    calls = []

    def fetch_readme(self, repository):
        calls.append((repository, QThread.currentThread()))
        if outcome == "error":
            raise ValueError("offline")
        if outcome == "missing":
            return None
        return "# Repository README", repository.url + "/blob/HEAD/README.md"

    monkeypatch.setattr(market.PluginDownloader, "fetch_readme", fetch_readme)
    details = market._MarketDetailsDialog(market.MarketRow(entry))
    qtbot.addWidget(details)
    labels = [label.text() for label in details.findChildren(QLabel)]
    assert entry.description in labels
    assert entry.author in labels
    assert entry.repository.url in labels
    if outcome == "present":
        qtbot.waitUntil(lambda: "Repository README" in details._browser.toPlainText())
        assert details._readme_status.isHidden()
    else:
        expected = "offline" if outcome == "error" else "仓库中未找到 README"
        qtbot.waitUntil(lambda: expected in details._readme_status.text())
        assert details._browser.isHidden()
    assert len(calls) == 1
    assert calls[0][0] == entry.repository
    assert calls[0][1] != main_thread
    details.reject()
    assert details._cancel_readme.is_set()


def test_closing_market_details_cancels_pending_readme(qtbot, monkeypatch):
    from threading import Event

    entered, release, cancelled = Event(), Event(), Event()

    def fetch_readme(self, repository):
        entered.set()
        assert release.wait(5)
        try:
            self._check_cancelled()
        except market.DownloadCancelled:
            cancelled.set()
            raise
        return "# Late README", repository.url

    monkeypatch.setattr(market.PluginDownloader, "fetch_readme", fetch_readme)
    details = market._MarketDetailsDialog(market.MarketRow(parse_index(INDEX)[0]))
    qtbot.addWidget(details)
    details.show()
    try:
        qtbot.waitUntil(entered.is_set)
        details.reject()
        assert details.isHidden()
    finally:
        release.set()
    qtbot.waitUntil(cancelled.is_set)
    assert details._browser.toPlainText() == ""


@pytest.mark.parametrize(("locale", "expected"), [
    ("en_US", {
        "title": "Plugin Marketplace", "refresh": "Refresh",
        "filter": "All", "status": "Status", "close": "Close",
        "source_label": "GitHub topic: metasweeper-plugin",
    }),
    ("de_DE", {
        "title": "Plugin-Marktplatz", "refresh": "Aktualisieren",
        "filter": "Alle", "status": "Status", "close": "Schließen",
        "source_label": "GitHub-Thema: metasweeper-plugin",
    }),
    ("ja_JP", {
        "title": "プラグインマーケット", "refresh": "更新",
        "filter": "すべて", "status": "状態", "close": "閉じる",
        "source_label": "GitHub トピック: metasweeper-plugin",
    }),
    ("pl_PL", {
        "title": "Rynek wtyczek", "refresh": "Odśwież",
        "filter": "Wszystkie", "status": "Stan", "close": "Zamknij",
        "source_label": "Temat GitHub: metasweeper-plugin",
    }),
])
def test_market_dialog_uses_translated_catalog(qtbot, monkeypatch, tmp_path,
                                               locale, expected):
    from PySide6.QtCore import QTranslator
    from PySide6.QtWidgets import QApplication
    from tests.plugin_manager.test_menu_layout import find_lrelease
    import subprocess
    from pathlib import Path

    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    source = Path(__file__).resolve().parents[2] / "src" / "ui" / f"{locale}.ts"
    catalog = tmp_path / f"{locale}.qm"
    subprocess.run([str(find_lrelease()), str(source), "-qm", str(catalog)],
                   check=True, capture_output=True, text=True)
    translator = QTranslator()
    assert translator.load(str(catalog))
    app = QApplication.instance()
    app.installTranslator(translator)
    try:
        dialog = market.PluginMarketDialog("")
        qtbot.addWidget(dialog)
        assert dialog.windowTitle() == expected["title"]
        assert dialog.scan_button.text() == expected["refresh"]
        assert dialog.source_label.text() == expected["source_label"]
        assert [dialog.source.itemData(i) for i in range(dialog.source.count())] == [
            "github", "gitee",
        ]
        assert dialog.filter.itemText(0) == expected["filter"]
        assert dialog.table.horizontalHeaderItem(3).text() == expected["status"]
        dialog._show_snapshot(market.MarketSnapshot([market.MarketRow(parse_index(INDEX)[0])]))
        assert dialog.table.horizontalHeaderItem(4).text() == translator.translate("PluginMarketDialog", "详情")
        button = dialog.table.cellWidget(0, 4)
        label = translator.translate("PluginMarketDialog", "查看详情")
        assert label and label != "查看详情"
        assert button.text() == label
        button_box = dialog.findChild(market.QDialogButtonBox)
        assert button_box.button(
            market.QDialogButtonBox.StandardButton.Close).text() == expected["close"]
    finally:
        app.removeTranslator(translator)


def test_market_source_switch_restarts_discovery(qtbot, monkeypatch):
    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    dialog = market.PluginMarketDialog("")
    qtbot.addWidget(dialog)
    started = []
    monkeypatch.setattr(
        dialog, "_start_task",
        lambda index_url, target, version, source="github": started.append(source))

    dialog.source.setCurrentIndex(1)

    assert started == ["gitee"]
    assert dialog.source_label.text() == "Gitee 关键词：metasweeper"
    assert dialog.status.text() == "正在 Gitee 搜索插件并检查版本..."


def test_market_source_can_cancel_slow_scan_and_switch(qtbot, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    dialog = market.PluginMarketDialog("")
    qtbot.addWidget(dialog)
    interrupted = []
    started = []
    task = SimpleNamespace(
        target=None, error="", requestInterruption=lambda: interrupted.append(True),
        deleteLater=lambda: None)
    dialog._task = task
    monkeypatch.setattr(
        dialog, "_start_task",
        lambda index_url, target, version, source="github": started.append(source))

    dialog.source.setCurrentIndex(1)
    assert interrupted == [True]
    dialog._task_finished()

    assert started == ["gitee"]


def test_market_restores_last_source_before_first_scan(qtbot, monkeypatch, tmp_path):
    from plugin_manager.settings_manager import SettingsManager

    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    scans = []
    monkeypatch.setattr(market.PluginMarketDialog, "_start_task",
                        lambda self, *args, source: scans.append(source))
    dialog = market.PluginMarketDialog("", settings=SettingsManager(tmp_path))
    qtbot.addWidget(dialog)
    dialog.source.setCurrentIndex(dialog.source.findData("gitee"))
    dialog.reject()

    reopened = market.PluginMarketDialog("", settings=SettingsManager(tmp_path))
    qtbot.addWidget(reopened)
    reopened.start_scan()

    assert reopened.source.currentData() == "gitee"
    assert scans == ["gitee", "gitee"]


def test_market_restart_is_connected_to_window(qtbot, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from plugin_manager import main_window
    from plugin_manager.settings_manager import SettingsManager
    from tests.plugin_manager.test_cov_pm_e_helpers import shell

    connected = []
    calls = []
    window = shell(qtbot)
    window._settings_mgr = SettingsManager(tmp_path)
    monkeypatch.setattr(window, "restart_plugin_manager", lambda: calls.append("restart"))

    class Dialog:
        def __init__(self, index_url, parent, *, settings):
            assert settings is window._settings_mgr
            self.restart_requested = SimpleNamespace(connect=connected.append)
        def exec(self):
            connected[0]()
        def deleteLater(self):
            calls.append("closed")

    monkeypatch.setattr(main_window, "PluginMarketDialog", Dialog)
    window._open_plugin_market()
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


@pytest.mark.parametrize(("existing", "result", "restart"), [
    (False, "loaded", False), (False, "failed", False),
    (False, "restart", True), (True, "loaded", True),
])
def test_market_activation_and_completion_message(
        qtbot, monkeypatch, tmp_path, existing, result, restart):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QWidget

    monkeypatch.setattr(market.QTimer, "singleShot", lambda *_: None)
    parent = QWidget()
    qtbot.addWidget(parent)
    calls = []
    parent.activate_installed_package = lambda path: (calls.append(path) or result)
    dialog = market.PluginMarketDialog("", parent)
    qtbot.addWidget(dialog)
    entry = parse_index(json.loads(INDEX))[0]
    installed = InstalledPlugin(name=entry.name, directory=tmp_path) if existing else None
    dialog._task = SimpleNamespace(target=market.MarketRow(entry, installed=installed))
    dialog._show_installed(str(tmp_path))

    def choose(box):
        assert ("重启" in {item.text() for item in box.buttons()}) == restart
        if not existing and result == "failed":
            assert "加载失败" in box.text()
        next(item for item in box.buttons() if item.text() == "确认").click()
        return 0

    monkeypatch.setattr(market.QMessageBox, "exec", choose)
    dialog._show_install_complete()
    assert calls == ([] if existing else [tmp_path])


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


def test_tray_quit_runs_after_market_modal_loop_returns(qtbot, monkeypatch, tmp_path):
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
    from plugin_manager.settings_manager import SettingsManager
    window._settings_mgr = SettingsManager(tmp_path)
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


def test_update_from_mirror_preserves_existing_install_directory(tmp_path, monkeypatch):
    from plugin_manager.plugin_download import PluginDownloader

    github = PluginRepository.from_url(
        "https://github.com/ljzloser/metasweeper-history")
    gitee = PluginRepository.from_url(
        "https://gitee.com/Q1312358581/metasweeper-history")
    plugin_dir = tmp_path / "user_plugins"
    destination = plugin_dir / github.module_name
    destination.mkdir(parents=True)
    (destination / "__init__.py").write_text("old", encoding="utf-8")
    (destination / ".metasweeper-plugin.json").write_text(json.dumps({
        "repository": github.url, "platform": "github",
    }), encoding="utf-8")
    downloader = PluginDownloader(FakeSession(), lambda: False, lambda *_: None)

    def install_from_gitee(repository, tag, work, search_dirs, **kwargs):
        package = work / repository.module_name
        package.mkdir()
        (package / "__init__.py").write_text("new", encoding="utf-8")
        (package / ".metasweeper-plugin.json").write_text(json.dumps({
            "repository": repository.url, "platform": repository.platform,
        }), encoding="utf-8")
        return package

    monkeypatch.setattr(downloader, "install", install_from_gitee)
    updated = downloader.update(
        gitee, market.RepositoryTag("metasweeper-v1.1.0", "a" * 40),
        plugin_dir, destination_name=destination.name)

    assert updated == destination
    assert (destination / "__init__.py").read_text(encoding="utf-8") == "new"
    assert json.loads((destination / ".metasweeper-plugin.json").read_text(
        encoding="utf-8"))["repository"] == gitee.url


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
