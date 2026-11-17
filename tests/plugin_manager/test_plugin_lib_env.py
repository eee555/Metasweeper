"""plugin_lib_env 覆盖：目录解析、虚拟环境识别、自动创建与 sys.path 接入。"""
from __future__ import annotations

import sys

import pytest

from plugin_manager import plugin_lib_env as lib_env


def test_resolve_lib_path_empty_and_missing(tmp_path):
    assert lib_env.resolve_lib_path("") == (None, "")
    assert lib_env.resolve_lib_path("   ") == (None, "")
    missing = tmp_path / "nope"
    target, message = lib_env.resolve_lib_path(str(missing))
    assert target is None
    assert "不存在" in message


def test_resolve_lib_path_plain_dir(tmp_path):
    target, message = lib_env.resolve_lib_path(str(tmp_path))
    assert target == tmp_path
    assert "库目录" in message


def test_resolve_lib_path_file_is_rejected(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    target, message = lib_env.resolve_lib_path(str(f))
    assert target is None
    assert "不是目录" in message


def test_resolve_lib_path_venv(tmp_path, monkeypatch):
    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("home = x", encoding="utf-8")
    if sys.platform == "win32":
        site = venv / "Lib" / "site-packages"
    else:
        major, minor, _ = lib_env.current_python_tag()
        site = venv / "lib" / f"python{major}.{minor}" / "site-packages"
    site.mkdir(parents=True)
    executable = lib_env.venv_python_executable(venv)
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.touch()
    monkeypatch.setattr(lib_env, "_probe_python",
                        lambda _: lib_env.current_python_tag())

    target, message = lib_env.resolve_lib_path(str(venv))
    assert target == site
    assert "虚拟环境" in message


def test_resolve_lib_path_incomplete_venv(tmp_path):
    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("home = x", encoding="utf-8")
    target, message = lib_env.resolve_lib_path(str(venv))
    assert target is None
    assert "site-packages" in message


def test_apply_plugin_lib_dir_rejects_mismatched_venv(tmp_path, monkeypatch):
    venv = tmp_path / "venv"
    (venv / "pyvenv.cfg").parent.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = x", encoding="utf-8")
    if sys.platform == "win32":
        (venv / "Lib" / "site-packages").mkdir(parents=True)
    else:
        major, minor, _ = lib_env.current_python_tag()
        (venv / "lib" / f"python{major}.{minor}" / "site-packages").mkdir(parents=True)
    site = lib_env.venv_site_packages(venv)
    assert site is not None
    executable = lib_env.venv_python_executable(venv)
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.touch()
    current = lib_env.current_python_tag()
    monkeypatch.setattr(lib_env, "_probe_python",
                        lambda _: (current[0], current[1] + 1, current[2]))
    monkeypatch.setattr(sys, "path", list(sys.path))
    before = list(sys.path)

    assert lib_env.apply_plugin_lib_dir(str(venv)) is None
    assert sys.path == before


def test_apply_plugin_lib_dir_appends_to_sys_path(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))
    target = lib_env.apply_plugin_lib_dir(str(tmp_path))
    assert target == tmp_path
    assert str(tmp_path) in sys.path


def test_apply_plugin_lib_dir_empty_is_noop(monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))
    before = list(sys.path)
    assert lib_env.apply_plugin_lib_dir("") is None
    assert sys.path == before


def test_prepare_lib_dir_empty():
    assert lib_env.prepare_lib_dir("") == (None, "")


def test_prepare_lib_dir_existing_non_empty_dir(tmp_path):
    (tmp_path / "pkg").mkdir()
    target, message = lib_env.prepare_lib_dir(str(tmp_path))
    assert target == tmp_path
    assert "库目录" in message


def test_prepare_lib_dir_creates_venv(tmp_path, monkeypatch):
    venv = tmp_path / "new-venv"
    created = []

    def fake_create(target, python_exe):
        created.append((target, python_exe))
        target.mkdir(parents=True, exist_ok=True)
        (target / "pyvenv.cfg").write_text("home = x", encoding="utf-8")
        if sys.platform == "win32":
            site = target / "Lib" / "site-packages"
        else:
            major, minor, _ = lib_env.current_python_tag()
            site = target / "lib" / f"python{major}.{minor}" / "site-packages"
        site.mkdir(parents=True)
        executable = lib_env.venv_python_executable(target)
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.touch()

    monkeypatch.setattr(lib_env, "find_matching_python", lambda: "python.exe")
    monkeypatch.setattr(lib_env, "_probe_python",
                        lambda _: lib_env.current_python_tag())
    monkeypatch.setattr(lib_env, "create_venv", fake_create)

    target, message = lib_env.prepare_lib_dir(str(venv))
    assert created and created[0][1] == "python.exe"
    assert target is not None and target.name == "site-packages"
    assert "已创建虚拟环境" in message


def test_prepare_lib_dir_without_matching_python(tmp_path, monkeypatch):
    monkeypatch.setattr(lib_env, "find_matching_python", lambda: None)
    target, message = lib_env.prepare_lib_dir(str(tmp_path / "venv"))
    assert target is None
    assert "未找到" in message


def test_prepare_lib_dir_create_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(lib_env, "find_matching_python", lambda: "python.exe")

    def boom(target, python_exe):
        raise RuntimeError("venv failed")

    monkeypatch.setattr(lib_env, "create_venv", boom)
    target, message = lib_env.prepare_lib_dir(str(tmp_path / "venv"))
    assert target is None
    assert "venv failed" in message


def test_probe_python_handles_missing_executable():
    assert lib_env._probe_python("definitely-not-a-python-exe") is None


def test_find_matching_python_skips_venv_and_selects_global(monkeypatch):
    monkeypatch.setattr(lib_env, "_candidate_interpreters",
                        lambda: ["venv-python", "global-python"])
    monkeypatch.setattr(lib_env, "_probe_python",
                        lambda exe: lib_env.current_python_tag())
    monkeypatch.setattr(lib_env, "_is_global_python",
                        lambda exe: exe == "global-python")
    assert lib_env.find_matching_python() == "global-python"


def test_find_matching_python_returns_none_when_only_venv_matches(monkeypatch):
    monkeypatch.setattr(lib_env, "_candidate_interpreters", lambda: ["venv-python"])
    monkeypatch.setattr(lib_env, "_probe_python",
                        lambda exe: lib_env.current_python_tag())
    monkeypatch.setattr(lib_env, "_is_global_python", lambda exe: False)
    assert lib_env.find_matching_python() is None


def test_list_installed_packages_only_reads_selected_environment(tmp_path):
    env = tmp_path / "venv"
    env.mkdir()
    (env / "pyvenv.cfg").write_text("home = test", encoding="utf-8")
    if sys.platform == "win32":
        site = env / "Lib" / "site-packages"
    else:
        major, minor, _ = lib_env.current_python_tag()
        site = env / "lib" / f"python{major}.{minor}" / "site-packages"
    info = site / "example_package-1.2.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: example-package\nVersion: 1.2\n",
        encoding="utf-8")
    assert lib_env.list_installed_packages(env) == [("example-package", "1.2")]
    assert lib_env.list_installed_packages(site) == [("example-package", "1.2")]


def test_list_installed_packages_rejects_missing_directory(tmp_path):
    with pytest.raises(ValueError):
        lib_env.list_installed_packages(tmp_path / "missing")


def test_python_tag_text_contains_version():
    text = lib_env.python_tag_text()
    assert text.startswith("Python ")
    assert "位" in text
