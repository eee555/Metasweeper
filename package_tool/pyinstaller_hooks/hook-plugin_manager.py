"""Collect the Python standard library for dynamically imported plugins."""
from __future__ import annotations

from importlib.util import find_spec
import sys
from sys import stdlib_module_names

from PyInstaller.utils.hooks import collect_submodules


_WINDOWS_EXCLUDES = {"_tkinter", "tkinter", "idlelib", "lib2to3"}


def _is_test_module(name: str) -> bool:
    return any(
        part in {"test", "tests", "unittest"}
        or part.startswith(("test_", "_test"))
        for part in name.split(".")
    )


hiddenimports: list[str] = []
for module_name in sorted(stdlib_module_names):
    if _is_test_module(module_name) or (sys.platform == "win32" and module_name in _WINDOWS_EXCLUDES):
        continue
    try:
        spec = find_spec(module_name)
    except (ImportError, ModuleNotFoundError, ValueError):
        continue
    if spec is None:
        continue
    hiddenimports.append(module_name)
    if spec.submodule_search_locations is not None:
        hiddenimports.extend(
            collect_submodules(module_name, filter=lambda name: not _is_test_module(name))
        )
