from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plugin_manager import restart


def test_invocation_keeps_cli_and_resolves_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(restart, "is_frozen", lambda: False)
    monkeypatch.setattr(sys, "orig_argv", ["python", "-X", "utf8", "-m", "plugin_manager", "--mode", "tray", "--data-dir", "relative"])
    monkeypatch.chdir(tmp_path)
    restart.configure_invocation(str(tmp_path / "data"))
    command, cwd = restart._invocation
    assert command == [sys.executable, "-X", "utf8", "-m", "plugin_manager", "--mode", "tray", "--data-dir", str(tmp_path / "data")]
    assert cwd == str(tmp_path)


def test_frozen_invocation_preserves_arguments(monkeypatch, tmp_path):
    monkeypatch.setattr(restart, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "argv", ["plugin_manager.exe", "--endpoint", "tcp://localhost:1000", "--mode", "tray"])
    restart.configure_invocation(str(tmp_path))
    assert restart._invocation[0] == [sys.executable, "--endpoint", "tcp://localhost:1000", "--mode", "tray", "--data-dir", str(tmp_path)]


def test_launch_failure_does_not_commit(monkeypatch):
    monkeypatch.setattr(restart, "_handoff", None)
    monkeypatch.setattr(restart, "_invocation", (["missing"], os.getcwd()))
    monkeypatch.setattr(restart.subprocess, "Popen", Mock(side_effect=OSError("launch failed")))
    with pytest.raises(OSError, match="launch failed"):
        restart.prepare_restart()
    assert restart._handoff is None


def test_mutex_is_retried_after_old_process_exit(monkeypatch):
    acquire = Mock(side_effect=[False, False, True])
    monkeypatch.setattr(restart.time, "sleep", lambda _: None)
    assert restart.acquire_after_restart(acquire)
    assert acquire.call_count == 3
    assert not restart.acquire_after_restart(lambda: False, timeout=0)


def test_child_waits_for_actual_parent_exit(tmp_path):
    marker = tmp_path / "replacement-started"
    child = (
        "from plugin_manager.restart import wait_for_predecessor; "
        "from pathlib import Path; import sys; "
        "wait_for_predecessor(); Path(sys.argv[1]).write_text('started')"
    )
    parent = (
        "from plugin_manager import restart; import os, sys; "
        "restart._invocation=([sys.executable, '-c', sys.argv[1], sys.argv[2]], os.getcwd()); "
        "h=restart.prepare_restart(); h.commit(); print('ready', flush=True); input()"
    )
    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    process = subprocess.Popen([sys.executable, "-c", parent, child, str(marker)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, env=env)
    try:
        assert process.stdout.readline().strip() == "ready"
        assert not marker.exists()
        _, error = process.communicate("\n", timeout=15)
        assert process.returncode == 0, error
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.read_text() == "started"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows named mutex integration")
def test_actual_mutex_is_released_before_replacement(tmp_path):
    marker = tmp_path / "locked"
    mutex_name = "Metasweeper-Restart-Test-" + os.urandom(16).hex()
    child = (
        "from plugin_manager.restart import wait_for_predecessor, acquire_after_restart; "
        "from plugin_manager import __main__ as entry; from pathlib import Path; import sys; "
        "entry._MUTEX_NAME=sys.argv[1]; wait_for_predecessor(); "
        "assert acquire_after_restart(entry._acquire_mutex); Path(sys.argv[2]).touch()"
    )
    parent = (
        "from plugin_manager import restart, __main__ as entry; import os, sys; "
        "entry._MUTEX_NAME=sys.argv[1]; assert entry._acquire_mutex(); "
        "restart._invocation=([sys.executable, '-c', sys.argv[2], sys.argv[1], sys.argv[3]], os.getcwd()); "
        "h=restart.prepare_restart(); h.commit(); print('locked', flush=True); input()"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    process = subprocess.Popen([sys.executable, "-c", parent, mutex_name, child, str(marker)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, env=env)
    try:
        assert process.stdout.readline().strip() == "locked"
        assert not marker.exists()
        _, error = process.communicate("\n", timeout=15)
        assert process.returncode == 0, error
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_cancelled_handoff_never_starts_replacement(monkeypatch, tmp_path):
    marker = tmp_path / "replacement-started"
    child = ("from plugin_manager.restart import wait_for_predecessor; "
             "from pathlib import Path; import sys; "
             "wait_for_predecessor(); Path(sys.argv[1]).touch()")
    monkeypatch.setattr(restart, "_handoff", None)
    monkeypatch.setattr(restart, "_invocation", ([sys.executable, "-c", child, str(marker)], os.getcwd()))
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2] / "src"))
    handoff = restart.prepare_restart()
    restart.cancel_restart(handoff)
    handoff.process.wait(timeout=10)
    assert handoff.process.returncode != 0
    assert not marker.exists()
    assert restart._handoff is None


def test_restart_is_registered_as_a_qt_slot():
    from plugin_manager.main_window import PluginManagerWindow

    assert PluginManagerWindow.staticMetaObject.indexOfSlot("restart_plugin_manager()") >= 0


def test_window_reports_launch_failure_and_does_not_stop(monkeypatch):
    from plugin_manager.main_window import PluginManagerWindow, QMessageBox

    stop = Mock()
    window = SimpleNamespace(_installation_in_progress=lambda: False,
                             _state_mgr=SimpleNamespace(save=Mock()),
                             _manager=SimpleNamespace(stop=stop),
                             tr=lambda text: text)
    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    monkeypatch.setattr(restart, "prepare_restart", Mock(side_effect=OSError("launch failed")))
    assert not PluginManagerWindow.restart_plugin_manager(window)
    stop.assert_not_called()
    assert "launch failed" in warning.call_args.args[2]


def test_window_stops_and_commits_before_quitting(monkeypatch):
    from plugin_manager import main_window
    from plugin_manager.main_window import PluginManagerWindow

    calls = []
    handoff = SimpleNamespace(commit=lambda: calls.append("commit"))
    window = SimpleNamespace(_installation_in_progress=lambda: False,
                             _state_mgr=SimpleNamespace(save=lambda: calls.append("save")),
                             _manager=SimpleNamespace(stop=lambda: calls.append("stop")))
    app = SimpleNamespace(quit=lambda: calls.append("quit"))
    monkeypatch.setattr(restart, "prepare_restart", lambda: handoff)
    monkeypatch.setattr(main_window, "QApplication", SimpleNamespace(instance=lambda: app))
    assert PluginManagerWindow.restart_plugin_manager(window)
    assert calls == ["save", "stop", "commit", "quit"]


def test_window_cancels_handoff_if_shutdown_fails(monkeypatch):
    from plugin_manager.main_window import PluginManagerWindow, QMessageBox

    handoff = Mock()
    window = SimpleNamespace(_installation_in_progress=lambda: False,
                             _state_mgr=SimpleNamespace(save=Mock()),
                             _manager=SimpleNamespace(stop=Mock(side_effect=RuntimeError("shutdown failed"))),
                             tr=lambda text: text)
    cancel = Mock()
    monkeypatch.setattr(restart, "prepare_restart", lambda: handoff)
    monkeypatch.setattr(restart, "cancel_restart", cancel)
    monkeypatch.setattr(QMessageBox, "warning", Mock())
    assert not PluginManagerWindow.restart_plugin_manager(window)
    handoff.commit.assert_not_called()
    cancel.assert_called_once_with(handoff)
