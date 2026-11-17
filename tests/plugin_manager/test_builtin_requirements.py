"""Audit built-in dependency manifests and their packaged resource locations."""
from __future__ import annotations

import ast
import re
import runpy
import shutil
import sys
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from plugin_manager import app_paths, dependency_scan
from plugin_manager.plugin_loader import PluginLoader

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / "src" / "plugins"
PACKAGES = sorted(
    path for path in PLUGINS.iterdir()
    if path.is_dir() and (path / "__init__.py").is_file()
    and not path.name.startswith("_") and path.name != "services"
)
DISTRIBUTIONS = {
    "PySide6": "pyside6", "ms_toollib": "ms-toollib", "msgspec": "msgspec", "zmq": "pyzmq",
}


def requirements(path: Path) -> list[Requirement]:
    return [Requirement(line) for raw in path.read_text(encoding="utf-8-sig").splitlines()
            if (line := raw.strip()) and not line.startswith("#")]


class RuntimeImports(ast.NodeVisitor):
    """Include lazy feature imports but exclude annotation-only dependencies."""
    def __init__(self):
        self.names: set[str] = set()

    def visit_If(self, node):
        test = node.test
        type_checking = (
            isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
            or isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if type_checking:
            for child in node.orelse:
                self.visit(child)
        else:
            self.generic_visit(node)

    def visit_Import(self, node):
        self.names.update(alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node):
        if not node.level and node.module:
            self.names.add(node.module.split(".")[0])


@pytest.mark.parametrize("package", PACKAGES, ids=lambda path: path.name)
def test_manifest_covers_direct_runtime_imports_only(package):
    imports = RuntimeImports()
    for source in package.rglob("*.py"):
        imports.visit(ast.parse(source.read_text(encoding="utf-8-sig")))
    local = {path.stem for path in (ROOT / "src").iterdir()}
    third_party = imports.names - sys.stdlib_module_names - local
    assert third_party <= DISTRIBUTIONS.keys(), f"Audit new third-party imports: {third_party - DISTRIBUTIONS.keys()}"
    declared = requirements(package / "requirements.txt")
    names = [canonicalize_name(req.name) for req in declared]
    provided = {canonicalize_name(req.name) for req in requirements(ROOT / "requirements.txt")}
    expected_extras = {
        DISTRIBUTIONS[name] for name in third_party
        if DISTRIBUTIONS[name] not in provided
    }
    assert set(names) == expected_extras
    assert len(names) == len(set(names))
    # requirements.txt is only for packages absent from the application's own environment.


@pytest.mark.parametrize("kind", ["pyinstaller", "nuitka"])
def test_frozen_manifests_remain_discoverable_without_metadata(tmp_path, monkeypatch, kind):
    bundle = tmp_path / "bundle"
    target = bundle / ("internal/plugins" if kind == "nuitka" else "plugins")
    for package in PACKAGES:
        destination = target / package.name
        destination.mkdir(parents=True)
        for name in ("__init__.py", "requirements.txt"):
            shutil.copy2(package / name, destination / name)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(sys, "executable", str(bundle / "plugin_manager.exe"))
    monkeypatch.delattr(app_paths, "__compiled__", raising=False)
    monkeypatch.delattr(dependency_scan, "__compiled__", raising=False)
    if kind == "nuitka":
        monkeypatch.setattr(app_paths, "__compiled__", object(), raising=False)
        monkeypatch.setattr(dependency_scan, "__compiled__", object(), raising=False)
        monkeypatch.delattr(sys, "frozen", raising=False)
    else:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    def absent(name):
        raise metadata.PackageNotFoundError(name)
    monkeypatch.setattr(metadata, "version", absent)
    dirs = app_paths.get_builtin_plugin_dirs()
    assert dirs == [target]
    discovered = PluginLoader(dirs).discover_plugins()
    assert {name for _, name in discovered} == {package.name for package in PACKAGES}
    for path, name in discovered:
        result = dependency_scan.scan_plugin_dependencies(path, name)
        assert result.requirements_path == target / name / "requirements.txt"
        assert result.status == "no_requirements"
        assert result.diagnostics == ()
        assert result.import_status == "not_attempted"


def assert_pyinstaller_collects_manifests(datas):
    # Exercise PyInstaller's real recursive data expansion without compiling apps.
    # Build tooling is optional in ordinary development/test environments.
    utils = pytest.importorskip("PyInstaller.building.utils")
    collected = utils.format_binaries_and_datas(datas, workingdir=str(ROOT))
    destinations = {Path(destination).as_posix() for destination, _source in collected}
    for package in PACKAGES:
        assert f"plugins/{package.name}/requirements.txt" in destinations


@pytest.mark.parametrize("script", ["build.bat", ".github/workflows/python-app.yml"])
def test_windows_pyinstaller_data_rules_include_manifests(script):
    text = (ROOT / script).read_text(encoding="utf-8-sig")
    manager = text[text.index("--name plugin_manager"):]
    rules = re.findall(r'--add-data\s+"(src/plugins);(plugins)"', manager)
    assert rules
    assert_pyinstaller_collects_manifests(rules)


def test_macos_pyinstaller_data_rules_include_manifests():
    captured = {}
    def analysis(*_args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])
    def no_build(*_args, **_kwargs):
        return None
    spec = ROOT / "package_tool" / "macos" / "plugin_manager_mac.spec"
    runpy.run_path(str(spec), init_globals={
        "SPECPATH": str(spec.parent), "Analysis": analysis,
        "PYZ": no_build, "EXE": no_build, "COLLECT": no_build, "BUNDLE": no_build,
    })
    rules = [(source, destination) for source, destination in captured["datas"]
             if Path(source).resolve() == PLUGINS.resolve()]
    assert rules
    assert_pyinstaller_collects_manifests(rules)


def test_nuitka_copies_plugin_tree_including_manifests():
    text = (ROOT / "package_tool" / "build_nuitka_main.bat").read_text(encoding="utf-8-sig")
    assert "--include-data-dir=src\\plugins=internal/plugins" in text
    # Nuitka excludes Python sources from data-dir processing, so the final
    # recursive copy supplies both sources and requirements beside each other.
    assert re.search(
        r'xcopy /e /i /y /h "src\\plugins\\\*" "%PACKAGE_DIR%\\internal\\plugins\\"', text)
