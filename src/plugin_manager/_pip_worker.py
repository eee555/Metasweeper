"""Run pip in a short-lived process using the application runtime."""
from __future__ import annotations

import os
import sys
import traceback

FLAG = "--plugin-dependency-pip"


def _restore_windows_output() -> None:
    if sys.platform != "win32" or (sys.stdout is not None and sys.stderr is not None):
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes

    get_handle = ctypes.WinDLL("kernel32", use_last_error=True).GetStdHandle
    get_handle.argtypes = [wintypes.DWORD]
    get_handle.restype = wintypes.HANDLE
    for name, number in (("stdout", -11), ("stderr", -12)):
        if getattr(sys, name) is not None:
            continue
        handle = get_handle(number)
        if handle and handle != ctypes.c_void_p(-1).value:
            fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
            stream = os.fdopen(fd, "w", encoding="utf-8", errors="replace", buffering=1)
        else:
            stream = open(os.devnull, "w", encoding="utf-8")
        setattr(sys, name, stream)


def main(args: list[str]) -> int:
    _restore_windows_output()
    for key in tuple(os.environ):
        if key.startswith("PIP_"):
            del os.environ[key]
    os.environ["PIP_CONFIG_FILE"] = os.devnull

    try:
        return _run_pip(args)
    except Exception:
        traceback.print_exc()
        return 1


def _run_pip(args: list[str]) -> int:
    from pip._vendor import distlib
    from pip._vendor.distlib import resources

    # The frozen loader still stores distlib's launcher resources on disk.
    resources.register_finder(distlib.__loader__, resources.ResourceFinder)

    from pip._internal.cli.main import main as pip_main
    from pip._internal.exceptions import InstallationError
    from pip._internal.operations.prepare import RequirementPreparer

    # pip's format filter does not cover direct links declared in wheel metadata.
    prepare = RequirementPreparer.prepare_linked_requirement

    def prepare_wheel(self, req, *args, **kwargs):
        if req.link is None or not req.link.is_wheel:
            raise InstallationError(f"A compatible wheel is required for {req.name or req}")
        return prepare(self, req, *args, **kwargs)

    RequirementPreparer.prepare_linked_requirement = prepare_wheel
    return pip_main(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
