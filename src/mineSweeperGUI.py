import base64
from PyQt5 import QtCore
from PyQt5.QtCore import QTimer, QCoreApplication, Qt, QRect, QUrl
from PyQt5.QtGui import QPixmap, QDesktopServices
import msgspec
# from PyQt5.QtWidgets import QLineEdit, QInputDialog, QShortcut
# from PyQt5.QtWidgets import QApplication, QFileDialog, QWidget
import gameDefinedParameter
import superGUI
import gameAbout
import gameSettings
import gameSettingShortcuts
import captureScreen
import mine_num_bar
import gameRecordPop
from CheckUpdateGui import CheckUpdateGui
from githubApi import GitHub, SourceManager
import win32con
import win32gui
import utils
import ms_toollib as ms
# import configparser
# from pathlib import Path
# import time
import os
import ctypes
import hashlib
import uuid
# from PyQt5.QtWidgets import QApplication
from country_name import country_name
import metaminesweeper_checksum
from mainWindowGUI import MainWindow
from datetime import datetime
from mineSweeperVideoPlayer import MineSweeperVideoPlayer
from pluginDialog import PluginManagerUI
from mp_plugins import PluginManager, PluginContext
from mp_plugins.events import GameEndEvent


class MineSweeperGUI(MineSweeperVideoPlayer):
    def __init__(self, MainWindow: MainWindow, args):
        self.mainWindow = MainWindow
        self.checksum_guard = metaminesweeper_checksum.ChecksumGuard()
        super(MineSweeperGUI, self).__init__(MainWindow, args)

        self.time_10ms: int = 0  # 已毫秒为单位的游戏时间，全局统一的
        self.showTime(self.time_10ms // 100)

        self.timer_10ms = QTimer()
        self.timer_10ms.setInterval(10)  # 10毫秒回调一次的定时器
        self.timer_10ms.timeout.connect(self.timeCount)
        # 开了高精度反而精度降低
        self.timer_10ms.setTimerType(Qt.PreciseTimer)
        self.mineUnFlagedNum = self.minenum  # 没有标出的雷，显示在左上角
        self.showMineNum(self.mineUnFlagedNum)    # 在左上角画雷数

        # 绑定菜单栏事件
        self.actionnew_game.triggered.connect(self.gameRestart)
        self.actionchu_ji.triggered.connect(lambda: self.predefined_Board(1))
        self.actionzhogn_ji.triggered.connect(lambda: self.predefined_Board(2))
        self.actiongao_ji.triggered.connect(lambda: self.predefined_Board(3))
        self.actionzi_ding_yi.triggered.connect(self.action_CEvent)

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
        self.actionchajian.triggered.connect(self.action_OpenPluginDialog)
        self.english_action.triggered.connect(
            lambda: self.trans_language("en_US"))
        self.chinese_action.triggered.connect(
            lambda: self.trans_language("zh_CN"))
        self.polish_action.triggered.connect(
            lambda: self.trans_language("pl_PL"))
        self.german_action.triggered.connect(
            lambda: self.trans_language("de_DE"))

        # 查看菜单
        self.action_open_replay.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.setting_path / 'replay'))))
        self.action_open_ini.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.setting_path))))

        self.frameShortcut1.activated.connect(lambda: self.predefined_Board(1))
        self.frameShortcut2.activated.connect(lambda: self.predefined_Board(2))
        self.frameShortcut3.activated.connect(lambda: self.predefined_Board(3))
        self.frameShortcut4.activated.connect(self.gameRestart)
        self.frameShortcut5.activated.connect(lambda: self.predefined_Board(4))
        self.frameShortcut6.activated.connect(lambda: self.predefined_Board(5))
        self.frameShortcut7.activated.connect(lambda: self.predefined_Board(6))
        self.frameShortcut8.activated.connect(self.showScores)
        self.frameShortcut9.activated.connect(self.screenShot)
        self.shortcut_hidden_score_board.activated.connect(
            self.hidden_score_board)

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
            "is_official": "--",
            "is_fair": "--",
            "row": self.row,
            "column": self.column,
            "minenum": self.minenum,
        })
        self.score_board_manager.reshow(self.label.ms_board, index_type=1)
        self.score_board_manager.visible()

        self.mainWindow.closeEvent_.connect(self.closeEvent_)
        self.mainWindow.dropFileSignal.connect(self.action_OpenFile)

        # 播放录像时，记录上一个鼠标状态用。
        # 这是一个补丁，因为工具箱里只有UpDown和UpDownNotFlag，
        # 也有DownUpAfterChording，但是没有UpDownAfterChording
        # 因此同样是UpDown，在数字和空上双击黄脸应该张嘴，但是双击后抬起时则
        # 不应该张嘴。工具箱缺少两种鼠标状态的区分，导致黄脸无法准确动作。
        self.last_mouse_state_video_playing_step = 1
        # evfs模块
        self.evfs = ms.Evfs()
        # 不带后缀、有绝对路径的、不含最后次数的文件名
        # C:/path/zhangsan_20251111_190114_
        self.old_evfs_filename = ""

    @property
    def pixSize(self):
        return self._pixSize

    @pixSize.setter
    def pixSize(self, pixSize):
        '''
        修改pixSize后，要调整ui尺寸，导致内部游戏状态变为"ready"
        '''
        pixSize = max(5, pixSize)
        pixSize = min(255, pixSize)
        pixSize = min(32767//self.column, pixSize)
        pixSize = min(32767//self.row, pixSize)
        if hasattr(self, "_pixSize") and pixSize == self._pixSize:
            return
        self.label.set_rcp(self.row, self.column, pixSize)
        self.label.reloadCellPic(pixSize)
        if (self.row, self.column, self.minenum) == (8, 8, 10):
            self.predefinedBoardPara[1]['pixsize'] = pixSize
        elif (self.row, self.column, self.minenum) == (16, 16, 40):
            self.predefinedBoardPara[2]['pixsize'] = pixSize
        elif (self.row, self.column, self.minenum) == (16, 30, 99):
            self.predefinedBoardPara[3]['pixsize'] = pixSize
        elif (self.row, self.column, self.minenum) == (self.predefinedBoardPara[4]['row'],
                                                       self.predefinedBoardPara[4]['column'],
                                                       self.predefinedBoardPara[4]['mine_num']):
            self.predefinedBoardPara[4]['pixsize'] = pixSize
        elif (self.row, self.column, self.minenum) == (self.predefinedBoardPara[5]['row'],
                                                       self.predefinedBoardPara[5]['column'],
                                                       self.predefinedBoardPara[5]['mine_num']):
            self.predefinedBoardPara[5]['pixsize'] = pixSize
        elif (self.row, self.column, self.minenum) == (self.predefinedBoardPara[6]['row'],
                                                       self.predefinedBoardPara[6]['column'],
                                                       self.predefinedBoardPara[6]['mine_num']):
            self.predefinedBoardPara[6]['pixsize'] = pixSize
        else:
            self.predefinedBoardPara[0]['pixsize'] = pixSize

        # self.label.setMinimumSize(QtCore.QSize(
        #     pixSize * self.column + 8, pixSize * self.row + 8))
        # self.label.setMaximumSize(QtCore.QSize(
        #     pixSize * self.column + 8, pixSize * self.row + 8))
        # self.label.setFixedSize(QtCore.QSize(self.pixSize*self.column + 8, self.pixSize*self.row + 8))

        self.reimportLEDPic(pixSize)  # 重新导入图片，无磁盘io
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

    # 游戏状态的状态转移
    # 只有ready有可能发生ready->ready
    @game_state.setter
    def game_state(self, game_state: str):
        # print(self._game_state, " -> " ,game_state)
        match self._game_state:
            case "playing":
                self.try_append_evfs(game_state)
                if game_state not in ("playing", "show", "joking"):
                    self.timer_10ms.stop()
                    self.unlimit_cursor()
                # if game_state in ("study", "joking", "jowin", "jofail", "show"):
            case "joking" | "show":
                if game_state not in ("playing", "show", "joking"):
                    self.timer_10ms.stop()
                    self.unlimit_cursor()
            case "display" | "showdisplay":
                if game_state not in ("display", "showdisplay"):
                    self.timer_video.stop()
                    self.ui_video_control.QWidget.close()
                    self.label.paint_cursor = False
                    self.label.paintProbability = False
                    self.set_country_flag()
                    self.score_board_manager.with_namespace({
                        "is_official": "--",
                        "is_fair": "--",
                        "mode": self.gameMode,
                        "row": self.row,
                        "column": self.column,
                        "minenum": self.minenum,
                    })
                    self.score_board_manager.show(
                        self.label.ms_board, index_type=1)
            case "study":
                # 这两个值涉及画局面时，画的是游戏局面还是虚拟的局面
                self.label.paint_cursor = False
                self.label.paintProbability = False
                self.num_bar_ui.QWidget.close()
        self._game_state = game_state

    @property
    def row(self):
        return self._row

    @row.setter
    def row(self, row):
        self.score_board_manager.with_namespace({
            "row": row,
        })
        self._row = row

    @property
    def column(self):
        return self._column

    @column.setter
    def column(self, column):
        self.score_board_manager.with_namespace({
            "column": column,
        })
        self._column = column

    @property
    def minenum(self):
        return self._minenum

    @minenum.setter
    def minenum(self, minenum):
        self.score_board_manager.with_namespace({
            "minenum": minenum,
        })
        self._minenum = minenum

    def layMine(self, i, j):

        xx = self.row
        yy = self.column
        num = self.minenum
        # 0，4, 5, 6, 7, 8, 9, 10代表：标准0、win74、经典无猜5、强无猜6、
        # 弱无猜7、准无猜8、强可猜9、弱可猜10
        if self.gameMode == 5 or self.gameMode == 6 or self.gameMode == 9:
            # 根据模式生成局面
            Board, _ = utils.laymine_solvable(self.board_constraint,
                                              self.attempt_times_limit, (xx, yy, num, i, j))
        elif self.gameMode == 0 or self.gameMode == 7 or self.gameMode == 8 or self.gameMode == 10:
            Board, _ = utils.laymine(self.board_constraint,
                                     self.attempt_times_limit, (xx, yy, num, i, j))
        elif self.gameMode == 4:
            Board, _ = utils.laymine_op(self.board_constraint,
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
            # 防CE作弊。
            # 假如标识不以"[lag]"开头，则误差大于100ms时重开。
            # 假如标识以"[lag]"开头，则误差大于1000ms、或误差大于50ms且大于10%时重开。
            gap_ms = abs(t * 1000 - since_time_unix_2)
            if gap_ms > 100 and\
                    (self.game_state == "playing" or self.game_state == "joking"):
                if self.player_identifier[:5] != "[lag]":
                    self.gameRestart()
                elif gap_ms > 1000 or gap_ms > 50 and\
                        gap_ms / min(t * 1000, since_time_unix_2) > 0.1:
                    self.gameRestart()

        if self.time_10ms % 1 == 0:
            # 计数器用100Hz的刷新率
            # self.score_board_manager.with_namespace({
            #     "rtime": self.time_ms / 1000,
            #     })
            self.score_board_manager.show(self.label.ms_board, index_type=1)

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
            code = ms.is_guess_while_needless(
                self.label.ms_board.game_board, (i, j))
            if code == 3:
                board = self.label.ms_board.board.into_vec_vec()
                board[i][j] = -1
                self.label.ms_board.board = board
            elif code == 2:
                board, flag = utils.enumerateChangeBoard(self.label.ms_board.board,
                                                         self.label.ms_board.game_board, [(i, j)])
                self.label.ms_board.board = board
            return
        elif self.gameMode == 8:
            code = ms.is_guess_while_needless(
                self.label.ms_board.game_board, (i, j))
            if code == 2:
                board, flag = utils.enumerateChangeBoard(self.label.ms_board.board,
                                                         self.label.ms_board.game_board, [(i, j)])
                self.label.ms_board.board = board
            return
        elif self.gameMode == 9 or self.gameMode == 10:
            if self.label.ms_board.board[i][j] == -1:
                # 可猜调整的核心逻辑
                board, flag = utils.enumerateChangeBoard(self.label.ms_board.board,
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
        not_mine_round = []  # 没有标雷，且非雷
        is_mine_round = []  # 没有标雷，且是雷
        flag_not_mine_round = []  # 标雷，且非雷
        flag_is_mine_round = []  # 标雷，且是雷
        for ii in range(max(0, i-1), min(self.row, i+2)):
            for jj in range(max(0, j-1), min(self.column, j+2)):
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
                code = ms.is_guess_while_needless(
                    self.label.ms_board.game_board, (x, y))
                if code == 3:
                    must_guess = False
                    break
            if must_guess:
                board, flag = utils.enumerateChangeBoard(board,
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
                code = ms.is_guess_while_needless(
                    self.label.ms_board.game_board, (x, y))
                if code == 3:
                    must_guess = False
                    break
            if must_guess:
                board, flag = utils.enumerateChangeBoard(board,
                                                         self.label.ms_board.game_board,
                                                         not_mine_round + is_mine_round)
                self.label.ms_board.board = board
        elif self.gameMode == 9 or self.gameMode == 10:
            board, flag = utils.enumerateChangeBoard(board,
                                                     self.label.ms_board.game_board,
                                                     not_mine_round + is_mine_round)
            self.label.ms_board.board = board

    def mineNumWheel(self, i):
        '''
        在雷上滚轮，调雷数
        '''
        if self.game_state == 'ready':
            if i > 0:
                if self.minenum < self.row * self.column - 1:
                    self.minenum += 1
                    self.mineUnFlagedNum += 1
            elif i < 0:
                if self.minenum > 1:
                    self.minenum -= 1
                    self.mineUnFlagedNum -= 1
            self.showMineNum(self.mineUnFlagedNum)
            self.score_board_manager.show(self.label.ms_board, index_type=1)
            # self.timer_mine_num = QTimer()
            # self.timer_mine_num.timeout.connect(self.refreshSettingsDefault)
            # self.timer_mine_num.setSingleShot(True)
            # self.timer_mine_num.start(3000)

    def gameStart(self):
        # 画界面，但是不埋雷。等价于点脸、f2、设置确定后的效果
        self.mineUnFlagedNum = self.minenum  # 没有标出的雷，显示在左上角
        self.showMineNum(self.mineUnFlagedNum)    # 在左上角画雷数
        self.set_face(14)
        self.time_10ms = 0
        self.showTime(self.time_10ms)
        self.timer_10ms.stop()
        self.score_board_manager.editing_row = -1

        # self.label.paintProbability = False
        self.label_info.setText(self.player_identifier)

        # 这里有点乱
        # self.label.set_rcp(self.row, self.column, self.pixSize)
        self.game_state = 'ready'
        self.label.ms_board.reset(self.row, self.column, self.pixSize)
        self.label.reloadCellPic(self.pixSize)
        self.label_2.reloadFace(self.pixSize)

        self.minimumWindow()

    # 点击脸时调用，或尺寸不变时重开
    def gameRestart(self, e=None):  # 画界面，但是不埋雷，改数据而不是重新生成label
        if e:
            # 点脸周围时，会传入一个e参数
            if not (self.MinenumTimeWigdet.width() >= e.localPos().x() >= 0 and 0 <= e.localPos().y() <= self.MinenumTimeWigdet.height()):
                return
        # 此时self.label.ms_board是utils.abstract_game_board的实例
        if self.game_state == 'display' or self.game_state == 'showdisplay':
            self.label.ms_board = ms.BaseVideo(
                [[0] * self.column for _ in range(self.row)], self.pixSize)
            self.label.ms_board.mode = self.gameMode
        elif self.game_state == 'study':
            self.score_board_manager.visible()
            self.label.ms_board = ms.BaseVideo(
                [[0] * self.column for _ in range(self.row)], self.pixSize)
            self.label.ms_board.mode = self.gameMode
        self.label_info.setText(self.player_identifier)
        self.game_state = 'ready'
        self.enable_screenshot()

        self.time_10ms = 0
        self.showTime(self.time_10ms)
        self.mineUnFlagedNum = self.minenum
        self.showMineNum(self.mineUnFlagedNum)
        self.set_face(14)

        self.timer_10ms.stop()
        self.score_board_manager.editing_row = -1
        self.label.ms_board.reset(self.row, self.column, self.pixSize)
        self.label.update()

        # self.label.paintProbability = False
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
            "is_fair": self.is_fair(),
            # "row": self.row,
            # "column": self.column,
            # "minenum": self.minenum,
        })

        self.score_board_manager.show(self.label.ms_board, index_type=2)
        self.enable_screenshot()
        self.unlimit_cursor()
        ms_board = self.label.ms_board
        status = utils.GameBoardState(ms_board.game_board_state)
        if status == utils.GameBoardState.Win:
            self.dump_evf_file_data()
            event = GameEndEvent()
            data = msgspec.structs.asdict(event)
            for key in data:
                if hasattr(ms_board, key):
                    if key == "raw_data":
                        data[key] = base64.b64encode(
                            ms_board.raw_data).decode("utf-8")
                    data[key] = getattr(ms_board, key)
            event = GameEndEvent(**data)
            PluginManager.instance().send_event(event, response_count=0)

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
        return True
        # return hashlib.sha256(bytes(metaminesweeper_checksum.get_self_key())).hexdigest() ==\
        #     '590028493bb58a25ffc76e2e2ad490df839a1f449435c35789d3119ca69e5d4f'

    # 搜集数据，生成evf文件的二进制数据，但是不保存
    def dump_evf_file_data(self):
        if isinstance(self.label.ms_board, ms.BaseVideo):
            if not self.label.ms_board.raw_data:
                self.label.ms_board.use_question = False  # 禁用问号是共识
                self.label.ms_board.use_cursor_pos_lim = self.cursor_limit
                self.label.ms_board.use_auto_replay = self.auto_replay > 0

                self.label.ms_board.is_fair = self.is_fair()
                self.label.ms_board.is_official = self.is_official()

                self.label.ms_board.software = superGUI.version
                self.label.ms_board.mode = self.gameMode
                self.label.ms_board.player_identifier = self.player_identifier
                self.label.ms_board.race_identifier = self.race_identifier
                self.label.ms_board.uniqueness_identifier = self.unique_identifier
                self.label.ms_board.country = "XX" if not self.country else\
                    country_name[self.country].upper()
                self.label.ms_board.device_uuid = hashlib.md5(
                    bytes(str(uuid.getnode()).encode())).hexdigest().encode("UTF-8")

                self.label.ms_board.generate_evf_v4_raw_data()
                # 补上校验值
                checksum = self.checksum_guard.get_checksum(
                    self.label.ms_board.raw_data[:-2])
                self.label.ms_board.checksum = checksum
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
            # rmv的国家是用户手动输入的，工具箱无法自动解析两位字母缩写
            # 在元扫雷端解析完，传如工具箱
            country = self.label.ms_board.country
            if not country:
                country = "XX"
            elif len(country) == 2 and country.isalpha() and country.isascii():
                file_path = self.r_path.with_name('media') / (country.lower() + ".svg")
                if os.path.exists(file_path):
                    country = country.upper()
            elif country in country_name:
                country = country_name[country].upper()
            elif c := country.capitalize() in country_name:
                country = country_name[c].upper()
            else:
                country = "XX"
            self.label.ms_board.country = country
            self.label.ms_board.generate_evf_v4_raw_data()
            return

    # 将evf数据存成evf文件
    # 调试的时候不会自动存录像，见checksum_module_ok
    # 菜单保存的回调。以及游戏结束自动保存。
    def save_evf_file(self):
        if not os.path.exists(self.replay_path):
            os.mkdir(self.replay_path)

        self.label.ms_board.save_to_evf_file(self.cal_evf_filename())

    # 拼接evf录像的文件名，无后缀
    def cal_evf_filename(self, absolute=True) -> str:
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
        if absolute:
            file_name = self.replay_path + '\\'
        else:
            file_name = ""
        file_name += filename_level +\
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
        return file_name

    # 保存evfs文件。先保存后一个文件，再删除前一个文件。
    def save_evfs_file(self):
        # 文件名包含秒为单位的时间戳，理论上不会重复
        # 即使重复，会变为文件名+(2)
        if self.old_evfs_filename:
            file_name = self.old_evfs_filename + str(self.evfs.len())
            self.evfs.save_evfs_file(file_name)
            old_evfs_filename = self.old_evfs_filename + \
                str(self.evfs.len() - 1) + ".evfs"
            if os.path.exists(old_evfs_filename):
                # 进一步确认是文件而不是目录
                if os.path.isfile(old_evfs_filename):
                    os.remove(old_evfs_filename)
        else:
            now = datetime.now()
            date_str = now.strftime("_%Y%m%d_%H%M%S_")
            file_name = self.replay_path + '\\' +\
                self.label.ms_board.player_identifier + date_str
            self.evfs.save_evfs_file(file_name + "1")
            self.old_evfs_filename = file_name

    def gameFailed(self):  # 失败后改脸和状态变量
        self.timer_10ms.stop()
        self.score_board_manager.editing_row = -1

        # “自动重开比例”，大于等于该比例时，不自动重开。负数表示禁用。0相当于禁用，但可以编辑。
        if self.label.ms_board.bbbv_solved / self.label.ms_board.bbbv * 100 < self.auto_replay:
            self.gameRestart()
        else:
            if self.game_state == 'joking':
                self.game_state = 'jofail'
            else:
                self.game_state = 'fail'
            self.set_face(16)
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
                    self.record_setting.set_value(
                        f"BEGINNER/{b.bbbv}", b.rtime)
                    del_items += [14, 15]
                else:
                    del_items += [13, 14, 15]
            elif b.level == 4:
                if b.rtime < self.record_setting.value(f"INTERMEDIATE/{b.bbbv}", None, float):
                    self.record_setting.set_value(
                        f"INTERMEDIATE/{b.bbbv}", b.rtime)
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
            ui = gameRecordPop.ui_Form(
                self.r_path, del_items, b.bbbv, nf_items, self.mainWindow)
            ui.Dialog.setModal(True)
            ui.label_16.setText(mode_text)
            ui.Dialog.show()
            ui.Dialog.exec_()

    # 根据条件是否满足，尝试追加evfs文件
    # 当且仅当game_state发生变化，且旧状态为"playing"时调用（即使点一下就获胜也会经过"playing"）
    # 加入evfs是空的，且当前游戏状态不是"win"，则不追加
    def try_append_evfs(self, new_game_state):
        # 只有开启了自动保存evfs，才会保存。也要防止通过关闭这个选项，逃避自动记录重开
        if not self.autosave_video_set:
            self.evfs.clear()
            return
        if not self.checksum_module_ok():
            return
        # 从第一次扫开开始记录
        if new_game_state != "win" and self.evfs.is_empty():
            return
        # 存在以下断言
        # assert isinstance(self.label.ms_board, ms.BaseVideo)
        # assert self.label.ms_board.game_board_state in (2, 3, 4)
        if self.label.ms_board.game_board_state == 2:
            self.label.ms_board.step_game_state("replay")
        # 生成当前局面的数据
        if not self.label.ms_board.raw_data:
            self.label.ms_board.use_question = False  # 禁用问号是共识
            self.label.ms_board.use_cursor_pos_lim = self.cursor_limit
            self.label.ms_board.use_auto_replay = self.auto_replay > 0

            self.label.ms_board.is_fair = self.is_fair()
            self.label.ms_board.is_official = self.is_official()

            self.label.ms_board.software = superGUI.version
            self.label.ms_board.mode = self.gameMode
            self.label.ms_board.player_identifier = self.player_identifier
            self.label.ms_board.race_identifier = self.race_identifier
            self.label.ms_board.uniqueness_identifier = self.unique_identifier
            self.label.ms_board.country = "XX" if not self.country else\
                country_name[self.country].upper()
            self.label.ms_board.device_uuid = hashlib.md5(
                bytes(str(uuid.getnode()).encode())).hexdigest().encode("UTF-8")

            self.label.ms_board.generate_evf_v4_raw_data()
            # 补上校验值
            checksum = self.checksum_guard.get_checksum(
                self.label.ms_board.raw_data[:-2])
            self.label.ms_board.checksum = checksum
        # 计算当前单元的校验码，并追加到evfs中
        # evfs的第一个单元的校验码，只考虑第一个录像
        # 此后每个单元，都考虑当前录像和最后一个单元的校验码
        if self.evfs.is_empty():
            # self.evfs[0].checksum
            checksum = self.checksum_guard.get_checksum(
                self.label.ms_board.raw_data)
            self.evfs.push(self.label.ms_board.raw_data,
                           self.cal_evf_filename(absolute=False), checksum)
        else:
            evfs_len = self.evfs.len()
            checksum = self.checksum_guard.get_checksum(
                self.label.ms_board.raw_data + self.evfs[evfs_len - 1].checksum)
            self.evfs.push(self.label.ms_board.raw_data,
                           self.cal_evf_filename(absolute=False), checksum)
        self.evfs.generate_evfs_v0_raw_data()
        self.save_evfs_file()

    def showMineNum(self, n):
        # 显示剩余雷数，雷数大于等于0，小于等于999，整数

        self.mineNumShow = n
        if n >= 0 and n <= 999:
            self.label_11.setPixmap(self.pixmapLEDNum[n//100])
            self.label_12.setPixmap(self.pixmapLEDNum[n//10 % 10])
            self.label_13.setPixmap(self.pixmapLEDNum[n % 10])
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
            self.label_32.setPixmap(self.pixmapLEDNum[t//10 % 10])
            self.label_33.setPixmap(self.pixmapLEDNum[t % 10])
            return
        elif t >= 1000:
            return

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
            self.label.ms_board = ms.BaseVideo(
                [[0] * column for _ in range(row)], self.pixSize)
        self.gameMode = self.predefinedBoardPara[k]['gamemode']
        self.score_board_manager.with_namespace({
            "mode": self.gameMode,
            # "row": self.row,
            # "column": self.column,
            # "minenum": self.minenum,
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

        video = ms.EvfVideo("virtual_preview.evf", raw_data)
        video.parse()
        video.analyse()
        video.analyse_for_features(["high_risk_guess", "jump_judge", "needless_guess",
                                    "mouse_trace", "vision_transfer", "pluck",
                                    "super_fl_local"])
        self.play_video(video, True)

    def action_CEvent(self):
        # 点击菜单栏的自定义后回调
        ui = gameDefinedParameter.ui_Form(self.r_path, self.row, self.column,
                                          self.minenum, self.mainWindow)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()
        if ui.alter:
            self.setBoard_and_start(ui.row, ui.column, ui.minenum)
            # self.score_board_manager.with_namespace({
            #     "row": self.row,
            #     "column": self.column,
            #     "minenum": self.minenum,
            # })

    def set_board_params(self, row, column, minenum):
        # 把局面设置成(row, column, minenum)，同时提取配套参数
        # 打开录像时、改级别、改设置时用
        self.row = row
        self.column = column
        self.minenum = minenum
        if (row, column, minenum) == (8, 8, 10):
            self.pixSize = self.predefinedBoardPara[1]['pixsize']
            self.gameMode = self.predefinedBoardPara[1]['gamemode']
            self.board_constraint = self.predefinedBoardPara[1]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[1]['attempt_times_limit']
        elif (row, column, minenum) == (16, 16, 40):
            self.pixSize = self.predefinedBoardPara[2]['pixsize']
            self.gameMode = self.predefinedBoardPara[2]['gamemode']
            self.board_constraint = self.predefinedBoardPara[2]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[2]['attempt_times_limit']
        elif (row, column, minenum) == (16, 30, 99):
            self.pixSize = self.predefinedBoardPara[3]['pixsize']
            self.gameMode = self.predefinedBoardPara[3]['gamemode']
            self.board_constraint = self.predefinedBoardPara[3]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[3]['attempt_times_limit']
        elif (row, column, minenum) == (self.predefinedBoardPara[4]['row'],
                                        self.predefinedBoardPara[4]['column'],
                                        self.predefinedBoardPara[4]['mine_num']):
            self.pixSize = self.predefinedBoardPara[4]['pixsize']
            self.gameMode = self.predefinedBoardPara[4]['gamemode']
            self.board_constraint = self.predefinedBoardPara[4]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[4]['attempt_times_limit']
        elif (row, column, minenum) == (self.predefinedBoardPara[5]['row'],
                                        self.predefinedBoardPara[5]['column'],
                                        self.predefinedBoardPara[5]['mine_num']):
            self.pixSize = self.predefinedBoardPara[5]['pixsize']
            self.gameMode = self.predefinedBoardPara[5]['gamemode']
            self.board_constraint = self.predefinedBoardPara[5]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[5]['attempt_times_limit']
        elif (row, column, minenum) == (self.predefinedBoardPara[6]['row'],
                                        self.predefinedBoardPara[6]['column'],
                                        self.predefinedBoardPara[6]['mine_num']):
            self.pixSize = self.predefinedBoardPara[6]['pixsize']
            self.gameMode = self.predefinedBoardPara[6]['gamemode']
            self.board_constraint = self.predefinedBoardPara[6]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[6]['attempt_times_limit']
        else:
            self.pixSize = self.predefinedBoardPara[0]['pixsize']
            self.gameMode = self.predefinedBoardPara[0]['gamemode']
            self.board_constraint = self.predefinedBoardPara[0]['board_constraint']
            self.attempt_times_limit = self.predefinedBoardPara[0]['attempt_times_limit']

    def setBoard_and_start(self, row, column, minenum):
        # 把局面设置成(row, column, minenum)，把3BV的限制设置成min3BV, max3BV
        # 比gameStart更高级
        # if self.game_state == 'display' or self.game_state == 'showdisplay':
        #     self.label.paintProbability = False
        if (self.row, self.column, self.minenum) != (row, column, minenum):
            self.set_board_params(row, column, minenum)
            self.label.set_rcp(row, column, self.pixSize)
            self.gameStart()
        else:
            self.gameRestart()

    def action_NEvent(self):
        # 游戏设置
        ui = gameSettings.ui_Form(self)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()
        if ui.alter:
            self.gameStart()
            self.pixSize = ui.pixSize
            self.gameMode = ui.gameMode
            self.auto_replay = ui.auto_replay
            self.end_then_flag = ui.end_then_flag
            self.cursor_limit = ui.cursor_limit
            self.auto_notification = ui.auto_notification
            self.player_identifier = ui.player_identifier
            self.label_info.setText(self.player_identifier)
            self.race_identifier = ui.race_identifier
            # 用户的国家或地区名的全称，例如”中国“。必须是country_name中有的或None
            # 播放录像时，self.country不会遭到修改
            self.country = ui.country
            self.set_country_flag()
            self.autosave_video = ui.autosave_video
            self.autosave_video_set = ui.autosave_video_set
            self.filter_forever = ui.filter_forever

            self.board_constraint = ui.board_constraint
            self.attempt_times_limit = ui.attempt_times_limit
            if (self.row, self.column, self.minenum) == (8, 8, 10):
                self.predefinedBoardPara[1]['attempt_times_limit'] = self.attempt_times_limit
                self.predefinedBoardPara[1]['board_constraint'] = self.board_constraint
                self.predefinedBoardPara[1]['gamemode'] = ui.gameMode
            elif (self.row, self.column, self.minenum) == (16, 16, 40):
                self.predefinedBoardPara[2]['attempt_times_limit'] = self.attempt_times_limit
                self.predefinedBoardPara[2]['board_constraint'] = self.board_constraint
                self.predefinedBoardPara[2]['gamemode'] = ui.gameMode
            elif (self.row, self.column, self.minenum) == (16, 30, 99):
                self.predefinedBoardPara[3]['attempt_times_limit'] = self.attempt_times_limit
                self.predefinedBoardPara[3]['board_constraint'] = self.board_constraint
                self.predefinedBoardPara[3]['gamemode'] = ui.gameMode
            else:
                self.predefinedBoardPara[0]['attempt_times_limit'] = self.attempt_times_limit
                self.predefinedBoardPara[0]['board_constraint'] = self.board_constraint
                self.predefinedBoardPara[0]['gamemode'] = ui.gameMode

            self.score_board_manager.with_namespace({
                # "race_identifier": ui.race_identifier,
                "mode": self.gameMode,
                # "row": self.row,
                # "column": self.column,
                # "minenum": self.minenum,
            })
            self.score_board_manager.show(self.label.ms_board, index_type=1)

    def action_QEvent(self):
        # 快捷键设置的回调
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
        ui = gameAbout.ui_Form(self.r_path, self.mainWindow)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()

    def auto_Update(self):
        data = {
            "Github": {
                "url": "https://api.github.com/repos/eee555/Metasweeper",
                "t": ""
            },
            "gitee": {
                "url": "https://gitee.com/api/v5/repos/ee55/Metasweeper",
                "t": "02d95b894b8a5ccb3731a9464b2a6f2b"
            }
        }
        update_dialog = CheckUpdateGui(GitHub(SourceManager(
            data, "Github"), superGUI.version, "(\d+\.\d+\.\d+)"), parent=self)
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

        self.unlimit_cursor()
        self.enable_screenshot()

        ui = captureScreen.CaptureScreen()
        ui.show()
        ui.exec_()

        if not ui.success_flag or len(ui.board) < 6 or len(ui.board[0]) < 6:
            return

        # 会报两种runtimeerror，标记阶段无解的局面、枚举阶段无解的局面
        try:
            ans = ms.cal_probability_onboard(
                ui.board, 0.20625 if len(ui.board[0]) >= 24 else 0.15625)
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

        # self.label.ms_board = utils.abstract_game_board()
        # self.label.ms_board.mouse_state = 1
        # self.label.ms_board.game_board_state = 1
        # self.label.ms_board.game_board = ui.board

        # 在局面上画概率，或不画
        # game_board = ui.board

        self.row = len(ui.board)
        self.column = len(ui.board[0])

        self.num_bar_ui = mine_num_bar.ui_Form(
            ans[1], self.pixSize * self.row, self.mainWindow)
        self.num_bar_ui.QWidget.barSetMineNum.connect(self.showMineNum)
        self.num_bar_ui.QWidget.barSetMineNumCalPoss.connect(
            self.render_poss_on_board)
        self.num_bar_ui.setSignal()

        # self.mainWindow.closeEvent_.connect(self.num_bar_ui.QWidget.close)

        self.timer_close_bar = QTimer()
        self.timer_close_bar.timeout.connect(
            lambda: self.num_bar_ui.QWidget.show())
        self.timer_close_bar.setSingleShot(True)
        self.timer_close_bar.start(1)
        # self.num_bar_ui.QWidget.show()

        # self.setBoard_and_start(len(ui.board), len(ui.board[0]), ans[1][1])
        self.set_board_params(self.row, self.column, ans[1][1])

        self.label.paintProbability = True
        self.label.set_rcp(self.row, self.column, self.pixSize)

        self.label.ms_board.game_board = ui.board
        self.label.ms_board.mouse_state = 1
        self.label.ms_board.game_board_state = 1
        self.mineNumShow = ans[1][1]
        self.showMineNum(self.mineNumShow)
        self.label.boardProbability = ans[0]

        self.label.update()
        # self.label.setMouseTracking(True)

        self.minimumWindow()

    def render_poss_on_board(self):
        # 雷数条拉动后、改局面后，显示雷数并展示
        try:
            ans = ms.cal_probability_onboard(
                self.label.ms_board.game_board, self.mineNumShow)
        except:
            try:
                ans = ms.cal_probability_onboard(self.label.ms_board.game_board,
                                                 self.mineNumShow / self.row / self.column)
            except:
                # 无解，算法增加雷数后无解
                self.label.paintProbability = False
                self.num_bar_ui.QWidget.hide()
                self.label.update()
                return
            else:
                # 无解，算法增加雷数后有解
                self.mineNumShow = ans[1][1]
                self.label.boardProbability = ans[0]
                self.label.paintProbability = True

        self.label.boardProbability = ans[0]
        self.label.paintProbability = True
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
            self.label.paintProbability = True
            # self.label.setMouseTracking(True)
            minenum = self.minenum
            # 删去用户标的雷，因为可能标错
            # game_board = list(map(lambda x: list(map(lambda y: min(y, 10), x)),
            #                  self.label.ms_board.game_board))
            ans = ms.cal_probability_onboard(
                self.label.ms_board.game_board, minenum)
            self.label.boardProbability = ans[0]
            self.label.update()

    def mineKeyReleaseEvent(self, keyName):
        # 松开空格键
        if keyName == 'Space':
            if self.game_state == 'show':
                self.game_state = 'joking'
                self.label.paintProbability = False
                self.label_info.setText(self.player_identifier)
                self.label.update()
            elif self.game_state == 'display':
                self.game_state = 'showdisplay'
                self.label.paintProbability = True
                self.label.update()
            elif self.game_state == 'showdisplay':
                self.game_state = 'display'
                self.label.paintProbability = False
                self.label_info.setText(self.player_identifier)
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

    def is_official(self) -> bool:
        # 局面开始时，判断一下局面是设置是否正式。
        # 极端小的3BV依然是合法的，而网站是否认同不关软件的事。
        if not self.is_fair():
            return False
        # 检查获胜，且标准模式
        return self.label.ms_board.game_board_state == 3 and self.gameMode == 0

    def is_fair(self) -> bool:
        if self.board_constraint:
            return False
        # 因为记录evfs是绑定game_state的setter方法的，所以假如勾选记录evfs，
        # 此处就是"playing"；反之，此处就是"win"或"fail"，总之都是fair的
        return self.game_state == "win" or self.game_state == "fail" or self.game_state == "playing"

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
        # 设置窗口置顶
        hwnd = self.mainWindow.winId()
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    def unlimit_cursor(self):
        '''
        取消将鼠标区域限制在游戏界面中。
        '''
        ctypes.windll.user32.ClipCursor(None)
        # 取消窗口置顶
        hwnd = self.mainWindow.winId()
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

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
        self.game_setting.set_value(
            "DEFAULT/mainWinTop", str(self.mainWindow.y()))
        self.game_setting.set_value(
            "DEFAULT/mainWinLeft", str(self.mainWindow.x()))
        self.game_setting.set_value("DEFAULT/row", str(self.row))
        self.game_setting.set_value("DEFAULT/column", str(self.column))
        self.game_setting.set_value("DEFAULT/minenum", str(self.minenum))

        if (self.row, self.column, self.minenum) == (8, 8, 10):
            self.game_setting.set_value(
                "BEGINNER/gamemode", str(self.gameMode))
            self.game_setting.set_value("BEGINNER/pixsize", str(self.pixSize))
        elif (self.row, self.column, self.minenum) == (16, 16, 40):
            self.game_setting.set_value(
                "INTERMEDIATE/gamemode", str(self.gameMode))
            self.game_setting.set_value(
                "INTERMEDIATE/pixsize", str(self.pixSize))
        elif (self.row, self.column, self.minenum) == (16, 30, 99):
            self.game_setting.set_value("EXPERT/gamemode", str(self.gameMode))
            self.game_setting.set_value("EXPERT/pixsize", str(self.pixSize))
        else:
            self.game_setting.set_value("CUSTOM/gamemode", str(self.gameMode))
            self.game_setting.set_value("CUSTOM/pixsize", str(self.pixSize))

        self.game_setting.sync()
        self.record_setting.sync()

    def action_OpenPluginDialog(self):
        dialog = PluginManagerUI(PluginManager.instance().Get_Plugin_Names())
        dialog.exec()
