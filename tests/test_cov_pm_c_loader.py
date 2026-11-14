"""Coverage tests for plugin_manager.plugin_loader using real temp plugin packages."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from plugin_manager.plugin_loader import PluginLoader
from plugin_sdk.plugin_base import BasePlugin


PLUGIN_SOURCE = """\
from plugin_sdk.plugin_base import BasePlugin, PluginInfo

class Sample(BasePlugin):
    @classmethod
    def plugin_info(cls):
        return PluginInfo(name="sample-{name}")

class Second(BasePlugin):
    @classmethod
    def plugin_info(cls):
        return PluginInfo(name="second-{name}")
"""


@pytest.fixture(autouse=True)
def offline_plugin(monkeypatch, tmp_path):
    """Keep plug-in construction away from the repo's real data directory."""
    import plugin_manager.app_paths as app_paths
    import plugin_manager.logging_setup as logging_setup
    from loguru import logger

    def plugin_data_dir(cls):
        return tmp_path / "plugin_data" / cls.__name__

    monkeypatch.setattr(app_paths, "get_plugin_data_dir", plugin_data_dir)
    monkeypatch.setattr(logging_setup, "get_plugin_logger",
                        lambda *a, **k: (logger, 0))
    monkeypatch.setattr(logging_setup, "set_plugin_log_level",
                        lambda *a, **k: None)


@pytest.fixture
def clean_sys_path(monkeypatch):
    original = list(sys.path)
    yield
    sys.path[:] = original


def make_package(root: Path, name: str) -> Path:
    pkg = root / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        PLUGIN_SOURCE.format(name=name), encoding="utf-8")
    return pkg


def unique_module(name: str, monkeypatch) -> str:
    """Return a module name that cannot collide with an already imported module."""
    candidate = f"_cov_pm_c_{name}_{id(monkeypatch)}"
    monkeypatch.delitem(sys.modules, candidate, raising=False)
    return candidate


def test_init_registers_existing_dirs_and_parent_in_sys_path(tmp_path, monkeypatch, clean_sys_path):
    parent = tmp_path / "plugins"
    first = parent / "one"
    second = parent / "two"
    first.mkdir(parents=True)
    second.mkdir()
    monkeypatch.delitem(sys.modules, "_cov_pm_c_init", raising=False)

    loader = PluginLoader([first, second, tmp_path / "absent"])

    assert loader._plugin_dirs == [first, second]
    assert str(parent) in sys.path
    assert loader._added_paths == {parent}
    assert loader.discover_plugins() == []
    loader.add_plugin_dir(second)
    assert loader._added_paths == {parent}


def test_add_plugin_dir_rejects_missing_and_adds_new_parent(tmp_path, clean_sys_path):
    loader = PluginLoader()
    missing = tmp_path / "missing"
    loader.add_plugin_dir(missing)
    assert loader._plugin_dirs == []

    other = tmp_path / "other" / "plugins"
    other.mkdir(parents=True)
    loader.add_plugin_dir(str(other))
    assert str(other.parent) in sys.path
    assert loader._plugin_dirs == [other]


def test_discover_plugins_skips_hidden_services_and_underscore_files(tmp_path):
    root = tmp_path / "plugins"
    root.mkdir()
    make_package(root, "alpha")
    make_package(root, "beta")
    (root / "services").mkdir()
    (root / "services" / "__init__.py").write_text("", encoding="utf-8")
    (root / "_hidden").mkdir()
    (root / "_hidden" / "__init__.py").write_text("", encoding="utf-8")
    (root / "__hidden_pkg").mkdir()
    (root / "__hidden_pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "single.py").write_text("", encoding="utf-8")
    (root / "_private.py").write_text("", encoding="utf-8")
    (root / "not_plugin").mkdir()

    discovered = PluginLoader([root]).discover_plugins()

    assert discovered == [
        (root / "single.py", "single"),
        (root / "alpha" / "__init__.py", "alpha"),
        (root / "beta" / "__init__.py", "beta"),
    ]


def test_discover_plugins_multiple_dirs_and_missing_dir(tmp_path):
    one, two, deleted = tmp_path / "one", tmp_path / "two", tmp_path / "gone"
    one.mkdir()
    deleted.mkdir()
    make_package(one, "pkg_one")
    loader = PluginLoader([one, deleted])
    make_package(two, "pkg_two")
    loader.add_plugin_dir(two)
    deleted.rmdir()
    assert loader.discover_plugins() == [
        (one / "pkg_one" / "__init__.py", "pkg_one"),
        (two / "pkg_two" / "__init__.py", "pkg_two"),
    ]


def test_load_module_success_and_sys_modules_cache(tmp_path, monkeypatch):
    pkg = make_package(tmp_path, "loaded")
    name = unique_module("loaded", monkeypatch)
    loader = PluginLoader()

    module = loader.load_module(pkg / "__init__.py", name)

    assert module is sys.modules[name]
    assert hasattr(module, "Sample")
    assert loader.load_module(pkg / "__init__.py", name) is module
    monkeypatch.delitem(sys.modules, name, raising=False)


def test_load_module_returns_none_for_missing_file(tmp_path, monkeypatch):
    name = unique_module("absent", monkeypatch)
    assert PluginLoader().load_module(tmp_path / "absent.py", name) is None
    monkeypatch.delitem(sys.modules, name, raising=False)


def test_load_module_returns_none_when_spec_has_no_loader(tmp_path, monkeypatch):
    name = unique_module("nospec", monkeypatch)
    empty_spec = importlib.util.spec_from_loader(name, loader=None)
    monkeypatch.setattr(importlib.util, "spec_from_file_location",
                        lambda *a, **k: empty_spec)
    assert PluginLoader().load_module(tmp_path / "x.py", name) is None
    monkeypatch.delitem(sys.modules, name, raising=False)


def test_load_module_returns_none_on_syntax_error(tmp_path, monkeypatch):
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n    pass\n", encoding="utf-8")
    name = unique_module("bad", monkeypatch)
    assert PluginLoader().load_module(bad, name) is None
    monkeypatch.delitem(sys.modules, name, raising=False)


def test_get_plugin_classes_filters_base_imported_private_and_unrelated(monkeypatch):
    module = ModuleType("fake_plugin_module")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    module.BasePlugin = BasePlugin
    module._PrivatePlugin = type("_PrivatePlugin", (BasePlugin,), {})
    module.NotAPlugin = object()
    module.value = 42
    imported = type("ImportedPlugin", (BasePlugin,), {"__module__": "elsewhere"})
    module.ImportedPlugin = imported
    local = type("LocalPlugin", (BasePlugin,), {"__module__": module.__name__})
    module.LocalPlugin = local

    assert PluginLoader().get_plugin_classes(module) == [imported, local]
    assert PluginLoader().get_plugin_classes(SimpleNamespace()) == []


def test_load_plugins_from_module_success_and_get_plugin_info(tmp_path, monkeypatch):
    pkg = make_package(tmp_path, "instances")
    name = unique_module("instances", monkeypatch)
    loader = PluginLoader()
    assert loader._get_plugin_info.__name__ == "_get_plugin_info"

    plugins = loader.load_plugins_from_module(pkg / "__init__.py", name)

    assert {p.name for p in plugins} == {"sample-instances", "second-instances"}
    assert all(isinstance(p, BasePlugin) for p in plugins)
    monkeypatch.delitem(sys.modules, name, raising=False)
    for plugin in plugins:
        plugin.shutdown()


def test_load_plugins_from_module_returns_empty_when_module_fails(tmp_path, monkeypatch):
    name = unique_module("broken_module", monkeypatch)
    assert PluginLoader().load_plugins_from_module(tmp_path / "no.py", name) == []
    monkeypatch.delitem(sys.modules, name, raising=False)


def test_load_plugins_from_module_skips_classes_without_plugin_info(monkeypatch):
    module = ModuleType("no_info_module")
    monkeypatch.setitem(sys.modules, module.__name__, module)

    class NoInfo(BasePlugin):
        pass

    module.NoInfo = NoInfo
    loader = PluginLoader()
    monkeypatch.setattr(loader, "load_module", lambda *a: module)

    assert loader.load_plugins_from_module(Path("unused"), module.__name__) == []


def test_load_plugins_from_module_skips_instantiation_exception(monkeypatch):
    module = ModuleType("raising_module")
    monkeypatch.setitem(sys.modules, module.__name__, module)

    class Broken(BasePlugin):
        @classmethod
        def plugin_info(cls):
            raise RuntimeError("no metadata")

    module.Broken = Broken
    loader = PluginLoader()
    monkeypatch.setattr(loader, "load_module", lambda *a: module)

    assert loader.load_plugins_from_module(Path("unused"), module.__name__) == []


def test_load_plugins_from_module_skips_raising_class_instantiation(monkeypatch):
    module = ModuleType("bad_init_module")
    monkeypatch.setitem(sys.modules, module.__name__, module)

    class BadInit(BasePlugin):
        @classmethod
        def plugin_info(cls):
            from plugin_sdk.plugin_base import PluginInfo
            return PluginInfo(name="bad-init")

        def __init__(self, info):
            raise RuntimeError("cannot construct")

    module.BadInit = BadInit
    loader = PluginLoader()
    monkeypatch.setattr(loader, "load_module", lambda *a: module)

    assert loader.load_plugins_from_module(Path("unused"), module.__name__) == []


def test_load_all_loads_every_discovered_plugin(tmp_path, monkeypatch):
    root = tmp_path / "plugins"
    root.mkdir()
    make_package(root, "one")
    make_package(root, "two")
    (root / "plain.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    modules = []
    monkeypatch.setattr(PluginLoader, "load_module", lambda self, path, name: (
        modules.append((path, name)), None)[1])

    assert PluginLoader([root]).load_all() == []
    assert [name for _, name in modules] == ["plain", "one", "two"]


def test_reload_module_existing_and_missing(monkeypatch):
    name = unique_module("reload", monkeypatch)
    loader = PluginLoader()
    assert loader.reload_module(name) is False

    module = ModuleType(name)
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(importlib, "reload", lambda value: value)
    assert loader.reload_module(name) is True

    monkeypatch.setattr(importlib, "reload",
                        lambda value: (_ for _ in ()).throw(RuntimeError("reload failed")))
    assert loader.reload_module(name) is False
