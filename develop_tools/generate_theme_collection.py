"""生成保留的两套扩展主题：复古绿显和赛博霓虹。

复用 generate_skin.py 的格子、数字、笑脸、LED 几何。
用法（项目根目录）：python develop_tools/generate_theme_collection.py
"""
from __future__ import annotations

import json
from pathlib import Path

import generate_skin as base

ROOT = (Path(__file__).resolve().parent.parent
        / "src" / "plugins" / "skin_manager" / "skins")

THEMES: tuple[dict, ...] = (
    {
        "directory": "retro_green",
        "name": "复古绿显",
        "note": "深绿 CRT 氛围、荧光绿七段 LED 与冷绿凸面格",
        "palette": {
            "cover_top": "#91B99A", "cover_face": "#426E50", "cover_dark": "#1A3625",
            "open_bg": "#183B29", "open_edge": "#0D281B", "grid": "#315A3E",
            "numbers": {1:"#77C8FF",2:"#9CFFA5",3:"#FF806E",4:"#C5A7FF",5:"#FFD36E",6:"#72E4D8",7:"#FFA1D2",8:"#E1E9E2"},
            "led_bg": "#091710", "led_off": "#264532", "led_on": "#91FFA0",
            "face_bg": "#163525", "face_hi": "#79A985", "face_lo": "#0A1C12",
            "face_yellow": "#D5E879", "face_line": "#243315",
            "mine": "#C9F7C7", "mine_highlight": "#95FFA8",
            "frame": "#0C1D13", "text": "#D7F3D8", "flag_bg": "#153321",
            "sb_bg": "#12291C", "sb_text": "#D7F3D8", "sb_grid": "#31533B", "sb_header": "#1B3A26",
            "svg": ("#173D2A", "#102A1D", "#0B2016", "#8DFFA0", "#65C77C"),
        },
    },
    {
        "directory": "cyber_neon",
        "name": "赛博霓虹",
        "note": "深紫黑底、青蓝和洋红点缀，保留格子数字可读性",
        "palette": {
            "cover_top": "#8F7AC4", "cover_face": "#51416F", "cover_dark": "#241E37",
            "open_bg": "#201B2D", "open_edge": "#110E1B", "grid": "#403454",
            "numbers": {1:"#48D8FF",2:"#6BF0B4",3:"#FF6C8E",4:"#B998FF",5:"#FFC857",6:"#49E0D1",7:"#FF75D8",8:"#D8D5E3"},
            "led_bg": "#100D18", "led_off": "#432545", "led_on": "#55F0E0",
            "face_bg": "#211B30", "face_hi": "#8F7AC4", "face_lo": "#120F1C",
            "face_yellow": "#FFD166", "face_line": "#352A28",
            "mine": "#E2D8FF", "mine_highlight": "#50F3FF",
            "frame": "#21182F", "text": "#E5DDF5", "flag_bg": "#211B30",
            "sb_bg": "#191422", "sb_text": "#E5DDF5", "sb_grid": "#49355D", "sb_header": "#2A203C",
            "svg": ("#211B31", "#171321", "#100E19", "#4CE7F5", "#D74FC7"),
        },
    },
)


def _frame_svg(palette: dict[str, object]) -> str:
    top, middle, bottom, glow, wave = palette["svg"]
    if palette["frame"] == "#0C1D13":
        motif = '''<g fill="#91FFA0" opacity="0.24"><path d="M0 0h224v14H14v164H0zM1200 800H976v-14h210V622h14zM30 250h14v12H30zm24 0h14v12H54zm24 0h14v12H78zm24 0h14v12h-14zM1080 530h14v12h-14zm24 0h14v12h-14z"/><path d="M24 300h180v8H24zm0 18h132v5H24zm990 210h160v8h-160z"/></g><path d="M0 390H1200M0 396H1200M0 404H1200" stroke="#A0FFAA" stroke-opacity="0.11" stroke-width="2"/>'''
    else:
        motif = '''<g opacity="0.42"><path d="M0 800V700h56v-82h63V510h48v65h34V454h61v346z" fill="#26CBE2"/><path d="M1200 0v112h-64v78h-52v96h-70v-58h-44v118h-76v72h-74V0z" fill="#E446C5"/><path d="M0 800V772h54v-70h63v-88h42v-50h34v236zM1200 0v30h-66v72h-46v82h-44v48h-40V0z" fill="#171321"/></g>'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
  <defs>
    <linearGradient id="base" x1="0" y1="0" x2="0.9" y2="1">
      <stop offset="0" stop-color="{top}"/><stop offset="0.56" stop-color="{middle}"/><stop offset="1" stop-color="{bottom}"/>
    </linearGradient>
    <radialGradient id="glowA" cx="16%" cy="10%" r="82%">
      <stop offset="0" stop-color="{glow}" stop-opacity="0.32"/><stop offset="1" stop-color="{glow}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowB" cx="88%" cy="84%" r="74%">
      <stop offset="0" stop-color="{wave}" stop-opacity="0.15"/><stop offset="1" stop-color="{wave}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="800" fill="url(#base)"/>
    <rect width="1200" height="800" fill="url(#glowA)"/><rect width="1200" height="800" fill="url(#glowB)"/>
    {motif}
</svg>
'''


def _generate(theme: dict) -> None:
    c = theme["palette"]
    base.OUT = ROOT / theme["directory"]
    for attr, key in (
        ("COVER_TOP", "cover_top"), ("COVER_FACE", "cover_face"),
        ("COVER_DARK", "cover_dark"), ("OPEN_BG", "open_bg"),
        ("OPEN_EDGE", "open_edge"), ("GRID", "grid"),
        ("NUM_COLORS", "numbers"), ("LED_BG", "led_bg"),
        ("LED_OFF", "led_off"), ("LED_ON", "led_on"),
        ("FACE_BG", "face_bg"), ("FACE_HI", "face_hi"),
        ("FACE_LO", "face_lo"), ("FACE_YELLOW", "face_yellow"),
        ("FACE_LINE", "face_line"), ("MINE_COLOR", "mine"),
        ("MINE_HIGHLIGHT", "mine_highlight"),
    ):
        setattr(base, attr, c[key])
    base.COLORS = {
        key: c[key] for key in (
            "frame", "text", "flag_bg", "sb_bg", "sb_text", "sb_grid", "sb_header")
    }
    base.FRAME_SVG = _frame_svg(c)
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
        _generate(theme)


if __name__ == "__main__":
    main()
