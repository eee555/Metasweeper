# -*- coding: utf-8 -*-
"""DPI 感知的图片渲染工具。

解决两个历史问题：
1. `QPixmap(xxx.svg).scaled(n, n)` 的老管线会先把 SVG 按固有尺寸（160px）
   一次性栅格化成位图，之后全靠位图插值缩放——放大必然发糊；
2. 生成的位图 devicePixelRatio=1，在 Retina（DPR=2）屏幕上绘制时被
   整体拉伸 2 倍，再次重采样导致模糊。

正确做法：按「目标逻辑尺寸 × 屏幕 DPR」的物理分辨率直接栅格化/缩放，
并给 QPixmap 打上 devicePixelRatio 标记，屏幕 1:1 直出，不再重采样。
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def render_svg_pixmap(svg_path: str, logical_width: int, logical_height: int,
                      device_pixel_ratio: float) -> QPixmap:
    """把 SVG 直接栅格化到目标物理尺寸，并打上 DPR 标记。

    每次尺寸变化都从矢量重新渲染，任意 pixSize 下边缘都锐利。
    """
    physical_w = max(1, round(logical_width * device_pixel_ratio))
    physical_h = max(1, round(logical_height * device_pixel_ratio))
    image = QImage(physical_w, physical_h,
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(svg_path)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, physical_w, physical_h))
    painter.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(device_pixel_ratio)
    return pixmap


def scale_bitmap_pixmap(source: QPixmap, logical_width: int, logical_height: int,
                        device_pixel_ratio: float) -> QPixmap:
    """把位图素材平滑缩放到「逻辑尺寸 × DPR」的物理分辨率，并打上 DPR 标记。

    适用于 PNG 等位图资源：显示时屏幕不再整体重采样。
    超过素材原生分辨率的放大仍受素材本身限制，但不会出现 DPR 拉伸糊。
    """
    physical_w = max(1, round(logical_width * device_pixel_ratio))
    physical_h = max(1, round(logical_height * device_pixel_ratio))
    image = source.toImage().scaled(
        physical_w, physical_h,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation)
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(device_pixel_ratio)
    return pixmap
