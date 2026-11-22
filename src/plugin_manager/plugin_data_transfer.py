"""插件数据的管理器级聚合导出与导入。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from io import BytesIO
from pathlib import Path
import re
from typing import Callable
from zipfile import ZIP_DEFLATED, ZipFile

from plugin_sdk.plugin_base import BasePlugin


_FORMAT = "metasweeper-plugin-data"
_VERSION = 1
_NAME_RE = re.compile(r"^[^/\\]+$")


@dataclass
class DataTransferResult:
    succeeded: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed


def _archive_name(name: str) -> str:
    if (not _NAME_RE.fullmatch(name) or name in {".", ".."}
            or any(ord(character) < 32 for character in name)):
        raise ValueError(f"Invalid plugin name: {name!r}")
    return f"plugins/{name}.zip"


def _call_plugin(plugin: BasePlugin, method: str, *args):
    """Run a transfer hook on the plugin thread when it is active."""
    return plugin.call_in_plugin_thread(getattr(plugin, method), *args)


def _validate_plugin_archive(data: bytes) -> None:
    with ZipFile(BytesIO(data)) as plugin_archive:
        if plugin_archive.testzip() is not None:
            raise ValueError("插件数据 ZIP 校验失败")


def export_plugins(
    plugins: dict[str, BasePlugin],
    output: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> DataTransferResult:
    result = DataTransferResult()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with BytesIO() as buffer:
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            manifest = {
                "format": _FORMAT,
                "version": _VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "plugins": [],
            }
            for name, plugin in plugins.items():
                if progress:
                    progress(f"导出插件数据：{name}")
                try:
                    data = _call_plugin(plugin, "export_data")
                    if not isinstance(data, (bytes, bytearray)):
                        raise TypeError("export_data() must return bytes")
                    _validate_plugin_archive(bytes(data))
                    archive_path = _archive_name(name)
                    archive.writestr(archive_path, bytes(data))
                    manifest["plugins"].append({"name": name, "archive": archive_path})
                    result.succeeded.append(name)
                except Exception as exc:
                    result.failed[name] = f"{type(exc).__name__}: {exc}"
            archive.writestr("manifest.json", json.dumps(
                {**manifest, "errors": result.failed},
                ensure_ascii=False, indent=2,
            ).encode("utf-8"))
        output.write_bytes(buffer.getvalue())
    return result


def import_plugins(
    plugins: dict[str, BasePlugin],
    source: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> DataTransferResult:
    result = DataTransferResult()
    with ZipFile(source) as archive:
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except Exception as exc:
            raise ValueError(f"无效的插件数据归档：{exc}") from exc
        if manifest.get("format") != _FORMAT or manifest.get("version") != _VERSION:
            raise ValueError("不支持的插件数据归档版本")
        entries = manifest.get("plugins")
        if not isinstance(entries, list):
            raise ValueError("插件数据归档缺少插件清单")
        for entry in entries:
            name = entry.get("name") if isinstance(entry, dict) else None
            archive_name = entry.get("archive") if isinstance(entry, dict) else None
            if not isinstance(name, str) or not isinstance(archive_name, str):
                result.failed[str(name)] = "插件清单格式错误"
                continue
            if name not in plugins:
                result.skipped.append(name)
                continue
            if archive_name != _archive_name(name) or archive_name not in archive.namelist():
                result.failed[name] = "插件数据条目缺失或路径无效"
                continue
            if progress:
                progress(f"导入插件数据：{name}")
            try:
                data = archive.read(archive_name)
                _validate_plugin_archive(data)
                _call_plugin(plugins[name], "import_data", data)
                result.succeeded.append(name)
            except Exception as exc:
                result.failed[name] = f"{type(exc).__name__}: {exc}"
    return result


def export_plugin(plugin: BasePlugin, name: str, output: Path) -> DataTransferResult:
    """Export one plugin's data as the ZIP returned by its hook."""
    result = DataTransferResult()
    try:
        data = _call_plugin(plugin, "export_data")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("export_data() must return bytes")
        data = bytes(data)
        _validate_plugin_archive(data)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        result.succeeded.append(name)
    except Exception as exc:
        result.failed[name] = f"{type(exc).__name__}: {exc}"
    return result


def import_plugin(plugin: BasePlugin, name: str, source: Path) -> DataTransferResult:
    """Import one plugin ZIP through its data hook."""
    result = DataTransferResult()
    try:
        data = Path(source).read_bytes()
        _validate_plugin_archive(data)
        _call_plugin(plugin, "import_data", data)
        result.succeeded.append(name)
    except Exception as exc:
        result.failed[name] = f"{type(exc).__name__}: {exc}"
    return result
