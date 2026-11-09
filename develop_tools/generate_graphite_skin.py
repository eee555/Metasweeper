"""生成内置皮肤「石墨夜 / Graphite Night」。

复用 generate_skin.py 的资源几何，只替换配色与 frame.svg 背景，
输出一套完整资源到 src/plugins/skin_manager/skins/graphite_night/。

用法（项目根目录）：
    python develop_tools/generate_graphite_skin.py
"""
from __future__ import annotations

import json
from pathlib import Path

import generate_skin as base

OUT = (Path(__file__).resolve().parent.parent
       / "src" / "plugins" / "skin_manager" / "skins" / "graphite_night")

# 未翻开格：石墨面 + 柔和的冷灰高光，保留经典凸起层次。
base.COVER_TOP = "#76828E"
base.COVER_FACE = "#343F4A"
base.COVER_DARK = "#141A20"

# 已翻开格：深炭灰，不用纯黑。
base.OPEN_BG = "#252D36"
base.OPEN_EDGE = "#13191F"
base.GRID = "#3B4651"

# 数字高对比但不刺眼。
base.NUM_COLORS = {
    1: "#66B8FF", 2: "#8CD7A5", 3: "#FF8975", 4: "#B9A5F5",
    5: "#F2C66D", 6: "#6ED6D0", 7: "#F08DB7", 8: "#D5DCE3",
}

# LED 用温暖琥珀红，避免黑底上大面积亮红过于刺眼。
base.LED_BG = "#10151B"
base.LED_OFF = "#49343A"
base.LED_ON = "#FF8068"

# 笑脸改为暖金色，暗灰面板和银灰立体边。
base.FACE_BG = "#252D36"
base.FACE_HI = "#7B8792"
base.FACE_LO = "#11171D"
base.FACE_YELLOW = "#F2C66D"
base.FACE_LINE = "#302719"

base.MINE_COLOR = "#D8E0E6"
base.MINE_HIGHLIGHT = "#F4B95E"

base.COLORS = {
    "frame": "#11171D",
    "text": "#D5DDE5",
    "flag_bg": "#202830",
    "sb_bg": "#202830",
    "sb_text": "#D5DDE5",
    "sb_grid": "#3A4652",
    "sb_header": "#151B21",
}

# 只有渐变、漫反射、微点阵与柔和海流；不画固定边框/角标，
# 因此窗口与棋盘尺寸变化时背景不会再和控件边界错位。
base.FRAME_SVG = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
  <defs>
    <linearGradient id="graphite" x1="0" y1="0" x2="0.85" y2="1">
      <stop offset="0" stop-color="#303B47"/>
      <stop offset="0.56" stop-color="#222B34"/>
      <stop offset="1" stop-color="#171D24"/>
    </linearGradient>
    <radialGradient id="coolGlow" cx="18%" cy="12%" r="78%">
      <stop offset="0" stop-color="#7D9DB6" stop-opacity="0.16"/>
      <stop offset="1" stop-color="#7D9DB6" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="warmGlow" cx="88%" cy="82%" r="70%">
      <stop offset="0" stop-color="#A7865C" stop-opacity="0.10"/>
      <stop offset="1" stop-color="#A7865C" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="800" fill="url(#graphite)"/>
  <rect width="1200" height="800" fill="url(#coolGlow)"/>
  <rect width="1200" height="800" fill="url(#warmGlow)"/>
    <g opacity="0.22" stroke="#AEBBC6" stroke-width="3" fill="#596570">
      <path d="M0 0h215l88 88-88 88H0zM1200 800H965l-88-88 88-88h235z"/>
    </g>
  <g fill="none" stroke="#B8C6D2" stroke-width="1.4" opacity="0.075">
    <path d="M0 110H210l38 38h170l34-34h120M1200 610H1010l-44-44H790l-38 38H620"/>
    <path d="M0 690h145l52-52h126l36 36h94M1200 155h-160l-42 42H880l-35-35h-90"/>
    <path d="M78 0v94l42 42v110M1120 800V690l-42-42V530"/>
  </g>
  <g fill="#D7B77C" opacity="0.18">
    <circle cx="452" cy="114" r="3"/><circle cx="803" cy="682" r="3"/>
    <circle cx="171" cy="470" r="2"/><circle cx="1040" cy="345" r="2"/>
  </g>
  <g stroke="#DDE4EA" stroke-width="2" opacity="0.11"><path d="M15 205l180-180M30 232L230 32M1050 775l145-145M1020 760l155-155"/></g>
</svg>
'''


def main() -> None:
    base.OUT = OUT
    OUT.mkdir(parents=True, exist_ok=True)
    base.main()

    metadata = {
        "name": "石墨夜（黑曜石）",
        "author": "MetaSweeper",
        "version": "1.0.0",
        "note": "炭灰与石墨层次、冷灰凸起格、暖金表情与柔和琥珀 LED；不是纯黑",
    }
    (OUT / "skin.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已生成石墨夜皮肤 -> {OUT}")


if __name__ == "__main__":
    main()
