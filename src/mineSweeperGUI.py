from PyQt5 import QtCore
from PyQt5.QtCore import QTimer, QCoreApplication, Qt, QRect
from PyQt5.QtGui import QPixmap
# from PyQt5.QtWidgets import QLineEdit, QInputDialog, QShortcut
from PyQt5.QtWidgets import QApplication, QFileDialog, QWidget
import gameDefinedParameter
import superGUI, gameAbout, gameSettings, gameSettingShortcuts,\
    captureScreen, mine_num_bar, videoControl, gameRecordPop
from CheckUpdateGui import CheckUpdateGui
from githubApi import GitHub, SourceManager
import minesweeper_master as mm
import ms_toollib as ms
# import configparser
# from pathlib import Path
# import time
import os
import ctypes
import hashlib, uuid
# from PyQt5.QtWidgets import QApplication
from country_name import country_name
import metaminesweeper_checksum
from mainWindowGUI import MainWindow

class MineSweeperGUI(superGUI.Ui_MainWindow):
    def __init__(self, MainWindow: MainWindow, args):
        self.mainWindow = MainWindow
        self.checksum_guard = metaminesweeper_checksum.ChecksumGuard()

        super(MineSweeperGUI, self).__init__(MainWindow, args)
        
        
        # MineSweeperGUI父类的init中读.ini、读图片、设置字体、局面初始化等

        self.time_10ms: int = 0 # 已毫秒为单位的游戏时间，全局统一的
        self.showTime(self.time_10ms // 100)
        self.timer_10ms = QTimer()
        self.timer_10ms.setInterval(10)  # 10毫秒回调一次的定时器
        self.timer_10ms.timeout.connect(self.timeCount)
        # 开了高精度反而精度降低
        self.timer_10ms.setTimerType(Qt.PreciseTimer)
        self.mineUnFlagedNum = self.mineNum  # 没有标出的雷，显示在左上角
        self.showMineNum(self.mineUnFlagedNum)    # 在左上角画雷数

        # 绑定菜单栏事件
        self.actionnew_game.triggered.connect(self.gameRestart)
        self.actionchu_ji.triggered.connect(lambda: self.predefined_Board(1))
        self.actionzhogn_ji.triggered.connect(lambda: self.predefined_Board(2))
        self.actiongao_ji.triggered.connect(lambda: self.predefined_Board(3))
        self.actionzi_ding_yi.triggered.connect(self.action_CEvent)
        self.actiongao_ji.triggered.connect(lambda: self.predefined_Board(3))
        def save_evf_file_integrated():
            if self.game_state != "ready" and self.game_state != "playing" and\
                self.game_state != "show" and self.game_state != "study" and\
                    self.game_state != "joking":
                self.dump_evf_file_data()
                self.save_evf_file()
        self.action_save.triggered.connect(save_evf_file_integrated)
        self.action_replay.triggered.connect(self.replay_game)
        self.actiontui_chu.triggered.connect(QCoreApplication.instance().quit)
        self.actionyouxi_she_zhi.triggered.connect(self.action_NEvent)
        self.action_kuaijiejian.triggered.connect(self.action_QEvent)
        self.action_mouse.triggered.connect(self.action_mouse_setting)
        self.actiongaun_yv.triggered.connect(self.action_AEvent)
        self.actionauto_update.triggered.connect(self.auto_Update)
        self.actionopen.triggered.connect(self.action_OpenFile)
        self.english_action.triggered.connect(lambda: self.trans_language("en_US"))
        self.chinese_action.triggered.connect(lambda: self.trans_language("zh_CN"))
        self.polish_action.triggered.connect(lambda: self.trans_language("pl_PL"))
        self.german_action.triggered.connect(lambda: self.trans_language("de_DE"))

        # config = configparser.ConfigParser()
        # config.read(self.game_setting_path, encoding='utf-8')

        if (self.row, self.column, self.mineNum) == (8, 8, 10):
            self.actionChecked('B')
        elif (self.row, self.column, self.mineNum) == (16, 16, 40):
            self.actionChecked('I')
        elif (self.row, self.column, self.mineNum) == (16, 30, 99):
            self.actionChecked('E')
        else:
            self.actionChecked('C')

        self.frameShortcut1.activated.connect(lambda: self.predefined_Board(1))
        self.frameShortcut2.activated.connect(lambda: self.predefined_Board(2))
        self.frameShortcut3.activated.connect(lambda: self.predefined_Board(3))
        self.frameShortcut4.activated.connect(self.gameRestart)
        self.frameShortcut5.activated.connect(lambda: self.predefined_Board(4))
        self.frameShortcut6.activated.connect(lambda: self.predefined_Board(5))
        self.frameShortcut7.activated.connect(lambda: self.predefined_Board(6))
        self.frameShortcut8.activated.connect(self.showScores)
        self.frameShortcut9.activated.connect(self.screenShot)
        self.shortcut_hidden_score_board.activated.connect(self.hidden_score_board)

        self._game_state = self.game_state = 'ready'
        # 用状态机控制局面状态。
        # 约定：'ready'：预备状态。表示局面完全没有左键点过，可能被右键标雷；刚打开或点脸时进入这种状态。
        #               此时可以改雷数、改格子大小（ctrl+滚轮）、行数、列数（拖拉边框）。
        #      'study':研究状态。截图后进入。应该设计第二种方式进入研究状态，没想好。
        #      'modify':调整状态。'ready'下，拖拉边框时进入，拖拉结束后自动转为'ready'。
        #      'playing':正在游戏状态、标准模式、不筛选3BV、且没有看概率计算结果，游戏结果是official的。
        #      'joking':正在游戏状态，游戏中看过概率计算结果，游戏结果不是official的。
        #      'fail':游戏失败，踩雷了。
        #      'win':游戏成功。



        # 相对路径
        self.relative_path = args[0]
        # 用本软件打开录像
        if len(args) == 2:
            self.action_OpenFile(openfile_name=args[1])
                    
        self.trans_language()
        self.score_board_manager.with_namespace({
            "race_identifier": self.race_identifier,
            "mode": self.gameMode,
            "checksum_ok": "--",
            "is_official": "--",
            "is_fair": "--"
            })
        self.score_board_manager.reshow(self.label.ms_board, index_type = 1)
        self.score_board_manager.visible()

        self.mainWindow.closeEvent_.connect(self.closeEvent_)
        self.mainWindow.dropFileSignal.connect(self.action_OpenFile)
        
    @property
    def pixSize(self):
        return self._pixSize
    
    @pixSize.setter
    def pixSize(self, pixSize):
        pixSize = max(5, pixSize)
        pixSize = min(255, pixSize)
        pixSize = min(32767//self.column, pixSize)
        pixSize = min(32767//self.row, pixSize)
        if hasattr(self, "_pixSize") and pixSize == self._pixSize:
            return
        self.label.set_rcp(self.row, self.column, pixSize)
        self.label.reloadCellPic(pixSize)
        if (self.row, self.column, self.mineNum) == (8, 8, 10):
            self.predefinedBoardPara[1]['pixsize'] = pixSize
        elif (self.row, self.column, self.mineNum) == (16, 16, 40):
            self.predefinedBoardPara[2]['pixsize'] = pixSize
        elif (self.row, self.column, self.mineNum) == (16, 30, 99):
            self.predefinedBoardPara[3]['pixsize'] = pixSize
        else:
            self.predefinedBoardPara[0]['pixsize'] = pixSize

        self.label.setMinimumSize(QtCore.QSize(pixSize * self.column + 8, pixSize * self.row + 8))
        self.label.setMaximumSize(QtCore.QSize(pixSize * self.column + 8, pixSize * self.row + 8))
        # self.label.setFixedSize(QtCore.QSize(self.pixSize*self.column + 8, self.pixSize*self.row + 8))

        self.reimportLEDPic(pixSize) # 重新导入图片，无磁盘io
        self.label_2.reloadFace(pixSize)
        self.set_face(14)
        self.showMineNum(self.mineUnFlagedNum)
        self.showTime(0)
        if hasattr(self, "_pixSize") and pixSize < self._pixSize:
            self._pixSize = pixSize
            self.minimumWindow()
            return
        self._pixSize = pixSize

    @property
    def gameMode(self):
        return self._game_mode

    @gameMode.setter
    def gameMode(self, game_mode):
        if isinstance(self.label.ms_board.mode, ms.EvfVideo):
            self.label.ms_board.mode = game_mode
        self._game_mode = game_mode

    @property
    def game_state(self):
        return self._game_state

    @game_state.setter
    def game_state(self, game_state: str):
        # print(self._game_state, " -> " ,game_state)
        if self._game_state in ("playing", "show", "joking") and\
            game_state not in ("playing", "show", "joking"):
            self.timer_10ms.stop()
            self.unlimit_cursor()
        elif self._game_state in ("display", "showdisplay") and\
            game_state not in ("display", "showdisplay"):
            self.timer_video.stop()
            self.ui_video_control.QWidget.close()
            self.label.paint_cursor = False
            self.set_country_flag()
            self.score_board_manager.with_namespace({
                "checksum_ok": "--",
                "is_official": "--",
                "is_fair": "--",
                "mode": self.gameMode,
                })
            self.score_board_manager.show(self.label.ms_board, index_type = 1)

        elif self._game_state == 'study':
            self.num_bar_ui.QWidget.close()
        self._game_state = game_state


    def layMine(self, i, j):
        xx = self.row
        yy = self.column
        num = self.mineNum
        # 0，4, 5, 6, 7, 8, 9, 10代表：标准0、win74、经典无猜5、强无猜6、
        # 弱无猜7、准无猜8、强可猜9、弱可猜10
        if self.gameMode == 5 or self.gameMode == 6 or self.gameMode == 9:
            # 根据模式生成局面
            Board, _ = mm.laymine_solvable(self.board_constraint,
                                           self.attempt_times_limit, (xx, yy, num, i, j))
        elif self.gameMode == 0 or self.gameMode == 7 or self.gameMode == 8 or self.gameMode == 10:
            Board, _ = mm.laymine(self.board_constraint,
                                  self.attempt_times_limit, (xx, yy, num, i, j))
        elif self.gameMode == 4:
            Board, _ = mm.laymine_op(self.board_constraint,
                                     self.attempt_times_limit, (xx, yy, num, i, j))

        self.label.ms_board.board = Board

    def timeCount(self):
        # 10ms时间步进的回调，改计数器、改右上角时间
        self.time_10ms += 1
        if self.time_10ms % 100 == 0:
            t = self.label.ms_board.time
            self.time_10ms = int(t * 100)
            self.showTime(self.time_10ms // 100)
            since_time_unix_2 = QtCore.QDateTime.currentDateTime().\
                toMSecsSinceEpoch() - self.start_time_unix_2
            if abs(t * 1000 - since_time_unix_2) > 10 and\
                (self.game_state == "playing" or self.game_state == "joking"):
                # 防CE作弊
                self.gameRestart()

        if self.time_10ms % 1 == 0:
            # 计数器用100Hz的刷新率
            # self.score_board_manager.with_namespace({
            #     "rtime": self.time_ms / 1000,
            #     })
            self.score_board_manager.show(self.label.ms_board, index_type = 1)

    def ai(self, i, j):
        # 0，4, 5, 6, 7, 8, 9, 10代表：标准、win7、
        # 经典无猜、强无猜、弱无猜、准无猜、强可猜、弱可猜
        # 根据模式处理一次点击的全部流程
        # （i，j）一定是未打开状态、为索引
        if self.gameMode == 0 or self.gameMode == 4 or self.gameMode == 5:
            return
        elif self.gameMode == 6:
            if self.label.ms_board.board[i][j] >= 0 and \
                not ms.is_able_to_solve(self.label.ms_board.game_board, (i, j)):
                board = self.label.ms_board.board.into_vec_vec()
                board[i][j] = -1
                self.label.ms_board.board = board
            return
        elif self.gameMode == 7:
            code = ms.is_guess_while_needless(self.label.ms_board.game_board, (i, j))
            if code == 3:
                board = self.label.ms_board.board.into_vec_vec()
                board[i][j] = -1
                self.label.ms_board.board = board
            elif code == 2:
                board, flag = mm.enumerateChangeBoard(self.label.ms_board.board,
                                                      self.label.ms_board.game_board, [(i, j)])
                self.label.ms_board.board = board
            return
        elif self.gameMode == 8:
            code = ms.is_guess_while_needless(self.label.ms_board.game_board, (i, j))
            if code == 2:
                board, flag = mm.enumerateChangeBoard(self.label.ms_board.board,
                                                      self.label.ms_board.game_board, [(i, j)])
                self.label.ms_board.board = board
            return
        elif self.gameMode == 9 or self.gameMode == 10:
            if self.label.ms_board.board[i][j] == -1:
                # 可猜调整的核心逻辑
                board, flag = mm.enumerateChangeBoard(self.label.ms_board.board,
                                                      self.label.ms_board.game_board, [(i, j)])

                
                self.label.ms_board.board = board
            return
        
    # 双击时进入，可以双击猜雷
    # 此处架构可以改进，放到工具箱里
    def chording_ai(self, i, j):
        # 0，4, 5, 6, 7, 8, 9, 10代表：标准、win7、
        # 经典无猜、强无猜、弱无猜、准无猜、强可猜、弱可猜
        # i,j为索引
        if not self.cell_is_in_board(i, j):
            return
        if self.label.ms_board.mouse_state != 5 and self.label.ms_board.mouse_state != 6:
            return
        if self.label.ms_board.game_board[i][j] >= 10 or\
            self.label.ms_board.game_board[i][j] == 0:
            return
        if self.gameMode == 0 or self.gameMode == 4 or self.gameMode == 5:
            return
        not_mine_round = [] # 没有标雷，且非雷
        is_mine_round = [] # 没有标雷，且是雷
        flag_not_mine_round = [] # 标雷，且非雷
        flag_is_mine_round = [] # 标雷，且是雷
        for ii in range(max(0,i-1), min(self.row,i+2)):
            for jj in range(max(0,j-1), min(self.column,j+2)):
                if (ii, jj) != (i, j):
                    if self.label.ms_board.game_board[ii][jj] == 10:
                        if self.label.ms_board.board[ii][jj] == -1:
                            is_mine_round.append((ii, jj))
                        else:
                            not_mine_round.append((ii, jj))
                    elif self.label.ms_board.game_board[ii][jj] == 11:
                        if self.label.ms_board.board[ii][jj] == -1:
                            flag_is_mine_round.append((ii, jj))
                        else:
                            flag_not_mine_round.append((ii, jj))
        if len(flag_is_mine_round) + len(flag_not_mine_round) !=\
            self.label.ms_board.board[i][j]:
            # 不满足双击条件
            return
        board = self.label.ms_board.board.into_vec_vec()
        if self.gameMode == 6:
            for (x, y) in is_mine_round + not_mine_round:
                if not ms.is_able_to_solve(self.label.ms_board.game_board, (x, y)):
                    board[x][y] = -1
            self.label.ms_board.board = board
            return
        elif self.gameMode == 7:
            must_guess = True
            for (x, y) in is_mine_round + not_mine_round:
                code = ms.is_guess_while_needless(self.label.ms_board.game_board, (x, y))
                if code == 3:
                    must_guess = False
                    break
            if must_guess:
                board, flag = mm.enumerateChangeBoard(board,
                                                      self.label.ms_board.game_board,
                                                      not_mine_round + is_mine_round)
                self.label.ms_board.board = board
            else:
                for (x, y) in is_mine_round + not_mine_round:
                    board[x][y] = -1
                self.label.ms_board.board = board
        elif self.gameMode == 8:
            must_guess = True
            for (x, y) in is_mine_round + not_mine_round:
                code = ms.is_guess_while_needless(self.label.ms_board.game_board, (x, y))
                if code == 3:
                    must_guess = False
                    break
            if must_guess:
                board, flag = mm.enumerateChangeBoard(board,
                                                      self.label.ms_board.game_board,
                                                      not_mine_round + is_mine_round)
                self.label.ms_board.board = board
        elif self.gameMode == 9 or self.gameMode == 10:
            board, flag = mm.enumerateChangeBoard(board,
                                                  self.label.ms_board.game_board,
                                                  not_mine_round + is_mine_round)
            self.label.ms_board.board = board
            

    def mineAreaLeftPressed(self, i, j):
        if self.game_state == 'ready' or self.game_state == 'playing' or\
            self.game_state == 'joking':
            self.label.ms_board.step('lc', (i, j))
            self.label.update()

            self.set_face(15)

        elif self.game_state == 'show':
            # 看概率时，所有操作都移出局面外
            self.label.ms_board.step('lc', (self.row * self.pixSize, self.column * self.pixSize))
            self.set_face(15)

    def mineAreaLeftRelease(self, i, j):
        if self.game_state == 'ready':
            if not self.pos_is_in_board(i, j):
                self.label.ms_board.step('lr', (i, j))
            else:
                if self.label.ms_board.mouse_state == 4 and\
                    self.label.ms_board.game_board[i// self.pixSize][j// self.pixSize] == 10:
                    # 正式埋雷开始
                    self.layMine(i // self.pixSize, j // self.pixSize)
                    
                    if self.board_constraint:
                        self.game_state = 'joking'
                    else:
                        self.game_state = 'playing'

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
                if self.label.ms_board.game_board[i// self.pixSize][j// self.pixSize] == 10 \
                    and self.label.ms_board.mouse_state == 4:
                    self.ai(i // self.pixSize, j // self.pixSize)
                self.chording_ai(i// self.pixSize, j// self.pixSize)
                
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
            self.label.ms_board.step('lr', (self.row * self.pixSize, self.column * self.pixSize))
            self.set_face(14)

    def mineAreaRightPressed(self, i, j):
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
        if self.game_state == 'ready' or self.game_state == 'playing' or self.game_state == 'joking':
            self.chording_ai(i// self.pixSize, j// self.pixSize)
            self.label.ms_board.step('rr', (i, j))
            self.label.update()
            self.set_face(14)
        elif self.game_state == 'show':
            # 看概率时，所有操作都移出局面外
            self.label.ms_board.step('rr', (self.row * self.pixSize, self.column * self.pixSize))
            self.set_face(14)

    def mineAreaLeftAndRightPressed(self, i, j):
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
                text4 = '{:.3f}'.format(max(0, self.label.boardPossibility[i//self.pixSize][j//self.pixSize]))
                self.label_info.setText(text4)
        # 播放录像时的鼠标移动事件
        elif self.game_state == 'showdisplay':
            if not self.pos_is_in_board(i, j):
                self.label_info.setText('(是雷的概率)')
            else:
                text4 = '{:.3f}'.format(max(0, self.label.ms_board.game_board_poss[i//self.pixSize][j//self.pixSize]))
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

    def mineNumWheel(self, i):
        # 在雷上滚轮，调雷数
        if self.game_state == 'ready':
            if i > 0:
                if self.mineNum < self.row * self.column - 1:
                    self.mineNum += 1
                    self.mineUnFlagedNum += 1
                    self.showMineNum(self.mineUnFlagedNum)
            elif i < 0:
                if self.mineNum > 1:
                    self.mineNum -= 1
                    self.mineUnFlagedNum -= 1
                    self.showMineNum(self.mineUnFlagedNum)
            self.timer_mine_num = QTimer()
            # self.timer_mine_num.timeout.connect(self.refreshSettingsDefault)
            self.timer_mine_num.setSingleShot(True)
            self.timer_mine_num.start(3000)

    def gameStart(self):
        # 画界面，但是不埋雷
        self.mineUnFlagedNum = self.mineNum  # 没有标出的雷，显示在左上角
        self.showMineNum(self.mineUnFlagedNum)    # 在左上角画雷数
        # pixmap = QPixmap(self.pixmapNum[14])
        # self.label_2.setPixmap(self.pixmapNum[14])
        self.set_face(14)
        # self.label_2.setScaledContents(True)
        self.time_10ms = 0
        self.showTime(self.time_10ms)
        self.timer_10ms.stop()
        self.score_board_manager.editing_row = -1

        self.label.paintPossibility = False
        self.label_info.setText(self.player_identifier)

        # 这里有点乱
        self.label.set_rcp(self.row, self.column, self.pixSize)
        self.game_state = 'ready'
        self.label.reloadCellPic(self.pixSize)
        self.label.setMinimumSize(QtCore.QSize(self.pixSize*self.column + 8, self.pixSize*self.row + 8))
        self.label.setMaximumSize(QtCore.QSize(self.pixSize*self.column + 8, self.pixSize*self.row + 8))
        # self.label.setMinimumSize(QtCore.QSize(8, 8))
        self.label_2.reloadFace(self.pixSize)

        # self.mainWindow.setMaximumSize(QtCore.QSize(16777215, 16777215))
        # self.mainWindow.setMinimumSize(QtCore.QSize(10, 10))
        self.minimumWindow()

    # 点击脸时调用，或尺寸不变时重开
    def gameRestart(self, e = None):  # 画界面，但是不埋雷，改数据而不是重新生成label
        if e:
        # 点脸周围时，会传入一个e参数
            if not (self.MinenumTimeWigdet.width() >= e.localPos().x() >= 0 and 0 <= e.localPos().y() <= self.MinenumTimeWigdet.height()):
                return
        # 此时self.label.ms_board是mm.abstract_game_board的实例
        if self.game_state == 'display' or self.game_state == 'showdisplay':
            # self.timer_video.stop()
            # self.ui_video_control.QWidget.close()
            self.label.ms_board = ms.BaseVideo([[0] * self.column for _ in range(self.row)], self.pixSize)
            self.label.ms_board.mode = self.gameMode
        elif self.game_state == 'study':
            # self.num_bar_ui.QWidget.close()
            self.score_board_manager.visible()
            self.label.ms_board = ms.BaseVideo([[0] * self.column for _ in range(self.row)], self.pixSize)
            self.label.ms_board.mode = self.gameMode
        self.label_info.setText(self.player_identifier)
        self.game_state = 'ready'
        self.enable_screenshot()

        self.time_10ms = 0
        self.showTime(self.time_10ms)
        self.mineUnFlagedNum = self.mineNum
        self.showMineNum(self.mineUnFlagedNum)
        self.set_face(14)

        self.timer_10ms.stop()
        self.score_board_manager.editing_row = -1
        self.label.ms_board.reset(self.row, self.column, self.pixSize)
        self.label.update()

        self.label.paintPossibility = False
        # self.label.paint_cursor = False
        # self.label.setMouseTracking(False) # 鼠标未按下时，组织移动事件回调


    # 游戏结束画残局，改状态
    def gameFinished(self):
        if self.label.ms_board.game_board_state == 3 and self.end_then_flag:
            self.label.ms_board.win_then_flag_all_mine()
        elif self.label.ms_board.game_board_state == 4:
            self.label.ms_board.loss_then_open_all_mine()
        # 刷新游戏局面
        self.label.update()
        # 刷新计数器数值
        self.timeCount()
        self.score_board_manager.with_namespace({
            "is_official": self.is_official(),
            "is_fair": self.is_fair()
            })
        self.score_board_manager.show(self.label.ms_board, index_type = 2)
        self.enable_screenshot()
        self.unlimit_cursor()


    def gameWin(self):  # 成功后改脸和状态变量，停时间
        self.timer_10ms.stop()
        self.score_board_manager.editing_row = -1

        if self.game_state == 'joking' or self.game_state == 'show':
            self.game_state = 'jowin'
        elif self.game_state == 'playing':
            self.game_state = 'win'
        else:
            raise RuntimeError
        self.set_face(17)

        if self.autosave_video and self.checksum_module_ok():
            self.dump_evf_file_data()
            self.save_evf_file()


        self.gameFinished()


        # 尝试弹窗，没有破纪录则不弹
        if self.auto_notification and self.is_fair():
            self.try_record_pop()

    def checksum_module_ok(self):
        # 检查校验和模块的签名
        # 调试的时候不会自动存录像，除非将此处改为return True
        # return True
        return hashlib.sha256(bytes(metaminesweeper_checksum.get_self_key())).hexdigest() ==\
            '590028493bb58a25ffc76e2e2ad490df839a1f449435c35789d3119ca69e5d4f'


    # 搜集数据，生成evf文件的二进制数据，但是不保存
    def dump_evf_file_data(self):
        if isinstance(self.label.ms_board, ms.BaseVideo):
            self.label.ms_board.use_question = False # 禁用问号是共识
            self.label.ms_board.use_cursor_pos_lim = self.cursor_limit
            self.label.ms_board.use_auto_replay = self.auto_replay > 0
            
            self.label.ms_board.is_fair = self.is_fair()
            self.label.ms_board.is_official = self.is_official()
            
            self.label.ms_board.software = superGUI.version
            self.label.ms_board.mode = self.gameMode
            self.label.ms_board.player_identifier = self.player_identifier
            self.label.ms_board.race_identifier = self.race_identifier
            self.label.ms_board.uniqueness_identifier = self.unique_identifier
            self.label.ms_board.country = "XX" if not self.country else country_name[self.country].upper()
            self.label.ms_board.device_uuid = hashlib.md5(bytes(str(uuid.getnode()).encode())).hexdigest().encode( "UTF-8" )
    
            self.label.ms_board.generate_evf_v4_raw_data()
            # 补上校验值
            checksum = self.checksum_guard.get_checksum(self.label.ms_board.raw_data[:-1])
            self.label.ms_board.checksum_evf_v4 = checksum
            return
        elif isinstance(self.label.ms_board, ms.EvfVideo):
            return
        elif isinstance(self.label.ms_board, ms.AvfVideo):
            self.label.ms_board.generate_evf_v4_raw_data()
            return
        elif isinstance(self.label.ms_board, ms.MvfVideo):
            self.label.ms_board.generate_evf_v4_raw_data()
            return
        elif isinstance(self.label.ms_board, ms.RmvVideo):
            self.label.ms_board.generate_evf_v4_raw_data()
            return


    # 将evf数据存成evf文件
    # 调试的时候不会自动存录像，见checksum_module_ok
    # 菜单保存的回调。以及游戏结束自动保存。
    def save_evf_file(self):
        if not os.path.exists(self.replay_path):
            os.mkdir(self.replay_path)

        if (self.label.ms_board.row, self.label.ms_board.column, self.label.ms_board.mine_num) == (8, 8, 10):
            filename_level = "b_"
        elif (self.label.ms_board.row, self.label.ms_board.column, self.label.ms_board.mine_num) == (16, 16, 40):
            filename_level = "i_"
        elif (self.label.ms_board.row, self.label.ms_board.column, self.label.ms_board.mine_num) == (16, 30, 99):
            filename_level = "e_"
        else:
            filename_level = "c_"
        if self.game_state == "display" or self.game_state == "showdisplay":
            self.label.ms_board.current_time = 999999.9
        file_name = self.replay_path + '\\' + filename_level +\
                         f'{self.label.ms_board.mode}' + '_' +\
                             f'{self.label.ms_board.rtime:.3f}' +\
                                 '_' + f'{self.label.ms_board.bbbv}' +\
                                     '_' + f'{self.label.ms_board.bbbv_s:.3f}' +\
                                         '_' + self.label.ms_board.player_identifier
        
        if not self.label.ms_board.is_completed:
            file_name += "_fail"
        if not self.label.ms_board.is_fair:
            file_name += "_cheat"
        if self.label.ms_board.software[0] != "元":
            file_name += "_trans"
        elif not self.checksum_module_ok():
            file_name += "_fake"
        
        self.label.ms_board.save_to_evf_file(file_name)


    def gameFailed(self): # 失败后改脸和状态变量
        self.timer_10ms.stop()
        self.score_board_manager.editing_row = -1

        if self.game_state == 'joking':
            self.game_state = 'jofail'
        else:
            self.game_state = 'fail'

        self.set_face(16)

        # “自动重开比例”，大于等于该比例时，不自动重开。负数表示禁用。0相当于禁用，但可以编辑。
        if self.label.ms_board.bbbv_solved / self.label.ms_board.bbbv * 100 < self.auto_replay:
            self.gameRestart()
        else:
            self.gameFinished()

    def try_record_pop(self):
        # 尝试弹窗，或不弹窗
        # 不显示的记录的序号
        del_items = []
        nf_items = []
        b = self.label.ms_board
        if b.level == 6:
            # 自定义不弹窗
            return
        if b.level == 3:
            record_key = "B"
            LNF = "BNF"
        elif b.level == 4:
            record_key = "I"
            LNF = "INF"
        elif b.level == 5:
            record_key = "E"
            LNF = "ENF"
        else:
            raise RuntimeError()

        _translate = QtCore.QCoreApplication.translate

        # 上方的模式，标准和盲扫都是标准
        if self.gameMode == 0:
            record_key += "FLAG"
            mode_text = _translate("Form", "标准")
            if b.rce == 0:
                mode_text = _translate("Form", "标准（盲扫）")
            else:
                mode_text = _translate("Form", "标准")
        elif self.gameMode == 4:
            record_key += "WIN7"
            mode_text = _translate("Form", "Win7")
        elif self.gameMode == 5:
            record_key += "CS"
            mode_text = _translate("Form", "经典无猜")
        elif self.gameMode == 6:
            record_key += "SS"
            mode_text = _translate("Form", "强无猜")
        elif self.gameMode == 7:
            record_key += "WS"
            mode_text = _translate("Form", "弱无猜")
        elif self.gameMode == 8:
            record_key += "TBS"
            mode_text = _translate("Form", "准无猜")
        elif self.gameMode == 9:
            record_key += "SG"
            mode_text = _translate("Form", "强可猜")
        elif self.gameMode == 10:
            record_key += "WG"
            mode_text = _translate("Form", "弱可猜")
        else:
            raise RuntimeError()

        
        if b.rtime < self.record_setting.value(f"{record_key}/rtime", None, float):
            if b.rce == 0 and self.gameMode == 0:
                self.record_setting.set_value(f"{record_key}/rtime", b.rtime)
                self.record_setting.set_value(f"{LNF}/rtime", b.rtime)
            else:
                self.record_setting.set_value(f"{record_key}/rtime", b.rtime)
        elif b.rce == 0 and self.gameMode == 0 and\
            b.rtime < self.record_setting.value(f"{LNF}/rtime", None, float):
            self.record_setting.set_value(f"{LNF}/rtime", b.rtime)
            nf_items.append(1)
        else:
            del_items.append(1)
        if b.bbbv_s > self.record_setting.value(f"{record_key}/bbbv_s", None, float):
            if b.rce == 0 and self.gameMode == 0:
                self.record_setting.set_value(f"{record_key}/bbbv_s", b.bbbv_s)
                self.record_setting.set_value(f"{LNF}/bbbv_s", b.bbbv_s)
            else:
                self.record_setting.set_value(f"{record_key}/bbbv_s", b.bbbv_s)
        elif b.rce == 0 and self.gameMode == 0 and\
            b.bbbv_s > self.record_setting.value(f"{LNF}/bbbv_s", None, float):
            self.record_setting.set_value(f"{LNF}/bbbv_s", b.bbbv_s)
            nf_items.append(3)
        else:
            del_items.append(3)
        if b.stnb > self.record_setting.value(f"{record_key}/stnb", None, float):
            if b.rce == 0 and self.gameMode == 0:
                self.record_setting.set_value(f"{record_key}/stnb", b.stnb)
                self.record_setting.set_value(f"{LNF}/stnb", b.stnb)
            else:
                self.record_setting.set_value(f"{record_key}/stnb", b.stnb)
        elif b.rce == 0 and self.gameMode == 0 and\
            b.stnb > self.record_setting.value(f"{LNF}/stnb", None, float):
            self.record_setting.set_value(f"{LNF}/stnb", b.stnb)
            nf_items.append(5)
        else:
            del_items.append(5)
        if b.ioe > self.record_setting.value(f"{record_key}/ioe", None, float):
            if b.rce == 0 and self.gameMode == 0:
                self.record_setting.set_value(f"{record_key}/ioe", b.ioe)
                self.record_setting.set_value(f"{LNF}/ioe", b.ioe)
            else:
                self.record_setting.set_value(f"{record_key}/ioe", b.ioe)
        elif b.rce == 0 and self.gameMode == 0 and\
            b.ioe > self.record_setting.value(f"{LNF}/ioe", None, float):
            self.record_setting.set_value(f"{LNF}/ioe", b.ioe)
            nf_items.append(7)
        else:
            del_items.append(7)
        if b.path < self.record_setting.value(f"{record_key}/path", None, float):
            if b.rce == 0 and self.gameMode == 0:
                self.record_setting.set_value(f"{record_key}/path", b.path)
                self.record_setting.set_value(f"{LNF}/path", b.path)
            else:
                self.record_setting.set_value(f"{record_key}/path", b.path)
        elif b.rce == 0 and self.gameMode == 0 and\
            b.path < self.record_setting.value(f"{LNF}/path", None, float):
            self.record_setting.set_value(f"{LNF}/path", b.path)
            nf_items.append(9)
        else:
            del_items.append(9)
        if b.rqp < self.record_setting.value(f"{record_key}/rqp", None, float):
            if b.rce == 0 and self.gameMode == 0:
                self.record_setting.set_value(f"{record_key}/rqp", b.rqp)
                self.record_setting.set_value(f"{LNF}/rqp", b.rqp)
            else:
                self.record_setting.set_value(f"{record_key}/rqp", b.rqp)
        elif b.rce == 0 and self.gameMode == 0 and\
            b.rqp < self.record_setting.value(f"{LNF}/rqp", None, float):
            self.record_setting.set_value(f"{LNF}/rqp", b.rqp)
            nf_items.append(11)
        else:
            del_items.append(11)

        # pb相关的弹窗。仅高级（不分FL还是NF）
        if self.gameMode == 0:
            if b.level == 3:
                if b.rtime < self.record_setting.value(f"BEGINNER/{b.bbbv}", None, float):
                    self.record_setting.set_value(f"BEGINNER/{b.bbbv}", b.rtime)
                    del_items += [14, 15]
                else:
                    del_items += [13, 14, 15]
            elif b.level == 4:
                if b.rtime < self.record_setting.value(f"INTERMEDIATE/{b.bbbv}", None, float):
                    self.record_setting.set_value(f"INTERMEDIATE/{b.bbbv}", b.rtime)
                    del_items += [13, 15]
                else:
                    del_items += [13, 14, 15]
            elif b.level == 5:
                if b.rtime < self.record_setting.value(f"EXPERT/{b.bbbv}", None, float):
                    self.record_setting.set_value(f"EXPERT/{b.bbbv}", b.rtime)
                    del_items += [13, 14]
                else:
                    del_items += [13, 14, 15]
            else:
                raise RuntimeError()
        else:
            del_items += [13, 14, 15]

        if len(del_items) < 9:
            ui = gameRecordPop.ui_Form(self.r_path, del_items, b.bbbv, nf_items, self.mainWindow)
            ui.Dialog.setModal(True)
            ui.label_16.setText(mode_text)
            ui.Dialog.show()
            ui.Dialog.exec_()

    def showMineNum(self, n):
        # 显示剩余雷数，雷数大于等于0，小于等于999，整数

        self.mineNumShow = n
        if n >= 0 and n <= 999:
            self.label_11.setPixmap(self.pixmapLEDNum[n//100])
            self.label_12.setPixmap(self.pixmapLEDNum[n//10%10])
            self.label_13.setPixmap(self.pixmapLEDNum[n%10])
        elif n < 0:
            self.label_11.setPixmap(self.pixmapLEDNum[0])
            self.label_12.setPixmap(self.pixmapLEDNum[0])
            self.label_13.setPixmap(self.pixmapLEDNum[0])
        elif n >= 1000:
            self.label_11.setPixmap(self.pixmapLEDNum[9])
            self.label_12.setPixmap(self.pixmapLEDNum[9])
            self.label_13.setPixmap(self.pixmapLEDNum[9])

    def showTime(self, t):
        # 显示剩余时间，时间数大于等于0，小于等于999秒，整数
        if t >= 0 and t <= 999:
            self.label_31.setPixmap(self.pixmapLEDNum[t//100])
            self.label_32.setPixmap(self.pixmapLEDNum[t//10%10])
            self.label_33.setPixmap(self.pixmapLEDNum[t%10])
            return
        elif t >= 1000:
            return

    def actionChecked(self, k):
        # 菜单前面打勾
        self.actionchu_ji.setChecked(False)
        self.actionzhogn_ji.setChecked(False)
        self.actiongao_ji.setChecked(False)
        self.actionzi_ding_yi.setChecked(False)
        if k == 'B':
            self.actionchu_ji.setChecked(True)
        elif k == 'I':
            self.actionzhogn_ji.setChecked(True)
        elif k == 'E':
            self.actiongao_ji.setChecked(True)
        elif k == 'C':
            self.actionzi_ding_yi.setChecked(True)

    def predefined_Board(self, k):
        # 按快捷键123456时的回调
        row = self.predefinedBoardPara[k]['row']
        column = self.predefinedBoardPara[k]['column']
        mine_num = self.predefinedBoardPara[k]['mine_num']
        self.setBoard_and_start(row, column, mine_num)
        self.pixSize = self.predefinedBoardPara[k]['pixsize']
        if isinstance(self.label.ms_board, ms.BaseVideo):
            self.label.ms_board.reset(row, column, self.pixSize)
        else:
            # 解决播放录像时快捷键切换难度报错
            self.label.ms_board = ms.BaseVideo([[0] * column for _ in range(row)], self.pixSize)
        self.gameMode = self.predefinedBoardPara[k]['gamemode']
        self.score_board_manager.with_namespace({
            "mode": self.gameMode,
            })
        self.score_board_manager.show(self.label.ms_board, index_type=1)
        self.board_constraint = self.predefinedBoardPara[k]['board_constraint']
        self.attempt_times_limit = self.predefinedBoardPara[k]['attempt_times_limit']


    # 菜单回放的回调
    def replay_game(self):
        if not isinstance(self.label.ms_board, ms.BaseVideo):
            return
        if self.game_state not in ("fail", "win", "jofail", "jowin"):
            return
        self.dump_evf_file_data()
        raw_data = bytes(self.label.ms_board.raw_data)
        
        video = ms.EvfVideo("virtual.evf", raw_data)
        self.play_video(video)


    def action_CEvent(self):
        # 点击菜单栏的自定义后回调
        self.actionChecked('C')
        ui = gameDefinedParameter.ui_Form(self.r_path, self.row, self.column, 
                                          self.mineNum, self.mainWindow)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()
        if ui.alter:
            self.setBoard_and_start(ui.row, ui.column, ui.mineNum)

    def setBoard(self, row, column, mineNum):
        # 把局面设置成(row, column, mineNum)，同时提取配套参数
        # 打开录像时、改级别时用
        self.row = row
        self.column = column
        self.mineNum = mineNum
        if (row, column, mineNum) == (8, 8, 10):
            self.actionChecked('B')
            self.pixSize = self.predefinedBoardPara[1]['pixsize']
            self.gameMode = self.predefinedBoardPara[1]['gamemode']
            self.board_constraint = self.predefinedBoardPara[1]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[1]['attempt_times_limit']
        elif (row, column, mineNum) == (16, 16, 40):
            self.actionChecked('I')
            self.pixSize = self.predefinedBoardPara[2]['pixsize']
            self.gameMode = self.predefinedBoardPara[2]['gamemode']
            self.board_constraint = self.predefinedBoardPara[2]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[2]['attempt_times_limit']
        elif (row, column, mineNum) == (16, 30, 99):
            self.actionChecked('E')
            self.pixSize = self.predefinedBoardPara[3]['pixsize']
            self.gameMode = self.predefinedBoardPara[3]['gamemode']
            self.board_constraint = self.predefinedBoardPara[3]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[3]['attempt_times_limit']
        else:
            self.actionChecked('C')
            self.pixSize = self.predefinedBoardPara[0]['pixsize']
            self.gameMode = self.predefinedBoardPara[0]['gamemode']
            self.board_constraint = self.predefinedBoardPara[0]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[0]['attempt_times_limit']

    def setBoard_and_start(self, row, column, mineNum):
        # 把局面设置成(row, column, mineNum)，把3BV的限制设置成min3BV, max3BV
        # 比gameStart更高级
        if self.game_state == 'display' or self.game_state == 'showdisplay':
            self.label.paintPossibility = False
        if (self.row, self.column, self.mineNum) != (row, column, mineNum):
            self.setBoard(row, column, mineNum)
            self.gameStart()
        else:
            self.gameRestart()


    def action_NEvent(self):
        # 游戏设置
        self.actionChecked('N')
        ui = gameSettings.ui_Form(self)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()
        if ui.alter:
            
            self.pixSize = ui.pixSize
            self.gameStart()
            self.gameMode = ui.gameMode
            self.auto_replay = ui.auto_replay
            self.end_then_flag = ui.end_then_flag
            self.cursor_limit = ui.cursor_limit
            self.auto_notification = ui.auto_notification
            self.player_identifier = ui.player_identifier
            self.label_info.setText(self.player_identifier)
            self.race_identifier = ui.race_identifier
            # 国家或地区名的全称，例如”中国“
            self.country = ui.country
            self.set_country_flag()
            self.autosave_video = ui.autosave_video
            self.filter_forever = ui.filter_forever

            self.board_constraint = ui.board_constraint
            self.attempt_times_limit = ui.attempt_times_limit
            if (self.row, self.column, self.mineNum) == (8, 8, 10):
                self.predefinedBoardPara[1]['attempt_times_limit'] = self.attempt_times_limit
                self.predefinedBoardPara[1]['board_constraint'] = self.board_constraint
                self.predefinedBoardPara[1]['gamemode'] = ui.gameMode
            elif (self.row, self.column, self.mineNum) == (16, 16, 40):
                self.predefinedBoardPara[2]['attempt_times_limit'] = self.attempt_times_limit
                self.predefinedBoardPara[2]['board_constraint'] = self.board_constraint
                self.predefinedBoardPara[2]['gamemode'] = ui.gameMode
            elif (self.row, self.column, self.mineNum) == (16, 30, 99):
                self.predefinedBoardPara[3]['attempt_times_limit'] = self.attempt_times_limit
                self.predefinedBoardPara[3]['board_constraint'] = self.board_constraint
                self.predefinedBoardPara[3]['gamemode'] = ui.gameMode
            else:
                self.predefinedBoardPara[0]['attempt_times_limit'] = self.attempt_times_limit
                self.predefinedBoardPara[0]['board_constraint'] = self.board_constraint
                self.predefinedBoardPara[0]['gamemode'] = ui.gameMode

            self.mainWindow.setWindowOpacity(ui.transparency / 100)
            for child in self.mainWindow.findChildren(QWidget):
                # 设置子窗口的透明度
                child.setWindowOpacity(ui.transparency / 100)
            
            self.score_board_manager.with_namespace({
                "race_identifier": ui.race_identifier,
                "mode": self.gameMode,
                })
            self.score_board_manager.show(self.label.ms_board, index_type=1)

    def action_QEvent(self):
        # 快捷键设置的回调
        self.actionChecked('Q')
        ui = gameSettingShortcuts.myGameSettingShortcuts(self.game_setting,
                                                         self.ico_path, self.r_path,
                                                         self.mainWindow)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()
        if ui.alter:
            self.readPredefinedBoardPara()

    def action_mouse_setting(self):
        # 打开鼠标设置的第三个菜单
        try:
            os.system("start rundll32.exe shell32.dll,Control_RunDLL main.cpl,,2")
        except:
            ...
        

    def action_AEvent(self):
        # 关于
        self.actionChecked('A')
        ui = gameAbout.ui_Form(self.r_path)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()

    def auto_Update(self):
        data = {
            "Github": "https://api.github.com/repos/",
            "Gitee": "https://api.gitee.com/repos/",
        }
        update_dialog = CheckUpdateGui(GitHub(SourceManager(data), "eee555",
                       "Metasweeper", superGUI.version, "(\d+\.\d+\.\d+)"), parent = self)
        update_dialog.setModal(True)
        update_dialog.show()
        update_dialog.exec_()

    def screenShot(self):
        # ‘ctrl’ + ‘space’ 事件，启动截图

        if self.game_state == "playing":
            self.game_state = "joking"
        if self.game_state == "display" or self.game_state == "showdisplay":
            self.video_playing = False
            self.timer_video.stop()
            
        
        self.enable_screenshot()

        ui = captureScreen.CaptureScreen()
        ui.show()
        ui.exec_()

        if not ui.success_flag or len(ui.board) < 6 or len(ui.board[0]) < 6:
            return

        # 会报两种runtimeerror，标记阶段无解的局面、枚举阶段无解的局面
        try:
            ans = ms.cal_possibility_onboard(ui.board, 0.20625 if len(ui.board[0]) >= 24 else 0.15625)
        except:
            return

        if not ans[0]:
            # 概率矩阵为空就是出错了
            return


        # 连续截屏时
        # if self.game_state == 'study':
        #     self.num_bar_ui.QWidget.close()
        self.game_state = 'study'    # 局面进入研究模式

        # 主定时器停一下，不停的话需要的修补太多
        self.timer_10ms.stop()
        self.score_board_manager.invisible()

        # self.label.ms_board = mm.abstract_game_board()
        # self.label.ms_board.mouse_state = 1
        # self.label.ms_board.game_board_state = 1
        # self.label.ms_board.game_board = ui.board

        # 在局面上画概率，或不画
        # game_board = ui.board

        self.row = len(ui.board)
        self.column = len(ui.board[0])

        self.num_bar_ui = mine_num_bar.ui_Form(ans[1], self.pixSize * self.row, self.mainWindow)
        self.num_bar_ui.QWidget.barSetMineNum.connect(self.showMineNum)
        self.num_bar_ui.QWidget.barSetMineNumCalPoss.connect(self.render_poss_on_board)
        self.num_bar_ui.setSignal()

        # self.mainWindow.closeEvent_.connect(self.num_bar_ui.QWidget.close)

        self.timer_close_bar = QTimer()
        self.timer_close_bar.timeout.connect(lambda:self.num_bar_ui.QWidget.show())
        self.timer_close_bar.setSingleShot(True)
        self.timer_close_bar.start(1)
        # self.num_bar_ui.QWidget.show()

        # self.setBoard_and_start(len(ui.board), len(ui.board[0]), ans[1][1])
        self.setBoard(self.row, self.column, ans[1][1])
        
        self.label.paintPossibility = True
        self.label.set_rcp(self.row, self.column, self.pixSize)
        
        self.label.ms_board.game_board = ui.board
        self.label.ms_board.mouse_state = 1
        self.label.ms_board.game_board_state = 1
        self.mineNumShow = ans[1][1]
        self.showMineNum(self.mineNumShow)
        self.label.boardPossibility = ans[0]
        

        self.label.update()
        # self.label.setMouseTracking(True)

        self.minimumWindow()

    def render_poss_on_board(self):
        # 雷数条拉动后、改局面后，显示雷数并展示
        try:
            ans = ms.cal_possibility_onboard(self.label.ms_board.game_board, self.mineNumShow)
        except:
            try:
                ans = ms.cal_possibility_onboard(self.label.ms_board.game_board,
                                                 self.mineNumShow / self.row / self.column)
            except:
                # 无解，算法增加雷数后无解
                self.label.paintPossibility = False
                self.num_bar_ui.QWidget.hide()
                self.label.update()
                return
            else:
                # 无解，算法增加雷数后有解
                self.mineNumShow = ans[1][1]
                self.label.boardPossibility = ans[0]
                self.label.paintPossibility = True

        self.label.boardPossibility = ans[0]
        self.label.paintPossibility = True
        self.num_bar_ui.QWidget.show()
        self.num_bar_ui.spinBox.setMinimum(ans[1][0])
        self.num_bar_ui.spinBox.setMaximum(ans[1][2])
        self.num_bar_ui.spinBox.setValue(ans[1][1])
        self.num_bar_ui.verticalSlider.setMinimum(ans[1][0])
        self.num_bar_ui.verticalSlider.setMaximum(ans[1][2])
        self.num_bar_ui.verticalSlider.setValue(ans[1][1])
        self.num_bar_ui.label_4.setText(str(ans[1][0]))
        self.num_bar_ui.label_5.setText(str(ans[1][2]))
        self.label.update()

        self.showMineNum(self.mineNumShow)


    def showScores(self):
        # 按空格
        if self.game_state == 'win' or self.game_state == 'fail':
            # 游戏结束后，按空格展示成绩(暂时屏蔽这个功能)
            # ui = gameScores.Ui_Form(self.scores, self.scoresValue)
            # ui.setModal(True)
            # ui.show()
            # ui.exec_()
            # # 展示每格概率
            ...
        elif self.game_state == 'playing' or self.game_state == 'joking':
            self.game_state = 'show'
            self.label.paintPossibility = True
            # self.label.setMouseTracking(True)
            mineNum = self.mineNum
            # 删去用户标的雷，因为可能标错
            # game_board = list(map(lambda x: list(map(lambda y: min(y, 10), x)),
            #                  self.label.ms_board.game_board))
            ans = ms.cal_possibility_onboard(self.label.ms_board.game_board, mineNum)
            self.label.boardPossibility = ans[0]
            self.label.update()


    def mineKeyReleaseEvent(self, keyName):
        # 松开空格键
        if keyName == 'Space':
            if self.game_state == 'show':
                self.game_state = 'joking'
                self.label.paintPossibility = False
                # self.label.setMouseTracking(False)
                self.label_info.setText(self.player_identifier)
                self.label.update()
            elif self.game_state == 'display':
                self.game_state = 'showdisplay'
                self.label.paintPossibility = True
                # self.label.setMouseTracking(True)
                self.label.update()
            elif self.game_state == 'showdisplay':
                self.game_state = 'display'
                self.label.paintPossibility = False
                # self.label.setMouseTracking(False)
                self.label.update()

    def refreshSettingsDefault(self):
        # 刷新游戏设置.ini里默认部分的设置，与当前游戏里一致，
        # 除了transparency、mainwintop和mainwinleft
        self.game_setting.set_value("DEFAULT/gamemode", str(self.gameMode))
        self.game_setting.set_value("DEFAULT/pixsize", str(self.pixSize))
        self.game_setting.set_value("DEFAULT/row", str(self.row))
        self.game_setting.set_value("DEFAULT/column", str(self.column))
        self.game_setting.set_value("DEFAULT/minenum", str(self.minenum))
        self.game_setting.sync()

    # 打开录像文件的回调
    def action_OpenFile(self, openfile_name = None):
        if not openfile_name:
            openfile_name = QFileDialog.\
                getOpenFileName(self.mainWindow, '打开文件','../replay','All(*.avf *.evf *.rmv *.mvf);;Arbiter video(*.avf);;Metasweeper video(*.evf);;Vienna MineSweeper video(*.rmv);;Minesweeper Clone 0.97(*.mvf)')
            openfile_name = openfile_name[0]
        # 实例化
        if not openfile_name:
            return
        self.set_face(14)

        try:
            if openfile_name[-3:] == "avf":
                video = ms.AvfVideo(openfile_name)
            elif openfile_name[-3:] == "rmv":
                video = ms.RmvVideo(openfile_name)
            elif openfile_name[-3:] == "evf":
                # evf版本过时以后会引发异常
                video = ms.EvfVideo(openfile_name)
            elif openfile_name[-3:] == "mvf":
                video = ms.MvfVideo(openfile_name)
            else:
                return
        except:
            return
        self.play_video(video)

    # 播放AvfVideo、RmvVideo、EvfVideo、MvfVideo或BaseVideo
    def play_video(self, video):
        if self.game_state == 'display':
            self.ui_video_control.QWidget.close()
        self.game_state = 'display'

        video.parse_video()
        video.analyse()
        # 检查evf的checksum，其余录像没有鉴定能力
        if isinstance(video, ms.EvfVideo):
            self.score_board_manager.with_namespace({
                "checksum_ok": self.checksum_guard.\
                    valid_checksum(video.raw_data[:-33], video.checksum),
                })
        else:
            self.score_board_manager.with_namespace({
                "checksum_ok": False,
                })
        self.score_board_manager.with_namespace({
            "is_official": video.is_official,
            "is_fair": video.is_fair,
            "mode": video.mode,
            })
        video.analyse_for_features(["high_risk_guess", "jump_judge", "needless_guess",
                                    "mouse_trace", "vision_transfer", "survive_poss"])

        # 组织录像评论
        comments = []
        for event in video.events:
            t = event.time
            comment = event.comments
            if comment:
                comments.append((t, [i.split(': ') for i in comment.split(';')[:-1]]))
        # 调整窗口
        if (video.row, video.column) != (self.row, self.column):
            self.setBoard(video.row, video.column, video.mine_num)
            self.label.paintPossibility = False
            self.label.set_rcp(self.row, self.column, self.pixSize)
            # self.label.reloadCellPic(self.pixSize)
            self.label.setMinimumSize(QtCore.QSize(self.pixSize*self.column + 8, self.pixSize*self.row + 8))
            self.label.setMaximumSize(QtCore.QSize(self.pixSize*self.column + 8, self.pixSize*self.row + 8))
            self.label_2.reloadFace(self.pixSize)
            self.minimumWindow()



        self.timer_video = QTimer()
        self.timer_video.timeout.connect(self.video_playing_step)
        self.ui_video_control = videoControl.ui_Form(self.r_path, video, comments, 
                                                     self.game_setting, self.mainWindow)
        # self.mainWindow.closeEvent_.connect(self.ui_video_control.QWidget.close)
        self.ui_video_control.pushButton_play.clicked.connect(self.video_play)
        self.ui_video_control.pushButton_replay.clicked.connect(self.video_replay)
        self.ui_video_control.videoSetTime.connect(self.video_set_time)
        self.ui_video_control.label_speed.wEvent.connect(self.video_set_speed)
        for labels in self.ui_video_control.comments_labels:
            labels[0].Release.connect(self.video_set_a_time)
            labels[1].Release.connect(self.video_set_a_time)
            labels[2].Release.connect(self.video_set_a_time)
        self.ui_video_control.QWidget.show()

        self.video_time = video.video_start_time # 录像当前时间
        self.video_stop_time = video.video_end_time # 录像停止时间
        self.video_time_step = 0.01 # 录像时间的步长，定时器始终是10毫秒
        self.label.paint_cursor = True
        self.video_playing = True # 录像正在播放
        # 禁用双击修改指标名称公式
        self.score_board_manager.editing_row = -2

        video.video_playing_pix_size = self.label.pixSize
        self.label.ms_board = video
        # 改成录像的标识
        # print(self.label.ms_board.player_identifier)
        self.label_info.setText(self.label.ms_board.player_identifier)
        # 改成录像的国旗
        self.set_country_flag(self.label.ms_board.country)
        
        self.timer_video.start(10)


    def video_playing_step(self):
        # 播放录像时定时器的回调
        self.label.ms_board.current_time = self.video_time
        if self.video_time >= self.video_stop_time:
            self.timer_video.stop()
            self.video_playing = False
        self.label.update()
        self.score_board_manager.show(self.label.ms_board, index_type = 3)
        self.video_time += self.video_time_step
        self.showTime(int(self.video_time))
        self.ui_video_control.horizontalSlider_time.blockSignals(True)
        self.ui_video_control.horizontalSlider_time.setValue(int(self.video_time * 1000))
        self.ui_video_control.horizontalSlider_time.blockSignals(False)
        self.ui_video_control.doubleSpinBox_time.blockSignals(True)
        self.ui_video_control.doubleSpinBox_time.setValue(self.label.ms_board.time)
        self.ui_video_control.doubleSpinBox_time.blockSignals(False)

    def video_play(self):
        # 点播放、暂停键的回调
        if self.video_playing:
            self.video_playing = False
            self.timer_video.stop()
        else:
            self.video_playing = True
            self.timer_video.start(10)
            self.video_stop_time = self.label.ms_board.video_end_time

    def video_replay(self):
        self.video_playing = True
        self.video_time = self.label.ms_board.video_start_time
        self.timer_video.start(10)
        self.video_stop_time = self.label.ms_board.video_end_time

    def video_set_speed(self, speed):
        self.video_time_step = speed * 0.01

    def video_set_time(self, t):
        # 把录像定位到某一个时刻。是拖动进度条的回调
        self.video_time = t / 1000
        self.label.ms_board.current_time = self.video_time
        self.label.update()
        self.score_board_manager.show(self.label.ms_board, index_type = 3)

    def video_set_a_time(self, t):
        # 把录像定位到某一段时间，默认前后一秒，自动播放。是点录像事件的回调
        self.video_time = (t - 1000) / 1000
        self.video_stop_time = (t + 1000) / 1000  # 大了也没关系，ms_toollib自动处理
        self.timer_video.start()
        self.video_playing = True

    def is_official(self) -> bool:
        # 局面开始时，判断一下局面是设置是否正式。
        # 极端小的3BV依然是合法的，而网站是否认同不关软件的事。
        if self.board_constraint:
            return False
        return self.game_state == "win" and self.gameMode == 0

    def is_fair(self) -> bool:
        if self.board_constraint:
            return False
        return self.game_state == "win" or self.game_state == "fail"

    def cell_is_in_board(self, i, j):
        # 点在局面内，单位是格不是像素
        return i >= 0 and i < self.row and j >= 0 and j < self.column

    def pos_is_in_board(self, i, j) -> bool:
        # 点在局面内，单位是像素不是格
        return i >= 0 and i < self.row * self.pixSize and j >= 0 and j < self.column * self.pixSize

    def set_face(self, face_type):
        # 设置脸 14smile；15click
        pixmap = QPixmap(self.pixmapNum[face_type])
        self.label_2.setPixmap(pixmap)
        self.label_2.setScaledContents(True)
        
    def hidden_score_board(self):
        # 按/隐藏计数器，再按显示
        if self.game_state == 'study':
            return
        if self.score_board_manager.ui.QWidget.isVisible():
            self.score_board_manager.invisible()
        else:
            self.score_board_manager.visible()
            self.mainWindow.activateWindow()

    # 将鼠标区域限制在游戏界面中
    def limit_cursor(self):
        widget_pos = self.label.mapToGlobal(self.label.rect().topLeft())
        widget_size = self.label.size()
        # 计算限制区域
        rect = QRect(widget_pos, widget_size)
        self._clip_mouse(rect)

    # 取消将鼠标区域限制在游戏界面中
    def unlimit_cursor(self):
        ctypes.windll.user32.ClipCursor(None)

    def _clip_mouse(self, rect):
        # 定义RECT结构体
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long),
                        ("top", ctypes.c_long),
                        ("right", ctypes.c_long),
                        ("bottom", ctypes.c_long)]
        # 创建RECT实例
        r = RECT(rect.left() + 4, rect.top() + 4, 
                 rect.right() - 4, rect.bottom() - 4)
        # 调用Windows API函数ClipCursor来限制光标
        ctypes.windll.user32.ClipCursor(ctypes.byref(r))


    def closeEvent_(self):
        # 主窗口关闭的回调
        self.unlimit_cursor()
        # self.score_board_manager.close()
        self.game_setting.set_value("DEFAULT/mainWinTop", str(self.mainWindow.x()))
        self.game_setting.set_value("DEFAULT/mainWinLeft", str(self.mainWindow.y()))
        self.game_setting.set_value("DEFAULT/row", str(self.row))
        self.game_setting.set_value("DEFAULT/column", str(self.column))
        self.game_setting.set_value("DEFAULT/mineNum", str(self.mineNum))
        
        if (self.row, self.column, self.mineNum) == (8, 8, 10):
            self.game_setting.set_value("BEGINNER/gamemode", str(self.gameMode))
            self.game_setting.set_value("BEGINNER/pixsize", str(self.pixSize))
        elif (self.row, self.column, self.mineNum) == (16, 16, 40):
            self.game_setting.set_value("INTERMEDIATE/gamemode", str(self.gameMode))
            self.game_setting.set_value("INTERMEDIATE/pixsize", str(self.pixSize))
        elif (self.row, self.column, self.mineNum) == (16, 30, 99):
            self.game_setting.set_value("EXPERT/gamemode", str(self.gameMode))
            self.game_setting.set_value("EXPERT/pixsize", str(self.pixSize))
        else:
            self.game_setting.set_value("CUSTOM/gamemode", str(self.gameMode))
            self.game_setting.set_value("CUSTOM/pixsize", str(self.pixSize))

        self.game_setting.sync()
        self.record_setting.sync()









