"""Hand off a restart to a new manager without relying on the game process."""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from dataclasses import dataclass

from .app_paths import is_frozen

_RESTART_PORT = "METASWEEPER_RESTART_PORT"
_RESTART_TOKEN = "METASWEEPER_RESTART_TOKEN"
_START_TIMEOUT = 10.0


class RestartCancelled(Exception):
    """The predecessor declined to complete the handoff."""


@dataclass
class RestartHandoff:
    process: subprocess.Popen
    connection: socket.socket

    def commit(self) -> None:
        """Permit the replacement to start after this process has exited."""
        self.connection.sendall(b"G")

    def cancel(self) -> None:
        try:
            self.connection.sendall(b"C")
        except OSError:
            pass
        finally:
            self.connection.close()


# Retain the socket until process termination: EOF signals actual process exit,
# including after a crash, rather than just the end of plugin shutdown.
_handoff: RestartHandoff | None = None
_invocation: tuple[list[str], str] | None = None


def configure_invocation(data_dir: str) -> None:
    """Capture the current CLI, cwd and resolved data directory at startup."""
    global _invocation
    if is_frozen():
        command = [sys.executable, *sys.argv[1:]]
    else:
        command = [sys.executable, *sys.orig_argv[1:]]
    # Override a possibly relative argument with the resolved effective directory.
    # Avoid accumulating overrides on successive restarts.
    if len(command) >= 2 and command[-2] == "--data-dir":
        command[-1] = data_dir
    else:
        command.extend(["--data-dir", data_dir])
    _invocation = (command, os.getcwd())


def prepare_restart() -> RestartHandoff:
    """Start the replacement and wait for its readiness; raise on failure."""
    global _handoff
    if _handoff is not None:
        raise RuntimeError("A plugin manager restart is already in progress")
    if _invocation is None:
        raise RuntimeError("Restart is unavailable: the manager was not started via its CLI")
    command, cwd = _invocation
    token = secrets.token_hex(32)
    env = os.environ.copy()
    # A PyInstaller one-file child must unpack independently: the original
    # process removes its temporary bundle when it exits.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    env[_RESTART_TOKEN] = token
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(_START_TIMEOUT)
        env[_RESTART_PORT] = str(listener.getsockname()[1])
        process = subprocess.Popen(command, cwd=cwd, env=env,
                                   stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        connection = None
        try:
            connection, _ = listener.accept()
            connection.settimeout(_START_TIMEOUT)
            received = bytearray()
            while len(received) < len(token):
                chunk = connection.recv(len(token) - len(received))
                if not chunk:
                    break
                received.extend(chunk)
            if received != token.encode("ascii"):
                raise RuntimeError("Invalid restart handshake")
            connection.settimeout(None)
        except Exception:
            if connection is not None:
                connection.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
    _handoff = RestartHandoff(process, connection)
    return _handoff


def cancel_restart(handoff: RestartHandoff) -> None:
    global _handoff
    handoff.cancel()
    if _handoff is handoff:
        _handoff = None


def wait_for_predecessor() -> bool:
    """On a replacement, wait until the committed predecessor has exited.

    Returns False for an ordinary launch. Raises on a cancelled or broken handoff.
    """
    port = os.environ.pop(_RESTART_PORT, None)
    token = os.environ.pop(_RESTART_TOKEN, None)
    if port is None and token is None:
        return False
    if not port or not token:
        raise RuntimeError("Incomplete restart handoff")
    with socket.create_connection(("127.0.0.1", int(port)), timeout=_START_TIMEOUT) as connection:
        connection.sendall(token.encode("ascii"))
        connection.settimeout(None)
        if connection.recv(1) != b"G":
            raise RestartCancelled()
        if connection.recv(1) != b"":
            raise RestartCancelled()
    return True


def acquire_after_restart(acquire, timeout: float = 10.0) -> bool:
    """Wait for the old process's named mutex to be released."""
    deadline = time.monotonic() + timeout
    while not acquire():
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)
    return True


def report_restart_failure(error: Exception) -> None:
    """Report failure even when the predecessor's window no longer exists."""
    from PySide6.QtCore import QCoreApplication
    message = QCoreApplication.translate(
        "PluginManagerWindow", "Plugin manager restart failed:\n{error}").format(error=error)
    title = QCoreApplication.translate("PluginManagerWindow", "Plugin manager")
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    else:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(None, title, message)
