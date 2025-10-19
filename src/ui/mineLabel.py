from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QPolygonF, QPainter, QPixmap, QPainterPath
import ms_toollib as ms
from PyQt5.QtCore import QPoint, Qt
# from PyQt5.QtSvg import QSvgWidget
import minesweeper_master as mm


class mineLabel(QtWidgets.QLabel):
    # 一整个局面的控件，而不是一个格子
    leftRelease = QtCore.pyqtSignal (int, int)  # 定义信号
    rightRelease = QtCore.pyqtSignal (int, int)
    leftPressed = QtCore.pyqtSignal (int, int)
    rightPressed = QtCore.pyqtSignal (int, int)
    leftAndRightPressed = QtCore.pyqtSignal (int, int)
    leftAndRightRelease = QtCore.pyqtSignal (int, int)
    mouseMove = QtCore.pyqtSignal (int, int)
    mousewheelEvent = QtCore.pyqtSignal (int, int, int)
    row = 0
    column = 0
    pixSize = 0

    def __init__(self, parent):
        super (mineLabel, self).__init__ (parent)
        points = []
        mouse_ = QPolygonF(points)
        self.mouse = QPainterPath()
        self.mouse.addPolygon(mouse_)
        self.setMouseTracking(True)
        self.paint_cursor = False # 是否画光标。不仅控制画光标，还代表了是游戏还是播放录像。
        self.paintProbability = False

    def setPath(self, r_path):
        # 告诉局面控件，相对路径
        self.celldown_path = str(r_path.with_name('media').joinpath('celldown.svg'))
        self.cell1_path = str(r_path.with_name('media').joinpath('cell1.svg'))
        self.cell2_path = str(r_path.with_name('media').joinpath('cell2.svg'))
        self.cell3_path = str(r_path.with_name('media').joinpath('cell3.svg'))
        self.cell4_path = str(r_path.with_name('media').joinpath('cell4.svg'))
        self.cell5_path = str(r_path.with_name('media').joinpath('cell5.svg'))
        self.cell6_path = str(r_path.with_name('media').joinpath('cell6.svg'))
        self.cell7_path = str(r_path.with_name('media').joinpath('cell7.svg'))
        self.cell8_path = str(r_path.with_name('media').joinpath('cell8.svg'))
        self.cellup_path = str(r_path.with_name('media').joinpath('cellup.svg'))
        self.cellmine_path = str(r_path.with_name('media').joinpath('cellmine.svg'))
        self.cellflag_path = str(r_path.with_name('media').joinpath('cellflag.svg'))
        self.blast_path = str(r_path.with_name('media').joinpath('blast.svg'))
        self.falsemine_path = str(r_path.with_name('media').joinpath('falsemine.svg'))
        self.mine_path = str(r_path.with_name('media').joinpath('mine.svg'))

    def set_rcp(self, row, column, pixSize):
        # ui层面，重设一下宽、高、大小
        # self.paintProbability = False  # 是否打印概率
        self.row = row
        self.column = column
        if self.paintProbability:
            # self.ms_board = mm.abstract_game_board()
            self.ms_board = mm.CoreBaseVideo([[0] * column for _ in range(row)], pixSize)
        else:
            if hasattr(self, "ms_board"):
                if isinstance(self.ms_board, mm.CoreBaseVideo) or\
                    not isinstance(self.ms_board, ms.BaseVideo):
                    self.ms_board = ms.BaseVideo([[0] * column for _ in range(row)], pixSize)
                else:
                    self.ms_board.reset(row, column, pixSize)
            else:
                self.ms_board = ms.BaseVideo([[0] * column for _ in range(row)], pixSize)
            self.boardProbability = [[0.0] * column for _ in range(row)]
        
        if self.pixSize != pixSize:
            self.pixSize = pixSize
            self.importCellPic(pixSize)
            self.resize(QtCore.QSize(pixSize * column + 8, pixSize * row + 8))
            self.current_x = self.row # 鼠标坐标，和高亮的展示有关
            self.current_y = self.column
    
            points = [ QPoint(0, 0),   # 你猜这个多边形是什么，它就是鼠标
                      QPoint(0, pixSize),
                    QPoint(int(0.227 * pixSize), int(0.773 * pixSize)),
                    QPoint(int(0.359 * pixSize), int(1.125 * pixSize)),
                    QPoint(int(0.493 * pixSize), int(1.066 * pixSize)),
                    QPoint(int(0.357 * pixSize), int(0.72 * pixSize)),
                    QPoint(int(0.666 * pixSize), int(0.72 * pixSize)) ]
            mouse_ = QPolygonF(points)
            self.mouse = QPainterPath()
            self.mouse.addPolygon(mouse_)

    def mousePressEvent(self, e):
        # 重载一下鼠标点击事件
        xx = int(e.localPos().x() - 4)
        yy = int(e.localPos().y() - 4)
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
            if e.buttons () == QtCore.Qt.LeftButton:
                self.leftPressed.emit(self.current_x, self.current_y)
            elif e.buttons () == QtCore.Qt.RightButton:
                self.rightPressed.emit(self.current_x, self.current_y)

    def mouseReleaseEvent(self, e):
        #每个标签的鼠标事件发射给槽的都是自身的坐标
        #所以获取释放点相对本标签的偏移量，矫正发射的信号
        xx = int(e.localPos().x() - 4)
        yy = int(e.localPos().y() - 4)
        
        if yy < 0 or xx < 0 or yy >= self.row * self.pixSize or\
            xx >= self.column * self.pixSize:
            self.current_x = self.row * self.pixSize
            self.current_y = self.column * self.pixSize
        else:
            self.current_x = yy
            self.current_y = xx
            
        if e.button() == QtCore.Qt.LeftButton:
            self.leftRelease.emit(self.current_x, self.current_y)
        elif e.button () == QtCore.Qt.RightButton:
            self.rightRelease.emit(self.current_x, self.current_y)

    def mouseMoveEvent(self, e):
        xx = int(e.localPos().x() - 4)
        yy = int(e.localPos().y() - 4)
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
        xx = int(event.x() - 4) # 距离左侧
        yy = int(event.y() - 4) # 距离上方
        if yy < 0 or xx < 0 or yy >= self.row * self.pixSize or\
            xx >= self.column * self.pixSize:
            self.mousewheelEvent.emit(angle_y, self.row, self.column)
        else:
            self.mousewheelEvent.emit(angle_y, yy // self.pixSize, xx // self.pixSize)

    def paintEvent(self, event):
        super().paintEvent(event)
        pix_size = self.pixSize
        painter = QPainter()
        game_board = self.ms_board.game_board
        mouse_state = self.ms_board.mouse_state
        if self.paint_cursor: # 播放录像
            game_board_state = 1
            (x, y) = self.ms_board.x_y
            current_x = y // self.pixSize
            current_y = x // self.pixSize
            # poss = self.ms_board.game_board_poss
        else: # 游戏
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
                if game_board[i][j] == 10:
                    painter.drawPixmap(j * pix_size + 4, i * pix_size + 4, QPixmap(self.pixmapNum[10]))
                    if self.paintProbability: # 画概率
                        if self.paint_cursor:
                            painter.setOpacity(self.ms_board.game_board_poss[i][j])
                        else:
                            painter.setOpacity(self.boardProbability[i][j])
                        painter.drawPixmap(j * pix_size + 4, i * pix_size + 4, QPixmap(self.pixmapNum[100]))
                        painter.setOpacity(1.0)
                else:
                    painter.drawPixmap(j * pix_size + 4, i * pix_size + 4, QPixmap(self.pixmapNum[game_board[i][j]]))


        # 画高亮
        if (game_board_state == 2 or game_board_state == 1 or game_board_state == 5) and\
            current_x < row and current_y < column:
            if mouse_state == 5 or mouse_state == 6:
                for r in range(max(current_x - 1, 0), min(current_x + 2, row)):
                    for c in range(max(current_y - 1, 0), min(current_y + 2, column)):
                        if game_board[r][c] == 10:
                            painter.drawPixmap(c * pix_size + 4, r * pix_size + 4, QPixmap(self.pixmapNum[0]))
            elif mouse_state == 4 and game_board[current_x][current_y] == 10:
                painter.drawPixmap(current_y * pix_size + 4, current_x * pix_size + 4, QPixmap(self.pixmapNum[0]))
        # 画光标
        if self.paint_cursor:
            painter.translate(x + 4, y + 4)
            painter.drawPath(self.mouse)
            painter.fillPath(self.mouse,Qt.white)
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
        cellmine = QPixmap(self.cellmine_path) # 白雷
        cellflag = QPixmap(self.cellflag_path) # 标雷
        blast = QPixmap(self.blast_path) # 红雷
        falsemine = QPixmap(self.falsemine_path) # 叉雷
        mine = QPixmap(self.mine_path) # 透明雷
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
        self.pixmapNum = {key:value.copy().scaled(pixSize, pixSize) for key,value in self.pixmapNumBack.items()}



