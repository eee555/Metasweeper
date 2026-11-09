"""
主窗口皮肤热替换（纯内存）。

插件通过 SetSkinCommand 把图片字节发到主进程，这里在主线程解码为
QPixmap 并写入各控件的「内存皮肤源」，再调用控件原有的缩放/重绘逻辑
刷新界面。全程不写磁盘、不改资源路径、不重启；主进程退出即自动还原。

覆盖范围：
  - 雷区 16 张格子图        -> mineLabel.skin_source
  - 顶部 10 张 LED 数字      -> ui.skin_leds
  - 5 张笑脸（含按下态）     -> ui.skin_faces + StatusLabel.skin_face_*
  - 主窗口框架浅灰区域配色   -> 可逆 QSS（window/frame/topbar/infobar/
                                text/flag_bg）

不覆盖（按要求）：窗口图标 cat.ico、右下角国旗图案、菜单栏（背景与文字）、
GLOBAL_QSS 按钮样式、字体、独立对话框内的图片资源。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QByteArray, QEvent, QObject, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPixmap, QPalette, QBrush, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QTableWidget, QWidget

from config.constants import (
    FACE_SMILE, FACE_CLICK, FACE_LOST, FACE_WIN, FACE_SMILE_DOWN,
)
from shared_types.commands import (
    SetSkinCommand, SKIN_CELL_KEYS, SKIN_LED_KEYS, SKIN_FACE_KEYS,
    SKIN_COLOR_KEYS,
)
from lib_zmq_plugins.shared.base import CommandResponse
from utils.app_logger import logger

if TYPE_CHECKING:
    from mineSweeperGUI import MineSweeperGUI

# 防护：handler 在主线程执行，必须限制 payload 大小，避免超大图片卡住 UI
_MAX_SINGLE_BYTES = 512 * 1024      # 单张 512 KB
_MAX_TOTAL_BYTES = 4 * 1024 * 1024  # 总 4 MB


class SkinError(ValueError):
    """皮肤资源校验/解码失败"""


def _validate_frame_svg(raw: bytes | None, total: list[int]) -> bytes | None:
    """校验可选的大幅 SVG 背景。"""
    if raw is None:
        return None
    if not isinstance(raw, (bytes, bytearray)):
        raise SkinError("frame.svg: 数据不是字节")
    if not raw or len(raw) > _MAX_SINGLE_BYTES:
        raise SkinError("frame.svg: 文件为空或超过 512 KB")
    total[0] += len(raw)
    if total[0] > _MAX_TOTAL_BYTES:
        raise SkinError("皮肤资源总大小超过 4 MB")
    svg_bytes = bytes(raw)
    if not QSvgRenderer(QByteArray(svg_bytes)).isValid():
        raise SkinError("frame.svg: SVG 解析失败")
    return svg_bytes


class _FrameSvgBackground(QObject):
    """在 centralwidget 上绘制单张完整 SVG，现有子控件透明透出背景。"""

    _CHILDREN = {
        "frame_1": "QFrame#frame_1",
        "frame": "QFrame#frame",
        "MinenumTimeWigdet": "QFrame#MinenumTimeWigdet",
        "label_info": "QLabel#label_info",
        "label_flag": "QLabel#label_flag",
    }

    def __init__(self, ui: "MineSweeperGUI", svg_bytes: bytes):
        super().__init__(ui.mainWindow)
        self.ui = ui
        self.renderer = QSvgRenderer(QByteArray(svg_bytes), self)
        self.renderer.setAspectRatioMode(Qt.AspectRatioMode.IgnoreAspectRatio)
        self._refresh_pending = False
        self._original: dict[str, tuple[QWidget, QPalette, bool, str]] = {}
        for name in ("centralwidget", *self._CHILDREN):
            widget = getattr(ui, name, None)
            if widget is not None:
                self._original[name] = (
                    widget, widget.palette(), widget.autoFillBackground(),
                    widget.styleSheet() or "",
                )
        ui.centralwidget.installEventFilter(self)
        self.refresh()

    def detach(self) -> None:
        """移除背景并恢复各现有控件换肤前的样式和 palette。"""
        self.ui.centralwidget.removeEventFilter(self)
        board_ui = getattr(
            getattr(self.ui, "score_board_manager", None), "ui", None)
        if board_ui is not None:
            board_ui.apply_frame_background(None)
        for name, (widget, palette, auto_fill, stylesheet) in self._original.items():
            try:
                widget.setPalette(palette)
                widget.setAutoFillBackground(auto_fill)
                widget.setStyleSheet(stylesheet)
                widget.update()
            except RuntimeError:
                continue
        self.deleteLater()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.ui.centralwidget and event.type() == QEvent.Type.Resize:
            if not self._refresh_pending:
                self._refresh_pending = True
                QTimer.singleShot(0, self._refresh_after_layout)
        return False

    def _refresh_after_layout(self) -> None:
        self._refresh_pending = False
        self.refresh()

    def refresh(self) -> None:
        area = self.ui.centralwidget
        size = area.size()
        if size.width() <= 0 or size.height() <= 0:
            return
        # 只保留一张与 centralwidget 同尺寸的完整画布；不按子控件复制/裁切。
        canvas = QPixmap(size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        self.renderer.render(painter, QRectF(0, 0, size.width(), size.height()))
        painter.end()

        central = area
        central_palette = self._original["centralwidget"][1]
        central_palette.setBrush(QPalette.ColorRole.Window, QBrush(canvas))
        central.setPalette(central_palette)
        central.setAutoFillBackground(True)
        central.update()

        # 计数器是独立窗口，直接复用同一张完整画布，不裁切为局部背景。
        board_ui = getattr(
            getattr(self.ui, "score_board_manager", None), "ui", None)
        if board_ui is not None:
            board_ui.apply_frame_background(canvas)

        # 仅让现有子控件透出父级完整底图。保留其边框和文字 QSS，不复制画布。
        for name, selector in self._CHILDREN.items():
            original = self._original.get(name)
            if original is None:
                continue
            widget, _palette, _auto_fill, base_stylesheet = original
            widget.setAutoFillBackground(False)
            widget.setStyleSheet(
                f"{base_stylesheet} {selector} "
                "{ background-color: transparent; }".strip())
            widget.update()


def _decode_images(
    data: dict[int, bytes],
    allowed_keys: tuple[int, ...],
    label: str,
    total: list[int],
) -> dict[int, QPixmap]:
    """把 {key: bytes} 解码为 {key: QPixmap}，全部成功才返回（原子性）。"""
    out: dict[int, QPixmap] = {}
    for key, raw in data.items():
        if key not in allowed_keys:
            raise SkinError(f"{label}: 未知 key {key}")
        if not isinstance(raw, (bytes, bytearray)):
            raise SkinError(f"{label}[{key}]: 数据不是字节")
        if len(raw) > _MAX_SINGLE_BYTES:
            raise SkinError(f"{label}[{key}]: 单张图片超过上限")
        total[0] += len(raw)
        if total[0] > _MAX_TOTAL_BYTES:
            raise SkinError(f"{label}: 图片总大小超过上限")
        pixmap = QPixmap()
        if not pixmap.loadFromData(bytes(raw)) or pixmap.isNull():
            raise SkinError(f"{label}[{key}]: 图片解码失败")
        out[int(key)] = pixmap
    return out


def _validate_colors(data: dict[str, str]) -> dict[str, str]:
    """校验配色字典：键合法、值是 Qt 能识别的颜色字符串。"""
    out: dict[str, str] = {}
    for key, value in data.items():
        if key not in SKIN_COLOR_KEYS:
            raise SkinError(f"colors: 未知键 {key}")
        if not isinstance(value, str) or len(value) > 32:
            raise SkinError(f"colors[{key}]: 颜色值无效")
        if not QColor(value).isValid():
            raise SkinError(f"colors[{key}]: 无法识别颜色 {value!r}")
        out[str(key)] = value
    return out


# 记录换肤前的原始样式，供 reset 精确还原（首次应用时只记一次）
_ORIGINAL_STYLES: dict[str, str] = {}

# 纯皮肤规则（不含原始 font-size），供 apply_scale 追加
_SCORE_BOARD_QSS_EXTRA: dict[str, str] = {}


def _score_board_widgets(ui: "MineSweeperGUI") -> dict[str, QWidget | None]:
    """取计数器（计分板）窗口及其子控件；窗口可能尚未创建。"""
    manager = getattr(ui, "score_board_manager", None)
    board_ui = getattr(manager, "ui", None)
    if board_ui is None:
        return {}
    return {
        "sb_window": getattr(board_ui, "QWidget", None),
        "sb_label": getattr(board_ui, "label_counter", None),
        "sb_table": getattr(board_ui, "tableWidget", None),
        "sb_button": getattr(board_ui, "pushButton_add", None),
    }


def _widget_keys(ui: "MineSweeperGUI") -> dict[str, QWidget | None]:
    widgets = {
        "mainWindow": ui.mainWindow,
        "centralwidget": ui.centralwidget,
        "frame_1": ui.frame_1,
        "frame": ui.frame,
        "MinenumTimeWigdet": ui.MinenumTimeWigdet,
        "label_info": ui.label_info,
        "label_flag": ui.label_flag,
        # 菜单栏按需求保持原样：纳入列表只是为了记录/还原原始样式，
        # _build_qss 不会为它生成任何规则。
        "menubar": ui.menubar,
    }
    widgets.update(_score_board_widgets(ui))
    return widgets


def _capture_original_styles(ui: "MineSweeperGUI") -> None:
    """首次换肤前记录各控件原始 styleSheet 与 palette，便于 reset 还原。"""
    if _ORIGINAL_STYLES:
        return
    widgets = _widget_keys(ui)
    for name, widget in widgets.items():
        if widget is None:
            continue
        _ORIGINAL_STYLES[f"{name}.qss"] = widget.styleSheet() or ""
    for name in ("mainWindow", "label_info", "label_flag",
                 "sb_window", "sb_label", "sb_table", "sb_button"):
        widget = widgets.get(name)
        if widget is None:
            continue
        pal = widget.palette()
        _ORIGINAL_STYLES[f"{name}.window"] = pal.window().color().name()
        _ORIGINAL_STYLES[f"{name}.windowtext"] = pal.windowText().color().name()
        if name == "sb_table":
            _ORIGINAL_STYLES["sb_table.base"] = pal.base().color().name()
            _ORIGINAL_STYLES["sb_table.alternatebase"] = (
                pal.alternateBase().color().name())


def _build_qss(
    colors: dict[str, str],
    *,
    frame_background: bool = False,
) -> dict[str, str]:
    """按配色生成各控件的 QSS；只覆盖传入的键。"""
    w = colors.get("window")
    frame = colors.get("frame")
    topbar = colors.get("topbar")
    infobar = colors.get("infobar")
    text = colors.get("text")
    flag_bg = colors.get("flag_bg")

    qss: dict[str, str] = {}

    # 主窗口/中央部件背景。
    # 保留主窗口原始 QSS（如 QMenu::indicator 宽度设置），只追加配色规则，
    # 避免 setStyleSheet 整体覆盖导致菜单行为异常。
    if w:
        original = _ORIGINAL_STYLES.get("mainWindow.qss", "")
        qss["mainWindow"] = (
            original + f" QMainWindow {{ background-color: {w}; }}").strip()
        if not frame_background:
            qss["centralwidget"] = f"QWidget#centralwidget {{ background-color: {w}; }}"
        else:
            qss["centralwidget"] = _ORIGINAL_STYLES.get(
                "centralwidget.qss", "")

    # 立体边框：用 QSS border 覆盖 QFrame 原生 3D 边框
    if frame:
        qss["frame_1"] = (
            f"QFrame#frame_1 {{ border: 6px solid {frame}; border-radius: 2px; }}")
        qss["frame"] = (
            f"QFrame#frame {{ border: 4px solid {frame}; border-radius: 2px; }}")
        qss["MinenumTimeWigdet"] = (
            f"QFrame#MinenumTimeWigdet {{ border: 4px solid {frame}; "
            f"border-radius: 2px; }}")
    elif frame_background:
        # 有整幅背景且未提供 frame 色：边框线交给背景 SVG，QFrame 不再画原生 3D 边。
        qss["frame_1"] = "QFrame#frame_1 { border: none; }"
        qss["frame"] = "QFrame#frame { border: none; }"
        qss["MinenumTimeWigdet"] = "QFrame#MinenumTimeWigdet { border: none; }"

    # 顶部条背景（与边框合并）
    if topbar and not frame_background:
        border = f"border: 4px solid {frame}; border-radius: 2px;" if frame else ""
        qss["MinenumTimeWigdet"] = (
            f"QFrame#MinenumTimeWigdet {{ background-color: {topbar}; "
            f"{border} }}")
    elif frame:
        qss["MinenumTimeWigdet"] = (
            f"QFrame#MinenumTimeWigdet {{ border: 4px solid {frame}; "
            "border-radius: 2px; }")

    # 底部信息栏：背景 + 文字色
    info_parts = []
    if infobar and not frame_background:
        info_parts.append(f"background-color: {infobar};")
    if text:
        info_parts.append(f"color: {text};")
    if info_parts:
        qss["label_info"] = "QLabel#label_info { " + " ".join(info_parts) + " }"

    # 菜单栏：按需求保持系统原样，不改背景、文字色与下拉菜单样式。

    # 右下角国旗标签白底（国旗图案本身不变）
    if flag_bg:
        qss["label_flag"] = f"QLabel#label_flag {{ background-color: {flag_bg}; }}"

    # ── 计数器（计分板）──
    # RoundQWidget 用 GLOBAL_QSS，QTableWidget 有独立的 font-size 样式表，
    # 两者都需要在这里显式覆盖；保留原样式表前缀以免丢字号设置。
    sb_bg = colors.get("sb_bg")
    sb_text = colors.get("sb_text")
    sb_grid = colors.get("sb_grid")
    sb_header = colors.get("sb_header")

    if sb_bg or sb_text:
        parts = []
        if sb_bg:
            parts.append(f"QWidget#Form {{ background-color: {sb_bg}; }}")
        if sb_text:
            parts.append(f"QLabel#label_counter {{ color: {sb_text}; }}")
        qss["sb_window"] = (
            _ORIGINAL_STYLES.get("sb_window.qss", "") + " " + " ".join(parts)
        ).strip()

    if any((sb_bg, sb_text, sb_grid, sb_header)):
        props: list[str] = []
        if sb_text:
            props.append(f"color: {sb_text};")
        if sb_grid:
            props.append(f"gridline-color: {sb_grid};")

        rules = [f"QTableWidget#tableWidget {{ {' '.join(props)} }}"]
        if sb_header:
            rules.append(
                f"QHeaderView::section {{ background-color: {sb_header}; "
                f"color: {sb_text or sb_bg or '#FFFFFF'}; }}")
        # 保留 ui_Form.apply_scale 设置的 font-size（每次缩放都会重设样式表）
        skin_rules = " ".join(rules)
        original_table = _ORIGINAL_STYLES.get("sb_table.qss", "")
        qss["sb_table"] = (original_table + " " + skin_rules).strip()
        # 只存皮肤规则（不含原始 font-size），供 apply_scale 追加
        _SCORE_BOARD_QSS_EXTRA["sb_table_rules"] = skin_rules

    if sb_header:
        qss["sb_button"] = (
            _ORIGINAL_STYLES.get("sb_button.qss", "") + " "
            f"QPushButton#pushButton_add:hover {{ background-color: {sb_header}; }}"
        ).strip()

    return qss


def _apply_colors(
    ui: "MineSweeperGUI",
    colors: dict[str, str],
    *,
    frame_background: bool = False,
) -> None:
    """把配色写到主窗口各控件；同时用 QPalette 兜底（QFrame/QLabel 更吃这套）。"""
    _capture_original_styles(ui)
    widgets = _widget_keys(ui)
    _SCORE_BOARD_QSS_EXTRA.clear()
    qss = _build_qss(colors, frame_background=frame_background)

    for name, stylesheet in qss.items():
        widget = widgets.get(name)
        if widget is not None:
            widget.setStyleSheet(stylesheet)

    # RoundMixin 自绘圆角背景不会受 QSS 影响，需设置其专用填充色。
    sb_window = widgets.get("sb_window")
    if sb_window is not None and hasattr(sb_window, "skin_bg_color"):
        sb_bg = colors.get("sb_bg")
        setattr(sb_window, "skin_bg_color", QColor(sb_bg) if sb_bg else None)
        sb_window.update()

    sb_table = widgets.get("sb_table")
    if sb_table is not None:
        table = cast(QTableWidget, sb_table)
        sb_bg = colors.get("sb_bg")
        if sb_bg:
            table_palette = table.palette()
            table_palette.setColor(QPalette.ColorRole.Base, QColor(sb_bg))
            table_palette.setColor(QPalette.ColorRole.AlternateBase,
                                   QColor(sb_bg))
            table.setPalette(table_palette)
            table.viewport().setPalette(table_palette)
            table.viewport().setAutoFillBackground(True)

    board_ui = getattr(getattr(ui, "score_board_manager", None), "ui", None)
    if board_ui is not None:
        board_ui.apply_skin_colors({
            key: colors.get(key)
            for key in ("sb_bg", "sb_text")
        })

    # QPalette 兜底：窗口背景与信息文字
    for name, role, key in (
        ("mainWindow", "window", "window"),
        ("label_info", "windowtext", "text"),
        ("label_flag", "window", "flag_bg"),
        ("sb_window", "window", "sb_bg"),
        ("sb_window", "windowtext", "sb_text"),
        ("sb_table", "window", "sb_bg"),
        ("sb_table", "windowtext", "sb_text"),
    ):
        if frame_background and name in (
            "centralwidget", "frame_1", "frame", "MinenumTimeWigdet",
            "label_info") and role == "window":
            continue
        value = colors.get(key)
        if not value:
            continue
        widget = widgets.get(name)
        if widget is None:
            continue
        pal = widget.palette()
        if role == "window":
            pal.setColor(QPalette.ColorRole.Window, QColor(value))
        else:
            pal.setColor(QPalette.ColorRole.WindowText, QColor(value))
        widget.setPalette(pal)
        widget.setAutoFillBackground(True)

    # QSS 变化需要重绘
    for widget in widgets.values():
        if widget is not None:
            widget.update()


def _restore_colors(ui: "MineSweeperGUI") -> None:
    """恢复换肤前记录的原始样式与 palette。"""
    _SCORE_BOARD_QSS_EXTRA.clear()
    widgets = _widget_keys(ui)
    for name, widget in widgets.items():
        if widget is None:
            continue
        widget.setStyleSheet(_ORIGINAL_STYLES.get(f"{name}.qss", ""))
    sb_window = widgets.get("sb_window")
    if sb_window is not None and hasattr(sb_window, "skin_bg_color"):
        setattr(sb_window, "skin_bg_color", None)
    board_ui = getattr(getattr(ui, "score_board_manager", None), "ui", None)
    if board_ui is not None:
        board_ui.apply_skin_colors(None)
    for name in ("mainWindow", "label_info", "label_flag",
                 "sb_window", "sb_label", "sb_table", "sb_button"):
        widget = widgets.get(name)
        if widget is None:
            continue
        pal = widget.palette()
        win = _ORIGINAL_STYLES.get(f"{name}.window")
        txt = _ORIGINAL_STYLES.get(f"{name}.windowtext")
        if win:
            pal.setColor(QPalette.ColorRole.Window, QColor(win))
        if txt:
            pal.setColor(QPalette.ColorRole.WindowText, QColor(txt))
        if name == "sb_table":
            base = _ORIGINAL_STYLES.get("sb_table.base")
            alternate = _ORIGINAL_STYLES.get("sb_table.alternatebase")
            if base:
                pal.setColor(QPalette.ColorRole.Base, QColor(base))
            if alternate:
                pal.setColor(QPalette.ColorRole.AlternateBase,
                             QColor(alternate))
        widget.setPalette(pal)
        widget.setAutoFillBackground(False)
        if name == "sb_table":
            table = cast(QTableWidget, widget)
            table.viewport().setPalette(pal)
            table.viewport().setAutoFillBackground(False)
    for widget in widgets.values():
        if widget is not None:
            widget.update()


def reset_skin(ui: "MineSweeperGUI") -> None:
    """清空所有内存皮肤源，恢复磁盘默认资源、原始配色并刷新显示。"""
    frame_background = getattr(ui, "_frame_svg_background", None)
    if frame_background is not None:
        frame_background.detach()
        delattr(ui, "_frame_svg_background")

    label = ui.label
    label.skin_source = None
    label.skin_source_bytes = None

    ui.skin_faces = None
    ui.skin_leds = None
    ui.label_2.skin_face_down = None
    ui.label_2.skin_face_normal = None

    _restore_colors(ui)
    _refresh(ui)
    logger.info("[Skin] 已恢复默认皮肤与配色")


def apply_skin(ui: "MineSweeperGUI", cmd: SetSkinCommand) -> None:
    """
    应用皮肤。先在临时变量里完成全部校验与解码，成功后一次性写入，
    中途失败不改动任何现有缓存（原子替换）。
    """
    if cmd.reset:
        reset_skin(ui)
        return

    total = [0]
    cells = _decode_images(cmd.cells, SKIN_CELL_KEYS, "cells", total)
    leds = _decode_images(cmd.leds, SKIN_LED_KEYS, "leds", total)
    faces = _decode_images(cmd.faces, SKIN_FACE_KEYS, "faces", total)
    frame_svg = _validate_frame_svg(
        getattr(cmd, "frame_svg", None), total
    )
    colors = _validate_colors(cmd.colors)

    # ── 全部校验成功，以下为原子写入 ──
    label = ui.label
    if cells:
        label.skin_source = cells
        # 保存原始字节，供复制局面为 SVG 时渲染
        label.skin_source_bytes = {
            key: bytes(raw) for key, raw in cmd.cells.items()
        }
    if leds:
        ui.skin_leds = leds
    if faces:
        ui.skin_faces = faces
        # StatusLabel 的按下/松开两张脸必须同步，否则按下时会露出默认脸
        ui.label_2.skin_face_normal = faces.get(FACE_SMILE)
        ui.label_2.skin_face_down = faces.get(FACE_SMILE_DOWN)

    # 每次切换皮肤都先清除上一张大 SVG，避免新皮肤未提供 frame.svg 时残留旧图。
    previous = getattr(ui, "_frame_svg_background", None)
    if previous is not None:
        previous.detach()
        delattr(ui, "_frame_svg_background")

    if colors or frame_svg is not None:
        _apply_colors(ui, colors, frame_background=frame_svg is not None)

    if frame_svg is not None:
        ui._frame_svg_background = _FrameSvgBackground(ui, frame_svg)

    _refresh(ui)
    logger.info(
        f"[Skin] 已应用皮肤: cells={len(cells)}, leds={len(leds)}, "
        f"faces={len(faces)}, colors={len(colors)}, "
        f"total={total[0]} bytes"
    )


def _refresh(ui: "MineSweeperGUI") -> None:
    """重建所有派生缓存并刷新当前显示状态。

    复用控件原有的缩放入口，保证 pixSize 变化、重开局、切模式时
    皮肤不会被磁盘默认资源覆盖。
    """
    pix_size = ui.pixSize
    label = ui.label

    # 原始资源缓存（后续所有 reload* 都从这里缩放）
    label.importCellPic(pix_size)
    ui.importLEDPic(pix_size)
    ui.label_2.reloadFace(pix_size)

    # 当前显示状态：否则界面会停在旧帧
    label.update()
    ui.set_face(FACE_SMILE)
    ui.showMineNum(ui.mineUnFlagedNum)
    ui.showTime(ui.time_10ms // 100)
    ui.set_country_flag()


def handle_set_skin(ui: "MineSweeperGUI", cmd: SetSkinCommand) -> CommandResponse:
    """SetSkinCommand 的主线程 handler 入口。"""
    try:
        apply_skin(ui, cmd)
        return CommandResponse(request_id=cmd.request_id, success=True)
    except SkinError as e:
        logger.warning(f"[Skin] 皮肤被拒绝: {e}")
        return CommandResponse(
            request_id=cmd.request_id, success=False, error=str(e))
    except Exception as e:
        logger.opt(exception=True).warning(f"[Skin] 应用皮肤失败: {e}")
        return CommandResponse(
            request_id=cmd.request_id, success=False, error=str(e))
