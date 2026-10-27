from __future__ import annotations

import subprocess
import sys
from email.message import Message
from pathlib import Path, PureWindowsPath


MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
SUPPORTED_SUFFIXES = {".avf", ".evf", ".evfs", ".mvf", ".rmv"}


def replay_suffix(content_disposition: str, content_type: str) -> str:
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type.startswith("text/") or media_type in {"application/json", "application/problem+json"}:
        raise ValueError(
            "Server returned a page or API error instead of a replay")
    message = Message()
    message["Content-Disposition"] = content_disposition
    filename = message.get_filename() or ""
    suffix = PureWindowsPath(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("Missing or unsupported replay filename")
    return suffix


def playback_command(replay_path: Path, executable_dir: Path) -> list[str]:
    main_py = executable_dir / "src" / "main.py"
    if main_py.is_file():
        return [sys.executable, str(main_py), str(replay_path)]
    for name in ("metasweeper.exe", "metaminsweeper.exe"):
        executable = executable_dir / name
        if executable.is_file():
            return [str(executable), str(replay_path)]
    raise FileNotFoundError(
        "Cannot find src/main.py, metasweeper.exe or metaminsweeper.exe")


def play_replay(replay_path: Path, executable_dir: Path) -> None:
    subprocess.Popen(playback_command(replay_path, executable_dir))
