from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugin_manager import plugin_lib_env, plugin_uninstall


@pytest.fixture
def environment(tmp_path, monkeypatch):
    root = tmp_path / "user_plugins"
    library = tmp_path / "plugin_libs"
    root.mkdir()
    library.mkdir()
    monkeypatch.setattr(plugin_uninstall, "get_executable_dir", lambda: tmp_path)
    monkeypatch.setattr(plugin_uninstall, "get_all_plugin_dirs", lambda: [root])
    monkeypatch.setattr(plugin_lib_env, "_ensure_environment",
                        lambda *_: (library, Path("python"), True))
    return tmp_path, root, library


def plugin(root, name, requirements):
    package = root / name
    package.mkdir()
    (package / "__init__.py").touch()
    (package / "requirements.txt").write_text(requirements, encoding="utf-8")
    (package / plugin_uninstall.META_FILENAME).write_text(
        json.dumps({"repository": f"https://github.com/example/{name}", "version": "1.0"}),
        encoding="utf-8")
    return package


def distribution(library, name, requires=()):
    stem = name.replace("-", "_")
    module = library / f"{stem}.py"
    module.write_text("# package", encoding="utf-8")
    info = library / f"{stem}-1.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n"
        + "".join(f"Requires-Dist: {req}\n" for req in requires), encoding="utf-8")
    (info / "RECORD").write_text(
        f"{module.name},,\n{info.name}/METADATA,,\n{info.name}/RECORD,,\n",
        encoding="utf-8")
    return module


def test_removes_exclusive_dependencies_and_preserves_shared_and_data(environment):
    data_dir, root, library = environment
    first = plugin(root, "first", "exclusive\nshared\nexisting")
    second = plugin(root, "second", "shared")
    saved = data_dir / "plugin_data" / "first"
    saved.mkdir(parents=True)
    data_file = saved / "history.db"
    data_file.write_bytes(b"retained")
    existing = distribution(library, "existing")
    before = plugin_uninstall.installed_fingerprints(library)
    exclusive = distribution(library, "exclusive", ["leaf"])
    leaf = distribution(library, "leaf")
    shared = distribution(library, "shared")
    plugin_uninstall.record_install(data_dir, library, before)

    plan = plugin_uninstall.plan_removal(first, data_dir)
    assert plan.packages == (("exclusive", "1.0"), ("leaf", "1.0"))
    assert plan.kept == ("existing", "shared")
    plugin_uninstall.remove_plugin(plan, data_dir)
    assert not first.exists()
    assert not exclusive.exists() and not leaf.exists()
    assert second.exists() and shared.exists() and existing.exists()
    assert data_file.read_bytes() == b"retained"

    plugin_uninstall.remove_plugin(plugin_uninstall.plan_removal(second, data_dir), data_dir)
    assert not shared.exists()
    assert existing.exists()


def test_failed_removal_restores_plugin_and_dependency_files(environment, monkeypatch):
    data_dir, root, library = environment
    package = plugin(root, "first", "exclusive")
    module = distribution(library, "exclusive")
    plugin_uninstall.record_install(data_dir, library, {})
    plan = plugin_uninstall.plan_removal(package, data_dir)
    rename = Path.rename

    def fail_plugin_move(source, target):
        if source == package:
            raise PermissionError("file in use")
        return rename(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", fail_plugin_move)
        with pytest.raises(PermissionError, match="file in use"):
            plugin_uninstall.remove_plugin(plan, data_dir)
    assert module.exists() and package.exists()
    assert plugin_uninstall.plan_removal(package, data_dir) == plan

    plugin_uninstall.queue_removal(plan, data_dir)
    assert plugin_uninstall.apply_queued_removal(data_dir) == ""
    assert not package.exists() and not module.exists()


def test_unmanaged_and_stale_plans_are_rejected(environment):
    data_dir, root, library = environment
    package = plugin(root, "first", "exclusive")
    manual = root / "manual"
    manual.mkdir()
    with pytest.raises(ValueError):
        plugin_uninstall.plan_removal(manual, data_dir)
    module = distribution(library, "exclusive")
    plugin_uninstall.record_install(data_dir, library, {})
    plan = plugin_uninstall.plan_removal(package, data_dir)
    plugin(root, "consumer", "exclusive")
    with pytest.raises(RuntimeError):
        plugin_uninstall.remove_plugin(plan, data_dir)
    assert package.exists() and module.exists()


def test_install_records_ownership_and_reinstall_restores_dependencies(environment, monkeypatch):
    data_dir, root, library = environment
    pkg = plugin(root, "first", "exclusive")
    settings = data_dir / "plugin_data" / "first.json"
    settings.parent.mkdir()
    settings.write_text("old settings", encoding="utf-8")

    def install(*_):
        distribution(library, "exclusive", ["leaf"])
        distribution(library, "leaf")
        return None

    monkeypatch.setattr(plugin_lib_env, "_append_import_path", lambda *_: None)
    monkeypatch.setattr(plugin_lib_env, "_run_install", install)
    assert plugin_lib_env.install_plugin_requirements(data_dir, pkg / "requirements.txt") is None
    plan = plugin_uninstall.plan_removal(pkg, data_dir)
    assert {name for name, _ in plan.packages} == {"exclusive", "leaf"}
    plugin_uninstall.remove_plugin(plan, data_dir)
    assert plugin_uninstall.installed_fingerprints(library) == {}

    pkg = plugin(root, "first", "exclusive")
    assert plugin_lib_env.install_plugin_requirements(data_dir, pkg / "requirements.txt") is None
    assert set(plugin_uninstall.installed_fingerprints(library)) == {"exclusive", "leaf"}
    assert settings.read_text(encoding="utf-8") == "old settings"
