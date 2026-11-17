"""Focused startup dependency bootstrap tests; no real pip/network calls."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from plugin_manager import plugin_lib_env as env
from plugin_manager.settings_manager import SettingsManager


def make_venv(path: Path) -> tuple[Path, Path]:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyvenv.cfg").write_text("home = test-python\n", encoding="utf-8")
    if sys.platform == "win32":
        site = path / "Lib" / "site-packages"
        executable = path / "Scripts" / "python.exe"
    else:
        major, minor, _ = env.current_python_tag()
        site = path / "lib" / f"python{major}.{minor}" / "site-packages"
        executable = path / "bin" / "python"
    site.mkdir(parents=True)
    executable.parent.mkdir(parents=True)
    executable.write_text("test executable placeholder", encoding="utf-8")
    return site, executable


def test_startup_does_not_create_environment_without_user_action(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    def unexpected(*args, **kwargs):
        raise AssertionError("startup must not create a venv or install packages")
    monkeypatch.setattr(env, "create_venv", unexpected)
    monkeypatch.setattr(env.subprocess, "run", unexpected)

    result = env.prepare_plugin_dependency_environment(data_dir)

    assert result.library_path is None
    assert result.errors
    assert not (data_dir / "plugin_venv").exists()
    assert SettingsManager(data_dir).plugin_lib_dir == ""


def test_failed_default_setup_keeps_path_unset_for_retry(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(env, "find_matching_python", lambda: None)

    result = env.prepare_plugin_dependency_environment(data_dir)

    assert result.library_path is None
    assert result.errors
    assert SettingsManager(data_dir).plugin_lib_dir == ""


def test_existing_venv_reused_and_debugpy_detection_skips_install(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    target = tmp_path / "shared-venv"
    site, executable = make_venv(target)
    SettingsManager(data_dir).set_plugin_lib_dir(str(target))
    monkeypatch.setattr(env, "create_venv", lambda *args: (_ for _ in ()).throw(AssertionError("must reuse venv")))
    monkeypatch.setattr(env, "_probe_python", lambda exe: env.current_python_tag())
    monkeypatch.setattr(env.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected pip")))
    monkeypatch.setattr(sys, "path", list(sys.path))

    result = env.prepare_plugin_dependency_environment(data_dir)

    assert result.library_path == site
    assert result.python_executable == executable
    assert result.errors == []
    assert str(site) in sys.path


def test_mismatched_existing_venv_is_not_used_for_installation(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    target = tmp_path / "shared-venv"
    site, _ = make_venv(target)
    SettingsManager(data_dir).set_plugin_lib_dir(str(target))
    other = (env.current_python_tag()[0], env.current_python_tag()[1] + 1,
             env.current_python_tag()[2])
    monkeypatch.setattr(env, "_probe_python", lambda exe: other)
    monkeypatch.setattr(env.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("must not install into mismatched venv")))

    result = env.prepare_plugin_dependency_environment(data_dir)

    assert result.library_path == site
    assert result.python_executable is None
    assert any("does not match" in error for error in result.errors)


def test_manual_plugin_install_uses_selected_target_directory(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    target = tmp_path / "library"
    target.mkdir()
    SettingsManager(data_dir).set_plugin_lib_dir(str(target))
    requirement_file = tmp_path / "requirements.txt"
    requirement_file.write_text("humanize>=4,<5\\n", encoding="utf-8")
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        assert kwargs["capture_output"] is True
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(env, "find_matching_python", lambda: "external-python")
    monkeypatch.setattr(env.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "path", list(sys.path))

    error = env.install_plugin_requirements(data_dir, requirement_file)

    assert error is None
    assert commands[0][:5] == ["external-python", "-m", "pip", "install", "--target"]
    assert commands[0][5] == str(target)
    assert "--index-url" in commands[0]
    assert "https://pypi.org/simple" in commands[0]
    assert "--extra-index-url" in commands[0]
    assert "https://pypi.tuna.tsinghua.edu.cn/simple" in commands[0]
    assert "--upgrade" in commands[0] and "--no-input" in commands[0]
    assert commands[0][-2:] == ["-r", str(requirement_file)]


def test_startup_only_prepares_environment_and_never_runs_pip(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    target = tmp_path / "target"
    target.mkdir()
    SettingsManager(data_dir).set_plugin_lib_dir(str(target))
    monkeypatch.setattr(env, "find_matching_python", lambda: "python-external")
    monkeypatch.setattr(env.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("startup must not install dependencies")))
    monkeypatch.setattr(sys, "path", list(sys.path))

    result = env.prepare_plugin_dependency_environment(data_dir)

    assert result.library_path == target
    assert result.python_executable == Path("python-external")
    assert result.errors == []
    assert str(target) in sys.path


def test_debugpy_installs_only_after_explicit_call(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    target = tmp_path / "target"
    target.mkdir()
    SettingsManager(data_dir).set_plugin_lib_dir(str(target))
    monkeypatch.setattr(env, "find_matching_python", lambda: "python-external")
    monkeypatch.setattr(env, "_has_debugpy", lambda path: False)
    monkeypatch.setattr(sys, "path", list(sys.path))
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, Path(command[-1]).read_text(encoding="utf-8")))
        return SimpleNamespace(returncode=0, stdout="installed", stderr="")

    monkeypatch.setattr(env.subprocess, "run", fake_run)
    assert env.prepare_plugin_dependency_environment(data_dir).errors == []
    assert commands == []

    error = env.install_debugpy(data_dir)

    assert error is None
    assert len(commands) == 1
    assert "debugpy>=1.8.20" in commands[0][1]
    assert commands[0][0][0] == "python-external"


def test_stream_install_delivers_output_lines_in_order():
    lines = []
    command = [
        sys.executable, "-u", "-c",
        "print('Collecting example'); print('Successfully installed example')",
    ]
    assert env._run_install(command, "stream test", lines.append) is None
    assert lines == ["Collecting example", "Successfully installed example"]


def test_pip_timeout_output_is_returned_and_logged(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output=b"partial stdout", stderr=b"partial stderr")
    monkeypatch.setattr(env.subprocess, "run", timeout)

    error = env._run_install(["python", "-m", "pip"], "test install")

    assert error is not None
    assert "timed out" in error
    assert "partial stdout" in error and "partial stderr" in error


def test_manual_plugin_install_passes_selected_requirements_file(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    target = tmp_path / "target"
    target.mkdir()
    SettingsManager(data_dir).set_plugin_lib_dir(str(target))
    requirement_file = tmp_path / "requirements.txt"
    requirement_file.write_text("invalid !!!\n", encoding="utf-8")
    monkeypatch.setattr(env, "find_matching_python", lambda: "python-external")
    monkeypatch.setattr(sys, "path", list(sys.path))
    commands = []
    monkeypatch.setattr(env.subprocess, "run", lambda command, **kwargs: (
        commands.append(command) or SimpleNamespace(returncode=0, stdout="", stderr="")))

    error = env.install_plugin_requirements(data_dir, requirement_file)

    assert error is None
    assert commands[0][-2:] == ["-r", str(requirement_file)]
