import random
import sys
from io import BytesIO
from PySide6.QtCore import QByteArray, Qt, QRectF, QBuffer, QIODevice
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
from PIL import Image
from PyMCUlib import Hct, hex_from_argb


if __name__ == '__main__':
    seed = sys.argv[1] if len(sys.argv) > 1 else None
    if seed:
        random.seed(seed)

    hue = random.uniform(0, 360)
    chroma = random.uniform(30, 55)
    tone = random.uniform(40, 70)

    hue2 = hue + random.choice([60, 90, 120, 150, 210, 240, 270, 300])
    chroma2 = random.uniform(25, 50)
    tone2 = (tone + random.uniform(-15, 15)) % 100
    tone2 = max(30, min(80, tone2))

    c1_hex = hex_from_argb(Hct.from_hct(hue, chroma, tone).to_int())
    c2_hex = hex_from_argb(Hct.from_hct(hue2, chroma2, tone2).to_int())

    with open('cat.svg', encoding='utf-8') as f:
        svg = f.read()
    svg = svg.replace('#2BD3D3', c1_hex).replace('#DE6DE1', c2_hex)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    img = QImage(128, 128, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    renderer.render(p, QRectF(0, 0, 128, 128))
    p.end()

    buf = QByteArray()
    buffer = QBuffer(buf)
    buffer.open(QIODevice.WriteOnly)
    img.save(buffer, 'PNG')
    buffer.close()

    pil_img = Image.open(BytesIO(buf.data())).convert('RGBA')
    pil_img.save('cat.ico', format='ICO', sizes=[(128, 128)])
    print(f'{c1_hex} {c2_hex}')
