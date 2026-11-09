"""皮肤 / 音效包 zip 导入（共用、与皮肤和音效逻辑均独立）。

把用户选的 zip 解压到**插件自己的数据目录**下，而不是让用户手填外部目录：
- 皮肤包 -> `<插件数据目录>/skins/<包名>/`
- 音效包 -> `<插件数据目录>/sounds/<包名>/`

安全性参照 `plugin_manager/plugin_download.py` 的做法：
拒绝绝对路径、`..`、非法字符、符号链接、超大文件与 zip-slip。
"""
from __future__ import annotations

import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import ClassVar

from PySide6.QtWidgets import QFileDialog

from plugin_sdk.config_types.base_config import BaseConfig, ConfigWidgetBase

# 防护上限
_MAX_SINGLE_BYTES = 8 * 1024 * 1024       # 单文件 8 MB
_MAX_TOTAL_BYTES = 32 * 1024 * 1024       # 单次解压 32 MB
_MAX_ENTRIES = 512
_CHUNK = 64 * 1024

# 允许的包内资源后缀（防止塞入可执行脚本）
_ALLOWED_SUFFIXES = {
    ".svg", ".png", ".jpg", ".jpeg", ".wav", ".ogg", ".mp3",
    ".json", ".txt", ".md", ".ico", ".webp", ".gif",
}


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


def _safe_entries(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    entries = zf.infolist()
    if not entries:
        raise ZipImportError("压缩包为空")
    if len(entries) > _MAX_ENTRIES:
        raise ZipImportError(f"文件数超过上限 {_MAX_ENTRIES}")
    total = 0
    for entry in entries:
        path = PurePosixPath(entry.filename)
        if (path.is_absolute() or ".." in path.parts or not path.parts
                or re.search(r'[\\:<>"|?*\x00-\x1f]', entry.filename)
                or any(p.endswith((".", " ")) for p in path.parts)
                or stat.S_ISLNK(entry.external_attr >> 16)):
            raise ZipImportError("压缩包包含不安全的路径或符号链接")
        if entry.is_dir():
            continue
        if PurePosixPath(entry.filename).suffix.lower() not in _ALLOWED_SUFFIXES:
            raise ZipImportError(f"不允许的文件类型: {entry.filename}")
        if entry.file_size > _MAX_SINGLE_BYTES:
            raise ZipImportError(f"单文件过大: {entry.filename}")
        total += entry.file_size
        if total > _MAX_TOTAL_BYTES:
            raise ZipImportError("解压后总大小超过 32 MB")
    return entries


def import_zip(zip_path: Path | str, target_root: Path, *,
               pack_name: str | None = None) -> ImportResult:
    """把 zip 解压到 `target_root/<包名>/`，返回导入结果。

    zip 里若只有一层根目录（如 `my_skin/cellup.svg`），自动剥掉该层；
    包名默认取 zip 文件名（去后缀）。已存在同名包时整体覆盖。
    """
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise ZipImportError(f"找不到文件: {zip_path}")

    with zipfile.ZipFile(zip_path) as zf:
        entries = _safe_entries(zf)
        # 只有一层公共根目录时剥掉该层，并用它作为包名（比 zip 文件名更贴合
        # 包内 sound.json / skin.json 的语义），否则用 zip 文件名。
        roots = {PurePosixPath(e.filename).parts[0] for e in entries
                 if PurePosixPath(e.filename).parts}
        strip = len(roots) == 1 and all(
            len(PurePosixPath(e.filename).parts) > 1 or e.is_dir()
            for e in entries)
        prefix = next(iter(roots)) if strip else ""
        raw_name = pack_name or (prefix if strip else zip_path.stem)

    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", raw_name).strip(". ")
    if not name or name.startswith("_"):
        raise ZipImportError("包名无效（不能为空或以下划线开头）")

    target_root = Path(target_root)
    target_root.mkdir(parents=True, exist_ok=True)
    dest = target_root / name

    with zipfile.ZipFile(zip_path) as zf:
        # 先写到临时目录，全部成功后再替换，避免半途失败留下半包
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory(dir=str(target_root)) as tmp:
            staging = Path(tmp) / name
            count = 0
            for entry in entries:
                parts = PurePosixPath(entry.filename).parts
                if strip and parts and parts[0] == prefix:
                    parts = parts[1:]
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

            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(staging), str(dest))

    # 读包内 meta 的显示名
    display = name
    for meta_name in ("skin.json", "sound.json"):
        meta = dest / meta_name
        if meta.is_file():
            try:
                import json
                data = json.loads(meta.read_text(encoding="utf-8"))
                display = str(data.get("name") or name)
            except (OSError, ValueError, TypeError):
                pass
            break
    return ImportResult(pack_name=name, files=count, display=display)


@dataclass
class ZipImportConfig(BaseConfig[str]):
    """自定义配置：一个「导入 zip」按钮，导入到指定的插件数据子目录。

    `target_subdir` 决定解压位置（相对插件数据目录）。控件把导入结果
    以 JSON 字符串保存为配置值，从而触发 `config_changed` 让插件刷新下拉框。
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
                self._value = default or ""
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(6)
                self._status = QLabel("尚未导入")
                self._status.setWordWrap(True)
                layout.addWidget(self._status, 1)
                btn = QPushButton(button_text)
                btn.clicked.connect(self._on_import)
                layout.addWidget(btn)
                if description:
                    self.setToolTip(description)
                self.set_value(self._value)

            def _data_root(self) -> Path:
                from plugin_manager.app_paths import get_plugin_data_dir
                # 插件类名固定，直接从 app_paths 拿数据目录，避免依赖插件实例
                return get_plugin_data_dir("SkinManagerPlugin") / target_subdir

            def _on_import(self) -> None:
                path, _ = QFileDialog.getOpenFileName(
                    self, "选择 zip 包", "", "Zip 文件 (*.zip);;所有文件 (*)")
                if not path:
                    return
                try:
                    result = import_zip(path, self._data_root())
                except ZipImportError as exc:
                    self._status.setText(f"导入失败：{exc}")
                    return
                except Exception as exc:
                    self._status.setText(f"导入失败：{exc}")
                    return
                self._status.setText(
                    f"已导入「{result.display}」({result.files} 个文件)")
                import json
                self._value = json.dumps(result.to_storage(),
                                         ensure_ascii=False)
                self.value_change.emit(self.get_value())

            def get_value(self) -> str:
                return self._value

            def set_value(self, value: str) -> None:
                self._value = str(value) if value else ""
                if self._value:
                    try:
                        import json
                        data = json.loads(self._value)
                        r = ImportResult.from_storage(data)
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
