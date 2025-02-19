from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtCore import QTranslator
from os import environ
from PyQt5.QtWidgets import QApplication
import configparser
from PyQt5.QtGui import QPalette, QPixmap, QIcon
# from PyQt5.QtWidgets import QScrollArea
# from PyQt5.QtSvg import QSvgWidget
from ui.ui_main_board import Ui_MainWindow
from pathlib import Path
from gameScoreBoard import gameScoreBoardManager
import minesweeper_master as mm
# import metaminesweeper_checksum
from country_name import country_name
import os


version = "元3.2.1"


class Ui_MainWindow(Ui_MainWindow):
    minimum_counter = 0 # 最小化展示窗口有关
    # windowSizeState = 'loose'  # loose or tight
    def __init__(self, MainWindow, args):
        self.mainWindow = MainWindow
        self.setupUi(self.mainWindow)
                
        
        # 设置全局路径
        r_path = Path(args[0]).parent
        self.r_path = r_path
        # 录像保存位置
        self.replay_path = str(r_path.with_name('replay'))
        # 记录了全局游戏设置
        self.game_setting_path = str(r_path.with_name('gameSetting.ini'))
        # 个人记录，用来弹窗
        self.record_path = str(r_path.with_name('record.ini'))


        self.ico_path = str(r_path.with_name('media').joinpath('cat.ico'))
        self.smileface_path = str(r_path.with_name('media').joinpath('smileface.svg'))
        self.clickface_path = str(r_path.with_name('media').joinpath('clickface.svg'))
        self.lostface_path = str(r_path.with_name('media').joinpath('lostface.svg'))
        self.winface_path = str(r_path.with_name('media').joinpath('winface.svg'))
        self.smilefacedown_path = str(r_path.with_name('media').joinpath('smilefacedown.svg'))
        self.LED0_path = str(r_path.with_name('media').joinpath('LED0.png'))
        self.LED1_path = str(r_path.with_name('media').joinpath('LED1.png'))
        self.LED2_path = str(r_path.with_name('media').joinpath('LED2.png'))
        self.LED3_path = str(r_path.with_name('media').joinpath('LED3.png'))
        self.LED4_path = str(r_path.with_name('media').joinpath('LED4.png'))
        self.LED5_path = str(r_path.with_name('media').joinpath('LED5.png'))
        self.LED6_path = str(r_path.with_name('media').joinpath('LED6.png'))
        self.LED7_path = str(r_path.with_name('media').joinpath('LED7.png'))
        self.LED8_path = str(r_path.with_name('media').joinpath('LED8.png'))
        self.LED9_path = str(r_path.with_name('media').joinpath('LED9.png'))


        self.mainWindow.setWindowIcon(QIcon(self.ico_path))

        self.predefinedBoardPara = [{}] * 7
        # 缓存了6套游戏模式的配置，以减少快捷键切换模式时的io
        # gameMode = 0，1，2，3，4，5，6，7代表：
        # 标准、win7、经典无猜、强无猜、弱无猜、准无猜、强可猜、弱可猜

        self.read_or_create_record()
        self.label.setPath(r_path)
        self.label_2.setPath(r_path)
        _scoreBoardTop, _scoreBoardLeft = self.read_or_create_game_setting()
        self.initMineArea()


        self.readPredefinedBoardPara()
        self.retranslateUi(MainWindow)

        self.trans = QTranslator()


        # 记录了计数器的配置，显示哪些指标等等
        score_board_path = str(r_path.with_name('scoreBoardSetting.ini'))
        self.score_board_manager = gameScoreBoardManager(r_path, score_board_path,
                                                         self.game_setting_path,
                                                         self.pixSize, MainWindow)
        self.score_board_manager.ui.QWidget.move(_scoreBoardTop, _scoreBoardLeft)


        self.importLEDPic(self.pixSize) # 导入图片
        # self.label.setPath(r_path)


        self.label_2.leftRelease.connect(self.gameRestart)
        self.MinenumTimeWigdet.mouseReleaseEvent = self.gameRestart

        self.label_2.setPixmap(self.pixmapNum[14])
        self.label_2.setScaledContents(True)
        pe = QPalette()
        pe.setColor(QPalette.WindowText, Qt.black)  # 设置字体颜色
        self.label_info.setPalette(pe)         # 最下面的框
        self.label_info.setText(self.player_identifier)
        self.set_country_flag()

        self.frameShortcut1 = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_1), MainWindow)
        self.frameShortcut2 = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_2), MainWindow)
        self.frameShortcut3 = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_3), MainWindow)
        self.frameShortcut5 = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_4), MainWindow)
        self.frameShortcut6 = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_5), MainWindow)
        self.frameShortcut7 = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_6), MainWindow)
        self.frameShortcut4 = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F2), MainWindow)
        self.frameShortcut8 = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Space), MainWindow)
        self.frameShortcut8.setAutoRepeat(False)
        self.frameShortcut9 = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Space"), MainWindow)
        self.shortcut_hidden_score_board = QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Slash), MainWindow) # /键隐藏计数器

        QtCore.QMetaObject.connectSlotsByName(MainWindow)

        self.minimumWindow()

    def initMineArea(self):

        # self.label.set_rcp(self.row, self.column, self.pixSize)
        self.label.setMinimumSize(QSize(self.pixSize*self.column + 8, self.pixSize*self.row + 8))
        self.label.leftPressed.connect(self.mineAreaLeftPressed)
        self.label.leftRelease.connect(self.mineAreaLeftRelease)
        self.label.leftAndRightPressed.connect(self.mineAreaLeftAndRightPressed)
        # self.label.leftAndRightRelease.connect(self.mineAreaLeftAndRightRelease)
        self.label.rightPressed.connect(self.mineAreaRightPressed)
        self.label.rightRelease.connect(self.mineAreaRightRelease)
        self.label.mouseMove.connect(self.mineMouseMove)
        self.label.mousewheelEvent.connect(lambda x, y, z: self.resizeWheel(x, y, z))
        self.label_11.mousewheelEvent.connect(self.mineNumWheel)
        self.label_12.mousewheelEvent.connect(self.mineNumWheel)
        self.label_13.mousewheelEvent.connect(self.mineNumWheel)

        self.mainWindow.keyRelease.connect(self.mineKeyReleaseEvent)

        self.label.setObjectName("label")



    def importLEDPic(self, pixSize):
        # 从磁盘导入资源，并缩放到希望的尺寸、比例
        pixmap14 = QPixmap(self.smileface_path)
        pixmap15 = QPixmap(self.clickface_path)
        pixmap16 = QPixmap(self.lostface_path)
        pixmap17 = QPixmap(self.winface_path)
        pixmap18 = QPixmap(self.smilefacedown_path)
        self.pixmapNumPix = {14: pixmap14, 15: pixmap15, 16: pixmap16, 17: pixmap17, 18: pixmap18}
        pixmap14_ = pixmap14.scaled(int(pixSize * 1.5), int(pixSize * 1.5))
        pixmap15_ = pixmap15.scaled(int(pixSize * 1.5), int(pixSize * 1.5))
        pixmap16_ = pixmap16.scaled(int(pixSize * 1.5), int(pixSize * 1.5))
        pixmap17_ = pixmap17.scaled(int(pixSize * 1.5), int(pixSize * 1.5))
        pixmap18_ = pixmap18.scaled(int(pixSize * 1.5), int(pixSize * 1.5))
        self.pixmapNum = {14: pixmap14_, 15: pixmap15_, 16: pixmap16_, 17: pixmap17_, 18: pixmap18_}
        # 以上是读取数字的图片，局面中的数字；以下是上方LED数字的图片
        pixLEDmap0 = QPixmap(self.LED0_path)
        pixLEDmap1 = QPixmap(self.LED1_path)
        pixLEDmap2 = QPixmap(self.LED2_path)
        pixLEDmap3 = QPixmap(self.LED3_path)
        pixLEDmap4 = QPixmap(self.LED4_path)
        pixLEDmap5 = QPixmap(self.LED5_path)
        pixLEDmap6 = QPixmap(self.LED6_path)
        pixLEDmap7 = QPixmap(self.LED7_path)
        pixLEDmap8 = QPixmap(self.LED8_path)
        pixLEDmap9 = QPixmap(self.LED9_path)
        self.pixmapLEDNumPix = {0: pixLEDmap0, 1: pixLEDmap1, 2: pixLEDmap2, 3: pixLEDmap3,
                        4: pixLEDmap4, 5: pixLEDmap5, 6: pixLEDmap6, 7: pixLEDmap7,
                        8: pixLEDmap8, 9: pixLEDmap9}
        pixLEDmap0_ = pixLEDmap0.copy().scaled(pixSize, int(pixSize * 1.75))
        pixLEDmap1_ = pixLEDmap1.copy().scaled(pixSize, int(pixSize * 1.75))
        pixLEDmap2_ = pixLEDmap2.copy().scaled(pixSize, int(pixSize * 1.75))
        pixLEDmap3_ = pixLEDmap3.copy().scaled(pixSize, int(pixSize * 1.75))
        pixLEDmap4_ = pixLEDmap4.copy().scaled(pixSize, int(pixSize * 1.75))
        pixLEDmap5_ = pixLEDmap5.copy().scaled(pixSize, int(pixSize * 1.75))
        pixLEDmap6_ = pixLEDmap6.copy().scaled(pixSize, int(pixSize * 1.75))
        pixLEDmap7_ = pixLEDmap7.copy().scaled(pixSize, int(pixSize * 1.75))
        pixLEDmap8_ = pixLEDmap8.copy().scaled(pixSize, int(pixSize * 1.75))
        pixLEDmap9_ = pixLEDmap9.copy().scaled(pixSize, int(pixSize * 1.75))
        self.pixmapLEDNum = {0: pixLEDmap0_, 1: pixLEDmap1_, 2: pixLEDmap2_, 3: pixLEDmap3_,
                        4: pixLEDmap4_, 5: pixLEDmap5_, 6: pixLEDmap6_, 7: pixLEDmap7_,
                        8: pixLEDmap8_, 9: pixLEDmap9_}

    def reimportLEDPic(self, pixSize):
        # 重新将资源的尺寸缩放到希望的尺寸、比例
        self.pixmapNum = {key:value.copy().scaled(int(pixSize * 1.5), int(pixSize * 1.5)) for key,value in self.pixmapNumPix.items()}
        self.pixmapLEDNum = {key:value.copy().scaled(pixSize, int(pixSize * 1.75)) for key,value in self.pixmapLEDNumPix.items()}


    def readPredefinedBoardPara(self):
        # 从配置中更新出快捷键1, 2, 3, 4、5、6的定义(0是自定义)
        config = configparser.ConfigParser()
        config.read(self.game_setting_path, encoding='utf-8')
        self.predefinedBoardPara[0] = {
            "game_mode": config.getint('CUSTOM','gamemode'),
            "row": 8,
            "column": 8,
            "pix_size": config.getint('CUSTOM','pixsize'),
            "mine_num": 10,
            "board_constraint": config["CUSTOM"]["board_constraint"],
            "attempt_times_limit": config.getint('CUSTOM','attempt_times_limit'),
            }
        self.predefinedBoardPara[1] = {
            "game_mode": config.getint('BEGINNER','gamemode'),
            "row": 8,
            "column": 8,
            "pix_size": config.getint('BEGINNER','pixsize'),
            "mine_num": 10,
            "board_constraint": config["BEGINNER"]["board_constraint"],
            "attempt_times_limit": config.getint('BEGINNER','attempt_times_limit'),
            }
        self.predefinedBoardPara[2] = {
            "game_mode": config.getint('INTERMEDIATE','gamemode'),
            "row": 16,
            "column": 16,
            "pix_size": config.getint('INTERMEDIATE','pixsize'),
            "mine_num": 40,
            "board_constraint": config["INTERMEDIATE"]["board_constraint"],
            "attempt_times_limit": config.getint('INTERMEDIATE','attempt_times_limit'),
            }
        self.predefinedBoardPara[3] = {
            "game_mode": config.getint('EXPERT','gamemode'),
            "row": 16,
            "column": 30,
            "pix_size": config.getint('EXPERT','pixsize'),
            "mine_num": 99,
            "board_constraint": config["EXPERT"]["board_constraint"],
            "attempt_times_limit": config.getint('EXPERT','attempt_times_limit'),
            }
        self.predefinedBoardPara[4] = {
            "game_mode": config.getint('CUSTOM_PRESET_4','gameMode'),
            "row": config.getint('CUSTOM_PRESET_4','row'),
            "column": config.getint('CUSTOM_PRESET_4','column'),
            "pix_size": config.getint('CUSTOM_PRESET_4','pixSize'),
            "mine_num": config.getint('CUSTOM_PRESET_4','mineNum'),
            "board_constraint": config["CUSTOM_PRESET_4"]["board_constraint"],
            "attempt_times_limit": config.getint('CUSTOM_PRESET_4','attempt_times_limit'),
            }

        self.predefinedBoardPara[5] = {
            "game_mode": config.getint('CUSTOM_PRESET_5','gameMode'),
            "row": config.getint('CUSTOM_PRESET_5','row'),
            "column": config.getint('CUSTOM_PRESET_5','column'),
            "pix_size": config.getint('CUSTOM_PRESET_5','pixSize'),
            "mine_num": config.getint('CUSTOM_PRESET_5','mineNum'),
            "board_constraint": config["CUSTOM_PRESET_5"]["board_constraint"],
            "attempt_times_limit": config.getint('CUSTOM_PRESET_5','attempt_times_limit'),
            }

        self.predefinedBoardPara[6] = {
            "game_mode": config.getint('CUSTOM_PRESET_6','gameMode'),
            "row": config.getint('CUSTOM_PRESET_6','row'),
            "column": config.getint('CUSTOM_PRESET_6','column'),
            "pix_size": config.getint('CUSTOM_PRESET_6','pixSize'),
            "mine_num": config.getint('CUSTOM_PRESET_6','mineNum'),
            "board_constraint": config["CUSTOM_PRESET_6"]["board_constraint"],
            "attempt_times_limit": config.getint('CUSTOM_PRESET_6','attempt_times_limit'),
            }

    def minimumWindow(self):
        # 最小化展示窗口，并固定尺寸
        self.label.setFixedSize(QtCore.QSize(self.pixSize*self.column + 8,
                                             self.pixSize*self.row + 8))
        self.windowSizeState = 'tight'
        self.timer_ = QTimer()
        self.timer_.timeout.connect(self.__minimumWindow)
        self.timer_.start(1)

    def __minimumWindow(self):
        self.mainWindow.setFixedSize(self.mainWindow.minimumSize())
        self.minimum_counter += 1
        if self.minimum_counter >= 100:
            self.minimum_counter = 0
            self.timer_.stop()
            


    def trans_language(self, language = ""):
        if not language:
            language = self.language
        app = QApplication.instance()
        if language != "zh_CN":
            self.trans.load(str(self.r_path.with_name(language + '.qm')))
            app.installTranslator(self.trans)
            self.retranslateUi(self.mainWindow)
            self.score_board_manager.retranslateUi(self.score_board_manager.ui.QWidget)
        else:
            app.removeTranslator(self.trans)
            self.retranslateUi(self.mainWindow)
            self.score_board_manager.retranslateUi(self.score_board_manager.ui.QWidget)
        mm.updata_ini(self.game_setting_path, [("DEFAULT", "language", language)])
        self.language = language



    def read_or_create_game_setting(self):
        config = configparser.ConfigParser()
        if config.read(self.game_setting_path, encoding='utf-8'):
            self.mainWindow.setWindowOpacity((config.getint('DEFAULT', 'transparency') + 1) / 100)
            # self._pixSize = config.getint('DEFAULT', 'pixSize')
            self.mainWindow.move(config.getint('DEFAULT', 'mainWinTop'), config.getint('DEFAULT', 'mainWinLeft'))
            # self.score_board_manager.ui.QWidget.move(config.getint('DEFAULT', 'scoreBoardTop'),
            #                                          config.getint('DEFAULT', 'scoreBoardLeft'))
            _scoreBoardTop = config.getint('DEFAULT', 'scoreBoardTop')
            _scoreBoardLeft = config.getint('DEFAULT', 'scoreBoardLeft')
            self.row = config.getint("DEFAULT", "row")
            self.column = config.getint("DEFAULT", "column")

            # self.label.set_rcp(self.row, self.column, self.pixSize)

            self.mineNum = config.getint("DEFAULT", "mineNum")
            # self.gameMode = config.getint('DEFAULT', 'gameMode')
            # 完成度低于该百分比炸雷自动重开
            if config.getboolean("DEFAULT", "allow_auto_replay"):
                self.auto_replay = config.getint("DEFAULT", "auto_replay")
            else:
                self.auto_replay = -1
            self.auto_notification = config.getboolean("DEFAULT", "auto_notification")

            self.player_identifier = config["DEFAULT"]["player_identifier"]
            self.race_identifier = config["DEFAULT"]["race_identifier"]
            self.unique_identifier = config["DEFAULT"]["unique_identifier"]
            self.country = config["DEFAULT"]["country"]
            self.autosave_video = config.getboolean("DEFAULT", "autosave_video")
            self.filter_forever = config.getboolean("DEFAULT", "filter_forever")
            self.language = config["DEFAULT"]["language"]
            # self.auto_show_score = config.getint("DEFAULT", "auto_show_score") # 自动弹成绩
            self.end_then_flag = config.getboolean("DEFAULT", "end_then_flag") # 游戏结束后自动标雷
            self.cursor_limit = config.getboolean("DEFAULT", "cursor_limit")
            if (self.row, self.column, self.mineNum) == (8, 8, 10):
                self._pixSize = config.getint('BEGINNER', 'pixsize')
                self.label.set_rcp(self.row, self.column, self.pixSize)
                self.gameMode = config.getint('BEGINNER', 'gamemode')
                self.board_constraint = config["BEGINNER"]["board_constraint"]
                self.attempt_times_limit = config.getint('BEGINNER', 'attempt_times_limit')
            elif (self.row, self.column, self.mineNum) == (16, 16, 40):
                self._pixSize = config.getint('INTERMEDIATE', 'pixsize')
                self.label.set_rcp(self.row, self.column, self.pixSize)
                self.gameMode = config.getint('INTERMEDIATE', 'gamemode')
                self.board_constraint = config["INTERMEDIATE"]["board_constraint"]
                self.attempt_times_limit = config.getint('INTERMEDIATE', 'attempt_times_limit')
            elif (self.row, self.column, self.mineNum) == (16, 30, 99):
                self._pixSize = config.getint('EXPERT', 'pixsize')
                self.label.set_rcp(self.row, self.column, self.pixSize)
                self.gameMode = config.getint('EXPERT', 'gamemode')
                self.board_constraint = config["EXPERT"]["board_constraint"]
                self.attempt_times_limit = config.getint('EXPERT', 'attempt_times_limit')
            else:
                self._pixSize = config.getint('CUSTOM', 'pixsize')
                self.label.set_rcp(self.row, self.column, self.pixSize)
                self.gameMode = config.getint('CUSTOM', 'gamemode')
                self.board_constraint = config["CUSTOM"]["board_constraint"]
                self.attempt_times_limit = config.getint('CUSTOM', 'attempt_times_limit')
        else:
            # 找不到配置文件就初始化
            self.min3BV = 100
            self.max3BV = 381
            self.mainWindow.setWindowOpacity(1)
            self._pixSize = 20
            self.mainWindow.move(100, 200)
            _scoreBoardTop = 100
            _scoreBoardLeft = 100
            self.row = 16
            self.column = 30
            self.label.set_rcp(self.row, self.column, self.pixSize)
            self.gameMode = 0
            self.mineNum = 99
            self.auto_replay = 30
            self.allow_auto_replay = False
            self.auto_notification = True
            self.allow_min3BV = False
            self.allow_max3BV = False
            self.player_identifier = "匿名玩家(anonymous player)"
            self.race_identifier = ""
            self.unique_identifier = ""
            self.country = ""
            self.autosave_video = True
            self.filter_forever = False
            self.end_then_flag = True
            self.cursor_limit = False
            self.board_constraint = ""
            self.attempt_times_limit = 100000
            if environ.get('LANG', None) == "zh_CN":
                self.language = "zh_CN"
            else:
                self.language = "en_US"
            config["DEFAULT"] = {'transparency': 100,
                                 'mainWinTop': 100,
                                 'mainWinLeft': 200,
                                 'scoreBoardTop': 100,
                                 'scoreBoardLeft': 100,
                                 'row': 16,
                                 'column': 30,
                                 'mineNum': 99,
                                 "auto_replay": 30,
                                 "allow_auto_replay": False,
                                 "auto_notification": True,
                                 "player_identifier": "匿名玩家(anonymous player)",
                                 "race_identifier": "",
                                 "unique_identifier": "",
                                 "country": "",
                                 "autosave_video": True,
                                 "filter_forever": False,
                                 "end_then_flag": True,
                                 "cursor_limit": False,
                                 "language": self.language,
                                 }
            config["BEGINNER"] = {"gameMode": 0,
                                  "pixSize": 20,
                                  "board_constraint": "",
                                  "attempt_times_limit": 100000,
                                  }
            config["INTERMEDIATE"] = {"gameMode": 0,
                                      "pixSize": 20,
                                      "board_constraint": "",
                                      "attempt_times_limit": 100000,
                                      }
            config["EXPERT"] = {"gameMode": 0,
                                "pixSize": 20,
                                "board_constraint": "",
                                "attempt_times_limit": 100000,
                                }
            config["CUSTOM"] = {"gameMode": 0,
                                "pixSize": 20,
                                "board_constraint": "",
                                "attempt_times_limit": 100000,
                                 }
            config["CUSTOM_PRESET_4"] = {'row': 16,
                                         'column': 16,
                                         'minenum': 72,
                                         'gameMode': 5,
                                         'pixSize': 20,
                                         "board_constraint": "",
                                         "attempt_times_limit": 100000,
                                         }
            config["CUSTOM_PRESET_5"] = {'row': 16,
                                         'column': 30,
                                         'minenum': 120,
                                         'gamemode': 5,
                                         'pixsize': 20,
                                         "board_constraint": "",
                                         "attempt_times_limit": 100000,
                                         }
            config["CUSTOM_PRESET_6"] = {'row': 24,
                                         'column': 36,
                                         'minenum': 200,
                                         'gamemode': 5,
                                         'pixsize': 20,
                                         "board_constraint": "",
                                         "attempt_times_limit": 100000,
                                         }
            with open(self.game_setting_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)  # 将对象写入文件
        self.label_2.reloadFace(self.pixSize)
        return _scoreBoardTop, _scoreBoardLeft

    def read_or_create_record(self):
        config = configparser.ConfigParser()
        record_key_name_list = ["BFLAG", "BNF", "BWIN7", "BSS", "BWS", "BCS", "BTBS", "BSG",
                                "BWG", "IFLAG", "INF", "IWIN7", "ISS", "IWS", "ICS", "ITBS",
                                "ISG", "IWG", "EFLAG", "ENF", "EWIN7", "ESS", "EWS", "ECS",
                                "ETBS", "ESG", "EWG"]
        self.record_key_name_list = record_key_name_list + ["BEGINNER", "INTERMEDIATE", "EXPERT"]
        if config.read(self.record_path):
            self.record = {}
            for record_key_name in record_key_name_list:
                self.record[record_key_name] = {'rtime': config.getfloat(record_key_name, 'rtime'),
                                       'bbbv_s': config.getfloat(record_key_name, 'bbbv_s'),
                                       'stnb': config.getfloat(record_key_name, 'stnb'),
                                       'ioe': config.getfloat(record_key_name, 'ioe'),
                                       'path': config.getfloat(record_key_name, 'path'),
                                       'rqp': config.getfloat(record_key_name, 'rqp'),
                                       }
            self.record["BEGINNER"] = dict(zip(map(lambda x: str(x), range(1, 55)),
                                               map(lambda x: config.\
                                                   getfloat('BEGINNER', str(x)),
                                                   range(1, 55))))
            self.record["INTERMEDIATE"] = dict(zip(map(lambda x: str(x), range(1, 217)),
                                               map(lambda x: config.\
                                                   getfloat('INTERMEDIATE', str(x)),
                                                   range(1, 217))))
            self.record["EXPERT"] = dict(zip(map(lambda x: str(x), range(1, 382)),
                                               map(lambda x: config.\
                                                   getfloat('EXPERT', str(x)),
                                                   range(1, 382))))
        else:
            # 找不到配置文件就初始化
            # 只有标准模式记录pb，且分nf/flag
            self.record = {}
            record_init_dict = {'rtime': 999.999,
                                'bbbv_s': 0.000,
                                'stnb': 0.000,
                                'ioe': 0.000,
                                'path': 999999.999,
                                'rqp': 999999.999,
                                }
            for record_key_name in record_key_name_list:
                self.record[record_key_name] = record_init_dict.copy()

            self.record["BEGINNER"] = dict.fromkeys(map(lambda x: str(x), range(1, 55)), 999.999)
            self.record["INTERMEDIATE"] = dict.fromkeys(map(lambda x: str(x), range(1, 217)), 999.999)
            self.record["EXPERT"] = dict.fromkeys(map(lambda x: str(x), range(1, 382)), 999.999)
            config["BFLAG"] = self.record["BFLAG"]
            config["BNF"] = self.record["BNF"]
            config["BWIN7"] = self.record["BWIN7"]
            config["BSS"] = self.record["BSS"]
            config["BWS"] = self.record["BWS"]
            config["BCS"] = self.record["BCS"]
            config["BTBS"] = self.record["BTBS"]
            config["BSG"] = self.record["BSG"]
            config["BWG"] = self.record["BWG"]

            config["IFLAG"] = self.record["IFLAG"]
            config["INF"] = self.record["INF"]
            config["IWIN7"] = self.record["IWIN7"]
            config["ISS"] = self.record["ISS"]
            config["IWS"] = self.record["IWS"]
            config["ICS"] = self.record["ICS"]
            config["ITBS"] = self.record["ITBS"]
            config["ISG"] = self.record["ISG"]
            config["IWG"] = self.record["IWG"]

            config["EFLAG"] = self.record["EFLAG"]
            config["ENF"] = self.record["ENF"]
            config["EWIN7"] = self.record["EWIN7"]
            config["ESS"] = self.record["ESS"]
            config["EWS"] = self.record["EWS"]
            config["ECS"] = self.record["ECS"]
            config["ETBS"] = self.record["ETBS"]
            config["ESG"] = self.record["ESG"]
            config["EWG"] = self.record["EWG"]

            config["BEGINNER"] = self.record["BEGINNER"]
            config["INTERMEDIATE"] = self.record["INTERMEDIATE"]
            config["EXPERT"] = self.record["EXPERT"]
            with open(self.record_path, 'w') as configfile:
                config.write(configfile)  # 将对象写入文件

    def set_country_flag(self, country = None):
        if country == None:
            country = self.country
        # 设置右下角国旗图案
        if country not in country_name:
            file_path = self.r_path.with_name('media') / (country.lower() + ".svg")
            if os.path.exists(file_path):
                flag_name = file_path
            else:
                self.label_flag.clear()
                self.label_flag.update()
                return
        else:
            flag_name = self.r_path.with_name('media') / (country_name[country] + ".svg")
        pixmap = QPixmap(str(flag_name)).scaled(51, 31)
        self.label_flag.setPixmap(pixmap)
        self.label_flag.update()








