from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from plugin_manager.plugin_data_transfer import export_plugins, import_plugins
from plugin_sdk.data_archive import DataArchiveError, export_directory, import_directory


class TransferPlugin:
    def __init__(self, name: str, archive: bytes, *, fail_export: bool = False):
        self.name = name
        self.archive = archive
        self.fail_export = fail_export
        self.imported: bytes | None = None
        self.hook_calls: list[str] = []

    def call_in_plugin_thread(self, func, *args):
        self.hook_calls.append(func.__name__)
        return func(*args)

    def export_data(self) -> bytes:
        if self.fail_export:
            raise RuntimeError("export failed")
        return self.archive

    def import_data(self, archive: bytes) -> None:
        self.imported = archive


def _zip_file(name: str, data: bytes) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(name, data)
    return output.getvalue()


def test_default_directory_archive_round_trips_and_merges(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "nested").mkdir(parents=True)
    (source / "nested" / "record.json").write_text('{"ok":true}', encoding="utf-8")
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")

    import_directory(target, export_directory(source))

    assert (target / "nested" / "record.json").read_text(encoding="utf-8") == '{"ok":true}'
    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_default_import_rejects_zip_slip_without_writing_outside(tmp_path):
    target = tmp_path / "plugin-data"
    outside = tmp_path / "escaped.txt"
    malicious = _zip_file("../escaped.txt", b"no")

    with pytest.raises(DataArchiveError):
        import_directory(target, malicious)

    assert not outside.exists()
    assert not target.exists()


def test_manager_export_aggregates_plugins_and_reports_individual_errors(tmp_path):
    first_archive = _zip_file("state.json", b"first")
    second_archive = _zip_file("state.json", b"second")
    plugins = {
        "first": TransferPlugin("first", first_archive),
        "second": TransferPlugin("second", second_archive),
        "broken": TransferPlugin("broken", b"", fail_export=True),
    }
    output = tmp_path / "all-plugin-data.zip"

    result = export_plugins(plugins, output)

    assert result.succeeded == ["first", "second"]
    assert "broken" in result.failed
    with ZipFile(output) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert [item["name"] for item in manifest["plugins"]] == ["first", "second"]
        assert archive.read("plugins/first.zip") == first_archive
        assert archive.read("plugins/second.zip") == second_archive


def test_manager_import_dispatches_custom_hooks_and_skips_unknown_plugins(tmp_path):
    first_archive = _zip_file("state.json", b"first backup")
    output = tmp_path / "all-plugin-data.zip"
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("plugins/first.zip", first_archive)
        archive.writestr("manifest.json", json.dumps({
            "format": "metasweeper-plugin-data",
            "version": 1,
            "plugins": [
                {"name": "first", "archive": "plugins/first.zip"},
                {"name": "removed-plugin", "archive": "plugins/removed-plugin.zip"},
            ],
        }))
    plugin = TransferPlugin("first", b"")

    result = import_plugins({"first": plugin}, output)

    assert result.succeeded == ["first"]
    assert result.skipped == ["removed-plugin"]
    assert plugin.imported == first_archive
    assert plugin.hook_calls == ["import_data"]


def test_manager_rejects_unknown_or_unsafe_manifest(tmp_path):
    output = tmp_path / "bad.zip"
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({
            "format": "other", "version": 1, "plugins": [],
        }))

    with pytest.raises(ValueError, match="不支持"):
        import_plugins({}, output)
