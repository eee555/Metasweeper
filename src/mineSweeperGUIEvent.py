from PyQt5 import QtCore
from PyQt5.QtCore import Qt
# from PyQt5.QtWidgets import QLineEdit, QInputDialog, QShortcut
from PyQt5.QtWidgets import QApplication
import superGUI

# 局面中的鼠标和滚轮事件

class MineSweeperGUIEvent(superGUI.Ui_MainWindow):
    def mineAreaLeftPressed(self, i, j):
        # print("lc", i, j)
        if self.game_state == 'ready' or self.game_state == 'playing' or\
                self.game_state == 'joking':
            self.label.ms_board.step('lc', (i, j))
            self.label.update()

            self.set_face(15)

        elif self.game_state == 'show':
            # 看概率时，所有操作都移出局面外
            self.label.ms_board.step(
                'lc', (self.row * self.pixSize, self.column * self.pixSize))
            self.set_face(15)
    
    def mineAreaLeftRelease(self, i, j):
        # print("lr", i, j)
        if self.game_state == 'ready':
            if not self.pos_is_in_board(i, j):
                self.label.ms_board.step('lr', (i, j))
            else:
                if self.label.ms_board.mouse_state == 4 and\
                        self.label.ms_board.game_board[i // self.pixSize][j // self.pixSize] == 10:
                    # 正式埋雷开始
                    self.layMine(i // self.pixSize, j // self.pixSize)

                    # 只有没有“局面约束”时，录像才可能是“official”的
                    if self.board_constraint:
                        self.game_state = 'joking'
                    else:
                        self.game_state = 'playing'

                    # 假如未开启“直播模式”，禁用代码截图
                    if self.player_identifier[:6] != "[live]":
                        self.disable_screenshot()
                    else:
                        self.enable_screenshot()

                    if self.cursor_limit:
                        self.limit_cursor()

                    # 核实用的时间，防变速齿轮
                    self.start_time_unix_2 = QtCore.QDateTime.currentDateTime().\
                        toMSecsSinceEpoch()
                    self.timer_10ms.start()
                    # 禁用双击修改指标名称公式
                    self.score_board_manager.editing_row = -2

                self.label.ms_board.step('lr', (i, j))

                if self.label.ms_board.game_board_state == 3:
                    # 点一下可能获胜
                    self.gameWin()
                    self.label.update()
                    return
                elif self.label.ms_board.game_board_state == 4:
                    # 点一下不可能踩雷，但为完整性需要这样写
                    self.gameFailed()
                    self.label.update()
                    return
                else:
                    self.label.update()
            self.set_face(14)
        elif self.game_state == 'playing' or self.game_state == 'joking':
            # 如果是游戏中，且是左键抬起（不是双击），且是在10上，且在局面内，则用ai劫持、处理下
            if self.pos_is_in_board(i, j):
                if self.label.ms_board.game_board[i // self.pixSize][j // self.pixSize] == 10 \
                        and self.label.ms_board.mouse_state == 4:
                    self.ai(i // self.pixSize, j // self.pixSize)
                self.chording_ai(i // self.pixSize, j // self.pixSize)
            self.label.ms_board.step('lr', (i, j))

            if self.label.ms_board.game_board_state == 3:
                self.gameWin()
                self.label.update()
                return
            elif self.label.ms_board.game_board_state == 4:
                self.gameFailed()
                self.label.update()
                return
            self.label.update()
            self.set_face(14)

        elif self.game_state == 'show':
            # 看概率时，所有操作都移出局面外
            self.label.ms_board.step(
                'lr', (self.row * self.pixSize, self.column * self.pixSize))
            self.set_face(14)

    def mineAreaRightPressed(self, i, j):
        # print("rc", i, j)
        if self.game_state == 'ready' or self.game_state == 'playing' or self.game_state == 'joking':
            if i < self.pixSize * self.row and j < self.pixSize * self.column:
                # 计算左上角显示的雷数用。必须校验：当前格的状态、鼠标状态为双键都抬起。
                # 假如按下左键，再切屏（比如快捷键截图），再左键抬起，再切回来，再右键按下，
                # 就会导致DownUp状态下右键按下。此时不应该标雷，左上角雷数也应该不变
                if self.label.ms_board.game_board[i//self.pixSize][j//self.pixSize] == 11 and\
                        self.label.ms_board.mouse_state == 1:
                    self.mineUnFlagedNum += 1
                    self.showMineNum(self.mineUnFlagedNum)
                elif self.label.ms_board.game_board[i//self.pixSize][j//self.pixSize] == 10 and\
                        self.label.ms_board.mouse_state == 1:
                    self.mineUnFlagedNum -= 1
                    self.showMineNum(self.mineUnFlagedNum)
            self.label.ms_board.step('rc', (i, j))
            self.label.update()
            self.set_face(15)

    def mineAreaRightRelease(self, i, j):
        # print("rr", i, j)
        if self.game_state == 'ready' or self.game_state == 'playing' or self.game_state == 'joking':
            self.chording_ai(i // self.pixSize, j // self.pixSize)
            self.label.ms_board.step('rr', (i, j))
            self.label.update()
            self.set_face(14)
        elif self.game_state == 'show':
            # 看概率时，所有操作都移出局面外
            self.label.ms_board.step(
                'rr', (self.row * self.pixSize, self.column * self.pixSize))
            self.set_face(14)

    def mineAreaLeftAndRightPressed(self, i, j):
        # print("cc", i, j)
        if self.game_state == 'ready' or self.game_state == 'playing' or\
                self.game_state == 'joking':
            self.label.ms_board.step('cc', (i, j))
            self.label.update()

            self.set_face(15)

    def mineMouseMove(self, i, j):
        # 正常情况的鼠标移动事件，与高亮的显示有关
        if self.game_state == 'playing' or self.game_state == 'joking' or self.game_state == 'ready':
            self.label.ms_board.step('mv', (i, j))
            self.label.update()
        # 按住空格后的鼠标移动事件，与概率的显示有关
        elif self.game_state == 'show' or self.game_state == 'study':
            if not self.pos_is_in_board(i, j):
                self.label_info.setText('(是雷的概率)')
            else:
                text4 = '{:.3f}'.format(
                    max(0, self.label.boardProbability[i//self.pixSize][j//self.pixSize]))
                self.label_info.setText(text4)
        # 播放录像时的鼠标移动事件
        elif self.game_state == 'showdisplay':
            if not self.pos_is_in_board(i, j):
                self.label_info.setText('(是雷的概率)')
            else:
                text4 = '{:.3f}'.format(
                    max(0, self.label.ms_board.game_board_poss[i//self.pixSize][j//self.pixSize]))
                self.label_info.setText(text4)

    def resizeWheel(self, i, x, y):
        # 按住ctrl滚轮，调整局面大小
        # study状态下，滚轮修改局面
        # 函数名要改了
        if QApplication.keyboardModifiers() == Qt.ControlModifier and\
                self.game_state == 'ready' and self.label.ms_board.game_board_state == 1:
            # 调整局面大小需要满足：ui端是ready且状态机是ready
            if i > 0:
                self.pixSize += 1
            elif i < 0:
                self.pixSize -= 1

        elif self.game_state == 'study':
            if x < 0 or x >= self.row or y < 0 or y >= self.column:
                return
            v = self.label.ms_board.game_board[x][y]
            if i > 0:
                v += 1
                if v == 9:
                    v = 10
                elif v >= 10:
                    v = 0
            elif i < 0:
                v -= 1
                if v == 9:
                    v = 8
                elif v <= -1:
                    v = 10
            self.label.ms_board.game_board[x][y] = v
            self.render_poss_on_board()
