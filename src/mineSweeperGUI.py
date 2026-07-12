import base64
from PyQt5 import QtCore
from PyQt5.QtCore import QTimer, QCoreApplication, Qt, QRect, QUrl
from PyQt5.QtGui import QPixmap, QDesktopServices
import msgspec
from textdistance import length
from dialogs import gameDefinedParameter
from plugin_sdk.server_bridge import GameServerBridge
from shared_types.events import GameFinishedEvent, BoardUpdateEvent, GameStatusChangeEvent, CloseEvent, ShowPluginManagerEvent
import superGUI
from dialogs import gameAbout
from dialogs import gameSettings
from dialogs import gameSettingShortcuts
from dialogs import gameAdvancedSettings
from utils.board_format import (copy_board_to_clipboard,
                                parse_board_text)
import captureScreen
import mine_num_bar
from dialogs import gameRecordPop
from dialogs.CheckUpdateGui import CheckUpdateGui
from network.githubApi import GitHub, SourceManager
import utils
import ms_toollib as ms
import os
import hashlib
import uuid
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import csv
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QDialog
from country_name import country_name
import metasweeper_checksum
from mainWindowGUI import MainWindow
from mainWindowGUIImportExport import MainWindowGUIImportExport
from ui.ui_import import Ui_Form as Ui_Import
from ui.uiComponents import RoundQDialog
from app.game_engine import GameEngine
from app.board_renderer import BoardRenderer
from config.constants import (
    READY, PLAYING, JOKING, WIN, FAIL, STUDY, DISPLAY, SHOW_DISPLAY, SHOW,
    JOWIN, JOFAIL,
    MODE_STANDARD, MODE_WIN7, MODE_CLASSIC_NO_GUESS, MODE_STRONG_NO_GUESS,
    MODE_WEAK_NO_GUESS, MODE_QUASI_NO_GUESS, MODE_STRONG_GUESSABLE, MODE_WEAK_GUESSABLE,
    FACE_SMILE,
    BOARD_BEGINNER, BOARD_INTERMEDIATE, BOARD_EXPERT,
    IDX_BEGINNER, IDX_INTERMEDIATE, IDX_EXPERT, IDX_CUSTOM,
    MIN_PIX_SIZE, MAX_PIX_SIZE,
    GAME_EVENT_STATE_MAP, GAME_STATE_ORDER,
    NO_RECORD,
)

_translate = QCoreApplication.translate




class MineSweeperGUI(MainWindowGUIImportExport):

    def __init__(self, MainWindow: MainWindow, args):
        self.mainWindow = MainWindow
        self.checksum_guard = metasweeper_checksum.ChecksumGuard()
        super(MineSweeperGUI, self).__init__(MainWindow, args)

        self.engine = GameEngine(ms_board=getattr(self.label, 'ms_board', None))
        self.renderer = BoardRenderer()



        raw = self.game_setting.value('DEFAULT/allowed_controls', '', str)
        self._allowed_controls: set[str] = set(raw.split(',')) if raw else set()
        self.engine._allowed_controls = self._allowed_controls

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
            if self.game_state not in (READY, PLAYING, SHOW, STUDY, JOKING):
                self.dump_evf_file_data()
                self.save_evf_file()
        self.action_save.triggered.connect(save_evf_file_integrated)
        self.action_replay.triggered.connect(self.replay_game)
        self.actiontui_chu.triggered.connect(QCoreApplication.instance().quit)
        self.actionyouxi_she_zhi.triggered.connect(self.action_NEvent)
        self.action_kuaijiejian.triggered.connect(self.action_QEvent)
        self.action_mouse.triggered.connect(self.action_mouse_setting)
        self.actiongaun_yv.triggered.connect(self.action_AEvent)
        self.action_advance.triggered.connect(self.action_AdvancedSettings)
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
        self.japanese_action.triggered.connect(
            lambda: self.trans_language("ja_JP"))

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
        self.frameShortcutF3.activated.connect(self.replay_current_board)
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
            "max_block_len": 0,
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
        pixSize = max(MIN_PIX_SIZE, pixSize)
        pixSize = min(MAX_PIX_SIZE, pixSize)
        pixSize = min(32767//self.column, pixSize)
        pixSize = min(32767//self.row, pixSize)
        if hasattr(self, "_pixSize") and pixSize == self._pixSize:
            return
        self.label.set_rcp(self.row, self.column, pixSize)
        self.label.reloadCellPic(pixSize)

        board_key = (self.row, self.column, self.minenum)
        if board_key == BOARD_BEGINNER:
            idx = IDX_BEGINNER
        elif board_key == BOARD_INTERMEDIATE:
            idx = IDX_INTERMEDIATE
        elif board_key == BOARD_EXPERT:
            idx = IDX_EXPERT
        else:
            idx = IDX_CUSTOM
            for i in range(4, 7):
                p = self.predefinedBoardPara[i]
                if board_key == (p.get('row'), p.get('column'), p.get('mine_num')):
                    idx = i
                    break
        self.predefinedBoardPara[idx]['pixsize'] = pixSize

        # self.label.setMinimumSize(QtCore.QSize(
        #     pixSize * self.column + 8, pixSize * self.row + 8))
        # self.label.setMaximumSize(QtCore.QSize(
        #     pixSize * self.column + 8, pixSize * self.row + 8))
        # self.label.setFixedSize(QtCore.QSize(self.pixSize*self.column + 8, self.pixSize*self.row + 8))

        self.reimportLEDPic(pixSize)
        self.label_2.reloadFace(pixSize)
        self.set_face(FACE_SMILE)
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
        if game_state == self._game_state:
            return
        last_state = self._game_state

        match last_state:
            case "playing":
                self.onGameFinished(game_state)
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
                    self.label.path_trace_enabled = False
                    self.label.path_trace_points = []
                    if hasattr(self, 'show_path_trace'):
                        self.show_path_trace = False
                        self.ui_video_control.pushButton_path.blockSignals(True)
                        self.ui_video_control.pushButton_path.setChecked(False)
                        self.ui_video_control.pushButton_path.blockSignals(False)
                    self.label.show_opening = False
                    if hasattr(self, 'ui_video_control'):
                        self.ui_video_control.pushButton_op.blockSignals(True)
                        self.ui_video_control.pushButton_op.setChecked(False)
                        self.ui_video_control.pushButton_op.blockSignals(False)
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

        # 发送游戏状态变化事件
        event = GameStatusChangeEvent(
            last_status=GAME_EVENT_STATE_MAP.get(last_state, 0),
            current_status=GAME_EVENT_STATE_MAP.get(game_state, 0),
        )
        GameServerBridge.instance().send_event(event)
        self._send_board_update_event()


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


    # 生命周期函数，正式的游戏结束时调用。由游戏状态的变更触发，当且仅当由playing变为其他状态
    # 处理数据相关。不处理前端显示
    def onGameFinished(self, new_game_state):
        try:
            # 不论如何都必然生成数据
            if self.label.ms_board.game_board_state == 2:
                self.label.ms_board.step_game_state("replay")
            self.dump_evf_file_data()
            # 发信号给插件，游戏结束了
            board = self.label.ms_board.board
            event = GameFinishedEvent(
                game_state = GAME_STATE_ORDER.index(new_game_state),
                nf = self.label.ms_board.rce == 0,
                row = self.label.ms_board.row,
                column = self.label.ms_board.column,
                mine_num = self.label.ms_board.mine_num,
                rtime = self.label.ms_board.rtime,
                left = self.label.ms_board.left,
                right = self.label.ms_board.right,
                double = self.label.ms_board.double,
                # 游戏难度（级别）。3是初级；4是中级；5是高级；6是自定义。
                level = self.label.ms_board.level,
                cl = self.label.ms_board.cl,
                ce = self.label.ms_board.ce,
                rce = self.label.ms_board.rce,
                lce = self.label.ms_board.lce,
                dce = self.label.ms_board.dce,
                bbbv = self.label.ms_board.bbbv,
                bbbv_solved = self.label.ms_board.bbbv_solved,
                zini = self.label.ms_board.zini,
                flag = self.label.ms_board.flag,
                path = self.label.ms_board.path,
                start_time = self.label.ms_board.start_time,
                end_time = self.label.ms_board.end_time,
                mode = self.label.ms_board.mode,
                software = self.label.ms_board.software,
                player_identifier = self.label.ms_board.player_identifier,
                race_identifier = self.label.ms_board.race_identifier,
                unique_identifier = self.label.ms_board.unique_identifier,
                is_official = self.label.ms_board.is_official,
                is_fair = self.label.ms_board.is_fair,
                op = self.label.ms_board.op,
                isl = self.label.ms_board.isl,
                pluck = self.label.ms_board.pluck,
                board = board if isinstance(board, list) else board.into_vec_vec(),
                raw_data = self.label.ms_board.raw_data
            )

            # 强制保存stats.dat文件
            record = utils.StatsRecord(
                game_state=event.game_state,
                row=event.row,
                column=event.column,
                mine_num=event.mine_num,
                rtime_ms=self.label.ms_board.rtime_ms,
                left=event.left,
                right=event.right,
                double=event.double,
                rce=event.rce,
                lce=event.lce,
                dce=event.dce,
                bbbv=event.bbbv,
                bbbv_solved=event.bbbv_solved,
                zini=event.zini,
                flag=event.flag,
                path=event.path,
                start_time=event.start_time,
                mode=event.mode,
                is_official=event.is_official,
                is_fair=event.is_fair,
                op=event.op,
                isl=event.isl,
                pluck=event.pluck,
                board_bytes=utils.board_list_to_bytes(event.board),
                short_md5 = hashlib.md5(self.label.ms_board.raw_data).digest()[:8]
            )
            GameServerBridge.instance().send_event(event)

            binary_data = record.encode()
            # GCM 推荐 12 字节 nonce
            nonce = get_random_bytes(12)
            cipher = AES.new(superGUI.STATS_DAT_KEY, AES.MODE_GCM, nonce=nonce)
            # 加密并生成认证 tag
            ciphertext, tag = cipher.encrypt_and_digest(binary_data)
            dat_file_path = self.setting_path / 'stats.dat'
            if (not dat_file_path.exists()) or dat_file_path.stat().st_size == 0:
                with open(dat_file_path, 'wb') as f:
                    # 文件版本号
                    f.write((0).to_bytes(1, byteorder='big'))
            # 写入：
            # [2字节长度][12字节nonce][16字节tag][ciphertext]
            with open(dat_file_path, 'ab') as f:
                blob = nonce + tag + ciphertext
                blob_length = len(blob)
                len_bytes = blob_length.to_bytes(2, byteorder="big", signed=False)
                f.write(len_bytes)
                f.write(blob)

            # 根据策略保存录像文件到磁盘
            if self.autosave_video and self.checksum_module_ok() and\
                  new_game_state in "win":
                self.save_evf_file()
            self.try_append_evfs(new_game_state)
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())


    def _sync_engine(self):
        self.engine._row = self.row
        self.engine._column = self.column
        self.engine._minenum = self.minenum
        self.engine._game_mode = self.gameMode
        self.engine._pixSize = self.pixSize
        self.engine.board_constraint = self.board_constraint
        self.engine.attempt_times_limit = self.attempt_times_limit
        self.engine.ms_board = getattr(self.label, 'ms_board', self.engine.ms_board)

    def layMine(self, i, j):
        self._sync_engine()
        used_pending = self.engine.layMine(i, j)
        if used_pending:
            self.game_state = JOKING
            self.gameMode = self.engine.gameMode
        return used_pending

    def timeCount(self):
        try:
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
                if gap_ms > 100 and self.game_state == "playing":
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
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    def ai(self, i, j):
        self._sync_engine()
        self.engine.ai(i, j)
        self.score_board_manager.with_namespace({
            "max_block_len": self.engine._max_block_len,
        })

    def chording_ai(self, i, j):
        self._sync_engine()
        self.engine.chording_ai(i, j)

    def mineNumWheel(self, i):
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

    def _send_board_update_event(self):
        """发送棋盘更新事件给插件"""
        if 'board_update' not in self._allowed_controls:
            return
        try:
            ms_board = self.label.ms_board
            # 将 game_board 转换为列表格式
            game_board_list = []
            for row in ms_board.game_board:
                game_board_list.append(list(row))

            event = BoardUpdateEvent(
                rows=self.row,
                cols=self.column,
                game_board=game_board_list,
                mines_remaining=self.mineUnFlagedNum,
                game_time=ms_board.time if hasattr(ms_board, 'time') else 0.0,
            )
            GameServerBridge.instance().send_event(event)
        except Exception:
            pass  # 忽略发送失败

    def execute_cell_click(self, row: int, col: int, button: int):
        """
        执行格子点击（供外部命令调用）

        Args:
            row: 行索引（从 0 开始）
            col: 列索引（从 0 开始）
            button: 鼠标按钮（0=左键, 1=中键, 2=右键）
        """
        if row < 0 or row >= self.row or col < 0 or col >= self.column:
            return False
        x = row * self.pixSize
        y = col * self.pixSize
        if button == 0:
            self.mineAreaLeftPressed(x, y)
            self.mineAreaLeftRelease(x, y)
        elif button == 1:
            self.mineAreaLeftPressed(x, y)
            self.mineAreaLeftAndRightPressed(x, y)
            self.mineAreaRightRelease(x, y)
            self.mineAreaLeftRelease(x, y)
        else:
            self.mineAreaRightPressed(x, y)
            self.mineAreaRightRelease(x, y)

        self._send_board_update_event()
        return True

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
        try:
            if self.game_state == 'show':
                return
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
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    def replay_current_board(self):
        if self.game_state not in (WIN, FAIL, DISPLAY, SHOW_DISPLAY, JOWIN, JOFAIL):
            return
        board = self.label.ms_board.board.into_vec_vec() if hasattr(self.label.ms_board.board, 'into_vec_vec') else self.label.ms_board.board
        gm = getattr(self.label.ms_board, 'mode', self.gameMode)
        self.gameMode = gm
        self.engine.pending_boards.append({
            "board": board,
            "game_mode": gm,
        })
        self.gameRestart()

    # 游戏结束画残局，改状态。前端的游戏结束逻辑
    def gameFinished(self):
        try:
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
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())
        # ms_board = self.label.ms_board
        # status = utils.GameBoardState(ms_board.game_board_state)
        # if status == utils.GameBoardState.Win:
        #     self.dump_evf_file_data()
            # event = VideoSaveEvent()
            # data = msgspec.structs.asdict(event)
            # for key in data:
            #     if hasattr(ms_board, key):
            #         if key == "raw_data":
            #             data[key] = base64.b64encode(
            #                 ms_board.raw_data).decode("utf-8")
            #             continue
            #         data[key] = getattr(ms_board, key)
            # event = VideoSaveEvent(**data)
            # GameServerBridge.instance().send_event(event)

        # 发送棋盘更新事件，让插件知道最终状态
        # self._send_board_update_event()

    def gameWin(self):  # 成功后改脸和状态变量，停时间
        try:
            self.timer_10ms.stop()
            self.score_board_manager.editing_row = -1

            if self.game_state == 'joking' or self.game_state == 'show':
                self.game_state = 'jowin'
            elif self.game_state == 'playing':
                self.game_state = 'win'
            else:
                raise RuntimeError
            self.set_face(17)

            # if self.autosave_video and self.checksum_module_ok():
            #     self.dump_evf_file_data()
            #     self.save_evf_file()

            self.gameFinished()

            # 尝试弹窗，没有破纪录则不弹
            if self.auto_notification and self.is_fair():
                self.try_record_pop()
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    def checksum_module_ok(self):
        return GameEngine.checksum_module_ok()

    # 搜集数据，生成evf文件的二进制数据，但是不保存
    def dump_evf_file_data(self):
        try:
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
                    self.label.ms_board.unique_identifier = self.unique_identifier
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
                    file_path = superGUI.resource_path(
                        'media') / (country.lower() + ".svg")
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
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    # 将evf数据存成evf文件
    # 调试的时候不会自动存录像，见checksum_module_ok
    # 菜单保存的回调。以及游戏结束自动保存。
    # 返回保存的文件绝对路径
    def save_evf_file(self) -> str:
        if not os.path.exists(self.replay_path):
            os.mkdir(self.replay_path)

        file_name = self.cal_evf_filename()
        # 加上后缀和重复标识数字
        real_file_name = self.label.ms_board.save_to_evf_file(file_name)
        absolute_path = os.path.abspath(os.path.join(self.replay_path, real_file_name))
        return absolute_path


    # 拼接evf录像的文件名，无后缀
    def cal_evf_filename(self, absolute=True) -> str:
        return self.engine.cal_evf_filename(
            self.label.ms_board, self.game_state,
            self.label.ms_board.player_identifier,
            self.replay_path, absolute)

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
        try:
            self.timer_10ms.stop()
            self.score_board_manager.editing_row = -1

            # "自动重开比例"，大于等于该比例时，不自动重开。负数表示禁用。0相当于禁用，但可以编辑。
            if self.label.ms_board.bbbv_solved / self.label.ms_board.bbbv * 100 < self.auto_replay:
                self.gameRestart()
            else:
                if self.game_state == 'joking':
                    self.game_state = 'jofail'
                else:
                    self.game_state = 'fail'
                self.set_face(16)
                self.gameFinished()
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

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
                del_items, b.bbbv, nf_items, self.mainWindow)
            ui.label_16.setText(mode_text)
            ui.Dialog.show()
            self._popup_dialog = ui
            ui.Dialog.finished.connect(lambda _: setattr(self, '_popup_dialog', None))


    # 根据条件是否满足，尝试追加evfs文件
    # 当且仅当game_state发生变化，且旧状态为"playing"时调用（即使点一下就获胜也会经过"playing"）
    # 加入evfs是空的，且当前游戏状态不是"win"，则不追加
    def try_append_evfs(self, new_game_state):
        try:
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
                self.label.ms_board.unique_identifier = self.unique_identifier
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
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())

    def showMineNum(self, n):
        self.mineNumShow = n
        if n >= 0 and n <= 999:
            self.label_11.setPixmap(self.pixmapLEDNum[n // 100])
            self.label_12.setPixmap(self.pixmapLEDNum[n // 10 % 10])
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
        if t >= 0 and t <= 999:
            self.label_31.setPixmap(self.pixmapLEDNum[t // 100])
            self.label_32.setPixmap(self.pixmapLEDNum[t // 10 % 10])
            self.label_33.setPixmap(self.pixmapLEDNum[t % 10])
            return
        elif t >= 1000:
            return

    def predefined_Board(self, k):
        # 按快捷键123456时的回调
        if self.game_state == 'show':
            return
        self.game_state = 'ready'
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
            self.game_state = 'ready'
            self.setBoard_and_start(ui.row, ui.column, ui.minenum)
            # self.score_board_manager.with_namespace({
            #     "row": self.row,
            #     "column": self.column,
            #     "minenum": self.minenum,
            # })

    def set_board_params(self, row, column, minenum):
        self.row = row
        self.column = column
        self.minenum = minenum

        board_key = (row, column, minenum)
        for i in range(1, 7):
            p = self.predefinedBoardPara[i]
            if (row, column, minenum) == (p.get('row'), p.get('column'), p.get('mine_num')):
                board_key = i
                break

        params = self.predefinedBoardPara[0] if isinstance(
            board_key, tuple) else self.predefinedBoardPara[board_key]
        self.pixSize = params['pixsize']
        self.gameMode = params['gamemode']
        self.board_constraint = params['board_constraint']
        self.attempt_times_limit = params['attempt_times_limit']

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
        self.score_board_manager.show(self.label.ms_board, index_type=1)

    def action_NEvent(self):
        # 游戏设置
        ui = gameSettings.ui_Form(self)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()
        if ui.alter:
            self.gameRestart()
            self.pixSize = ui.pixSize
            self.gameMode = ui.gameMode
            self.auto_replay = ui.auto_replay
            self.end_then_flag = ui.end_then_flag
            self.cursor_limit = ui.cursor_limit
            self.auto_notification = ui.auto_notification
            self.player_identifier = ui.player_identifier
            self.label_info.setText(self.player_identifier)
            self.race_identifier = ui.race_identifier
            self.unique_identifier = ui.unique_identifier
            # 用户的国家或地区名的全称，例如”中国“。必须是country_name中有的或None
            # 播放录像时，self.country不会遭到修改
            self.country = ui.country
            self.set_country_flag()
            self.autosave_video = ui.autosave_video
            self.autosave_video_set = ui.autosave_video_set

            self.board_constraint = ui.board_constraint
            self.attempt_times_limit = ui.attempt_times_limit

            board_key = (self.row, self.column, self.minenum)
            idx = IDX_CUSTOM
            if board_key == BOARD_BEGINNER:
                idx = IDX_BEGINNER
            elif board_key == BOARD_INTERMEDIATE:
                idx = IDX_INTERMEDIATE
            elif board_key == BOARD_EXPERT:
                idx = IDX_EXPERT
            self.predefinedBoardPara[idx]['attempt_times_limit'] = self.attempt_times_limit
            self.predefinedBoardPara[idx]['board_constraint'] = self.board_constraint
            self.predefinedBoardPara[idx]['gamemode'] = ui.gameMode

            self.score_board_manager.with_namespace({
                "mode": self.gameMode,
            })
            self.score_board_manager.show(self.label.ms_board, index_type=1)

    def action_AdvancedSettings(self):
        ui = gameAdvancedSettings.ui_Form(self)
        ui.Dialog.setModal(True)
        ui.Dialog.show()
        ui.Dialog.exec_()
        if ui.alter:
            self.gameRestart()
            self.filter_forever = ui.filter_forever
            self._allowed_controls = ui._allowed_controls.copy()

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
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Failed to open mouse settings")

    def action_AEvent(self):
        # 关于
        ui = gameAbout.ui_Form(self.mainWindow)
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
            data, "Github"), superGUI.version, r"(\d+\.\d+\.\d+)"), parent=self)
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
        if not self.is_fair():
            return False
        return self.label.ms_board.game_board_state == 3 and self.gameMode == 0

    def is_fair(self) -> bool:
        if self.board_constraint:
            return False
        if self._allowed_controls:
            return False
        return self.game_state in ("win", "fail", "playing")

    def cell_is_in_board(self, i, j):
        return 0 <= i < self.row and 0 <= j < self.column

    def pos_is_in_board(self, i, j) -> bool:
        return 0 <= i < self.row * self.pixSize and 0 <= j < self.column * self.pixSize

    def set_face(self, face_type):
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
        self.renderer.limit_cursor(self.label, self.mainWindow)

    def unlimit_cursor(self):
        self.renderer.unlimit_cursor(self.mainWindow)

    def closeEvent_(self):
        self.unlimit_cursor()
        self.game_setting.set_value(
            "DEFAULT/mainwintop", str(self.mainWindow.y()))
        self.game_setting.set_value(
            "DEFAULT/mainwinleft", str(self.mainWindow.x()))
        self.game_setting.set_value("DEFAULT/row", str(self.row))
        self.game_setting.set_value("DEFAULT/column", str(self.column))
        self.game_setting.set_value("DEFAULT/minenum", str(self.minenum))

        board_key = (self.row, self.column, self.minenum)
        if board_key == BOARD_BEGINNER:
            section = "BEGINNER"
        elif board_key == BOARD_INTERMEDIATE:
            section = "INTERMEDIATE"
        elif board_key == BOARD_EXPERT:
            section = "EXPERT"
        else:
            section = "CUSTOM"

        self.game_setting.set_value(f"{section}/gamemode", str(self.gameMode))
        self.game_setting.set_value(f"{section}/pixsize", str(self.pixSize))

        self.game_setting.sync()
        self.record_setting.sync()
        event = CloseEvent()
        GameServerBridge.instance().send_event(event)

    def copy_board(self):
        if self.game_state in ("playing", "ready"):
            return
        try:
            board = self.label.ms_board.board
            if isinstance(board, ms.SafeBoard):
                board = board.into_vec_vec()
            game_board = self.label.ms_board.game_board
        except AttributeError:
            return
        if not board:
            return
        copy_format = self.game_setting.value("DEFAULT/copy_format", 1, int)
        copy_render = self.game_setting.value("DEFAULT/copy_render", "ascii", str)
        copy_board_to_clipboard(
            board, game_board,
            self.row, self.column, self.minenum,
            self.gameMode, copy_format,
            author=self.player_identifier, render=copy_render,
        )

    def paste_board(self):
        if self.game_state not in (
            "study", "ready", "fail", "win",
            "jofail", "jowin", "display", "showdisplay",
        ):
            return

        text = QApplication.clipboard().text()
        game_board = mines = None

        if text:
            game_board, mines, source = parse_board_text(text)

        if not game_board:
            mime = QApplication.clipboard().mimeData()
            if mime.hasUrls():
                for url in mime.urls():
                    if url.isLocalFile() and url.toLocalFile().endswith(".board"):
                        try:
                            with open(url.toLocalFile(), "r", encoding="utf-8") as f:
                                game_board, mines, source = parse_board_text(f.read())
                            if game_board:
                                break
                        except OSError:
                            continue

        if not game_board:
            QMessageBox.warning(self.mainWindow, _translate("MainWindow", "粘贴失败"), _translate("MainWindow", "剪贴板内容无法识别为扫雷局面"))
            return

        rows, cols = len(game_board), len(game_board[0])
        if mines <= 0:
            mines = max(1, rows * cols // 6)
        self.set_board_params(rows, cols, mines)
        self.label.paintProbability = True
        self.label.set_rcp(rows, cols, self.pixSize)
        self.label.ms_board.reset(rows, cols, self.pixSize)

        if self.game_state == "display" or self.game_state == "showdisplay":
            self.video_playing = False
            self.timer_video.stop()

        self.timer_10ms.stop()
        self.score_board_manager.invisible()

        try:
            self.num_bar_ui.QWidget.close()
        except AttributeError:
            pass
        self.mineNumShow = mines if mines > 0 else max(1, rows * cols // 6)
        self.num_bar_ui = mine_num_bar.ui_Form(
            (self.mineNumShow, self.mineNumShow, self.mineNumShow),
            self.pixSize * rows, self.mainWindow,
        )
        self.num_bar_ui.QWidget.barSetMineNum.connect(self.showMineNum)
        self.num_bar_ui.QWidget.barSetMineNumCalPoss.connect(
            self.render_poss_on_board)
        self.num_bar_ui.setSignal()
        QTimer.singleShot(1, self.num_bar_ui.QWidget.show)

        self.game_state = "study"
        self.set_face(14)

        game_board = [[cell if 0 <= cell <= 8 else 10 for cell in row] for row in game_board]
        self.label.ms_board.game_board = game_board
        self.label.ms_board.mouse_state = 1
        self.label.ms_board.game_board_state = 1
        self.showMineNum(self.mineNumShow)
        self.render_poss_on_board()
        self.minimumWindow()

    def _read_stats_dat_short_md5s(self) -> set[bytes]:
        """读取 stats.dat 中所有记录的 short_md5"""
        dat_path = self.setting_path / "stats.dat"
        if not dat_path.exists() or dat_path.stat().st_size == 0:
            return set()
        md5s = set()
        try:
            with open(dat_path, "rb") as f:
                f.read(1)
                while True:
                    lb = f.read(2)
                    if not lb or len(lb) < 2:
                        break
                    bl = int.from_bytes(lb, "big")
                    blob = f.read(bl)
                    if not blob or len(blob) < bl:
                        break
                    nonce = blob[:12]
                    tag = blob[12:28]
                    ct = blob[28:]
                    try:
                        cipher = AES.new(superGUI.STATS_DAT_KEY, AES.MODE_GCM, nonce=nonce)
                        pt = cipher.decrypt_and_verify(ct, tag)
                        md5s.add(utils.StatsRecord.decode(pt).short_md5)
                    except Exception:
                        continue
        except Exception:
            pass
        return md5s


    def action_OpenPluginDialog(self):
        try:
            bridge = GameServerBridge.instance()
            bridge.send_event(ShowPluginManagerEvent())
        except Exception:
            pass

