from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QPolygonF, QPainter, QPixmap, QPainterPath, QColor, QPen, QFont
import ms_toollib as ms
from PySide6.QtCore import QPoint, QPointF, Qt, QRect, QPropertyAnimation, QEasingCurve
from config.constants import BOARD_READY, BOARD_PLAYING, CELL_UNOPENED
from shared_types.enums import MouseState
from shared_types.commands import SKIN_CELL_KEYS
import utils
from utils.path_utils import resource_path
from utils.pixmap_utils import render_svg_pixmap, scale_bitmap_pixmap


class mineLabel(QtWidgets.QLabel):
    # 一整个局面的控件，而不是一个格子
    leftRelease = QtCore.Signal(int, int)  # 定义信号
    leftDoubleRelease = QtCore.Signal(int, int)
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
        self._left_double_click = False
        # 开格打击感：抖动偏移（绘制时整体平移）与单个动画对象（打断重启）
        self._shake_offset = QPointF(0.0, 0.0)
        self._shake_anim = None
        self.shake_enabled = True
        # 皮肤内存源：{key: 原始 QPixmap}。None 表示使用磁盘默认资源。
        # 由 app.skin_applier 在运行时写入；不落盘、重启即还原。
        # 同时保存原始字节，供 _copy_board_svg 用 QSvgRenderer 渲染。
        self.skin_source: dict[int, QPixmap] | None = None
        self.skin_source_bytes: dict[int, bytes] | None = None

    def _get_shake_offset(self):
        return self._shake_offset

    def _set_shake_offset(self, offset):
        self._shake_offset = offset
        self.update()

    shakeOffset = QtCore.Property(
        QPointF, _get_shake_offset, _set_shake_offset)

    @staticmethod
    def _reduced_motion():
        # Windows“显示动画”偏好（SPI_GETCLIENTAREAANIMATION）；取不到则视为未减少
        try:
            import ctypes
            val = ctypes.c_int(1)
            ok = ctypes.windll.user32.SystemParametersInfoW(
                0x1042, 0, ctypes.byref(val), 0)
            return bool(ok) and val.value == 0
        except Exception:
            return False

    # ── 抖动参数（表现层审美常量，集中调参）──
    SHAKE_AMP_RATIO = 0.2           # 弱档振幅相对格子边长的比例
    SHAKE_AMP_MAX_PX = 4.0          # 弱档振幅的物理像素上限（按 devicePixelRatio 换算）
    SHAKE_DURATION_MS = 130         # 弱档时长（ms）
    SHAKE_STRONG_SCALE = 2.0        # 踩雷强档振幅 = 弱档 × 该倍率
    SHAKE_STRONG_DURATION_MS = 280  # 踩雷强档时长（ms）

    def start_shake(self, *, strong=False):
        # 是否触发由调用方判断（开格数增加才调用弱档）。
        # 弱档：固定振幅 min(格边长×SHAKE_AMP_RATIO, SHAKE_AMP_MAX_PX/dpr)，
        # 与本次开格数无关；SHAKE_DURATION_MS、OutQuad、末帧归零。
        # strong=True：踩雷强档（振幅 ×SHAKE_STRONG_SCALE、
        # SHAKE_STRONG_DURATION_MS、独立节奏）
        if not self.shake_enabled or self.pixSize <= 0:
            return
        if self._reduced_motion():
            return
        dpr = self.devicePixelRatioF() or 1.0
        amp = min(self.pixSize * self.SHAKE_AMP_RATIO,
                  self.SHAKE_AMP_MAX_PX / dpr)
        if self._shake_anim is None:
            self._shake_anim = QPropertyAnimation(self, b"shakeOffset", self)
            self._shake_anim.finished.connect(self._on_shake_finished)
        anim = self._shake_anim
        anim.stop()
        if strong:
            amp *= self.SHAKE_STRONG_SCALE
            anim.setDuration(self.SHAKE_STRONG_DURATION_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setKeyValues([
                (0.0, QPointF(0.0, 0.0)),
                (0.2, QPointF(amp, -0.5 * amp)),
                (0.45, QPointF(-0.7 * amp, 0.4 * amp)),
                (0.7, QPointF(0.5 * amp, -0.25 * amp)),
                (1.0, QPointF(0.0, 0.0)),
            ])
        else:
            anim.setDuration(self.SHAKE_DURATION_MS)
            anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            anim.setKeyValues([
                (0.0, QPointF(0.0, 0.0)),
                (0.25, QPointF(amp, -0.6 * amp)),
                (0.55, QPointF(-0.7 * amp, 0.5 * amp)),
                (0.8, QPointF(0.4 * amp, -0.3 * amp)),
                (1.0, QPointF(0.0, 0.0)),
            ])
        # 打断重启时先归零，避免上一段动画的残移成为新起点
        self._set_shake_offset(QPointF(0.0, 0.0))
        anim.start()

    def _on_shake_finished(self):
        # 结束精确归位
        self._set_shake_offset(QPointF(0.0, 0.0))

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
        self.cellquestion_path = str(m.joinpath('cellquestion.svg'))
        self.blast_path = str(m.joinpath('blast.svg'))
        self.falsemine_path = str(m.joinpath('falsemine.svg'))
        self.mine_path = str(m.joinpath('mine.svg'))
        # key -> 默认磁盘路径，供皮肤未覆盖的格子回退使用
        self.cell_path_map: dict[int, str] = {
            0: self.celldown_path, 1: self.cell1_path, 2: self.cell2_path,
            3: self.cell3_path, 4: self.cell4_path, 5: self.cell5_path,
            6: self.cell6_path, 7: self.cell7_path, 8: self.cell8_path,
            10: self.cellup_path, 11: self.cellflag_path,
            14: self.falsemine_path, 15: self.blast_path,
            16: self.cellmine_path, 17: self.cellquestion_path,
            100: self.mine_path,
        }

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
        self._left_double_click = False
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
        # 忠实记录左/右键按下：双键时 e.button() 即后按下的键，按原样转发，
        # 状态机会自然合成双击（UpUp+rc 或 UpDown+lc 都进入 Chording）。
        # 不再合并发 'cc'：状态机对 (残留 MouseState, 'cc') 有硬 Err 分支，
        # wheel 以 panic=abort 编译，一旦命中进程直接崩溃（2026-11-09 crash）。
        if e.button() == QtCore.Qt.LeftButton:
            self.leftPressed.emit(self.current_x, self.current_y)
        elif e.button() == QtCore.Qt.RightButton:
            self.rightPressed.emit(self.current_x, self.current_y)

    def mouseDoubleClickEvent(self, e):
        # 保留第二次按下的正常行为，由控制器在抬起时决定是否重开。
        self.mousePressEvent(e)
        self._left_double_click = (e.button() == QtCore.Qt.LeftButton
                                   and e.buttons() == QtCore.Qt.LeftButton)

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

        left_double_click = self._left_double_click
        self._left_double_click = False
        if e.button() == QtCore.Qt.LeftButton:
            if left_double_click and e.buttons() == QtCore.Qt.NoButton:
                self.leftDoubleRelease.emit(self.current_x, self.current_y)
            else:
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
        # 格子间距取整到整数物理像素（再转回逻辑单位）。DPR 为非整数
        # （如 4K 缩放模式的 8/3）时，pixSize × DPR 会带小数，格子原点
        # 落在不同的小数物理像素位置上，整张位图被双线性重采样——表现为
        # 以小数周期（如每 3 列）出现的细线。取整后绘制坐标 × DPR 恒为
        # 整数，位图严格 1:1 直出，任何缩放档位都无重采样。
        dpr = self.devicePixelRatioF()
        cell_pitch = round(pix_size * dpr) / dpr if dpr > 0 else pix_size
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
        # 经典扫雷面板底色，垫在所有格子 SVG 之下。
        # cellup 等素材由高光/阴影两个 polygon 拼成、无背景 rect，斜边抗锯齿
        # 会产生半透明像素（实测每格右上/左下对角线各约 30 个，alpha≈192）；
        # 不垫底时这些像素透出窗口背景，形成格子附近的亮灰细线。
        # 数字等已翻开格子的抗锯齿边缘也同样正确混到面板色上。
        painter.fillRect(self.rect(), QColor("#c0c0c0"))
        if not self._shake_offset.isNull():
            painter.translate(self._shake_offset)
        # 画游戏局面
        row = len(game_board)
        column = len(game_board[0])
        for i in range(row):
            for j in range(column):
                if game_board[i][j] == CELL_UNOPENED:
                    painter.drawPixmap(QPointF(j * cell_pitch, i * cell_pitch),
                                       QPixmap(self.pixmapNum[10]))
                    if self.paintProbability:  # 画概率
                        if self.paint_cursor:
                            painter.setOpacity(
                                self.ms_board.game_board_poss[i][j])
                        else:
                            painter.setOpacity(self.boardProbability[i][j])
                        painter.drawPixmap(
                            QPointF(j * cell_pitch, i * cell_pitch), QPixmap(self.pixmapNum[100]))
                        painter.setOpacity(1.0)
                else:
                    painter.drawPixmap(
                        QPointF(j * cell_pitch, i * cell_pitch), QPixmap(self.pixmapNum[game_board[i][j]]))

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
                                QPointF(c * cell_pitch, r * cell_pitch), QPixmap(self.pixmapNum[0]))
            elif mouse_state == MouseState.DownUp.value and game_board[current_x][current_y] == CELL_UNOPENED:
                painter.drawPixmap(
                    QPointF(current_y * cell_pitch, current_x * cell_pitch), QPixmap(self.pixmapNum[0]))
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
        # 导入原始资源到 pixmapNumBack：有内存皮肤源时优先取内存（可逐 key
        # 回退到磁盘默认资源），再统一按「目标尺寸 × 屏幕 DPR」出图。
        # 磁盘默认格子是 SVG，矢量重栅格化；内存皮肤位图（无法矢量化）走
        # 物理分辨率平滑缩放。取代老的「QPixmap(svg) 先 160px 位图化、
        # 再 scaled() 插值」管线：放大不再发糊，Retina 屏不再被 DPR 拉伸
        # 二次重采样。
        skin = self.skin_source
        dpr = self.devicePixelRatioF()
        self.pixmapNumBack = {
            key: (skin[key] if skin and key in skin
                  else QPixmap(self.cell_path_map[key]))
            for key in SKIN_CELL_KEYS
        }
        self.pixmapNum = {
            key: (scale_bitmap_pixmap(source, pixSize, pixSize, dpr)
                  if skin and key in skin
                  else render_svg_pixmap(self.cell_path_map[key],
                                         pixSize, pixSize, dpr))
            for key, source in self.pixmapNumBack.items()
        }

    def reloadCellPic(self, pixSize):
        # 重新渲染资源：一律按当前皮肤/磁盘源以目标尺寸（× DPR）重出图，
        # 不基于旧位图二次插值；setPath 尚未调用时退回位图缩放。
        if hasattr(self, "cell_path_map"):
            self.importCellPic(pixSize)
        else:
            dpr = self.devicePixelRatioF()
            self.pixmapNum = {key: scale_bitmap_pixmap(value, pixSize, pixSize, dpr)
                              for key, value in self.pixmapNumBack.items()}
