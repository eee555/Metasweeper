"""生成 macOS 打包所需图标资源。

输入:  package_tool/cat.svg（项目自带矢量图标）
输出:  package_tool/macos/build/Metasweeper.iconset/  （随后由 iconutil 转 icns）
       src/media/cat.ico                              （UI 多处引用 media/cat.ico，
                                                        源码仓库默认缺失，若已存在则不覆盖）
"""
import os
import struct

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

MACOS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(MACOS_DIR, "..", ".."))
SVG = os.path.join(MACOS_DIR, "..", "cat.svg")
BUILD = os.path.join(MACOS_DIR, "build")
SRC_MEDIA = os.path.join(ROOT, "src", "media")

ICNS_SIZES = [16, 32, 128, 256, 512]        # iconset 每级基础尺寸（@2x 自动翻倍）
ICO_SIZES = [16, 32, 48, 64, 128, 256]


def render(size: int) -> QImage:
    renderer = QSvgRenderer(os.path.abspath(SVG))
    if not renderer.isValid():
        raise SystemExit(f"无效的 SVG 文件: {SVG}")
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    return img


def write_iconset() -> str:
    iconset = os.path.join(BUILD, "Metasweeper.iconset")
    os.makedirs(iconset, exist_ok=True)
    for base in ICNS_SIZES:
        for suffix, size in (("", base), ("@2x", base * 2)):
            img = render(size)
            img.save(os.path.join(iconset, f"icon_{base}x{base}{suffix}.png"), "PNG")
    return iconset


def write_ico(path: str, sizes) -> None:
    """手工写 ICO 容器（条目采用 PNG 压缩，Vista+/Qt 均支持）"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    entries = b""
    body = b""
    offset = 6 + 16 * len(sizes)
    for s in sizes:
        png_path = os.path.join(BUILD, f"ico_tmp_{s}.png")
        render(s).save(png_path, "PNG")
        with open(png_path, "rb") as f:
            data = f.read()
        os.remove(png_path)
        dim = 0 if s >= 256 else s  # 0 表示 256
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        body += data
        offset += len(data)
    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(sizes)) + entries + body)


def main() -> None:
    os.makedirs(BUILD, exist_ok=True)
    iconset = write_iconset()
    print(f"[assets] iconset 就绪: {iconset}")

    ico_path = os.path.join(SRC_MEDIA, "cat.ico")
    if os.path.exists(ico_path):
        print(f"[assets] 已存在，跳过: {ico_path}")
    else:
        write_ico(ico_path, ICO_SIZES)
        print(f"[assets] 已生成: {ico_path}")


if __name__ == "__main__":
    QGuiApplication([])  # Qt 应用环境（offscreen）
    main()
