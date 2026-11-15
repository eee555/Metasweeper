"""PyInstaller compatibility entry point; CLI logic lives in ``__main__``."""
from __future__ import annotations

import os
import sys

# Set high-DPI attributes before importing the shared entry point (and Qt).
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

from . import __main__ as _entry

_MUTEX_NAME = _entry._MUTEX_NAME
_mutex_handle = _entry._mutex_handle
_core_acquire_mutex = _entry._acquire_mutex


def _acquire_mutex() -> bool:
    """Compatibility alias used by older embedding code and tests."""
    global _mutex_handle
    result = _core_acquire_mutex()
    _mutex_handle = _entry._mutex_handle
    return result


def main() -> int:
    """Run the shared CLI implementation while honoring compatibility patches."""
    global _mutex_handle
    _entry._mutex_handle = _mutex_handle
    original_acquire_mutex = _entry._acquire_mutex
    _entry._acquire_mutex = _acquire_mutex
    try:
        return _entry.main()
    finally:
        _entry._acquire_mutex = original_acquire_mutex
        _mutex_handle = _entry._mutex_handle


if __name__ == "__main__":
    sys.exit(main())
