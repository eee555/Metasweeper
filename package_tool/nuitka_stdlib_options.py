"""Emit Nuitka options for standard-library modules used by dynamic plugins."""
from importlib.util import find_spec
import sys


def main() -> None:
    options = []
    for name in sorted(sys.stdlib_module_names):
        if name in {"test", "tests", "unittest", "_tkinter", "tkinter", "idlelib", "lib2to3"} or name.startswith(("test_", "_test")):
            continue
        try:
            spec = find_spec(name)
        except (ImportError, ModuleNotFoundError, ValueError):
            continue
        if spec is None or spec.origin in {"built-in", "frozen"}:
            continue
        option = "include-package" if spec.submodule_search_locations is not None else "include-module"
        options.append(f"--{option}={name}")
    print(" ".join(options))


if __name__ == "__main__":
    main()
