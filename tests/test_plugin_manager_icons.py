"""插件管理器统一操作图标的资源、尺寸、禁用与身份图标回归测试。"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QFile, QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QPushButton

from plugin_manager.icons import (
    ACTION_ICON_NAMES, ICON_NAMES, action_icon, set_action_icon,
)
from plugin_manager.plugin_download_dialog import PluginDownloadDialog


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_action_qrc_matches_compiled_resource() -> None:
    """每个声明的 SVG 都在 qrc 中，且编译后的资源可读。"""
    qrc = (_project_root() / "src/plugin_manager/resources/actions.qrc").read_text(
        encoding="utf-8")
    for name in ICON_NAMES:
        assert f'alias="{name}.svg"' in qrc
        assert (_project_root() / f"src/plugin_manager/resources/icons/{name}.svg").is_file()
        resource = QFile(f":/plugin_manager/actions/{name}.svg")
        assert resource.open(QFile.OpenModeFlag.ReadOnly)
        assert b"<svg" in bytes(resource.readAll().data())
        resource.close()


@pytest.fixture(params=[("#123456", "#789abc"), ("#eeeeee", "#606060")],
                ids=["light", "dark"])
def icon_palette(qapp, request):
    """固定测试颜色，并在结束时恢复共享 QApplication 的调色板。"""
    original = QPalette(qapp.palette())
    palette = QPalette(original)
    normal, disabled = map(QColor, request.param)
    palette.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText, normal)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    qapp.setPalette(palette)
    try:
        yield normal, disabled
    finally:
        qapp.setPalette(original)


def test_icons_render_at_small_sizes_and_disabled_state(icon_palette) -> None:
    """16/24/32 逻辑像素均有可见图形，禁用模式使用调色板色。"""
    normal, disabled = icon_palette
    for name in ACTION_ICON_NAMES:
        icon = action_icon(name)
        assert not icon.isNull()
        for size in (16, 24, 32):
            pixmap = icon.pixmap(size, size)
            assert not pixmap.isNull()
            image = pixmap.toImage()
            assert any(image.pixelColor(x, y).alpha()
                       for x in range(size) for y in range(size)), (name, size)
        # QIcon 内部缓存按 (size, mode, state, devicePixelRatio) 索引；
        # 直接调用引擎并固定 scale，避免测试进程 DPR 造成的模式串扰。
        from plugin_manager.icons import _ActionIconEngine, _svg_data
        engine = _ActionIconEngine(_svg_data(name), True)
        normal_image = engine.pixmap(
            QSize(16, 16), QIcon.Mode.Normal, QIcon.State.Off).toImage()
        disabled_image = engine.pixmap(
            QSize(16, 16), QIcon.Mode.Disabled, QIcon.State.Off).toImage()
        for image, expected in ((normal_image, normal), (disabled_image, disabled)):
            # 忽略低透明度边缘；预乘 alpha 的舍入允许每个颜色通道有 2 级误差。
            colors = [image.pixelColor(x, y)
                      for x in range(16) for y in range(16)
                      if image.pixelColor(x, y).alpha() >= 128]
            assert colors, name
            assert all(
                abs(actual - wanted) <= 2
                for color in colors
                for actual, wanted in zip(color.getRgb()[:3], expected.getRgb()[:3])
            ), (name, expected.name(), {color.name() for color in colors})


@pytest.mark.parametrize("scale", [1.0, 1.25, 1.5, 2.0])
def test_icon_paint_matches_scaled_pixmap(qapp, scale) -> None:
    """paint 路径应使用目标设备分辨率，避免放大低分辨率位图。"""
    icon = action_icon("window")
    size = QSize(16, 16)
    target = QPixmap(size * scale)
    target.setDevicePixelRatio(scale)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    try:
        icon.paint(painter, QRect(0, 0, 16, 16))
    finally:
        painter.end()
    expected = icon.pixmap(size, scale)
    assert target.toImage() == expected.toImage()


def test_app_identity_icon_keeps_its_brand_colors(qtbot) -> None:
    """应用身份图标沿用项目应用标识，不参与禁用态重着色。"""
    assert qtbot is not None
    resource_svg = (_project_root() /
                    "src/plugin_manager/resources/icons/app.svg").read_text(
        encoding="utf-8")
    assert 'fill="#244b75"' in resource_svg
    assert 'fill="#237c9c"' in resource_svg
    assert 'viewBox="0 0 256 256"' in resource_svg

    icon = action_icon("app")
    from plugin_manager.icons import _ActionIconEngine, _svg_data
    engine = _ActionIconEngine(_svg_data("app"), False)
    normal_image = engine.pixmap(
        QSize(16, 16), QIcon.Mode.Normal, QIcon.State.Off).toImage()
    disabled_image = engine.pixmap(
        QSize(16, 16), QIcon.Mode.Disabled, QIcon.State.Off).toImage()
    normal_colors = {
        normal_image.pixelColor(x, y).rgb()
        for x in range(16) for y in range(16)
        if normal_image.pixelColor(x, y).alpha()
    }
    disabled_colors = {
        disabled_image.pixelColor(x, y).rgb()
        for x in range(16) for y in range(16)
        if disabled_image.pixelColor(x, y).alpha()
    }
    assert normal_colors and disabled_colors
    # 身份图标的颜色由 SVG 本身决定，而非普通/禁用按钮文字色。
    assert normal_colors.isdisjoint({0xFF000000, 0xFF787878})
    assert disabled_colors.isdisjoint({0xFF000000, 0xFF787878})


def test_set_action_icon_keeps_widget_state(qtbot) -> None:
    """图标接入不改变按钮文字、启用状态和 16px 逻辑尺寸。"""
    button = QPushButton("操作")
    button.setEnabled(False)
    set_action_icon(button, "download")
    assert button.text() == "操作"
    assert not button.isEnabled()
    assert button.iconSize() == QSize(16, 16)
    assert not button.icon().isNull()
    qtbot.addWidget(button)


def test_download_dialog_uses_action_icons_and_keeps_disabled_states(qtbot) -> None:
    """安装插件入口使用统一图标，原有禁用条件与文字不变。"""
    dialog = PluginDownloadDialog()
    qtbot.addWidget(dialog)
    assert not dialog.windowIcon().isNull()
    assert not dialog.fetch.icon().isNull()
    assert not dialog.install.icon().isNull()
    assert not dialog.close_button.icon().isNull()
    assert dialog.fetch.text() == "获取标签"
    assert dialog.install.text() == "下载插件"
    assert not dialog.fetch.isEnabled()
    assert not dialog.install.isEnabled()
