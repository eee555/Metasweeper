from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QPolygonF, QPainter, QPixmap, QPainterPath, QColor, QPen, QFont
import ms_toollib as ms
from PySide6.QtCore import QPoint, Qt, QRect
from config.constants import BOARD_READY, BOARD_PLAYING, CELL_UNOPENED
from shared_types.enums import MouseState
import utils
from utils.path_utils import resource_path


class mineLabel(QtWidgets.QLabel):
    # 一整个局面的控件，而不是一个格子
    leftRelease = QtCore.Signal(int, int)  # 定义信号
    rightRelease = QtCore.Signal(int, int)
    leftPressed = QtCore.Signal(int, int)
    rightPressed = QtCore.Signal(int, int)
    leftAndRightPressed = QtCore.Signal(int, int)
    leftAndRightRelease = QtCore.Signal(int, int)
    mouseMove = QtCore.Signal(int, int)
    mousewheelEvent = QtCore.Signal(int, int, int)
    row = 0
    column = 0
    pixSize = 0

    def __init__(self, parent):
        super(mineLabel, self).__init__(parent)
        points = []
        mouse_ = QPolygonF(points)
        self.mouse = QPainterPath()
        self.mouse.addPolygon(mouse_)
        self.setMouseTracking(True)
        # 是否画光标。不仅控制画光标，还代表了是游戏还是播放录像。
        self.paint_cursor = False
        # 是否打印概率
        self.paintProbability = False
        self.current_x = 0
        self.current_y = 0
        self.path_trace_enabled = False
        self.path_trace_points = []
        self.path_trace_left_clicks = set()
        self.path_trace_right_clicks = set()
        self.path_trace_double_clicks = set()
        self.current_trace_event_id = 0
        self.show_opening = False
        self.opening_nums = []
        self.opening_ops = []
        self.opening_ops2 = []
        self.opening_count = 0
        self.hover_highlight_cells = ()

    def setPath(self):
        m = resource_path('media')
        self.celldown_path = str(m.joinpath('celldown.svg'))
        self.cell1_path = str(m.joinpath('cell1.svg'))
        self.cell2_path = str(m.joinpath('cell2.svg'))
        self.cell3_path = str(m.joinpath('cell3.svg'))
        self.cell4_path = str(m.joinpath('cell4.svg'))
        self.cell5_path = str(m.joinpath('cell5.svg'))
        self.cell6_path = str(m.joinpath('cell6.svg'))
        self.cell7_path = str(m.joinpath('cell7.svg'))
        self.cell8_path = str(m.joinpath('cell8.svg'))
        self.cellup_path = str(m.joinpath('cellup.svg'))
        self.cellmine_path = str(m.joinpath('cellmine.svg'))
        self.cellflag_path = str(m.joinpath('cellflag.svg'))
        self.blast_path = str(m.joinpath('blast.svg'))
        self.falsemine_path = str(m.joinpath('falsemine.svg'))
        self.mine_path = str(m.joinpath('mine.svg'))

    def set_rcp(self, row, column, pixSize):
        '''
        ui层面，重设一下宽、高、大小
        '''
        # 即使只改pixSize，工具箱里的这些变量也要改，没有简便的接口，一步不能少。
        self.row = row
        self.column = column
        self.hover_highlight_cells = ()
        if self.paintProbability:
            # self.ms_board = utils.abstract_game_board()
            self.ms_board = utils.CoreBaseVideo(
                [[0] * column for _ in range(row)], pixSize)
        else:
            if hasattr(self, "ms_board"):
                if isinstance(self.ms_board, utils.CoreBaseVideo) or\
                        not isinstance(self.ms_board, ms.BaseVideo):
                    self.ms_board = ms.BaseVideo(
                        [[0] * column for _ in range(row)], pixSize)
                else:
                    self.ms_board.reset(row, column, pixSize)
            else:
                self.ms_board = ms.BaseVideo(
                    [[0] * column for _ in range(row)], pixSize)
            self.boardProbability = [[0.0] * column for _ in range(row)]

        if self.pixSize != pixSize:
            self.pixSize = pixSize
            self.importCellPic(pixSize)
            # self.resize(QtCore.QSize(pixSize * column + 8, pixSize * row + 8))
            self.setMinimumSize(QtCore.QSize(
                pixSize * column, pixSize * row))
            self.setMaximumSize(QtCore.QSize(
                pixSize * column, pixSize * row))
            # self.current_x = self.row # 鼠标坐标，和高亮的展示有关
            # self.current_y = self.column

            points = [QPoint(0, 0),   # 你猜这个多边形是什么，它就是鼠标
                      QPoint(0, pixSize),
                      QPoint(int(0.227 * pixSize), int(0.773 * pixSize)),
                      QPoint(int(0.359 * pixSize), int(1.125 * pixSize)),
                      QPoint(int(0.493 * pixSize), int(1.066 * pixSize)),
                      QPoint(int(0.357 * pixSize), int(0.72 * pixSize)),
                      QPoint(int(0.666 * pixSize), int(0.72 * pixSize))]
            mouse_ = QPolygonF(points)
            self.mouse = QPainterPath()
            self.mouse.addPolygon(mouse_)

    def mousePressEvent(self, e):
        # 重载一下鼠标点击事件
        xx = int(e.localPos().x())
        yy = int(e.localPos().y())
        # print("press: ", xx, yy)
        if yy < 0 or xx < 0 or yy >= self.row * self.pixSize or\
                xx >= self.column * self.pixSize:
            self.current_x = self.row * self.pixSize
            self.current_y = self.column * self.pixSize
        else:
            self.current_x = yy
            self.current_y = xx

        # xx和yy是反的，列、行
        if e.buttons() == QtCore.Qt.LeftButton | QtCore.Qt.RightButton:
            self.leftAndRightPressed.emit(self.current_x, self.current_y)
        else:
            if e.buttons() == QtCore.Qt.LeftButton:
                self.leftPressed.emit(self.current_x, self.current_y)
            elif e.buttons() == QtCore.Qt.RightButton:
                self.rightPressed.emit(self.current_x, self.current_y)

    def mouseReleaseEvent(self, e):
        # 每个标签的鼠标事件发射给槽的都是自身的坐标
        # 所以获取释放点相对本标签的偏移量，矫正发射的信号
        xx = int(e.localPos().x())
        yy = int(e.localPos().y())
        # print("release: ", xx, yy)

        if yy < 0 or xx < 0 or yy >= self.row * self.pixSize or\
                xx >= self.column * self.pixSize:
            self.current_x = self.row * self.pixSize
            self.current_y = self.column * self.pixSize
        else:
            self.current_x = yy
            self.current_y = xx

        if e.button() == QtCore.Qt.LeftButton:
            self.leftRelease.emit(self.current_x, self.current_y)
        elif e.button() == QtCore.Qt.RightButton:
            self.rightRelease.emit(self.current_x, self.current_y)

    def mouseMoveEvent(self, e):
        xx = int(e.localPos().x())
        yy = int(e.localPos().y())
        # print('移动位置{}, {}'.format(xx, yy))
        if yy < 0 or xx < 0 or yy >= self.row * self.pixSize or\
                xx >= self.column * self.pixSize:
            self.current_x = self.row * self.pixSize
            self.current_y = self.column * self.pixSize
        else:
            self.current_x = yy
            self.current_y = xx
        self.mouseMove.emit(self.current_x, self.current_y)

    def wheelEvent(self, event):
        # 滚轮事件
        angle = event.angleDelta()
        angle_y = angle.y()
        xx = int(event.position().x())  # 距离左侧
        yy = int(event.position().y())  # 距离上方
        if yy < 0 or xx < 0 or yy >= self.row * self.pixSize or\
                xx >= self.column * self.pixSize:
            self.mousewheelEvent.emit(angle_y, self.row, self.column)
        else:
            self.mousewheelEvent.emit(
                angle_y, yy // self.pixSize, xx // self.pixSize)

    def compute_openings(self):
        gb = self.ms_board.game_board
        row = len(gb)
        col = len(gb[0])
        nums = [[-1] * col for _ in range(row)]
        ops = [[0] * col for _ in range(row)]
        ops2 = [[0] * col for _ in range(row)]
        for i in range(row):
            for j in range(col):
                val = gb[i][j]
                if 0 <= val <= 8:
                    nums[i][j] = val
        opening_count = 0
        for i in range(row):
            for j in range(col):
                if nums[i][j] != 0 or ops[i][j] != 0:
                    continue
                opening_count += 1
                stack = [(i, j)]
                while stack:
                    ci, cj = stack.pop()
                    if not (0 <= ci < row and 0 <= cj < col) or nums[ci][cj] == -1:
                        continue
                    if ops[ci][cj] == opening_count or ops2[ci][cj] == opening_count:
                        continue
                    if nums[ci][cj] == 0:
                        ops[ci][cj] = opening_count
                        for di in (-1, 0, 1):
                            for dj in (-1, 0, 1):
                                if di != 0 or dj != 0:
                                    ni, nj = ci + di, cj + dj
                                    if 0 <= ni < row and 0 <= nj < col:
                                        if nums[ni][nj] == 0 and ops[ni][nj] == 0:
                                            stack.append((ni, nj))
                                        elif nums[ni][nj] > 0:
                                            if ops[ni][nj] == 0:
                                                ops[ni][nj] = opening_count
                                            elif ops[ni][nj] != opening_count and ops2[ni][nj] == 0:
                                                ops2[ni][nj] = opening_count
                    elif nums[ci][cj] > 0:
                        if ops[ci][cj] == 0:
                            ops[ci][cj] = opening_count
                        elif ops[ci][cj] != opening_count and ops2[ci][cj] == 0:
                            ops2[ci][cj] = opening_count
        self.opening_nums = nums
        self.opening_ops = ops
        self.opening_ops2 = ops2
        self.opening_count = opening_count

    def draw_openings(self, painter):
        pix_size = self.pixSize
        row = len(self.opening_ops)
        col = len(self.opening_ops[0])
        nums = self.opening_nums
        ops = self.opening_ops
        ops2 = self.opening_ops2

        def same_opening(i1, j1, i2, j2):
            if not (0 <= i2 < row and 0 <= j2 < col):
                return False
            if ops[i2][j2] == 0 and ops2[i2][j2] == 0:
                return False
            return (ops[i1][j1] == ops[i2][j2] or
                    ops[i1][j1] == ops2[i2][j2] or
                    ops2[i1][j1] == ops[i2][j2] or
                    ops2[i1][j1] == ops2[i2][j2])

        def is_zero_same(i1, j1, i2, j2):
            if not (0 <= i2 < row and 0 <= j2 < col):
                return False
            return nums[i2][j2] == 0 and same_opening(i1, j1, i2, j2)

        def is_nonzero_same(i1, j1, i2, j2):
            if not (0 <= i2 < row and 0 <= j2 < col):
                return False
            return nums[i2][j2] > 0 and same_opening(i1, j1, i2, j2)

        # 画黄色连线（将op边界格子的中心点连起来）
        pen = QPen(QColor("#ffff00"), 3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        for i in range(row):
            for j in range(col):
                if ops[i][j] <= 0 or nums[i][j] <= 0:
                    continue

                nonzero_down = is_nonzero_same(i, j, i + 1, j)
                nonzero_right = is_nonzero_same(i, j, i, j + 1)

                if nonzero_down:
                    if (is_zero_same(i, j, i, j - 1) or
                        is_zero_same(i, j, i, j + 1) or
                        is_zero_same(i, j, i + 1, j - 1) or
                            is_zero_same(i, j, i + 1, j + 1)):
                        cx = int((j + 0.5) * pix_size)
                        cy1 = 0 if i == 0 else int((i + 0.5) * pix_size)
                        cy2 = int((i + 2.0) * pix_size) if i == row - \
                            2 else int((i + 1.5) * pix_size)
                        painter.drawLine(cx, cy1, cx, cy2)

                if nonzero_right:
                    if (is_zero_same(i, j, i - 1, j) or
                        is_zero_same(i, j, i + 1, j) or
                        is_zero_same(i, j, i - 1, j + 1) or
                            is_zero_same(i, j, i + 1, j + 1)):
                        cy = int((i + 0.5) * pix_size)
                        cx1 = 0 if j == 0 else int((j + 0.5) * pix_size)
                        cx2 = int((j + 2.0) * pix_size) if j == col - \
                            2 else int((j + 1.5) * pix_size)
                        painter.drawLine(cx1, cy, cx2, cy)

        # 画黄色编号
        if self.opening_count > 0:
            pts = [[] for _ in range(self.opening_count)]
            for i in range(row):
                for j in range(col):
                    k = ops[i][j]
                    if nums[i][j] == 0 and k > 0 and k <= self.opening_count:
                        pts[k - 1].append((i, j))

            font = painter.font()
            font.setPixelSize(max(8, int(pix_size * 0.7)))
            painter.setFont(font)
            painter.setPen(QColor("#ffff00"))

            for k in range(self.opening_count):
                p = pts[k]
                if not p:
                    continue
                xs = sorted(set(x for x, _ in p))
                mx = xs[len(xs) // 2]
                ys = sorted([y for x, y in p if x == mx])
                my = ys[len(ys) // 2]
                cx = my * pix_size
                cy = mx * pix_size
                painter.drawText(QRect(cx, cy, pix_size, pix_size),
                                 Qt.AlignCenter, str(k + 1))

    def highlight_cells(self, cells):
        valid_cells = tuple(
            (row, column)
            for row, column in cells
            if 0 <= row < self.row and 0 <= column < self.column
        )
        if valid_cells != self.hover_highlight_cells:
            self.hover_highlight_cells = valid_cells
            self.update()

    def clear_highlight_cell(self):
        if self.hover_highlight_cells:
            self.hover_highlight_cells = ()
            self.update()

    def draw_hover_highlight(self, painter):
        if not self.hover_highlight_cells:
            return

        pix_size = self.pixSize
        painter.save()
        painter.setBrush(QColor(255, 235, 59, 90))
        painter.setPen(QPen(QColor("#ff9800"), max(2, pix_size // 12)))
        for row, column in self.hover_highlight_cells:
            painter.drawRect(column * pix_size + 1, row * pix_size + 1,
                             max(1, pix_size - 2), max(1, pix_size - 2))
        painter.restore()

    def paintEvent(self, event):
        super().paintEvent(event)
        pix_size = self.pixSize
        painter = QPainter()
        game_board = self.ms_board.game_board
        mouse_state = self.ms_board.mouse_state
        if self.paint_cursor:  # 播放录像
            game_board_state = BOARD_READY
            (x, y) = self.ms_board.x_y
            current_x = y // self.pixSize
            current_y = x // self.pixSize
            # poss = self.ms_board.game_board_poss
        else:  # 游戏
            game_board_state = self.ms_board.game_board_state
            current_x = self.current_x // self.pixSize
            current_y = self.current_y // self.pixSize
            # poss = self.boardProbability
        painter.begin(self)
        # 画游戏局面
        row = len(game_board)
        column = len(game_board[0])
        for i in range(row):
            for j in range(column):
                if game_board[i][j] == CELL_UNOPENED:
                    painter.drawPixmap(j * pix_size, i *
                                       pix_size, QPixmap(self.pixmapNum[10]))
                    if self.paintProbability:  # 画概率
                        if self.paint_cursor:
                            painter.setOpacity(
                                self.ms_board.game_board_poss[i][j])
                        else:
                            painter.setOpacity(self.boardProbability[i][j])
                        painter.drawPixmap(
                            j * pix_size, i * pix_size, QPixmap(self.pixmapNum[100]))
                        painter.setOpacity(1.0)
                else:
                    painter.drawPixmap(
                        j * pix_size, i * pix_size, QPixmap(self.pixmapNum[game_board[i][j]]))

        # 画 openings 黄色边框和编号
        if self.show_opening:
            self.compute_openings()
            self.draw_openings(painter)

        # 画高亮
        if (game_board_state == BOARD_PLAYING or game_board_state == BOARD_READY or game_board_state == 5) and\
                current_x < row and current_y < column:
            if mouse_state == MouseState.Chording.value or mouse_state == MouseState.ChordingNotFlag.value:
                for r in range(max(current_x - 1, 0), min(current_x + 2, row)):
                    for c in range(max(current_y - 1, 0), min(current_y + 2, column)):
                        if game_board[r][c] == CELL_UNOPENED:
                            painter.drawPixmap(
                                c * pix_size, r * pix_size, QPixmap(self.pixmapNum[0]))
            elif mouse_state == MouseState.DownUp.value and game_board[current_x][current_y] == CELL_UNOPENED:
                painter.drawPixmap(
                    current_y * pix_size, current_x * pix_size, QPixmap(self.pixmapNum[0]))
        # 画鼠标路径轨迹
        if self.path_trace_enabled and self.path_trace_points:
            n = min(self.current_trace_event_id, len(self.path_trace_points))
            if n > 0:
                painter.save()
                painter.fillRect(self.rect(), QColor(128, 128, 128, 100))
                pen = QPen(Qt.white, 2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                for i in range(n - 1):
                    x1, y1 = self.path_trace_points[i]
                    x2, y2 = self.path_trace_points[i + 1]
                    painter.drawLine(x1, y1, x2, y2)
                for i in range(n):
                    px, py = self.path_trace_points[i]
                    if i in self.path_trace_left_clicks:
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QColor(255, 255, 0))
                        painter.drawEllipse(QPoint(px, py), 4, 4)
                    elif i in self.path_trace_right_clicks:
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QColor(0, 255, 255))
                        painter.drawEllipse(QPoint(px, py), 4, 4)
                    elif i in self.path_trace_double_clicks:
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QColor(0, 255, 0))
                        painter.drawEllipse(QPoint(px, py), 4, 4)
                painter.restore()
        self.draw_hover_highlight(painter)
        # 画光标
        if self.paint_cursor:
            painter.translate(x, y)
            painter.drawPath(self.mouse)
            painter.fillPath(self.mouse, Qt.white)
        painter.end()

    def importCellPic(self, pixSize):
        # 从磁盘导入资源，并缩放到希望的尺寸、比例
        celldown = QPixmap(self.celldown_path)
        cell1 = QPixmap(self.cell1_path)
        cell2 = QPixmap(self.cell2_path)
        cell3 = QPixmap(self.cell3_path)
        cell4 = QPixmap(self.cell4_path)
        cell5 = QPixmap(self.cell5_path)
        cell6 = QPixmap(self.cell6_path)
        cell7 = QPixmap(self.cell7_path)
        cell8 = QPixmap(self.cell8_path)
        cellup = QPixmap(self.cellup_path)
        cellmine = QPixmap(self.cellmine_path)  # 白雷
        cellflag = QPixmap(self.cellflag_path)  # 标雷
        blast = QPixmap(self.blast_path)  # 红雷
        falsemine = QPixmap(self.falsemine_path)  # 叉雷
        mine = QPixmap(self.mine_path)  # 透明雷
        self.pixmapNumBack = {0: celldown, 1: cell1, 2: cell2, 3: cell3, 4: cell4,
                              5: cell5, 6: cell6, 7: cell7, 8: cell8,
                              10: cellup, 11: cellflag, 14: falsemine,
                              15: blast, 16: cellmine, 100: mine}
        celldown_ = celldown.copy().scaled(pixSize, pixSize)
        cell1_ = cell1.copy().scaled(pixSize, pixSize)
        cell2_ = cell2.copy().scaled(pixSize, pixSize)
        cell3_ = cell3.copy().scaled(pixSize, pixSize)
        cell4_ = cell4.copy().scaled(pixSize, pixSize)
        cell5_ = cell5.copy().scaled(pixSize, pixSize)
        cell6_ = cell6.copy().scaled(pixSize, pixSize)
        cell7_ = cell7.copy().scaled(pixSize, pixSize)
        cell8_ = cell8.copy().scaled(pixSize, pixSize)
        cellup_ = cellup.copy().scaled(pixSize, pixSize)
        cellmine_ = cellmine.copy().scaled(pixSize, pixSize)
        cellflag_ = cellflag.copy().scaled(pixSize, pixSize)
        blast_ = blast.copy().scaled(pixSize, pixSize)
        falsemine_ = falsemine.copy().scaled(pixSize, pixSize)
        mine_ = mine.copy().scaled(pixSize, pixSize)
        self.pixmapNum = {0: celldown_, 1: cell1_, 2: cell2_, 3: cell3_, 4: cell4_,
                          5: cell5_, 6: cell6_, 7: cell7_, 8: cell8_,
                          10: cellup_, 11: cellflag_, 14: falsemine_,
                          15: blast_, 16: cellmine_, 100: mine_}

    def reloadCellPic(self, pixSize):
        # 从内存导入资源，并缩放到希望的尺寸、比例。
        self.pixmapNum = {key: value.copy().scaled(pixSize, pixSize)
                          for key, value in self.pixmapNumBack.items()}
