"""在奶油暖白和石墨夜底图上分别生成无数字彩色圆点线索格。

每套只替换 cell1.svg–cell8.svg，其余图像、SVG 和 colors.json 都从对应原皮肤复制。
运行：python develop_tools/generate_color_only_skins.py
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = (Path(__file__).resolve().parent.parent
        / "src" / "plugins" / "skin_manager" / "skins")

THEMES = (
    {
        "directory": "color_only_light",
        "base": "cream_light",
        "name": "纯色线索（奶油暖白）",
        "note": "沿用奶油暖白的全部资源，仅将 1–8 数字格改为标准颜色圆点",
        "dot_outline": "none",
        "background": "#F8F3E8", "tile": "#F2EBDD", "edge": "#C9B99F",
    },
    {
        "directory": "color_only_dark",
        "base": "graphite_night",
        "name": "纯色线索（石墨夜）",
        "note": "沿用石墨夜的全部资源，仅将 1–8 数字格改为带浅色描边的标准颜色圆点",
        "dot_outline": "#D8E0E6",
        "background": "#252D36", "tile": "#252D36", "edge": "#13191F",
    },
)

CLUE_COLORS = ("#0000FF", "#008000", "#FF0000", "#000080",
               "#800000", "#008080", "#000000", "#808080")


def _color_clue_svg(source_path: Path, color: str, outline: str) -> str:
    """Preserve the base skin's opened-cell art and replace only its numeral with a dot."""
    source = source_path.read_text(encoding="utf-8")
    source, count = re.subn(
        r"\s*<text\b[^>]*>.*?</text>\s*", "\n", source,
        count=1, flags=re.DOTALL,
    )
    if count != 1:
        raise ValueError(f"未找到唯一的数字文本: {source_path}")
    dot = (
        f'<circle cx="80" cy="80" r="34" fill="{color}" '
        f'stroke="{outline}" stroke-width="3"/>\n'
    )
    return source.replace("</svg>", dot + "</svg>")


def _write_preview(
    directory: Path, colors: tuple[str, ...], background: str, tile_color: str,
    edge: str, outline: str,
) -> None:
    image = Image.new("RGB", (640, 360), background)
    draw = ImageDraw.Draw(image)
    margin, gap = 48, 14
    size = 112
    for index, color in enumerate(colors):
        row, column = divmod(index, 4)
        x = margin + column * (size + gap)
        y = 61 + row * (size + gap)
        draw.rectangle((x, y, x + size, y + size), fill=tile_color, outline=edge, width=3)
        radius = 25
        center_x, center_y = x + size // 2, y + size // 2
        bounds = (center_x - radius, center_y - radius,
                  center_x + radius, center_y + radius)
        if outline == "none":
            draw.ellipse(bounds, fill=color)
        else:
            draw.ellipse(bounds, fill=color, outline=outline, width=3)
    image.save(directory / "preview.png", "PNG")


def generate(theme: dict[str, object]) -> None:
    directory = ROOT / str(theme["directory"])
    base_directory = ROOT / str(theme["base"])
    directory.mkdir(parents=True, exist_ok=True)

    varying_cells = {f"cell{number}.svg" for number in range(1, 9)}
    generated_files = varying_cells | {"skin.json", "preview.png"}
    for path in base_directory.iterdir():
        if path.is_file() and path.name not in generated_files:
            shutil.copy2(path, directory / path.name)

    dot_outline = str(theme["dot_outline"])
    for number, color in enumerate(CLUE_COLORS, start=1):
        source_cell = base_directory / f"cell{number}.svg"
        (directory / source_cell.name).write_text(
            _color_clue_svg(source_cell, color, dot_outline), encoding="utf-8",
        )

    metadata = {
        "name": theme["name"], "author": "MetaSweeper",
        "version": "1.0.0", "note": theme["note"],
    }
    (directory / "skin.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    _write_preview(
        directory, CLUE_COLORS, str(theme["background"]), str(theme["tile"]),
        str(theme["edge"]), dot_outline,
    )


def main() -> None:
    for theme in THEMES:
        generate(theme)
        print(f"已生成 {theme['name']} -> {ROOT / theme['directory']}")


if __name__ == "__main__":
    main()
