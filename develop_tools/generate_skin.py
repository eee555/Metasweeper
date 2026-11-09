"""
生成内置示例皮肤「深海蓝 / Deep Ocean」的资源文件。

输出到 src/plugins/skin_manager/skins/deep_ocean/。
尺寸与默认资源保持一致：格子 160x160、笑脸 260x260、LED 208x368。

用法（在项目根执行）：
    python develop_tools/generate_skin.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = (Path(__file__).resolve().parent.parent
       / "src" / "plugins" / "skin_manager" / "skins" / "deep_ocean")

# ── 配色 ─────────────────────────────────────────────────────────
COVER_TOP = "#5B8FC9"       # 未翻开凸起高光
COVER_FACE = "#2E5C8A"      # 未翻开面
COVER_DARK = "#1B3A5C"      # 未翻开阴影
OPEN_BG = "#16324F"         # 已翻开底
OPEN_EDGE = "#0E2237"       # 已翻开边
GRID = "#244B6E"            # 已翻开网格线

NUM_COLORS = {
    1: "#4FC3F7", 2: "#81C784", 3: "#FF8A65", 4: "#BA68C8",
    5: "#FFD54F", 6: "#4DD0E1", 7: "#F06292", 8: "#E0E0E0",
}

LED_BG = "#0A1420"
LED_OFF = "#3A2830"
LED_ON = "#FF5A4E"
MINE_COLOR = "#D7E5F0"
MINE_HIGHLIGHT = "#FF6B7A"

FACE_BG = "#16324F"
FACE_HI = "#5B8FC9"
FACE_LO = "#0E2237"
FACE_YELLOW = "#FFD54F"
FACE_LINE = "#3A2A00"

SVG_HEAD = ('<?xml version="1.0" standalone="yes"?>\n'
            '<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">\n')
SVG_TAIL = '</svg>\n'


def svg(w: int, h: int, body: str) -> str:
    return SVG_HEAD.format(w=w, h=h) + body + SVG_TAIL


def covered() -> str:
    """未翻开格子：深蓝立体凸起。"""
    return (
        f'  <polygon points="0,0 160,0 140,20 20,20 20,140 0,160" fill="{COVER_TOP}" />\n'
        f'  <polygon points="160,160 160,0 140,20 140,140 20,140 0,160" fill="{COVER_DARK}" />\n'
        f'  <rect x="20" y="20" width="120" height="120" fill="{COVER_FACE}" />\n'
        f'  <rect x="34" y="34" width="92" height="92" fill="{COVER_TOP}" opacity="0.18" />\n'
    )


def opened(extra: str = "") -> str:
    """已翻开格子：深蓝底 + 细网格边。"""
    return (
        f'  <rect x="0" y="0" width="160" height="160" fill="{OPEN_EDGE}" />\n'
        f'  <rect x="6" y="6" width="148" height="148" fill="{OPEN_BG}" />\n'
        f'  <rect x="6" y="6" width="148" height="148" fill="none" '
        f'stroke="{GRID}" stroke-width="2" />\n'
        + extra
    )


def number_svg(n: int) -> str:
    color = NUM_COLORS[n]
    return svg(160, 160, opened(
        f'  <text x="80" y="118" font-family="Arial, sans-serif" '
        f'font-size="112" font-weight="bold" text-anchor="middle" '
        f'fill="{color}">{n}</text>\n'))


def flag_svg() -> str:
    return svg(160, 160, covered() +
               f'  <rect x="40" y="112" width="80" height="14" fill="{COVER_DARK}" />\n'
               f'  <rect x="62" y="102" width="36" height="10" fill="{COVER_DARK}" />\n'
               f'  <rect x="78" y="42" width="10" height="60" fill="#ECEFF1" />\n'
               f'  <path d="M 88 32 L 34 58 L 88 84 Z" fill="#FF5252" />\n')


def question_svg() -> str:
    return svg(160, 160, covered() +
               f'  <path d="M60 62 A20 20 0 0 1 100 62 L100 72 L80 86 L80 100" '
               f'fill="none" stroke="{FACE_YELLOW}" stroke-width="20" '
               f'stroke-linecap="butt" />\n'
               f'  <rect x="70" y="110" width="20" height="20" fill="{FACE_YELLOW}" />\n')


def mine_body() -> str:
    """地雷图形（可复用于不同底色）。"""
    return (
        f'  <circle cx="80" cy="80" r="42" fill="{MINE_COLOR}" />\n'
        f'  <rect x="20" y="76" width="120" height="8" fill="{MINE_COLOR}" />\n'
        f'  <rect x="76" y="20" width="8" height="120" fill="{MINE_COLOR}" />\n'
        f'  <line x1="38" y1="38" x2="122" y2="122" stroke-width="9" stroke="{MINE_COLOR}" />\n'
        f'  <line x1="122" y1="38" x2="38" y2="122" stroke-width="9" stroke="{MINE_COLOR}" />\n'
        f'  <circle cx="64" cy="64" r="11" fill="{MINE_HIGHLIGHT}" />\n'
    )


def mine_svg() -> str:
    return svg(160, 160, opened(mine_body()))


def blast_svg() -> str:
    return svg(160, 160,
               f'  <rect x="0" y="0" width="160" height="160" fill="#B71C1C" />\n'
               f'  <rect x="8" y="8" width="144" height="144" fill="#E53935" />\n'
               + mine_body())


def falsemine_svg() -> str:
    cross = (
        '  <polygon points="18,32 36,32 142,138 124,138" fill="#FF5252" />\n'
        '  <polygon points="142,32 124,32 18,138 36,138" fill="#FF5252" />\n'
    )
    return svg(160, 160, opened(mine_body() + cross))


def transparent_mine_svg() -> str:
    """概率叠加用：透明底 + 半透明雷。"""
    return svg(160, 160, mine_body())


# ── 笑脸 ─────────────────────────────────────────────────────────
def face_frame() -> str:
    return (
        f'  <polygon points="0,0 260,0 250,10 10,10 10,250 0,260" fill="{FACE_LO}" />\n'
        f'  <polygon points="10,10 250,10 230,30 30,30 30,230 10,250" fill="{FACE_HI}" />\n'
        f'  <rect x="30" y="30" width="200" height="200" fill="{FACE_BG}" />\n'
        f'  <polygon points="260,260 0,260 30,230 230,230 230,30 260,0" fill="{FACE_LO}" />\n'
    )


def face_circle() -> str:
    return (f'  <circle cx="130" cy="130" r="78" stroke-width="6" '
            f'stroke="{FACE_LINE}" fill="{FACE_YELLOW}" />\n')


def smile_svg() -> str:
    return svg(260, 260, face_frame() + face_circle() +
               '  <path d="M 90 145 Q 105 172, 130 172 T 170 145" fill="transparent" '
               f'stroke="{FACE_LINE}" stroke-width="8" />\n'
               f'  <circle cx="105" cy="106" r="11" fill="{FACE_LINE}" />\n'
               f'  <circle cx="155" cy="106" r="11" fill="{FACE_LINE}" />\n')


def click_svg() -> str:
    return svg(260, 260, face_frame() + face_circle() +
               f'  <circle cx="100" cy="102" r="13" fill="{FACE_LINE}" />\n'
               f'  <circle cx="160" cy="102" r="13" fill="{FACE_LINE}" />\n'
               f'  <ellipse cx="130" cy="160" rx="17" ry="20" fill="transparent" '
               f'stroke-width="10" stroke="{FACE_LINE}" />\n')


def lost_svg() -> str:
    return svg(260, 260, face_frame() + face_circle() +
               '  <line x1="86" y1="88" x2="114" y2="116" stroke-width="7" '
               f'stroke="{FACE_LINE}" />\n'
               '  <line x1="86" y1="116" x2="114" y2="88" stroke-width="7" '
               f'stroke="{FACE_LINE}" />\n'
               '  <line x1="174" y1="88" x2="146" y2="116" stroke-width="7" '
               f'stroke="{FACE_LINE}" />\n'
               '  <line x1="146" y1="88" x2="174" y2="116" stroke-width="7" '
               f'stroke="{FACE_LINE}" />\n'
               '  <path d="M 90 178 Q 105 152, 130 152 T 170 178" fill="transparent" '
               f'stroke="{FACE_LINE}" stroke-width="8" />\n')


def win_svg() -> str:
    return svg(260, 260, face_frame() + face_circle() +
               '  <polygon points="50,132 90,102 170,102 210,132 210,142 '
               f'170,112 90,112 50,142" fill="{FACE_LINE}" />\n'
               '  <path d="M 85 110 C 80 150, 125 150, 125 110" fill="transparent" '
               f'stroke="{FACE_LINE}" stroke-width="7" />\n'
               '  <path d="M 175 110 C 180 150, 135 150, 135 110" fill="transparent" '
               f'stroke="{FACE_LINE}" stroke-width="7" />\n'
               '  <path d="M 100 160 Q 105 175, 130 175 T 160 160" fill="transparent" '
               f'stroke="{FACE_LINE}" stroke-width="7" />\n')


def down_svg() -> str:
    return svg(260, 260,
               f'  <polygon points="0,0 260,0 250,10 10,10 10,250 0,260" fill="{FACE_LO}" />\n'
               f'  <rect x="10" y="10" width="250" height="250" fill="{FACE_LO}" />\n'
               f'  <rect x="30" y="30" width="220" height="220" fill="{FACE_BG}" />\n'
               f'  <polygon points="260,260 0,260 10,250 250,250 250,10 260,0" fill="{FACE_LO}" />\n'
               + face_circle() +
               '  <path d="M 90 145 Q 105 172, 130 172 T 170 145" fill="transparent" '
               f'stroke="{FACE_LINE}" stroke-width="8" />\n'
               f'  <circle cx="105" cy="106" r="11" fill="{FACE_LINE}" />\n'
               f'  <circle cx="155" cy="106" r="11" fill="{FACE_LINE}" />\n')


# ── LED 七段数码管 ───────────────────────────────────────────────
# 段顺序: a(上) b(右上) c(右下) d(下) e(左下) f(左上) g(中)
SEGMENTS = {
    0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc",
    5: "afgcd", 6: "afgecd", 7: "abc", 8: "abcdefg", 9: "abfgcd",
}


def led_png(n: int) -> Image.Image:
    w, h = 208, 368
    img = Image.new("RGB", (w, h), LED_BG)
    d = ImageDraw.Draw(img)
    # 边框
    d.rectangle([2, 2, w - 3, h - 3], outline="#1C2E40", width=3)

    on = set(SEGMENTS[n])
    m = 34          # 外边距
    t = 20          # 段厚
    x0, x1 = m, w - m
    y0, ym, y1 = m, h // 2, h - m

    def hseg(y: int, active: bool) -> None:
        color = LED_ON if active else LED_OFF
        # 水平段（带斜角端点）
        pts = [(x0 + t // 2, y), (x1 - t // 2, y),
               (x1 - t, y + t // 2), (x0 + t, y + t // 2),
               (x0, y - t // 2 + t // 2), (x0 + t, y - t // 2)]
        d.polygon([(x0 + t // 2, y - t // 2), (x1 - t // 2, y - t // 2),
                   (x1 - t, y), (x1 - t // 2, y + t // 2),
                   (x0 + t // 2, y + t // 2), (x0 + t, y)], fill=color)

    def vseg(x: int, ya: int, yb: int, active: bool) -> None:
        color = LED_ON if active else LED_OFF
        d.polygon([(x, ya + t // 2), (x + t // 2, ya + t),
                   (x + t // 2, yb - t), (x, yb - t // 2),
                   (x - t // 2, yb - t), (x - t // 2, ya + t)], fill=color)

    hseg(y0, "a" in on)
    hseg(ym, "g" in on)
    hseg(y1, "d" in on)
    vseg(x0, y0, ym, "f" in on)
    vseg(x1, y0, ym, "b" in on)
    vseg(x0, ym, y1, "e" in on)
    vseg(x1, ym, y1, "c" in on)
    return img


COLORS = {
    "frame": "#0E2237",
    "text": "#CFE4F7",
    "flag_bg": "#16324F",
    "sb_bg": "#16324F",
    "sb_text": "#CFE4F7",
    "sb_grid": "#244B6E",
    "sb_header": "#0E2237",
}

FRAME_SVG = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
    <defs>
        <linearGradient id="base" x1="0" y1="0" x2="0.9" y2="1">
            <stop offset="0" stop-color="#163653"/>
            <stop offset="0.55" stop-color="#102b45"/>
            <stop offset="1" stop-color="#0d2238"/>
        </linearGradient>
        <radialGradient id="glowA" cx="15%" cy="8%" r="80%">
            <stop offset="0" stop-color="#55a9d7" stop-opacity="0.20"/>
            <stop offset="1" stop-color="#55a9d7" stop-opacity="0"/>
        </radialGradient>
        <radialGradient id="glowB" cx="92%" cy="86%" r="72%">
            <stop offset="0" stop-color="#28628c" stop-opacity="0.17"/>
            <stop offset="1" stop-color="#28628c" stop-opacity="0"/>
        </radialGradient>
        <radialGradient id="glowC" cx="72%" cy="24%" r="48%">
            <stop offset="0" stop-color="#2b83ae" stop-opacity="0.10"/>
            <stop offset="1" stop-color="#2b83ae" stop-opacity="0"/>
        </radialGradient>
        <linearGradient id="wash" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="#8bd8f0" stop-opacity="0"/>
            <stop offset="0.5" stop-color="#8bd8f0" stop-opacity="0.055"/>
            <stop offset="1" stop-color="#8bd8f0" stop-opacity="0"/>
        </linearGradient>
        <pattern id="grain" width="48" height="48" patternUnits="userSpaceOnUse">
            <circle cx="5" cy="8" r="1.1" fill="#b8e3f5" opacity="0.085"/>
            <circle cx="29" cy="27" r="0.8" fill="#b8e3f5" opacity="0.065"/>
            <circle cx="42" cy="4" r="0.55" fill="#b8e3f5" opacity="0.05"/>
        </pattern>
        <pattern id="microgrid" width="96" height="96" patternUnits="userSpaceOnUse">
            <path d="M0 48H96M48 0V96" fill="none" stroke="#8bd8f0"
                  stroke-opacity="0.022" stroke-width="1"/>
            <circle cx="48" cy="48" r="1.5" fill="#9bdcf0" opacity="0.08"/>
        </pattern>
    </defs>
    <rect width="1200" height="800" fill="url(#base)"/>
    <rect width="1200" height="800" fill="url(#glowA)"/>
    <rect width="1200" height="800" fill="url(#glowB)"/>
    <rect width="1200" height="800" fill="url(#glowC)"/>
    <rect width="1200" height="800" fill="url(#wash)"/>
    <rect width="1200" height="800" fill="url(#grain)"/>
    <rect width="1200" height="800" fill="url(#microgrid)"/>
    <!-- Low-contrast bathymetry contours and current paths; no control-aligned edges. -->
    <g fill="none" stroke="#78c9e8" stroke-width="1.5" opacity="0.075">
        <path d="M-80 145 C90 60 240 70 340 132 S520 218 680 143 S970 43 1280 116"/>
        <path d="M-90 165 C80 82 235 91 330 150 S522 238 690 163 S978 65 1290 139"/>
        <path d="M-95 188 C72 108 225 115 320 172 S530 260 702 187 S992 91 1300 163"/>
        <path d="M-100 212 C65 135 215 140 310 196 S535 282 712 211 S1005 117 1310 188"/>
    </g>
    <g fill="none" stroke="#69b8dc" stroke-width="2" opacity="0.055">
        <path d="M-70 330 C130 250 250 286 390 326 C535 368 640 360 770 302 C900 245 1045 254 1280 332"/>
        <path d="M-80 349 C118 273 250 306 386 346 C532 389 650 380 782 322 C914 265 1055 274 1290 352"/>
        <path d="M-90 368 C108 296 248 327 380 366 C530 411 660 400 794 342 C928 285 1068 295 1300 372"/>
        <path d="M-90 570 C100 505 260 512 390 557 C520 602 670 625 820 566 C970 507 1090 512 1290 578"/>
        <path d="M-90 590 C100 526 260 534 390 578 C525 624 680 647 830 587 C980 529 1100 533 1290 598"/>
        <path d="M-90 611 C100 547 260 556 390 600 C530 646 690 669 840 609 C990 551 1110 555 1290 619"/>
    </g>
    <!-- Soft, unaligned current ribbons and sonar rings add depth without framing controls. -->
    <path d="M-80 260 C150 160 250 340 480 260 S850 155 1280 265"
          fill="none" stroke="#7ed2ed" stroke-opacity="0.035" stroke-width="64"/>
    <path d="M-60 720 C200 610 410 775 650 700 S1030 620 1280 735"
          fill="none" stroke="#3b86b1" stroke-opacity="0.045" stroke-width="88"/>
    <g fill="none" stroke="#8bd8f0" stroke-width="1.5" opacity="0.045">
        <circle cx="930" cy="270" r="54"/>
        <circle cx="930" cy="270" r="82"/>
        <circle cx="930" cy="270" r="110"/>
        <circle cx="242" cy="586" r="38"/>
        <circle cx="242" cy="586" r="64"/>
    </g>
    <g fill="#b8e3f5" opacity="0.20">
        <circle cx="930" cy="270" r="2.5"/>
        <circle cx="242" cy="586" r="2"/>
        <circle cx="703" cy="484" r="1.6"/>
        <circle cx="1080" cy="640" r="1.8"/>
        <circle cx="340" cy="240" r="1.5"/>
    </g>
</svg>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    cells: dict[str, str] = {
        "celldown.svg": svg(160, 160, opened()),
        "cellup.svg": svg(160, 160, covered()),
        "cellflag.svg": flag_svg(),
        "cellquestion.svg": question_svg(),
        "cellmine.svg": mine_svg(),
        "blast.svg": blast_svg(),
        "falsemine.svg": falsemine_svg(),
        "mine.svg": transparent_mine_svg(),
    }
    for n in range(1, 9):
        cells[f"cell{n}.svg"] = number_svg(n)

    faces = {
        "smileface.svg": smile_svg(),
        "clickface.svg": click_svg(),
        "lostface.svg": lost_svg(),
        "winface.svg": win_svg(),
        "smilefacedown.svg": down_svg(),
    }

    import json
    for name, text in {**cells, **faces}.items():
        (OUT / name).write_text(text, encoding="utf-8")

    for n in range(10):
        led_png(n).save(OUT / f"LED{n}.png", "PNG")

    (OUT / "frame.svg").write_text(FRAME_SVG, encoding="utf-8")

    (OUT / "colors.json").write_text(
        json.dumps(COLORS, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (OUT / "skin.json").write_text(
        '{\n'
        '  "name": "深海蓝",\n'
        '  "author": "MetaSweeper",\n'
        '  "version": "1.0.0",\n'
        '  "note": "深蓝灰背景、彩色数字与红色七段 LED"\n'
        '}\n',
        encoding="utf-8",
    )
    print(f"已生成 {len(cells) + len(faces) + 10 + 3} 个文件 -> {OUT}")


if __name__ == "__main__":
    main()
