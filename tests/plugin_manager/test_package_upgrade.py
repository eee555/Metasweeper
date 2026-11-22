"""Package update checks and upgrades use only the selected dependency environment."""
import csv
import functools
import io
import sys
import zipfile
from concurrent.futures import TimeoutError as FutureTimeout
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from plugin_manager import plugin_lib_env as env
from tests.plugin_manager.test_plugin_dependency_bootstrap import make_venv


def write_distribution(site: Path, name: str = "Example_Package") -> None:
    info = site / "example_package-1.0.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n", encoding="utf-8")


@pytest.mark.parametrize("venv", [False, True])
def test_check_updates_uses_selected_environment_and_indexes(tmp_path, monkeypatch, venv):
    if venv:
        directory = tmp_path / "venv"
        site, executable = make_venv(directory)
        monkeypatch.setattr(env, "_probe_python", lambda _: env.current_python_tag())
    else:
        directory = site = tmp_path / "library"
        site.mkdir()
        executable = Path(sys.executable)
        monkeypatch.setattr(env, "find_matching_python", lambda: str(executable))
    commands = []
    monkeypatch.setattr(env.subprocess, "run", lambda cmd, **kwargs: (
        commands.append(cmd) or SimpleNamespace(
            returncode=0, stdout='[{"name":"Example_Package","latest_version":"2.0"}]', stderr="")))

    assert env.check_package_updates(directory, ["https://one/simple", "https://two/simple"]) == {
        "example-package": "2.0"}
    cmd = commands[0]
    if venv:
        assert cmd[:5] == [str(executable), "-m", "pip", "list", "--outdated"]
    else:
        assert cmd[0] == sys.executable and Path(cmd[1]).name == "_pip_worker.py"
        assert cmd[2:4] == ["list", "--outdated"]
        assert "--only-binary=:all:" in cmd
    assert cmd[cmd.index("--path") + 1] == str(site)
    assert cmd[cmd.index("--index-url") + 1] == "https://one/simple"
    assert cmd[cmd.index("--extra-index-url") + 1] == "https://two/simple"


def test_check_updates_is_asynchronous_and_propagates_failure(tmp_path, monkeypatch):
    started, release = Event(), Event()

    def check(directory, indexes):
        started.set()
        assert release.wait(5)
        raise RuntimeError("index unavailable")

    monkeypatch.setattr(env, "check_package_updates", check)
    future = env.check_package_updates_async(tmp_path, ["https://example.org/simple"])
    try:
        assert started.wait(2)
        with pytest.raises(FutureTimeout):
            future.result(timeout=0.01)
        release.set()
        with pytest.raises(RuntimeError, match="index unavailable"):
            future.result(timeout=5)
    finally:
        release.set()


@pytest.mark.parametrize("output", ["not json", "{}", '[{"name":"x"}]'])
def test_check_updates_reports_invalid_response(tmp_path, monkeypatch, output):
    monkeypatch.setattr(env, "find_matching_python", lambda: "python-external")
    monkeypatch.setattr(env.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=output, stderr=""))
    with pytest.raises(RuntimeError, match="Invalid package update response"):
        env.check_package_updates(tmp_path, [])


def test_check_updates_reports_pip_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(env, "find_matching_python", lambda: "python-external")
    monkeypatch.setattr(env.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=1, stdout="", stderr="index unreachable"))
    with pytest.raises(RuntimeError, match="index unreachable"):
        env.check_package_updates(tmp_path, [])


def test_check_updates_reports_retry_even_when_pip_returns_success(tmp_path, monkeypatch):
    monkeypatch.setattr(env, "find_matching_python", lambda: "python-external")
    monkeypatch.setattr(env.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="[]", stderr="WARNING: Retrying after connection failure"))
    with pytest.raises(RuntimeError, match="incomplete"):
        env.check_package_updates(tmp_path, [])


def test_upgrade_uses_correct_environment_and_only_named_distribution(tmp_path, monkeypatch):
    directory = tmp_path / "venv"
    site, executable = make_venv(directory)
    monkeypatch.setattr(env, "_probe_python", lambda _: env.current_python_tag())
    write_distribution(site)
    calls = []
    monkeypatch.setattr(env, "_run_install", lambda command, label, callback: (
        calls.append((command, callback)) or None))
    output = []

    assert env.upgrade_installed_package(directory, ["https://example.org/simple"],
                                         "example-package", output_callback=output.append) is None
    cmd, callback = calls[0]
    assert cmd[:4] == [str(executable), "-m", "pip", "install"]
    assert cmd[-2:] == ["--", "example-package"]
    assert "--upgrade" in cmd
    assert cmd[cmd.index("--index-url") + 1] == "https://example.org/simple"
    assert "--target" not in cmd
    assert callback == output.append


def test_frozen_upgrade_uses_bundled_pip_and_wheels(tmp_path, monkeypatch):
    write_distribution(tmp_path)
    monkeypatch.setattr(env, "is_frozen", lambda: True)
    commands = []
    monkeypatch.setattr(env, "_run_install", lambda command, *_: commands.append(command))

    assert env.upgrade_installed_package(tmp_path, [], "example-package") is None

    command, = commands
    assert command[:3] == [sys.executable, env.FLAG, "install"]
    assert command[command.index("--target") + 1] == str(tmp_path)
    assert "--only-binary=:all:" in command
    assert command[-2:] == ["--", "example-package"]


@pytest.mark.parametrize("name", ["--help", "example; python_version", "../example", "example\n--index-url evil"])
def test_upgrade_rejects_pip_option_injection(tmp_path, monkeypatch, name):
    monkeypatch.setattr(env, "_run_install", lambda *args: pytest.fail("pip must not run"))
    assert env.upgrade_installed_package(tmp_path, [], name)


def test_upgrade_rejects_missing_package_and_surfaces_failure(tmp_path, monkeypatch):
    directory = tmp_path / "venv"
    site, _ = make_venv(directory)
    write_distribution(site)
    monkeypatch.setattr(env, "_probe_python", lambda _: env.current_python_tag())
    monkeypatch.setattr(env, "_run_install", lambda *args: "pip failed")
    assert "not installed" in env.upgrade_installed_package(directory, [], "missing")
    assert env.upgrade_installed_package(directory, [], "example-package") == "pip failed"


def test_update_check_does_not_block_installations(tmp_path, monkeypatch):
    directory = tmp_path / "venv"
    site, _ = make_venv(directory)
    write_distribution(site)
    monkeypatch.setattr(env, "_probe_python", lambda _: env.current_python_tag())
    check_started, release_check, install_started = Event(), Event(), Event()

    def run_check(*args, **kwargs):
        check_started.set()
        assert release_check.wait(5)
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")

    def run_install(*args):
        install_started.set()
        return None

    monkeypatch.setattr(env.subprocess, "run", run_check)
    monkeypatch.setattr(env, "_run_install", run_install)
    future = env.check_package_updates_async(directory, [])
    installer = Thread(target=env.upgrade_installed_package,
                       args=(directory, [], "example-package"))
    try:
        assert check_started.wait(2)
        assert not future.cancel()
        installer.start()
        assert install_started.wait(2)
        installer.join(timeout=2)
        assert not installer.is_alive()
        release_check.set()
        assert future.result(timeout=5) == {}
    finally:
        release_check.set()
        if installer.ident is not None:
            installer.join(timeout=5)


def test_real_pip_check_and_upgrade_against_local_index(tmp_path, monkeypatch):
    site = tmp_path / "library"
    site.mkdir()
    info = site / "upgrade_demo-1.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: upgrade-demo\nVersion: 1.0\n", encoding="utf-8")
    root = tmp_path / "index"
    simple = root / "simple" / "upgrade-demo"
    simple.mkdir(parents=True)
    wheel_dir = root / "packages"
    wheel_dir.mkdir()
    wheel_name = "upgrade_demo-2.0-py3-none-any.whl"
    files = {
        "upgrade_demo.py": "VERSION = '2.0'\n",
        "upgrade_demo-2.0.dist-info/METADATA":
            "Metadata-Version: 2.1\nName: upgrade-demo\nVersion: 2.0\n",
        "upgrade_demo-2.0.dist-info/WHEEL":
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for path in files:
        writer.writerow((path, "", ""))
    writer.writerow(("upgrade_demo-2.0.dist-info/RECORD", "", ""))
    files["upgrade_demo-2.0.dist-info/RECORD"] = record.getvalue()
    with zipfile.ZipFile(wheel_dir / wheel_name, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    (simple / "index.html").write_text(
        f'<a href="/packages/{wheel_name}">{wheel_name}</a>', encoding="utf-8")
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(env, "find_matching_python", lambda: sys.executable)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    indexes = [f"http://127.0.0.1:{server.server_port}/simple"]
    try:
        assert env.check_package_updates_async(site, indexes).result(timeout=30) == {
            "upgrade-demo": "2.0"}
        assert env.upgrade_installed_package(site, indexes, "upgrade-demo") is None
        assert env.list_installed_packages(site) == [("upgrade-demo", "2.0")]
        assert (site / "upgrade_demo.py").read_text(encoding="utf-8") == "VERSION = '2.0'\n"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
