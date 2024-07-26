from PyQt5 import QtCore
from PyQt5.QtCore import QTimer, QCoreApplication, Qt
from PyQt5.QtGui import QPixmap, QKeySequence
# from PyQt5.QtWidgets import QLineEdit, QInputDialog, QShortcut
from PyQt5.QtWidgets import QApplication, QFileDialog
import gameDefinedParameter
import superGUI, gameAbout, gameSettings, gameSettingShortcuts,\
    captureScreen, mine_num_bar, videoControl, gameRecordPop
import minesweeper_master as mm
import ms_toollib as ms
import configparser
# from pathlib import Path
import time
import os
import hashlib, uuid
# from PyQt5.QtWidgets import QApplication
from country_name import country_name
import metaminesweeper_checksum

class MineSweeperGUI(superGUI.Ui_MainWindow):
    def __init__(self, MainWindow, args):
        self.mainWindow = MainWindow
        super(MineSweeperGUI, self).__init__(MainWindow, args)
        # MineSweeperGUI父类的init中读.ini、读图片、设置字体、局面初始化等

        # self.operationStream = []

        self.time_10ms: int = 0 # 已毫秒为单位的游戏时间，全局统一的
        self.showTime(self.time_10ms // 100)
        self.timer_10ms = QTimer()
        # 开了高精度反而精度降低
        # self.timer_10ms.setTimerType(Qt.PreciseTimer)
        self.timer_10ms.setInterval(10)  # 10毫秒回调一次的定时器
        self.timer_10ms.timeout.connect(self.timeCount)
        # text4 = '1'
        # self.label_info.setText(text4)
        self.mineUnFlagedNum = self.mineNum  # 没有标出的雷，显示在左上角
        self.showMineNum(self.mineUnFlagedNum)    # 在左上角画雷数

        # 绑定菜单栏事件
        self.actionnew_game.triggered.connect(self.gameRestart)
        self.actionchu_ji.triggered.connect(lambda: self.predefined_Board(1))
        self.actionzhogn_ji.triggered.connect(lambda: self.predefined_Board(2))
        self.actiongao_ji.triggered.connect(lambda: self.predefined_Board(3))
        self.actionzi_ding_yi.triggered.connect(self.action_CEvent)
        self.actiontui_chu.triggered.connect(QCoreApplication.instance().quit)
        self.actionyouxi_she_zhi.triggered.connect(self.action_NEvent)
        self.action_kuaijiejian.triggered.connect(self.action_QEvent)
        self.action_mouse.triggered.connect(self.action_mouse_setting)
        self.actiongaun_yv.triggered.connect(self.action_AEvent)
        self.actionopen.triggered.connect(self.action_OpenFile)
        self.english_action.triggered.connect(lambda: self.trans_language("en_US"))
        self.chinese_action.triggered.connect(lambda: self.trans_language("zh_CN"))
        self.polish_action.triggered.connect(lambda: self.trans_language("pl_PL"))
        self.german_action.triggered.connect(lambda: self.trans_language("de_DE"))

        config = configparser.ConfigParser()
        config.read(self.game_setting_path, encoding='utf-8')

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
            self.action_OpenFile(args[1])


        self.score_board_manager.reshow(self.label.ms_board, index_type = 1)
        self.score_board_manager.visible()
        self.trans_language()

        self.mainWindow.closeEvent_.connect(self.closeEvent_)

    @property
    def pixSize(self):
        return self._pixSize
    
    @pixSize.setter
    def pixSize(self, pixSize):
        pixSize = max(5, pixSize)
        if pixSize == self._pixSize:
            return
        self.label.set_rcp(self.row, self.column, pixSize)
        self.label.reloadCellPic(pixSize)
        for i in range(4):
            self.predefinedBoardPara[i]['pix_size'] = pixSize
        self.reimportLEDPic(pixSize)
        self.label.setMinimumSize(QtCore.QSize(pixSize * self.column + 8, pixSize * self.row + 8))
        self.label.setMaximumSize(QtCore.QSize(pixSize * self.column + 8, pixSize * self.row + 8))
        # self.label.setFixedSize(QtCore.QSize(self.pixSize*self.column + 8, self.pixSize*self.row + 8))

        self.label_2.reloadFace(pixSize)
        self.set_face(14)
        self.showMineNum(self.mineUnFlagedNum)
        self.showTime(0)
        if pixSize < self._pixSize:
            self._pixSize = pixSize
            self.minimumWindow()
        else:
            self._pixSize = pixSize


    @property
    def gameMode(self):
        return self._game_mode

    @gameMode.setter
    def gameMode(self, game_mode):
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
        elif self._game_state in ("display", "showdisplay") and\
            game_state not in ("display", "showdisplay"):
            self.timer_video.stop()
            self.ui_video_control.QWidget.close()
            self.label.paint_cursor = False
        elif self._game_state == 'study':
            self.num_bar_ui.QWidget.close()
        self._game_state = game_state

    def layMine(self, i, j):
        xx = self.row
        yy = self.column
        num = self.mineNum
        # 0，4, 5, 6, 7, 8, 9, 10代表：标准0、win74、竞速无猜5、强无猜6、
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
        # 竞速无猜、强无猜、弱无猜、准无猜、强可猜、弱可猜
        # 根据模式处理一次点击的全部流程
        # （i，j）一定是未打开状态
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
                    
                    self.game_state = 'playing'

                    if self.player_designator[:6] != "[live]":
                        self.disable_screenshot()
                    else:
                        self.enable_screenshot()

                    # 核实用的时间，防变速齿轮
                    self.start_time_unix_2 = QtCore.QDateTime.currentDateTime().\
                                                toMSecsSinceEpoch()
                    self.timer_10ms.start()
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
                if self.label.ms_board.game_board[i//self.pixSize][j//self.pixSize] == 11:
                    self.mineUnFlagedNum += 1
                    self.showMineNum(self.mineUnFlagedNum)
                elif self.label.ms_board.game_board[i//self.pixSize][j//self.pixSize] == 10:
                    self.mineUnFlagedNum -= 1
                    self.showMineNum(self.mineUnFlagedNum)
            self.label.ms_board.step('rc', (i, j))
            self.label.update()
            self.set_face(15)

    def mineAreaRightRelease(self, i, j):
        if self.game_state == 'ready' or self.game_state == 'playing' or self.game_state == 'joking':
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
        if QApplication.keyboardModifiers() == Qt.ControlModifier and self.game_state == 'ready': # 检测是否按ctrl
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
        self.label_info.setText(self.player_designator)

        # 这里有点乱
        if self.game_state == 'display' or self.game_state == 'showdisplay':
            self.setBoard_and_start(self.row, self.column, self.mineNum)
            self.label.paintPossibility = False
            self.label.set_rcp(self.row, self.column, self.pixSize)
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
        self.label_info.setText(self.player_designator)
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

        self.score_board_manager.with_namespace({
            "checksum_ok": "--"
            })


    def gameFinished(self):  # 游戏结束画残局，改状态
        self.enable_screenshot()
        if self.label.ms_board.game_board_state == 3 and self.end_then_flag:
            self.label.ms_board.win_then_flag_all_mine()
        elif self.label.ms_board.game_board_state == 4:
            self.label.ms_board.loss_then_open_all_mine()
        # 刷新游戏局面
        self.label.update()
        # 刷新计数器数值
        self.timeCount()
        self.score_board_manager.show(self.label.ms_board, index_type = 2)

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
            self.save_evf_file()



        self.gameFinished()


        # 尝试弹窗，没有破纪录则不弹
        if self.auto_notification and self.is_fair():
            self.try_record_pop()

    def checksum_module_ok(self):
        # 检查校验和模块的签名
        # 调试的时候不会自动存录像，除非将此处改为return True
        return True
        # return hashlib.sha256(bytes(metaminesweeper_checksum.get_self_key())).hexdigest() ==\
        #     '590028493bb58a25ffc76e2e2ad490df839a1f449435c35789d3119ca69e5d4f'

    def save_evf_file(self):
        # 搜集本局各种信息，存成evf文件
        # 调试的时候不会自动存录像，见checksum_module_ok
        self.label.ms_board.use_question = False # 禁用问号是共识
        self.label.ms_board.use_cursor_pos_lim = False # 目前还不能限制
        self.label.ms_board.use_auto_replay = self.auto_replay > 0
        
        self.label.ms_board.is_fair = self.is_fair()
        self.label.ms_board.is_offical = self.is_official()

        self.label_info.setText(str(self.is_fair()) + str(self.is_official()) + self.game_state)

        # if self.label.ms_board.is_fair and self.label.ms_board.is_offical:
        #     self.label.ms_board.checksum = metaminesweeper_checksum.get_checksum()
        # self.label.ms_board.mode = self.gameMode
        self.label.ms_board.software = "元3.1.8".encode( "UTF-8" )
        self.label.ms_board.player_designator = self.player_designator.encode( "UTF-8" )
        self.label.ms_board.race_designator = self.race_designator.encode( "UTF-8" )
        self.label.ms_board.country = self.country.encode( "UTF-8" )
        self.label.ms_board.device_uuid = hashlib.md5(bytes(str(uuid.getnode()).encode())).hexdigest().encode( "UTF-8" )
        self.label.ms_board.uniqueness_designator = "".encode( "UTF-8" ) # 暂时不能填

        if not os.path.exists(self.replay_path):
            os.mkdir(self.replay_path)
        self.label.ms_board.generate_evf_v3_raw_data()
        # 补上校验值
        checksum = self.checksum_guard.get_checksum(self.label.ms_board.raw_data[:-1])
        self.label.ms_board.checksum = checksum


        if (self.row, self.column, self.mineNum) == (8, 8, 10):
            filename_level = "b_"
        elif (self.row, self.column, self.mineNum) == (16, 16, 40):
            filename_level = "i_"
        elif (self.row, self.column, self.mineNum) == (16, 30, 99):
            filename_level = "e_"
        else:
            filename_level = "c_"
        self.label.ms_board.\
            save_to_evf_file(self.replay_path + '\\' + filename_level +\
                             str(self.gameMode) + '_' +\
                                 f'{self.label.ms_board.rtime:.3f}' +\
                                     '_3BV=' + f'{self.label.ms_board.bbbv}' +\
                                         '_3BVs=' + f'{self.label.ms_board.bbbv_s:.3f}' +\
                                             '_' + self.player_designator)




    def gameFailed(self): # 失败后改脸和状态变量
        self.timer_10ms.stop()
        self.score_board_manager.editing_row = -1

        if self.game_state == 'joking':
            self.game_state = 'jofail'
        else:
            self.game_state = 'fail'

        self.set_face(16)

        if self.label.ms_board.bbbv_solved / self.label.ms_board.bbbv * 100 <= self.auto_replay:
            self.gameRestart()
        else:
            self.gameFinished()

    def try_record_pop(self):
        # 尝试弹窗，或不弹窗
        # 不显示的记录的序号
        del_items = []
        b = self.label.ms_board
        if b.level == 6:
            # 自定义不弹窗
            return
        if b.level == 3:
            record_key = "B"
        elif b.level == 4:
            record_key = "I"
        elif b.level == 5:
            record_key = "E"
        else:
            raise RuntimeError('没有定义的难度代码')

        _translate = QtCore.QCoreApplication.translate

        if self.gameMode == 0:
            if b.right == 0:
                record_key += "NF"
                mode_text = _translate("Form", "未标雷（标准）")
            else:
                record_key += "FLAG"
                mode_text = _translate("Form", "标准")
        elif self.gameMode == 4:
            record_key += "WIN7"
            mode_text = _translate("Form", "Win7")
        elif self.gameMode == 5:
            record_key += "CS"
            mode_text = _translate("Form", "竞速无猜")
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
            raise RuntimeError('没有定义的模式代码')

        if b.rtime < self.record[record_key]["rtime"]:
            self.record[record_key]["rtime"] = b.rtime
        else:
            del_items.append(1)
        if b.bbbv_s > self.record[record_key]["bbbv_s"]:
            self.record[record_key]["bbbv_s"] = b.bbbv_s
        else:
            del_items.append(3)
        if b.stnb > self.record[record_key]["stnb"]:
            self.record[record_key]["stnb"] = b.stnb
        else:
            del_items.append(5)
        if b.ioe > self.record[record_key]["ioe"]:
            self.record[record_key]["ioe"] = b.ioe
        else:
            del_items.append(7)
        if b.path < self.record[record_key]["path"]:
            self.record[record_key]["path"] = b.path
        else:
            del_items.append(9)
        if b.rqp < self.record[record_key]["rqp"]:
            self.record[record_key]["rqp"] = b.rqp
        else:
            del_items.append(11)

        if self.gameMode == 0:
            if b.level == 3:
                if b.rtime < self.record["BEGINNER"][str(b.bbbv)]:
                    self.record["BEGINNER"][str(b.bbbv)] = b.rtime
                    del_items += [14, 15]
                else:
                    del_items += [13, 14, 15]
            elif b.level == 4:
                if b.rtime < self.record["INTERMEDIATE"][str(b.bbbv)]:
                    self.record["INTERMEDIATE"][str(b.bbbv)] = b.rtime
                    del_items += [13, 15]
                else:
                    del_items += [13, 14, 15]
            elif b.level == 5:
                if b.rtime < self.record["EXPERT"][str(b.bbbv)]:
                    self.record["EXPERT"][str(b.bbbv)] = b.rtime
                    del_items += [13, 14]
                else:
                    del_items += [13, 14, 15]
            else:
                raise RuntimeError('没有定义的难度代码')
        else:
            del_items += [13, 14, 15]

        if len(del_items) < 9:
            ui = gameRecordPop.ui_Form(self.r_path, del_items, b.bbbv)
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
        self.pixSize = self.predefinedBoardPara[k]['pix_size']
        self.label.ms_board.reset(row, column, self.pixSize)
        self.gameMode = self.predefinedBoardPara[k]['game_mode']
        self.score_board_manager.with_namespace({
            "mode": mm.trans_game_mode(self.gameMode),
            })
        self.score_board_manager.show(self.label.ms_board, index_type=1)
        self.board_constraint = self.predefinedBoardPara[k]['board_constraint']
        self.attempt_times_limit = self.predefinedBoardPara[k]['attempt_times_limit']
        self.importLEDPic(self.pixSize)
        self.label.importCellPic(self.pixSize)
        self.label_2.reloadFace(self.pixSize)
        self.setBoard_and_start(row,
                                column,
                                self.predefinedBoardPara[k]['mine_num'])
        # self.refreshSettingsDefault()

    def action_CEvent(self):
        # 点击菜单栏的自定义后回调
        self.actionChecked('C')
        ui = gameDefinedParameter.ui_Form(self.r_path, self.row, self.column, self.mineNum)
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
            self.board_constraint = self.predefinedBoardPara[1]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[1]['attempt_times_limit']
        elif (row, column, mineNum) == (16, 16, 40):
            self.actionChecked('I')
            self.board_constraint = self.predefinedBoardPara[2]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[2]['attempt_times_limit']
        elif (row, column, mineNum) == (16, 30, 99):
            self.actionChecked('E')
            self.board_constraint = self.predefinedBoardPara[3]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[3]['attempt_times_limit']
        else:
            self.actionChecked('C')
            self.board_constraint = self.predefinedBoardPara[0]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[0]['attempt_times_limit']

    def setBoard_and_start(self, row, column, mineNum):
        # 把局面设置成(row, column, mineNum)，把3BV的限制设置成min3BV, max3BV
        if self.game_state == 'display' or self.game_state == 'showdisplay':
            self.label.paintPossibility = False
            # self.label.paint_cursor = False
            # self.timer_video.stop()
        if (self.row, self.column, self.mineNum) != (row, column, mineNum):
            self.setBoard(row, column, mineNum)
            self.gameStart()
        else:
            self.gameRestart()


    def action_NEvent(self):
        # 游戏设置
        self.actionChecked('N')
        ui = gameSettings.ui_Form(self.game_setting_path, self.r_path, self.pixSize)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()
        if ui.alter:
            self.gameMode = ui.gameMode

            self.pixSize = ui.pixSize
            for i in range(4):
                self.predefinedBoardPara[i]['pix_size'] = ui.pixSize
            if not ui.allow_auto_replay:
                self.auto_replay = -1
            else:
                self.auto_replay = ui.auto_replay
            self.end_then_flag = ui.end_then_flag
            self.auto_notification = ui.auto_notification
            self.player_designator = ui.player_designator
            self.label_info.setText(self.player_designator)
            self.race_designator = ui.race_designator
            self.country = ui.country
            self.set_country_flag()
            self.autosave_video = ui.autosave_video
            self.filter_forever = ui.filter_forever
            self.board_constraint = ui.board_constraint
            self.attempt_times_limit = ui.attempt_times_limit
            self.end_then_flag = ui.end_then_flag # 游戏结束后自动标雷

            self.importLEDPic(self.pixSize)
            self.label.importCellPic(self.pixSize)
            self.label_2.reloadFace(self.pixSize)
            self.gameStart()
            self.mainWindow.setWindowOpacity(ui.transparency / 100)
            self.score_board_manager.with_namespace({
                "race_designator": ui.race_designator,
                "mode": mm.trans_game_mode(ui.gameMode),
                })
            self.score_board_manager.show(self.label.ms_board, index_type=1)

    def action_QEvent(self):
        # 快捷键设置的回调
        self.actionChecked('Q')
        ui = gameSettingShortcuts.myGameSettingShortcuts(self.game_setting_path, self.ico_path, self.r_path)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()
        if ui.alter:
            self.readPredefinedBoardPara()

    def action_mouse_setting(self):
        # 打开鼠标设置的第三个菜单
        os.system("rundll32.exe shell32.dll,Control_RunDLL main.cpl,,2")

    def action_AEvent(self):
        # 关于
        self.actionChecked('A')
        ui = gameAbout.ui_Form(self.r_path)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()

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

        self.num_bar_ui = mine_num_bar.ui_Form(ans[1], self.pixSize * self.row)
        self.num_bar_ui.QWidget.barSetMineNum.connect(self.showMineNum)
        self.num_bar_ui.QWidget.barSetMineNumCalPoss.connect(self.render_poss_on_board)
        self.num_bar_ui.setSignal()

        self.mainWindow.closeEvent_.connect(self.num_bar_ui.QWidget.close)

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
                self.label_info.setText(self.player_designator)
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
        conf = configparser.ConfigParser()
        conf.read(self.game_setting_path, encoding='utf-8')
        conf.set("DEFAULT", "gamemode", str(self.gameMode))
        conf.set("DEFAULT", "pixsize", str(self.pixSize))
        conf.set("DEFAULT", "row", str(self.row))
        conf.set("DEFAULT", "column", str(self.column))
        conf.set("DEFAULT", "minenum", str(self.mineNum))
        conf.write(open(self.game_setting_path, "w", encoding='utf-8'))

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

        if openfile_name[-3:] == "avf":
            video = ms.AvfVideo(openfile_name)
        elif openfile_name[-3:] == "rmv":
            video = ms.RmvVideo(openfile_name)
        elif openfile_name[-3:] == "evf":
            video = ms.EvfVideo(openfile_name)
        elif openfile_name[-3:] == "mvf":
            video = ms.MvfVideo(openfile_name)
        else:
            return

        if self.game_state == 'display':
            self.ui_video_control.QWidget.close()
        self.game_state = 'display'

        video.parse_video()
        video.analyse()
        # 检查checksum
        if isinstance(video, ms.EvfVideo):
            self.score_board_manager.with_namespace({
                "checksum_ok": self.checksum_guard.valid_checksum(video.raw_data[:-33], video.checksum),
                })
        video.analyse_for_features(["high_risk_guess", "jump_judge", "needless_guess",
                                    "mouse_trace", "vision_transfer", "survive_poss"])

        # 组织录像评论
        event_len = video.events_len
        comments = []
        for event_id in range(event_len):
            time = video.events_time(event_id)
            comment = video.events_comments(event_id)
            if comment:
                comments.append((time, [i.split(': ') for i in comment.split(';')[:-1]]))
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
        self.ui_video_control = videoControl.ui_Form(self.r_path, video, comments)
        self.mainWindow.closeEvent_.connect(self.ui_video_control.QWidget.close)
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
        self.timer_video.start(10)

        video.video_playing_pix_size = self.label.pixSize
        self.label.ms_board = video
        self.label_info.setText(bytes(self.label.ms_board.player_designator).decode())

    def video_playing_step(self):
        # 播放录像时定时器的回调
        self.label.ms_board.current_time = self.video_time
        if self.video_time >= self.video_stop_time:
            self.timer_video.stop()
            self.video_playing = False
        self.label.update()
        self.score_board_manager.show(self.label.ms_board, index_type = 2)
        self.video_time += self.video_time_step
        self.ui_video_control.horizontalSlider_time.blockSignals(True)
        self.ui_video_control.horizontalSlider_time.setValue(int(self.video_time * 100))
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

    def video_set_time(self, time):
        # 把录像定位到某一个时刻。是拖动进度条的回调
        self.video_time = time / 100
        self.label.ms_board.current_time = self.video_time
        self.label.update()
        self.score_board_manager.show(self.label.ms_board, index_type = 2)

    def video_set_a_time(self, time):
        # 把录像定位到某一段时间，默认前后一秒，自动播放。是点录像事件的回调
        self.video_time = (time - 100) / 100
        self.video_stop_time = (time + 100) / 100  # 大了也没关系，ms_toollib自动处理
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

    # def cell_is_in_board(self, i, j):
        # 点在局面内，单位是格不是像素
        # return i >= 0 and i < self.row and j >= 0 and j < self.column

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
        if self.score_board_manager.ui.QWidget.isVisible():
            self.score_board_manager.invisible()
        else:
            self.score_board_manager.visible()


    def closeEvent_(self):
        # 主窗口关闭的回调
        self.score_board_manager.close()
        conf = configparser.ConfigParser()
        conf.read(self.game_setting_path, encoding='utf-8')
        conf.set("DEFAULT", "gamemode", str(self.gameMode))
        conf.set("DEFAULT", "mainWinTop", str(self.mainWindow.x()))
        conf.set("DEFAULT", "mainWinLeft", str(self.mainWindow.y()))
        conf.set("DEFAULT", "pixsize", str(self.pixSize))
        conf.set("DEFAULT", "row", str(self.row))
        conf.set("DEFAULT", "column", str(self.column))
        conf.set("DEFAULT", "minenum", str(self.mineNum))
        conf.write(open(self.game_setting_path, "w", encoding='utf-8'))

        conf = configparser.ConfigParser()
        conf.read(self.record_path, encoding='utf-8')
        for key_name in self.record_key_name_list:
            conf[key_name] = self.record[key_name]
        # conf["BFLAG"] = self.record["BFLAG"]
        # conf["BNF"] = self.record["BNF"]
        # conf["IFLAG"] = self.record["IFLAG"]
        # conf["INF"] = self.record["INF"]
        # conf["EFLAG"] = self.record["EFLAG"]
        # conf["ENF"] = self.record["ENF"]
        # conf["BEGINNER"] = self.record["BEGINNER"]
        # conf["INTERMEDIATE"] = self.record["INTERMEDIATE"]
        # conf["EXPERT"] = self.record["EXPERT"]
        with open(self.record_path, 'w') as configfile:
            conf.write(configfile)  # 将对象写入文件








