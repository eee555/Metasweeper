"""
皮肤包加载：把磁盘上的皮肤目录读成 SetSkinCommand 的字节字段。

皮肤包只是插件自己的资源目录，主进程从不读它们；所有图片字节通过
ZMQ 发送，由主进程解码进内存。皮肤切换不需要重启、不写用户配置目录。

目录结构（文件名固定，缺项即沿用默认资源）：
    skins/<name>/
        cellup.svg cell1.svg ... cell8.svg celldown.svg
        cellflag.svg cellquestion.svg cellmine.svg blast.svg falsemine.svg mine.svg
        LED0.png ... LED9.png
        smileface.svg clickface.svg lostface.svg winface.svg smilefacedown.svg
        frame.svg           # 可选：统一的大幅主窗口框架背景
        colors.json         # 可选：主窗口框架配色 {"window": "#1B3A5C", ...}
        skin.json           # 可选：{"name": "...", ...} 仅用于列表显示
"""
from __future__ import annotations

import json
from pathlib import Path

from shared_types.commands import SetSkinCommand, SKIN_COLOR_KEYS

# key -> 文件名
CELL_FILES: dict[int, str] = {
    0: "celldown.svg", 1: "cell1.svg", 2: "cell2.svg", 3: "cell3.svg",
    4: "cell4.svg", 5: "cell5.svg", 6: "cell6.svg", 7: "cell7.svg",
    8: "cell8.svg", 10: "cellup.svg", 11: "cellflag.svg",
    14: "falsemine.svg", 15: "blast.svg", 16: "cellmine.svg",
    17: "cellquestion.svg", 100: "mine.svg",
}
LED_FILES: dict[int, str] = {i: f"LED{i}.png" for i in range(10)}
# 注意：这里的 14..18 是 FACE_* 常量，与格子 key 无关
FACE_FILES: dict[int, str] = {
    14: "smileface.svg", 15: "clickface.svg", 16: "lostface.svg",
    17: "winface.svg", 18: "smilefacedown.svg",
}
COLORS_FILE = "colors.json"
FRAME_SVG_FILE = "frame.svg"


def list_skins(root: Path) -> list[tuple[str, str]]:
    """返回 [(目录名, 显示名), ...]，按目录名排序。"""
    if not root.is_dir():
        return []
    result: list[tuple[str, str]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        display = child.name
        meta = child / "skin.json"
        if meta.is_file():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                display = str(data.get("name") or child.name)
            except (OSError, ValueError, TypeError):
                pass
        result.append((child.name, display))
    return result


def find_skin_folder(roots: list[Path], skin_name: str) -> Path | None:
    """按优先级在多个皮肤库根目录里查找皮肤目录。"""
    for root in roots:
        folder = root / skin_name
        if folder.is_dir():
            return folder
    return None


def build_command(roots: list[Path], skin_name: str) -> SetSkinCommand:
    """读取指定皮肤目录，构造 SetSkinCommand；缺的文件不加入（沿用默认）。"""
    folder = find_skin_folder(roots, skin_name)
    if folder is None:
        return SetSkinCommand(reset=True)

    cells: dict[int, bytes] = {}
    leds: dict[int, bytes] = {}
    faces: dict[int, bytes] = {}

    for mapping, target in ((CELL_FILES, cells), (LED_FILES, leds),
                            (FACE_FILES, faces)):
        for key, filename in mapping.items():
            path = folder / filename
            if path.is_file():
                target[key] = path.read_bytes()

    colors: dict[str, str] = {}
    colors_path = folder / COLORS_FILE
    if colors_path.is_file():
        try:
            raw = json.loads(colors_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                colors = {
                    str(k): str(v) for k, v in raw.items()
                    if k in SKIN_COLOR_KEYS and isinstance(v, str)
                }
        except (OSError, ValueError, TypeError):
            colors = {}

    frame_svg_path = folder / FRAME_SVG_FILE
    frame_svg = frame_svg_path.read_bytes() if frame_svg_path.is_file() else None

    return SetSkinCommand(
        cells=cells, leds=leds, faces=faces, colors=colors,
        frame_svg=frame_svg)
