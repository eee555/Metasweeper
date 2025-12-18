import sys
import subprocess
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
import signal

class PluginProcess(object):

    def __init__(self, plugin_path: Path) -> None:
        self.__plugin_path = plugin_path
        self._process: Optional[subprocess.Popen] = None
        self.__pid: int
        self.plugin_dir_name = plugin_path.parent.parent.name
        self.plugin_name = plugin_path.name.split(".")[0]

    @property
    def pid(self):
        return self.__pid

    @property
    def plugin_path(self):
        return self.__plugin_path

    def start(self, host: str, port: int, env: Dict[str, str]):
        if self._process is not None:
            return
        module = f"{self.plugin_dir_name}.{self.plugin_name}.{self.plugin_name}"
        if self.__plugin_path.suffix == ".py":
            self._process = subprocess.Popen(
                [
                    sys.executable,
                    str(self.__plugin_path),
                    host,
                    str(port),
                ],
                env=env,
            )
        else:
            self._process = subprocess.Popen(
                [
                    self.__plugin_path,
                    host,
                    str(port),
                ],
            )
        self.__pid = self._process.pid

    def stop(self):
        if self._process is None:
            return
        if self._process.poll() is None:
            if sys.platform == "win32":
                self._process.kill()
            else:
                self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
