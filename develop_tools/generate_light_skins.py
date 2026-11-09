"""生成两套内置浅色皮肤：雾凇白与奶油暖白。

复用 generate_skin.py 的图形几何，只切换配色与统一 frame.svg。
用法（项目根目录）：python develop_tools/generate_light_skins.py
"""
from __future__ import annotations

import json
from pathlib import Path

import generate_skin as base

ROOT = (Path(__file__).resolve().parent.parent
        / "src" / "plugins" / "skin_manager" / "skins")


def make_frame_svg(
    top: str,
    middle: str,
    bottom: str,
    motif: str,
) -> str:
    """生成不含固定边框线的整幅柔和纹理，避免与控件布局错位。"""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
  <defs>
    <linearGradient id="base" x1="0" y1="0" x2="0.9" y2="1">
      <stop offset="0" stop-color="{top}"/>
      <stop offset="0.56" stop-color="{middle}"/>
      <stop offset="1" stop-color="{bottom}"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="800" fill="url(#base)"/>
    {motif}
</svg>
'''


THEMES = (
    {
        "directory": "frost_white",
        "name": "雾凇白",
        "note": "冷调浅灰蓝：霜白凸面、冰蓝整幅背景、清晰高对比数字",
        "colors": {
            "cover_top": "#FFFFFF", "cover_face": "#C5D3DF",
            "cover_dark": "#8296A8", "open_bg": "#E7EEF3",
            "open_edge": "#A7B9C8", "grid": "#B9C8D4",
            "numbers": {
                1: "#1769AA", 2: "#2D7A45", 3: "#C43E3E", 4: "#59449B",
                5: "#A55D12", 6: "#007E88", 7: "#3E4E9A", 8: "#374653",
            },
            "led_bg": "#202D38", "led_off": "#55464B", "led_on": "#FF7868",
            "face_bg": "#E7EEF3", "face_hi": "#FFFFFF", "face_lo": "#8296A8",
            "face_yellow": "#F5CD63", "face_line": "#4A3B22",
            "mine": "#17212A", "mine_highlight": "#62BFE2",
            "frame": "#8599A9", "text": "#293A49", "flag_bg": "#E7EEF3",
            "sb_bg": "#F4F7F9", "sb_text": "#293A49", "sb_grid": "#C3D0DA",
            "sb_header": "#D4E0E8",
            "svg_top": "#EAF2F7", "svg_mid": "#DCE7EE", "svg_bottom": "#C9D8E3",
            "motif": '''<g fill="none" stroke="#6FA9C7" stroke-width="5" stroke-linecap="round" opacity="0.30"><path d="M1030 55v210m-91-157 182 105m0-105L939 213m91-158-26 38m26-38 26 38m-117 67 45 3m-45-3 15 40m182-40-45 3m45-3-15 40m-117 67-26-38m26 38 26-38"/><path d="M140 565v145m-63-109 126 73m0-73-126 73m63-109-18 27m18-27 18 27m-81 39 31 2m-31-2 11 29m126-29-31 2m31-2-11 29"/></g><path d="M700 0Q850 60 960 0M760 0Q880 38 1000 0" fill="none" stroke="#83C5DF" stroke-width="18" opacity="0.12"/>''',
        },
    },
    {
        "directory": "cream_light",
        "name": "奶油暖白",
        "note": "暖调浅米色：奶油凸面、燕麦色背景、暖金 LED 与柔和棕色文字",
        "colors": {
            "cover_top": "#FFFDF7", "cover_face": "#D5C7B2",
            "cover_dark": "#9E8C75", "open_bg": "#F2EBDD",
            "open_edge": "#C9B99F", "grid": "#D8CBB7",
            "numbers": {
                1: "#346A9A", 2: "#47784B", 3: "#B7473B", 4: "#67529A",
                5: "#9B6D1F", 6: "#287A75", 7: "#8B4268", 8: "#51463A",
            },
            "led_bg": "#302820", "led_off": "#655448", "led_on": "#F09A4B",
            "face_bg": "#F2EBDD", "face_hi": "#FFFDF7", "face_lo": "#9E8C75",
            "face_yellow": "#F2C35C", "face_line": "#51402A",
            "mine": "#302820", "mine_highlight": "#E2A347",
            "frame": "#A99578", "text": "#4C4033", "flag_bg": "#F2EBDD",
            "sb_bg": "#FBF7EF", "sb_text": "#4C4033", "sb_grid": "#D8CBB7",
            "sb_header": "#E7DCC9",
            "svg_top": "#F8F3E8", "svg_mid": "#EFE6D5", "svg_bottom": "#E3D7C3",
            "motif": '''<g fill="none" stroke="#92744E" stroke-width="4" stroke-linecap="round" opacity="0.27"><path d="M66 790C115 690 97 565 34 442M72 707c-33-22-52-52-56-91m72 50c36-27 52-60 49-99m-91-13c-31-18-48-45-49-78m53 43c29-22 41-51 38-82m-58-20c-24-15-37-38-37-65m47 191 31-32m-59-87 31-29m106 153 35-30m838-386c-59 105-66 226-20 360m-12-258c-34-19-52-48-55-86m72 147c37-25 55-58 55-99m-43 171c-31-15-50-41-57-76m77 142c33-23 50-53 51-91"/></g><g fill="#B69A70" opacity="0.25"><ellipse cx="49" cy="553" rx="17" ry="38" transform="rotate(-43 49 553)"/><ellipse cx="104" cy="615" rx="16" ry="35" transform="rotate(38 104 615)"/><ellipse cx="1090" cy="127" rx="17" ry="38" transform="rotate(-38 1090 127)"/><ellipse cx="1150" cy="218" rx="16" ry="35" transform="rotate(38 1150 218)"/></g>''',
        },
    },
)


def generate(theme: dict) -> None:
    c = theme["colors"]
    base.OUT = ROOT / theme["directory"]
    base.COVER_TOP = c["cover_top"]
    base.COVER_FACE = c["cover_face"]
    base.COVER_DARK = c["cover_dark"]
    base.OPEN_BG = c["open_bg"]
    base.OPEN_EDGE = c["open_edge"]
    base.GRID = c["grid"]
    base.NUM_COLORS = c["numbers"]
    base.LED_BG = c["led_bg"]
    base.LED_OFF = c["led_off"]
    base.LED_ON = c["led_on"]
    base.FACE_BG = c["face_bg"]
    base.FACE_HI = c["face_hi"]
    base.FACE_LO = c["face_lo"]
    base.FACE_YELLOW = c["face_yellow"]
    base.FACE_LINE = c["face_line"]
    base.MINE_COLOR = c["mine"]
    base.MINE_HIGHLIGHT = c["mine_highlight"]
    base.COLORS = {
        "frame": c["frame"], "text": c["text"], "flag_bg": c["flag_bg"],
        "sb_bg": c["sb_bg"], "sb_text": c["sb_text"],
        "sb_grid": c["sb_grid"], "sb_header": c["sb_header"],
    }
    base.FRAME_SVG = make_frame_svg(
        c["svg_top"], c["svg_mid"], c["svg_bottom"],
        c["motif"],
    )
    base.main()

    metadata = {
        "name": theme["name"], "author": "MetaSweeper",
        "version": "1.0.0", "note": theme["note"],
    }
    (base.OUT / "skin.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    for theme in THEMES:
        generate(theme)


if __name__ == "__main__":
    main()
