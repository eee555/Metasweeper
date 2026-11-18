"""插件索引、版本解析与更新判定的单元测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugin_manager.plugin_catalog import (
    CatalogError, InstalledPlugin, PluginRelease, parse_index,
    parse_tag_version, rank_versions, read_installed_metadata, scan_installed,
)


def _entry_payload(**overrides):
    item = {
        "name": "training_stats",
        "repository": "https://github.com/example/metasweeper-training-stats",
        "description": "训练统计",
        "author": "example",
    }
    item.update(overrides)
    return item


def test_parse_index_basic_and_defaults():
    entries = parse_index({"schema_version": 1, "plugins": [_entry_payload()]})
    assert len(entries) == 1
    entry = entries[0]
    assert entry.name == "training_stats"
    assert entry.repository.url == (
        "https://github.com/example/metasweeper-training-stats")
    assert entry.tag_prefix == "metasweeper-v"


def test_parse_index_accepts_json_text_and_custom_prefix():
    payload = json.dumps({
        "schema_version": 1,
        "plugins": [_entry_payload(tag_prefix="plugin-")],
    })
    entries = parse_index(payload)
    assert entries[0].tag_prefix == "plugin-"


def test_parse_index_rejects_future_schema_and_bad_json():
    with pytest.raises(CatalogError):
        parse_index({"schema_version": 99, "plugins": []})
    with pytest.raises(CatalogError):
        parse_index("{not json")


def test_parse_index_skips_invalid_and_duplicate_entries():
    payload = {
        "schema_version": 1,
        "plugins": [
            _entry_payload(),
            _entry_payload(),  # 同名重复
            {"name": "broken", "repository": "ftp://example.com/x"},
            "not-a-dict",
            {"repository": "https://github.com/example/no-name"},
        ],
    }
    entries = parse_index(payload)
    assert [entry.name for entry in entries] == ["training_stats", "no-name"]


@pytest.mark.parametrize("tag,expected", [
    ("metasweeper-v1.2.3", "1.2.3"),
    ("v2.0.0", "2.0.0"),
    ("1.0", "1.0"),
    ("metasweeper-v1.2.3-beta", None),
    ("nightly", None),
    ("", None),
])
def test_parse_tag_version(tag, expected):
    version = parse_tag_version(tag)
    assert (str(version) if version is not None else None) == expected


def test_rank_versions_sorts_descending_and_filters_noise():
    entries = parse_index({"schema_version": 1, "plugins": [_entry_payload()]})
    entry = entries[0]
    ranked = rank_versions(entry, [
        ("metasweeper-v1.2.3", "a" * 40),
        ("metasweeper-v1.10.0", "b" * 40),
        ("docs-update", "c" * 40),
    ])
    assert [str(item[0]) for item in ranked] == ["1.10.0", "1.2.3"]
    assert ranked[0][1] == "metasweeper-v1.10.0"


def _write_plugin(root: Path, name: str, metadata: dict | None) -> Path:
    package = root / name
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    if metadata is not None:
        (package / ".metasweeper-plugin.json").write_text(
            json.dumps(metadata), encoding="utf-8")
    return package


def test_scan_installed_reads_market_metadata(tmp_path):
    _write_plugin(tmp_path, "with_meta", {
        "repository": "https://github.com/example/x",
        "tag": "metasweeper-v1.4.0",
        "platform": "github",
        "version": "1.4.0",
    })
    _write_plugin(tmp_path, "manual_copy", None)

    installed = scan_installed([tmp_path])
    assert set(installed) == {"https://github.com/example/x"}
    assert str(installed["https://github.com/example/x"].version) == "1.4.0"
    assert installed["https://github.com/example/x"].repository == "https://github.com/example/x"


def test_scan_installed_derives_version_from_tag(tmp_path):
    _write_plugin(tmp_path, "tag_only", {
        "repository": "https://github.com/example/y",
        "tag": "metasweeper-v0.9.1",
    })
    installed = scan_installed([tmp_path])
    assert str(installed["https://github.com/example/y"].version) == "0.9.1"


def test_read_installed_metadata_tolerates_broken_json(tmp_path):
    package = tmp_path / "broken"
    package.mkdir()
    (package / ".metasweeper-plugin.json").write_text("{oops", encoding="utf-8")
    assert read_installed_metadata(package) == {}


def test_update_available_comparison():
    entry = parse_index({"schema_version": 1, "plugins": [_entry_payload()]})[0]
    releases = PluginRelease(entry, rank_versions(entry, [
        ("metasweeper-v1.5.0", "a" * 40),
    ]))
    current = InstalledPlugin(
        name="training_stats", directory=Path("."),
        version=parse_tag_version("metasweeper-v1.4.0"))
    same = InstalledPlugin(
        name="training_stats", directory=Path("."),
        version=parse_tag_version("metasweeper-v1.5.0"))
    unknown = InstalledPlugin(name="training_stats", directory=Path("."))

    assert current.update_available(releases) is True
    assert same.update_available(releases) is False
    # 版本未知时不臆测可更新
    assert unknown.update_available(releases) is False
    assert releases.latest_version == parse_tag_version("1.5.0")
