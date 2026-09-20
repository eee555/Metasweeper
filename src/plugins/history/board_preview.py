"""局面预览浮窗

鼠标悬浮在历史记录表格的 `board` 列上时，弹出一个只读的局面预览窗口。

`board` 字段存的是「带数字答案局面」的 JSON 文本
（形如 ``[[0,0,1,-1,2], ...]``，见 GameFinishedEvent.board）：

- ``-1``          雷
- ``0``           空白格
- ``1`` ~ ``8``   周围雷数

同时兼容游戏显示局面的编码（BoardUpdateEvent.game_board）：

- ``10`` 未揭开、``11`` 标旗、``14`` 错误标旗、
  ``15`` 爆炸的雷、``16`` 未爆炸的雷
"""

from __future__ import annotations

import json

from PyQt5.QtCore import QPoint, QRect, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygon, QPaintEvent
from PyQt5.QtWidgets import QApplication, QWidget

# ── 格子编码（与 config/constants.py、BoardUpdateEvent 文档保持一致）──
CELL_MINE = -1
CELL_UNOPENED = 10
CELL_FLAGGED = 11
CELL_WRONG_FLAG = 14
CELL_EXPLODED_MINE = 15
CELL_UNEXPLODED_MINE = 16

# 已揭开/未揭开格子的底衬与网格线
COLOR_COVERED = QColor("#bdbdbd")
COLOR_REVEALED = QColor("#e6e6e6")
COLOR_GRID = QColor("#b4b4b4")
COLOR_BORDER = QColor("#8a8a8a")
COLOR_MINE = QColor("#212121")
COLOR_EXPLODED = QColor("#e57373")
COLOR_FLAG = QColor("#e53935")

# 经典扫雷数字配色（1~8）
NUMBER_COLORS = {
    1: QColor("#0000ff"),
    2: QColor("#008000"),
    3: QColor("#ff0000"),
    4: QColor("#000080"),
    5: QColor("#800000"),
    6: QColor("#008080"),
    7: QColor("#000000"),
    8: QColor("#808080"),
}

CELL_SIZE = 24            # 常规格子边长（像素）
MIN_CELL_SIZE = 5         # 超大局面时的最小边长
PADDING = 6               # 浮窗内边距
MAX_SCREEN_RATIO = 0.6    # 浮窗最多占屏幕可用区域的这个比例
CURSOR_OFFSET = QPoint(18, 18)   # 相对光标的偏移，避免浮窗盖住光标


def parse_board(text: object) -> list[list[int]] | None:
    """把 board 字段（JSON 文本 / 二维列表）解析成规整的二维整数列表

    Returns:
        规整的二维列表（每行等长、元素为 int）；
        解析失败或数据为空时返回 None。
    """
    if isinstance(text, str):
        text = text.strip()
        if not text:
            return None
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
    else:
        data = text

    if not isinstance(data, (list, tuple)) or not data:
        return None

    board: list[list[int]] = []
    width = 0
    for row in data:
        if not isinstance(row, (list, tuple)):
            return None
        cells: list[int] = []
        for cell in row:
            # 允许 bool/float 等数字形态，无法转成 int 的一律视为不可识别
            if isinstance(cell, bool) or not isinstance(cell, (int, float)):
                return None
            cells.append(int(cell))
        if not width:
            width = len(cells)
        if width == 0 or len(cells) != width:
            return None   # 非矩形局面，不预览
        board.append(cells)
    return board


def cell_size_for(board: list[list[int]], screen_size: QSize) -> int:
    """按屏幕可用区域计算格子边长（大局面自动缩小，保证浮窗能完整显示）"""
    rows = len(board)
    cols = len(board[0])
    max_w = max(1, int(screen_size.width() * MAX_SCREEN_RATIO) - 2 * PADDING)
    max_h = max(1, int(screen_size.height() * MAX_SCREEN_RATIO) - 2 * PADDING)
    fit = min(max_w // cols, max_h // rows)
    return max(MIN_CELL_SIZE, min(CELL_SIZE, fit))


class BoardPreviewPopup(QWidget):
    """只读局面预览浮窗（ToolTip 类型，不抢焦点、不接收鼠标操作）"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self._board: list[list[int]] = []
        self._cell_size = CELL_SIZE
        self._number_font = QFont()
        self._number_font.setBold(True)

    # ── 数据 ──────────────────────────────────────────────
    def set_board(self, board: list[list[int]]) -> None:
        """设置要预览的局面并重算尺寸（空局面视为不显示）"""
        self._board = board
        if not board:
            self.resize(0, 0)
            return
        screen = self.screen() or QApplication.primaryScreen()
        size = screen.availableGeometry().size() if screen else QSize(1920, 1080)
        self._cell_size = cell_size_for(board, size)
        self._number_font.setPixelSize(max(8, int(self._cell_size * 0.72)))
        self.setFixedSize(self.sizeHint())

    def board(self) -> list[list[int]]:
        return self._board

    def sizeHint(self) -> QSize:
        if not self._board:
            return QSize(0, 0)
        rows = len(self._board)
        cols = len(self._board[0])
        return QSize(cols * self._cell_size + 2 * PADDING,
                     rows * self._cell_size + 2 * PADDING)

    # ── 展示 ──────────────────────────────────────────────
    def show_board(self, board: list[list[int]], global_pos: QPoint) -> None:
        """在光标附近弹出预览（会自动贴边，保证完整落在屏幕内）"""
        self.set_board(board)
        if not self._board:
            self.hide()
            return
        self.move(self._clamp_position(global_pos))
        self.show()
        self.raise_()

    def _clamp_position(self, global_pos: QPoint) -> QPoint:
        """默认出现在光标右下方，超出屏幕时贴边（不盖住光标所在格子）"""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return global_pos + CURSOR_OFFSET
        area = screen.availableGeometry()
        pos = global_pos + CURSOR_OFFSET
        x = min(pos.x(), area.right() - self.width() + 1)
        y = min(pos.y(), area.bottom() - self.height() + 1)
        # 右下角放不下时往左上让位，仍然尽量避开光标
        if x < area.left() + CURSOR_OFFSET.x():
            x = max(area.left(), global_pos.x() - self.width() - CURSOR_OFFSET.x())
        if y < area.top() + CURSOR_OFFSET.y():
            y = max(area.top(), global_pos.y() - self.height() - CURSOR_OFFSET.y())
        return QPoint(x, y)

    # ── 绘制 ──────────────────────────────────────────────
    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._board:
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), COLOR_REVEALED)
        cell = self._cell_size
        for r, row in enumerate(self._board):
            for c, value in enumerate(row):
                rect = QRect(PADDING + c * cell, PADDING + r * cell, cell, cell)
                self._draw_cell(painter, rect, value)
        # drawRect 会用当前画刷填充，这里必须先清掉画刷（否则会把整个画面刷成
        # 上一个格子残留的画刷颜色，例如雷高光的白色）
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(COLOR_BORDER))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()

    def _draw_cell(self, painter: QPainter, rect: QRect, value: int) -> None:
        if value in (CELL_UNOPENED, CELL_FLAGGED, CELL_WRONG_FLAG):
            self._draw_covered(painter, rect)
            if value in (CELL_FLAGGED, CELL_WRONG_FLAG):
                self._draw_flag(painter, rect)
            if value == CELL_WRONG_FLAG:
                self._draw_cross(painter, rect)
            return

        # 已揭开：底衬 + 细网格线（drawRect 会填充画刷，务必置空）
        painter.fillRect(rect, COLOR_REVEALED)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(COLOR_GRID))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        if value == CELL_EXPLODED_MINE:
            painter.fillRect(rect.adjusted(1, 1, -1, -1), COLOR_EXPLODED)
            self._draw_mine(painter, rect)
        elif value in (CELL_MINE, CELL_UNEXPLODED_MINE):
            self._draw_mine(painter, rect)
        elif 1 <= value <= 8:
            self._draw_number(painter, rect, value)

    def _draw_covered(self, painter: QPainter, rect: QRect) -> None:
        """未揭开的格子：凸起立体感"""
        painter.fillRect(rect, COLOR_COVERED)
        painter.setPen(QPen(COLOR_REVEALED.lighter(115)))
        painter.drawLine(rect.topLeft(), rect.topRight())
        painter.drawLine(rect.topLeft(), rect.bottomLeft())
        painter.setPen(QPen(COLOR_BORDER))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.drawLine(rect.topRight(), rect.bottomRight())

    def _draw_number(self, painter: QPainter, rect: QRect, value: int) -> None:
        painter.setFont(self._number_font)
        painter.setPen(QPen(NUMBER_COLORS.get(value, COLOR_MINE)))
        painter.drawText(rect, Qt.AlignCenter, str(value))

    def _draw_mine(self, painter: QPainter, rect: QRect) -> None:
        cell = rect.width()
        radius = max(1.0, cell * 0.30)
        center = rect.center()
        painter.setPen(Qt.NoPen)
        painter.setBrush(COLOR_MINE)
        painter.drawEllipse(center, int(radius), int(radius))
        # 高光小点，让小尺寸下也能看出是雷
        if cell >= 10:
            painter.setBrush(QColor("#ffffff"))
            highlight = max(1, int(radius * 0.32))
            painter.drawEllipse(
                QPoint(center.x() - int(radius * 0.35),
                       center.y() - int(radius * 0.35)),
                highlight, highlight)

    def _draw_flag(self, painter: QPainter, rect: QRect) -> None:
        cell = rect.width()
        pole_x = rect.left() + int(cell * 0.46)
        top = rect.top() + int(cell * 0.22)
        bottom = rect.bottom() - int(cell * 0.20)
        painter.setPen(QPen(QColor("#37474f"), max(1, cell // 12)))
        painter.drawLine(pole_x, top, pole_x, bottom)
        painter.drawLine(pole_x - int(cell * 0.18), bottom,
                         pole_x + int(cell * 0.18), bottom)
        painter.setPen(Qt.NoPen)
        painter.setBrush(COLOR_FLAG)
        painter.drawPolygon(QPolygon([
            QPoint(pole_x, top),
            QPoint(pole_x + int(cell * 0.30), top + int(cell * 0.14)),
            QPoint(pole_x, top + int(cell * 0.28)),
        ]))

    def _draw_cross(self, painter: QPainter, rect: QRect) -> None:
        """错误标旗：旗子上再叠一个红叉"""
        painter.setPen(QPen(COLOR_FLAG, max(1, rect.width() // 10)))
        painter.drawLine(rect.left() + 2, rect.top() + 2,
                         rect.right() - 2, rect.bottom() - 2)
        painter.drawLine(rect.right() - 2, rect.top() + 2,
                         rect.left() + 2, rect.bottom() - 2)
