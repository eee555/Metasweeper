"""Dependency inspection and loader integration, without a GUI or installation."""
from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugin_manager.dependency_scan import scan_plugin_dependencies
from plugin_manager.plugin_loader import PluginLoader
from plugin_manager.plugin_manager import PluginManager


def package(root: Path, name: str, requirements: str | None, source: str = "") -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    module = directory / "__init__.py"
    module.write_text(source, encoding="utf-8")
    if requirements is not None:
        (directory / "requirements.txt").write_text(requirements, encoding="utf-8")
    return module


def test_requirements_diagnostics_and_markers(tmp_path, monkeypatch):
    module = package(tmp_path, "demo", """\
# comment
present>=1,<3  # supported
present>=3
absent>=1
present; python_version < '1'
present[extra]>=1
-r other.txt
invalid !!!
present @ https://example.invalid/package.whl
""")

    def version(name):
        if name == "absent":
            raise metadata.PackageNotFoundError(name)
        return "2.1"

    monkeypatch.setattr(metadata, "version", version)
    result = scan_plugin_dependencies(module, "demo")
    assert result.requirements_path == module.parent / "requirements.txt"
    assert result.status == "unknown"
    assert [item.status for item in result.diagnostics] == [
        "satisfied", "conflict", "missing", "skipped", "unknown", "unknown", "unknown", "unknown"
    ]
    assert result.diagnostics[0].installed_version == "2.1"
    assert result.diagnostics[0].line == 2
    assert result.import_status == "not_attempted"


@pytest.mark.parametrize(("requirements", "expected"), [
    ("", "no_requirements"),
    ("demo>=1", "satisfied"),
    ("demo>=3", "conflict"),
    ("missing", "missing"),
])
def test_overall_status(tmp_path, monkeypatch, requirements, expected):
    module = package(tmp_path, "demo", requirements)
    def version(name):
        if name == "missing":
            raise metadata.PackageNotFoundError(name)
        return "2.0"
    monkeypatch.setattr(metadata, "version", version)
    assert scan_plugin_dependencies(module, "demo").status == expected


def test_missing_file_single_file_and_unreadable_file(tmp_path):
    module = package(tmp_path, "demo", None)
    result = scan_plugin_dependencies(module, "demo")
    assert result.status == "no_requirements"
    assert result.requirements_path == module.parent / "requirements.txt"
    assert scan_plugin_dependencies(tmp_path / "single.py", "single").requirements_path is None
    (module.parent / "requirements.txt").write_bytes(b"\xff")
    result = scan_plugin_dependencies(module, "demo")
    assert result.status == "unknown"
    assert result.diagnostics[0].line == 0


def test_distribution_metadata_in_plugin_library_path(tmp_path, monkeypatch):
    module = package(tmp_path, "demo", "meta-scan-example>=2,<3")
    library = tmp_path / "plugin-library"
    info = library / "meta_scan_example-2.4.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: meta-scan-example\nVersion: 2.4\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(library))
    result = scan_plugin_dependencies(module, "demo")
    assert result.status == "satisfied"
    assert result.diagnostics[0].installed_version == "2.4"


def test_packaged_missing_metadata_is_unknown(tmp_path, monkeypatch):
    module = package(tmp_path, "demo", "missing")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    def missing(name):
        raise metadata.PackageNotFoundError(name)
    monkeypatch.setattr(metadata, "version", missing)
    assert scan_plugin_dependencies(module, "demo").diagnostics[0].status == "unknown"


def test_scan_all_before_any_import_and_expose_failed_module(tmp_path, monkeypatch):
    root = tmp_path / "plugins"
    root.mkdir()
    package(root, "dep_scan_good", "demo>=1", "VALUE = 1")
    bad = package(root, "dep_scan_bad", "missing", "raise ImportError('broken plugin')")
    observed = []
    def version(name):
        observed.append(name)
        if name == "missing":
            raise metadata.PackageNotFoundError(name)
        return "2.0"
    monkeypatch.setattr(metadata, "version", version)
    loader = PluginLoader([root])
    original_load = loader.load_module
    def load(path, name):
        assert set(observed) == {"demo", "missing"}
        return original_load(path, name)
    monkeypatch.setattr(loader, "load_module", load)
    monkeypatch.delitem(sys.modules, "dep_scan_good", raising=False)
    monkeypatch.delitem(sys.modules, "dep_scan_bad", raising=False)
    loader.load_all()
    assert loader.get_module_dependency_status("dep_scan_good").import_status == "loaded"
    result = loader.get_module_dependency_status("dep_scan_bad")
    assert result.module_path == bad
    assert result.import_status == "failed"
    assert "broken plugin" in result.import_error
    assert result.diagnostics[0].status == "missing"
    assert loader.get_module_dependency_status("absent") is None
    statuses = loader.module_dependency_statuses
    statuses.clear()
    assert len(loader.module_dependency_statuses) == 2
    sys.modules.pop("dep_scan_good", None)


def test_manager_plugin_name_mapping_and_multiple_classes(tmp_path, monkeypatch):
    root = tmp_path / "plugins"
    root.mkdir()
    module = package(root, "dep_scan_mapping", "", "VALUE = 1")
    loader = PluginLoader([root])
    monkeypatch.delitem(sys.modules, "dep_scan_mapping", raising=False)

    class FakePlugin:
        def __init__(self, info):
            self.name = info.name
    first = type("First", (FakePlugin,), {})
    second = type("Second", (FakePlugin,), {})
    monkeypatch.setattr(loader, "get_plugin_classes", lambda _: [first, second])
    monkeypatch.setattr(loader, "_get_plugin_info", lambda cls: SimpleNamespace(name=cls.__name__))
    loader.load_all()
    manager = PluginManager.__new__(PluginManager)
    manager._loader = loader
    assert manager.get_plugin_dependency_status("First") == manager.get_plugin_dependency_status("Second")
    assert manager.get_plugin_dependency_status("First").module_path == module
    assert manager.get_module_dependency_status("dep_scan_mapping").import_status == "loaded"
    assert manager.get_plugin_dependency_status("not-loaded") is None
    assert "dep_scan_mapping" in manager.module_dependency_statuses
    sys.modules.pop("dep_scan_mapping", None)


def test_direct_load_scans_before_execution(tmp_path, monkeypatch):
    module = package(tmp_path, "dep_scan_direct", "demo", "raise RuntimeError('failed')")
    seen = []
    monkeypatch.setattr(metadata, "version", lambda name: seen.append(name) or "1.0")
    monkeypatch.delitem(sys.modules, "dep_scan_direct", raising=False)
    loader = PluginLoader()
    assert loader.load_module(module, "dep_scan_direct") is None
    assert seen == ["demo"]
    assert loader.get_module_dependency_status("dep_scan_direct").import_status == "failed"
