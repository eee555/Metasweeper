"""皮肤 / 音效包 zip 导入（共用、与皮肤和音效逻辑均独立）。

把用户选的 zip 解压到**插件自己的数据目录**下，而不是让用户手填外部目录：
- 皮肤包 -> `<插件数据目录>/skins/<包名>/`
- 音效包 -> `<插件数据目录>/sounds/<包名>/`

安全性参照 `plugin_manager/plugin_download.py` 的做法：
拒绝绝对路径、`..`、非法字符、Windows 保留设备名、符号链接、超大文件与
zip-slip。上限按目标类型区分，与主进程 skin_applier 的解码上限对齐，避免
「导入成功、应用失败」。
"""
from __future__ import annotations

import os
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import ClassVar

from PySide6.QtWidgets import QFileDialog

from plugin_sdk.config_types.base_config import BaseConfig, ConfigWidgetBase
from utils.app_logger import logger

# 防护上限：按目标类型区分（与主进程 skin_applier.py 的 512KB/4MB 对齐）
_LIMITS = {
    "skins": (512 * 1024, 4 * 1024 * 1024),
    "sounds": (8 * 1024 * 1024, 32 * 1024 * 1024),
}
_MAX_ENTRIES = 512
_CHUNK = 64 * 1024

# 允许的包内资源后缀（防止塞入可执行脚本）；只保留固定文件名格式会用到的
_ALLOWED_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".wav", ".json"}

# 已知资源文件：用于「资源根定位」，避免顶层 README 或 images/ 子目录
# 让包被解成不可加载的结构（此前插件仍提示「已应用」的静默失败）。
_KNOWN_RESOURCE_SUFFIXES = (".svg", ".png", ".jpg", ".jpeg", ".wav")
_KNOWN_META_NAMES = ("skin.json", "sound.json", "colors.json")


class ZipImportError(ValueError):
    """zip 包校验/解压失败"""


def imported_dir(subdir: str) -> Path:
    """插件数据目录下某类资源的导入落地目录（会自动创建）。

    `SkinManagerPlugin` 是固定的插件类名，与 `BasePlugin.data_dir` 一致。
    """
    from plugin_manager.app_paths import get_plugin_data_dir
    path = get_plugin_data_dir("SkinManagerPlugin") / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class ImportResult:
    """一次导入的结果，作为配置值保存（JSON 可序列化）。"""

    pack_name: str = ""
    files: int = 0
    display: str = ""

    def to_storage(self) -> dict:
        return {
            "pack_name": self.pack_name,
            "files": self.files,
            "display": self.display,
        }

    @classmethod
    def from_storage(cls, data) -> "ImportResult":
        if not isinstance(data, dict):
            return cls()
        return cls(
            pack_name=str(data.get("pack_name") or ""),
            files=int(data.get("files") or 0),
            display=str(data.get("display") or ""),
        )


def _safe_entries(zf: zipfile.ZipFile, target_subdir: str) -> list[zipfile.ZipInfo]:
    entries = zf.infolist()
    if not entries:
        raise ZipImportError("压缩包为空")
    if len(entries) > _MAX_ENTRIES:
        raise ZipImportError(f"文件数超过上限 {_MAX_ENTRIES}")
    max_single, max_total = _LIMITS.get(
        target_subdir, _LIMITS["sounds"])
    total = 0
    for entry in entries:
        path = PurePosixPath(entry.filename)
        if (path.is_absolute() or ".." in path.parts or not path.parts
                or re.search(r'[\\:<>"|?*\x00-\x1f]', entry.filename)
                or any(p.endswith((".", " ")) or Path(p).is_reserved()
                       for p in path.parts)
                or stat.S_ISLNK(entry.external_attr >> 16)):
            # is_reserved() 拦 CON.svg / NUL.json 等 Windows 保留设备名，
            # 此前参照 plugin_download.py 时漏掉了这一项。
            raise ZipImportError("压缩包包含不安全的路径或符号链接")
        if entry.is_dir():
            continue
        if PurePosixPath(entry.filename).suffix.lower() not in _ALLOWED_SUFFIXES:
            raise ZipImportError(f"不允许的文件类型: {entry.filename}")
        if entry.file_size > max_single:
            raise ZipImportError(
                f"单文件过大（上限 {max_single // 1024} KB）: {entry.filename}")
        total += entry.file_size
        if total > max_total:
            raise ZipImportError(
                f"解压后总大小超过上限 {max_total // 1024 // 1024} MB")
    return entries


def _resource_root(staging: Path) -> Path:
    """在解出的目录里定位真正含资源的子目录。

    常见 zip 结构（顶层多一个 README.md、或资源放在 images/ 子目录）此前
    会让剥层逻辑失效，解出一个空壳包：插件仍提示「已应用（格子 0、LED 0）」，
    主进程什么都不改却返回 success=True。这里改为按内容定位资源根。
    """
    def score(folder: Path) -> int:
        try:
            names = [p.name for p in folder.iterdir() if p.is_file()]
        except OSError:
            return 0
        return (sum(n.lower().endswith(_KNOWN_RESOURCE_SUFFIXES) for n in names)
                + 10 * sum(n in _KNOWN_META_NAMES for n in names))

    best, best_score = staging, score(staging)
    try:
        for folder in staging.rglob("*"):
            if not folder.is_dir() or folder.name.startswith("_"):
                continue
            s = score(folder)
            if s > best_score:
                best, best_score = folder, s
    except OSError:
        pass
    return best


def import_zip(zip_path: Path | str, target_root: Path) -> ImportResult:
    """把 zip 解压到 `target_root/<包名>/`，返回导入结果。

    已存在同名包时先备份旧包再替换，任一步失败都回滚，避免「旧包已删、
    新包未就位」的数据丢失。临时目录建在 target_root 之外且以 `_` 开头，
    避免解压期间被 list_skins/list_packs 当成幽灵皮肤包扫进下拉框。
    """
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise ZipImportError(f"找不到文件: {zip_path}")
    target_root = Path(target_root)
    target_subdir = target_root.name or "sounds"

    with zipfile.ZipFile(zip_path) as zf:
        entries = _safe_entries(zf, target_subdir)

    # 包名优先取「唯一顶层目录」（与旧行为一致，用户惯用 my_pack/xxx.zip），
    # 否则回退 zip 文件名。顶层多个目录/文件时用文件名，避免歧义。
    roots = {PurePosixPath(e.filename).parts[0] for e in entries
             if PurePosixPath(e.filename).parts}
    raw_name = next(iter(roots)) if len(roots) == 1 else zip_path.stem
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", raw_name).strip(". ")
    if (not name or name.startswith("_") or Path(name).is_reserved()
            or name in (".", "..")):
        raise ZipImportError("包名无效（不能为空、下划线开头或保留设备名）")

    target_root.mkdir(parents=True, exist_ok=True)
    dest = target_root / name

    import tempfile
    import shutil
    # 临时目录放到系统临时区（而非被扫描的 target_root），杜绝幽灵选项。
    with tempfile.TemporaryDirectory(prefix="_zipimport_") as tmp:
        staging = Path(tmp) / name
        staging.mkdir(parents=True, exist_ok=True)
        count = 0
        with zipfile.ZipFile(zip_path) as zf:
            for entry in entries:
                parts = PurePosixPath(entry.filename).parts
                if not parts:
                    continue
                out = staging.joinpath(*parts)
                if entry.is_dir():
                    out.mkdir(parents=True, exist_ok=True)
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(entry) as src, out.open("wb") as dst:
                    while chunk := src.read(_CHUNK):
                        dst.write(chunk)
                count += 1

        content_root = _resource_root(staging)
        try:
            has_resource = any(
                p.is_file() and (p.name in _KNOWN_META_NAMES
                                 or p.suffix.lower() in _KNOWN_RESOURCE_SUFFIXES)
                for p in content_root.iterdir()
            )
        except OSError:
            has_resource = False
        if not has_resource:
            raise ZipImportError(
                "压缩包内没有找到任何皮肤/音效资源（可能需要检查目录结构）")

        # 把资源根（可能是 staging 的某个子目录）搬到最终 dest，做事务替换。
        backup = None
        try:
            if dest.exists():
                backup = target_root / f"_backup_{os.getpid()}_{name}"
                if backup.exists():
                    shutil.rmtree(backup)
                os.replace(str(dest), str(backup))
            if content_root != staging:
                shutil.move(str(content_root), str(dest))
            else:
                shutil.move(str(staging), str(dest))
            staging.mkdir(parents=True, exist_ok=True)  # 供 TemporaryDirectory 清理
            if backup is not None:
                shutil.rmtree(backup)
                backup = None
        except Exception as exc:
            logger.warning(f"导入 {name} 失败，正在回滚: {exc}")
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            if backup is not None and backup.exists():
                os.replace(str(backup), str(dest))
            raise ZipImportError(f"写入资源包失败: {exc}") from exc

    # 读包内 meta 的显示名（共享实现已对非 dict JSON 做类型守卫）
    from shared_types.sounds import read_meta_name, SKIN_META_FILE, SOUND_META_FILE
    display = name
    for meta_name in (SKIN_META_FILE, SOUND_META_FILE):
        meta = dest / meta_name
        if meta.is_file():
            display = read_meta_name(meta, name)
            break
    logger.info(f"已导入资源包「{display}」({count} 个文件) -> {dest}")
    return ImportResult(pack_name=name, files=count, display=display)


@dataclass
class ZipImportConfig(BaseConfig[str]):
    """自定义配置：一个「导入 zip」按钮，导入到指定的插件数据子目录。

    导入完成后控件发出 `value_change`，由插件的 `_on_config_changed` 立即
    重扫描下拉框；配置值本身只是一个单调递增的计数（不承载资源内容），
    因此「同名同文件数重导入」也会刷新，且「导入后点取消」不会产生
    「文件已落盘、下拉框永不刷新」的半状态。

    `from_storage` 保留对旧 `config.json` 里 JSON 字符串的兼容读取。
    """

    target_subdir: str = "skins"
    button_text: str = "导入 zip 包"

    widget_type: ClassVar[str] = "zip_import"  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.default = str(self.default) if self.default else ""

    def create_widget(self) -> ConfigWidgetBase:
        target_subdir = self.target_subdir
        button_text = self.button_text

        class ZipImportWidget(ConfigWidgetBase):
            def __init__(self, default: str, description: str, parent=None):
                super().__init__(parent)
                from PySide6.QtWidgets import QHBoxLayout, QPushButton, QLabel
                self._value = str(default or "")
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(6)
                self._status = QLabel("尚未导入")
                self._status.setWordWrap(True)
                layout.addWidget(self._status, 1)
                self._btn = QPushButton(button_text)
                self._btn.clicked.connect(self._on_import)
                layout.addWidget(self._btn)
                if description:
                    self.setToolTip(description)
                self.set_value(self._value)

            def _data_root(self) -> Path:
                from plugin_manager.app_paths import get_plugin_data_dir
                return get_plugin_data_dir("SkinManagerPlugin") / target_subdir

            def _on_import(self) -> None:
                path, _ = QFileDialog.getOpenFileName(
                    self, "选择 zip 包", "", "Zip 文件 (*.zip);;所有文件 (*)")
                if not path:
                    return
                self._btn.setEnabled(False)
                try:
                    result = import_zip(path, self._data_root())
                except ZipImportError as exc:
                    self._status.setText(f"导入失败：{exc}")
                    logger.warning(f"导入 zip 失败: {exc}")
                    return
                except Exception as exc:
                    self._status.setText(f"导入失败：{exc}")
                    logger.warning(f"导入 zip 失败: {exc}")
                    return
                finally:
                    self._btn.setEnabled(True)
                self._status.setText(
                    f"已导入「{result.display}」({result.files} 个文件)")
                # 单调递增，保证每次导入都触发 on_change 重扫描。
                try:
                    n = int(self._value)
                except (TypeError, ValueError):
                    n = 0
                self._value = str(n + 1)
                self.value_change.emit(self.get_value())

            def get_value(self) -> str:
                return self._value

            def set_value(self, value: str) -> None:
                self._value = str(value) if value else ""
                if self._value and self._value.isdigit():
                    self._status.setText("已导入")
                elif self._value:
                    # 兼容旧 config.json：显示历史导入结果
                    try:
                        import json
                        r = ImportResult.from_storage(json.loads(self._value))
                        self._status.setText(
                            f"已导入「{r.display or r.pack_name}」({r.files} 个文件)")
                    except (ValueError, TypeError):
                        self._status.setText("已导入")
                else:
                    self._status.setText("尚未导入")

        return ZipImportWidget(self.default, self.description)

    def to_storage(self, value: str):
        return str(value) if value else ""

    def from_storage(self, data) -> str:
        return str(data) if data else ""
