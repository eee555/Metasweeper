"""Track the game process across plugin manager restarts."""
from __future__ import annotations

import os
import sys


class HostLifetime:
    def __init__(self, pid: int):
        self.pid = pid
        self._handle = None
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self._kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            self._kernel.OpenProcess.restype = wintypes.HANDLE
            self._kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            self._kernel.WaitForSingleObject.restype = wintypes.DWORD
            self._kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            self._handle = self._kernel.OpenProcess(0x100000, False, pid)

    def is_alive(self) -> bool:
        if sys.platform == "win32":
            return bool(self._handle) and self._kernel.WaitForSingleObject(self._handle, 0) == 0x102
        try:
            os.kill(self.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def close(self) -> None:
        if self._handle:
            self._kernel.CloseHandle(self._handle)
            self._handle = None
