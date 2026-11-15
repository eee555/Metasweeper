"""app_paths.py 全分支覆盖：所有写操作都限制在 tmp_path / 打桩对象内。"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

app_paths = importlib.import_module("plugin_manager.app_paths")

_NON_WIN32_PLATFORM = "linux"
_WIN32_PLATFORM = "win32"


@pytest.fixture
def paths(monkeypatch, tmp_path):
    """每个用例独立重置模块全局状态，避免污染其他测试。"""
    monkeypatch.setattr(app_paths, "_data_dir_override", None)
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.delattr(app_paths, "__compiled__", raising=False)
    monkeypatch.setattr(sys, "platform", _WIN32_PLATFORM)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(Path, "home", classmethod(
        lambda cls, *a, **kw: tmp_path / "fakehome",
    ))
    return SimpleNamespace(tmp_path=tmp_path)


# ── 运行环境判断 ───────────────────────────────────────────────────────────


def test_is_nuitka_compiled_true(paths, monkeypatch):
    monkeypatch.setattr(app_paths, "__compiled__", "stub", raising=False)
    assert app_paths.is_nuitka_compiled() is True


def test_is_nuitka_compiled_false(paths):
    assert app_paths.is_nuitka_compiled() is False


def test_is_frozen_nuitka(paths, monkeypatch):
    monkeypatch.setattr(app_paths, "__compiled__", "stub", raising=False)
    assert app_paths.is_frozen() is True


def test_is_frozen_pyinstaller(paths, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "C:/bundle", raising=False)
    assert app_paths.is_frozen() is True


def test_is_frozen_requires_meipass(paths, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert app_paths.is_frozen() is False


def test_is_frozen_dev(paths):
    assert app_paths.is_frozen() is False


# ── get_bundle_dir / get_executable_dir ────────────────────────────────────


def test_get_bundle_dir_nuitka(paths, monkeypatch):
    exe = paths.tmp_path / "bin" / "app.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(app_paths, "__compiled__", "stub", raising=False)
    assert app_paths.get_bundle_dir() == exe.parent.resolve()


def test_get_bundle_dir_pyinstaller(paths, monkeypatch):
    bundle = paths.tmp_path / "meipass"
    bundle.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    assert app_paths.get_bundle_dir() == bundle


def test_get_bundle_dir_dev(paths):
    assert app_paths.get_bundle_dir() == Path(app_paths.__file__).resolve().parent.parent


def test_get_executable_dir_frozen(paths, monkeypatch):
    exe = paths.tmp_path / "dist" / "app.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(paths.tmp_path), raising=False)
    assert app_paths.get_executable_dir() == exe.parent.resolve()


def test_get_executable_dir_dev(paths):
    assert app_paths.get_executable_dir() == Path(app_paths.__file__).resolve().parent.parent.parent


# ── 指针文件 ──────────────────────────────────────────────────────────────


def test_get_pointer_path_win32_uses_appdata(paths):
    p = app_paths._get_pointer_path()
    assert p == Path(os.environ["APPDATA"]) / app_paths._POINTER_FILENAME


def test_get_pointer_path_non_win32_uses_home(paths, monkeypatch):
    monkeypatch.setattr(sys, "platform", _NON_WIN32_PLATFORM)
    p = app_paths._get_pointer_path()
    assert p == (paths.tmp_path / "fakehome" / "Library" / "Application Support" /
                 "Metasweeper" / app_paths._POINTER_FILENAME)


def test_write_pointer_file_success(paths, monkeypatch):
    target = paths.tmp_path / "appdata" / "pointer.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(app_paths, "_POINTER_FILENAME", str(target))
    app_paths._write_pointer_file(str(paths.tmp_path / "data"))
    assert target.read_text(encoding="utf-8") == str(paths.tmp_path / "data")


def test_write_pointer_file_failure_is_logged(paths, monkeypatch):
    def boom(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(app_paths, "_get_pointer_path", lambda: SimpleNamespace(
        write_text=boom,
    ))
    app_paths._write_pointer_file("unused")  # 仅警告，不抛


def test_read_pointer_file_valid(paths, monkeypatch, tmp_path):
    target = tmp_path / "valid-pointer"
    data = tmp_path / "data"
    data.mkdir()
    target.write_text(f"  {data}  \n", encoding="utf-8")
    monkeypatch.setattr(app_paths, "_get_pointer_path", lambda: target)
    assert app_paths._read_pointer_file() == str(data)


def test_read_pointer_file_missing(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "_get_pointer_path", lambda: tmp_path / "absent")
    assert app_paths._read_pointer_file() is None


def test_read_pointer_file_empty(paths, monkeypatch, tmp_path):
    target = tmp_path / "empty-pointer"
    target.write_text("  \n", encoding="utf-8")
    monkeypatch.setattr(app_paths, "_get_pointer_path", lambda: target)
    assert app_paths._read_pointer_file() is None


def test_read_pointer_file_corrupt_json_and_other_failures(
    paths, monkeypatch, tmp_path,
):
    corrupt = tmp_path / "corrupt-pointer"
    corrupt.write_text("{not-json\x00", encoding="utf-8")
    monkeypatch.setattr(app_paths, "_get_pointer_path", lambda: corrupt)
    assert app_paths._read_pointer_file() is None  # 非目录路径
    corrupt.write_text(json.dumps({"unexpected": "shape"}), encoding="utf-8")
    assert app_paths._read_pointer_file() is None

    def boom(*a, **kw):
        raise OSError("permission denied")

    monkeypatch.setattr(app_paths, "_get_pointer_path", lambda: SimpleNamespace(
        exists=boom,
    ))
    assert app_paths._read_pointer_file() is None


def test_read_pointer_file_non_existing_dir(paths, monkeypatch, tmp_path):
    target = tmp_path / "pointer"
    target.write_text(str(tmp_path / "no-such-dir"), encoding="utf-8")
    monkeypatch.setattr(app_paths, "_get_pointer_path", lambda: target)
    assert app_paths._read_pointer_file() is None


# ── 可写数据目录 ─────────────────────────────────────────────────────────


def test_set_data_dir_override_writes_pointer(paths, monkeypatch, tmp_path):
    written = []
    monkeypatch.setattr(app_paths, "_write_pointer_file", written.append)
    app_paths.set_data_dir_override(str(tmp_path / "override"))
    assert app_paths._data_dir_override == str(tmp_path / "override")
    assert written == [str(tmp_path / "override")]


def test_get_data_dir_override_branch(paths, tmp_path):
    target = tmp_path / "overridden" / "nested"
    app_paths._data_dir_override = str(target)
    assert app_paths.get_data_dir() == target
    assert target.is_dir()


def test_get_data_dir_pointer_branch(paths, monkeypatch, tmp_path):
    target = tmp_path / "from-pointer"
    target.mkdir()
    monkeypatch.setattr(app_paths, "_read_pointer_file", lambda: str(target))
    assert app_paths.get_data_dir() == target


def test_get_data_dir_frozen_fallback(paths, monkeypatch, tmp_path):
    exe = tmp_path / "dist" / "app.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(app_paths, "_read_pointer_file", lambda: None)
    written = []
    monkeypatch.setattr(app_paths, "_write_pointer_file", written.append)
    result = app_paths.get_data_dir()
    assert result == exe.parent.resolve() / "data"
    assert result.is_dir()
    assert written == [str(result)]


def test_get_data_dir_dev_fallback(paths, monkeypatch):
    monkeypatch.setattr(app_paths, "_read_pointer_file", lambda: None)
    monkeypatch.setattr(app_paths, "_write_pointer_file", lambda p: None)
    monkeypatch.setattr(app_paths, "get_executable_dir", lambda: paths.tmp_path / "root")
    result = app_paths.get_data_dir()
    assert result == paths.tmp_path / "root" / "data"
    assert result.is_dir()


def test_get_log_dir(paths, tmp_path):
    log_root = tmp_path / "logs-root"
    monkeypatch_root = tmp_path / "logs-root" / "logs"
    app_paths._data_dir_override = str(log_root)
    assert app_paths.get_log_dir() == monkeypatch_root
    assert monkeypatch_root.is_dir()


# ── 插件路径 ──────────────────────────────────────────────────────────────


def test_get_builtin_plugin_dirs_dev_existing(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_bundle_dir", lambda: tmp_path)
    (tmp_path / "plugins").mkdir()
    assert app_paths.get_builtin_plugin_dirs() == [tmp_path / "plugins"]


def test_get_builtin_plugin_dirs_missing_warns(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_bundle_dir", lambda: tmp_path)
    assert app_paths.get_builtin_plugin_dirs() == []


def test_get_builtin_plugin_dirs_nuitka_internal(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "__compiled__", "stub", raising=False)
    monkeypatch.setattr(app_paths, "get_bundle_dir", lambda: tmp_path)
    internal = tmp_path / "internal" / "plugins"
    internal.mkdir(parents=True)
    assert app_paths.get_builtin_plugin_dirs() == [internal]


def test_get_user_plugin_dirs_both(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_executable_dir", lambda: tmp_path)
    (tmp_path / "plugins").mkdir()
    (tmp_path / "user_plugins").mkdir()
    assert app_paths.get_user_plugin_dirs() == [
        tmp_path / "plugins", tmp_path / "user_plugins",
    ]


def test_get_user_plugin_dirs_none(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_executable_dir", lambda: tmp_path)
    assert app_paths.get_user_plugin_dirs() == []


def test_get_user_plugin_dirs_only_one(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_executable_dir", lambda: tmp_path)
    (tmp_path / "user_plugins").mkdir()
    assert app_paths.get_user_plugin_dirs() == [tmp_path / "user_plugins"]


def test_get_all_plugin_dirs(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_builtin_plugin_dirs", lambda: [tmp_path / "a"])
    monkeypatch.setattr(app_paths, "get_user_plugin_dirs", lambda: [tmp_path / "b"])
    assert app_paths.get_all_plugin_dirs() == [tmp_path / "a", tmp_path / "b"]


def test_get_plugin_data_dir_from_class(paths, monkeypatch, tmp_path):
    class DemoPlugin:
        pass

    monkeypatch.setattr(app_paths, "get_data_dir", lambda: tmp_path)
    assert app_paths.get_plugin_data_dir(DemoPlugin) == (
        tmp_path / "plugin_data" / "DemoPlugin"
    )
    assert (tmp_path / "plugin_data" / "DemoPlugin").is_dir()


def test_get_plugin_data_dir_from_string(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_data_dir", lambda: tmp_path)
    assert app_paths.get_plugin_data_dir("cool_plugin") == (
        tmp_path / "plugin_data" / "cool_plugin"
    )
    assert (tmp_path / "plugin_data" / "cool_plugin").is_dir()


# ── 环境变量补丁 ─────────────────────────────────────────────────────────


def test_patch_sys_path_dev_noop(paths, monkeypatch):
    before = list(sys.path)
    app_paths.patch_sys_path_for_frozen()
    assert sys.path == before


def test_patch_sys_path_frozen_inserts_once(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(app_paths, "get_bundle_dir", lambda: tmp_path / "bundle")
    target = str(tmp_path / "bundle")
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != target])
    app_paths.patch_sys_path_for_frozen()
    assert sys.path[0] == target
    app_paths.patch_sys_path_for_frozen()  # 已存在时不重复插入
    assert sys.path.count(target) == 1


def test_patch_sys_path_frozen_bundle_already_present(paths, monkeypatch, tmp_path):
    target = str(tmp_path / "bundle")
    monkeypatch.setattr(app_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(app_paths, "get_bundle_dir", lambda: tmp_path / "bundle")
    monkeypatch.setattr(sys, "path", [target, *sys.path])
    app_paths.patch_sys_path_for_frozen()
    assert sys.path.count(target) == 1


def test_get_env_for_subprocess_default(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_bundle_dir", lambda: tmp_path / "bundle")
    monkeypatch.setenv("QT_FONT_DPI", "144")
    monkeypatch.setenv("PYTHONPATH", "C:/existing")
    result = app_paths.get_env_for_subprocess()
    assert "QT_FONT_DPI" not in result
    assert result["PYTHONPATH"] == os.pathsep.join([
        str(tmp_path / "bundle"), "C:/existing",
    ])


def test_get_env_for_subprocess_explicit_env(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_bundle_dir", lambda: tmp_path / "bundle")
    env = {"QT_FONT_DPI": "96"}
    result = app_paths.get_env_for_subprocess(env)
    assert result is env
    assert "QT_FONT_DPI" not in env
    assert env["PYTHONPATH"] == str(tmp_path / "bundle")


def test_get_env_for_subprocess_no_existing_pythonpath(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_bundle_dir", lambda: tmp_path / "bundle")
    monkeypatch.delenv("PYTHONPATH", raising=False)
    result = app_paths.get_env_for_subprocess()
    assert result["PYTHONPATH"] == str(tmp_path / "bundle")


# ── 调试辅助 ─────────────────────────────────────────────────────────────


def test_debug_dump_paths(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(app_paths, "get_bundle_dir", lambda: tmp_path / "bundle")
    monkeypatch.setattr(app_paths, "get_executable_dir", lambda: tmp_path / "exe")
    monkeypatch.setattr(app_paths, "get_builtin_plugin_dirs", lambda: [tmp_path / "b"])
    monkeypatch.setattr(app_paths, "get_user_plugin_dirs", lambda: [tmp_path / "u"])
    result = app_paths.debug_dump_paths()
    assert result["frozen"] == "False"
    assert result["bundle_dir"] == str(tmp_path / "bundle")
    assert result["executable_dir"] == str(tmp_path / "exe")
    assert result["data_dir"] == str(tmp_path / "data")
    assert result["builtin_plugins"] == str([tmp_path / "b"])
    assert result["user_plugins"] == str([tmp_path / "u"])
    assert result["sys_executable"] == sys.executable
    assert result["_MEIPASS"] == "N/A"
    assert result["__file__"] == str(Path(app_paths.__file__).resolve())


def test_debug_dump_paths_with_meipass(paths, monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", "C:/meipass", raising=False)
    monkeypatch.setattr(app_paths, "get_data_dir", lambda: paths.tmp_path)
    assert app_paths.debug_dump_paths()["_MEIPASS"] == "C:/meipass"
