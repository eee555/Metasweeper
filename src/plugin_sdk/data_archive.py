"""安全地打包和恢复插件数据目录。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import shutil
import stat
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile


class DataArchiveError(ValueError):
    """插件数据归档格式或路径不安全。"""


def _safe_member_path(name: str) -> Path:
    path = Path(name)
    if not name or path.is_absolute() or path.drive:
        raise DataArchiveError(f"Invalid archive path: {name!r}")
    parts = Path(name.replace("\\", "/")).parts
    if any(part in ("", ".", "..") for part in parts):
        raise DataArchiveError(f"Invalid archive path: {name!r}")
    return Path(*parts)


def _is_symlink(info) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def export_directory(directory: Path) -> bytes:
    """Return a ZIP containing every regular file and empty directory."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(directory).as_posix()
            if path.is_symlink():
                continue
            if path.is_dir():
                if not any(path.iterdir()):
                    archive.writestr(relative + "/", b"")
            elif path.is_file():
                archive.write(path, relative)
    return output.getvalue()


def import_directory(directory: Path, archive_data: bytes) -> None:
    """Merge a validated ZIP archive into ``directory``.

    Extraction happens in a temporary directory first, so malformed or unsafe
    archives cannot modify the live plugin data directory. Files with matching
    paths are overwritten; files absent from the archive are retained.
    """
    directory = Path(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="plugin-data-") as staging:
        staging_path = Path(staging)
        try:
            with ZipFile(BytesIO(archive_data)) as archive:
                for info in archive.infolist():
                    name = info.filename.rstrip("/")
                    if not name:
                        continue
                    relative = _safe_member_path(name)
                    if _is_symlink(info):
                        raise DataArchiveError(f"Symbolic links are not allowed: {info.filename!r}")
                    target = staging_path / relative
                    if info.is_dir() or info.filename.endswith("/"):
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
        except DataArchiveError:
            raise
        except Exception as exc:
            raise DataArchiveError(f"Invalid plugin data archive: {exc}") from exc

        directory.mkdir(parents=True, exist_ok=True)
        for child in staging_path.iterdir():
            target = directory / child.name
            if child.is_dir():
                shutil.copytree(child, target, dirs_exist_ok=True)
            else:
                shutil.copy2(child, target)
