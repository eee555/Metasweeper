from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtCore import QTranslator
# from os import environ
from PyQt5.QtWidgets import QApplication
import configparser
from PyQt5.QtGui import QPalette, QPixmap, QIcon
from ui.ui_main_board import Ui_MainWindow
from pathlib import Path
from gameScoreBoard import gameScoreBoardManager
from country_name import country_name
import os
from typing import List, Tuple

version = "元3.2.2"

class IniConfig:
    def __init__(self, file_path):
        """
        初始化 IniConfig 对象
        :param file_path: 配置文件的路径
        """
        self.file_path = file_path
        # QSettings的键名是无序的，无法使用
        # ConfigParser会将%转义，而这里要求%是原义
        self.config = configparser.RawConfigParser()
        self.config.default_section = ""
        # 如果文件不存在则创建
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding="utf-8"):
                pass
        # 读取配置文件
        self.config.read(file_path, encoding="utf-8")

    def _parse_key(self, key):
        """
        解析 "section/key" 格式的键，返回节和键
        :param key: 格式为 "section/key" 的键
        :return: 节和键的元组
        """
        parts = key.split('/', 1)
        if len(parts) == 2:
            section, key = parts
        else:
            section = 'DEFAULT'
            key = parts[0]
        return section, key

    def value(self, key, default=None, value_type=str):
        """
        根据键获取值，如果键不存在则返回默认值
        :param key: 格式为 "section/key" 的键
        :param default: 键不存在时的默认值，默认为 None
        :param value_type: 值的类型，默认为字符串类型
        :return: 获取到的值或默认值
        """
        section, key = self._parse_key(key)
        if not self.config.has_section(section):
            return default
        if self.config.has_option(section, key):
            if value_type == int:
                return self.config.getint(section, key)
            elif value_type == float:
                return self.config.getfloat(section, key)
            elif value_type == bool:
                return self.config.getboolean(section, key)
            else:
                return self.config.get(section, key)
        else:
            return default

    def get_or_set_value(self, key, default=None, value_type=str):
        """
        获取值，如果键不存在则设置默认值并返回
        :param key: 格式为 "section/key" 的键
        :param default: 键不存在时的默认值，默认为 None
        :param value_type: 值的类型，默认为字符串类型
        :return: 获取到的值或默认值
        """
        section, key = self._parse_key(key)
        value = self.value(key=f"{section}/{key}", default=default, value_type=value_type)
        if value == default:
            self.set_value(key=f"{section}/{key}", value=default)
        return value
    
    def get_or_set_section(self, section, default: List[Tuple[str,str]], 
                           force_add=False) -> List[Tuple[str,str]]:
        """
        获取或设置 section 的内容。如果 section 为空，则重新设置为默认内容。
        :param section: 要获取或设置的 section 名称
        :param default: 默认的 section 内容，默认为 section_dict
        :param force_add: 是否强制补全default中的所有键
        :return: section 的内容
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
            for (key, value) in default:
                self.config.set(section, str(key), str(value))
            return default
        if len(self.config[section]) == 0:
            for (key, value) in default:
                self.config.set(section, str(key), str(value))
            return default
        if force_add:
            for (key, value) in default:
                self.get_or_set_value(f"{section}/{key}", str(value))
        return list(self.config.items(section))

    def set_value(self, key, value):
        """
        设置键值对
        :param key: 格式为 "section/key" 的键
        :param value: 要设置的值
        """
        section, key = self._parse_key(key)
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
        
    
    def set_section(self, section, section_value: List[Tuple[str,str]]):
        """
        设置 section 的内容。全量替换。假如有重复的键，例如key，改为key, key(2), key(3)...
        key假如为空字符串，替换为行号的id
        :param section: 要获取或设置的 section 名称
        :param section_value: section 内容
        """
        # key假如为空字符串，替换为行号的id
        section_value = [(idv, v[1]) if v[0] == "" else v for (idv, v) in enumerate(section_value)]
        # 假如有重复的键，例如key，改为key, key(2), key(3)...
        key_set = set()
        for (idv, v) in enumerate(section_value):
            key = v[0]
            if key not in key_set:
                key_set.add(key)
            else:
                idx = 2
                while (new_key := key + f"({idx})") in key_set:
                    idx += 1
                key_set.add(new_key)
                section_value[idv] = (new_key, v[1])
                    
        if not self.config.has_section(section):
            self.config.add_section(section)
            
        # 遍历并删除每个 option
        for option in list(self.config[section].keys()):
            self.config.remove_option(section, option)
        
        for (key, value) in section_value:
            self.set_value(f"{section}/{key}", str(value))
    
    def sync(self):
        """
        将内存中的配置写入文件
        """
        with open(self.file_path, 'w', encoding="utf-8") as f:
            self.config.write(f)

class Ui_MainWindow(Ui_MainWindow):
    minimum_counter = 0 # 最小化展示窗口有关
    # windowSizeState = 'loose'  # loose or tight
    def __init__(self, MainWindow, args):
        self.mainWindow = MainWindow
        self.setupUi(self.mainWindow)
                
        
        # 设置全局路径，需要读写权限
        # WindowsPath('f:/path/solvable-minesweeper/src/main.py')
        r_path = Path(args[0])
        # 检查是否有写入权限
        if self._can_write_to(r_path.with_name('gameSetting.ini')):
            self.setting_path = r_path.parent
        else:
            # 没权限，改用 %APPDATA%\你的程序名\
            self.setting_path = Path(os.environ['APPDATA']) / ('MetaMineSweeper' + version[1:])
            self.setting_path.mkdir(parents=True, exist_ok=True)
        self.r_path = r_path
            
        # 录像保存位置
        replay_path_dir = self.setting_path / 'replay'
        self.replay_path = str(replay_path_dir)
        replay_path_dir.mkdir(parents=True, exist_ok=True)
        # 记录了全局游戏设置
        game_setting_path = str(self.setting_path / 'gameSetting.ini')
        self.game_setting = IniConfig(game_setting_path)
        # 个人记录，用来弹窗
        record_path = str(self.setting_path / 'record.ini')
        self.record_setting = IniConfig(record_path)


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


        self.readPredefinedBoardPara()
        self.read_or_create_game_setting()
        self.initMineArea()
        self.retranslateUi(MainWindow)

        self.trans = QTranslator()


        # 记录了计数器的配置，显示哪些指标等等
        score_board_path = str(self.setting_path / 'scoreBoardSetting.ini')
        self.score_board_setting = IniConfig(score_board_path)
        self.score_board_manager = gameScoreBoardManager(r_path, self.score_board_setting,
                                                         self.game_setting,
                                                         self.pixSize, MainWindow)
        # self.score_board_manager.ui.QWidget.move(_scoreBoardTop, _scoreBoardLeft)


        # self.importLEDPic() # 导入图片
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
        if hasattr(self, "pixmapNumPix"):
            self.pixmapNum = {key:value.copy().scaled(int(pixSize * 1.5), int(pixSize * 1.5)) 
                              for key,value in self.pixmapNumPix.items()}
            self.pixmapLEDNum = {key:value.copy().scaled(pixSize, int(pixSize * 1.75)) 
                                 for key,value in self.pixmapLEDNumPix.items()}
        else:
            self.importLEDPic(pixSize)


    def readPredefinedBoardPara(self):
        # 从配置中更新出快捷键1, 2, 3, 4、5、6的定义(0是自定义)
        s = [
            ("gamemode", 0),
            ("row", 8),
            ("column", 8),
            ("pixsize", 20),
            ("mine_num", 10),
            ("board_constraint", ""),
            ("attempt_times_limit", 100000),
            ]
        s = self.game_setting.get_or_set_section("CUSTOM", s, True)
        self.predefinedBoardPara[0] = { k: int(v) if isinstance(v, str) and v.isdigit() else v for (k, v) in s }
        s = [
            ("gamemode", 0),
            ("row", 8),
            ("column", 8),
            ("pixsize", 20),
            ("mine_num", 10),
            ("board_constraint", ""),
            ("attempt_times_limit", 100000),
            ]
        s = self.game_setting.get_or_set_section("BEGINNER", s, True)
        self.predefinedBoardPara[1] = { k: int(v) if isinstance(v, str) and v.isdigit() else v for (k, v) in s }
        s = [
            ("gamemode", 0),
            ("row", 16),
            ("column", 16),
            ("pixsize", 20),
            ("mine_num", 40),
            ("board_constraint", ""),
            ("attempt_times_limit", 100000),
            ]
        s = self.game_setting.get_or_set_section("INTERMEDIATE", s, True)
        self.predefinedBoardPara[2] = { k: int(v) if isinstance(v, str) and v.isdigit() else v for (k, v) in s }
        s = [
            ("gamemode", 0),
            ("row", 16),
            ("column", 30),
            ("pixsize", 20),
            ("mine_num", 99),
            ("board_constraint", ""),
            ("attempt_times_limit", 100000),
            ]
        s = self.game_setting.get_or_set_section("EXPERT", s, True)
        self.predefinedBoardPara[3] = { k: int(v) if isinstance(v, str) and v.isdigit() else v for (k, v) in s }
        s = [
            ("gamemode", 5),
            ("row", 16),
            ("column", 16),
            ("pixsize", 20),
            ("mine_num", 72),
            ("board_constraint", ""),
            ("attempt_times_limit", 100000),
            ]
        s = self.game_setting.get_or_set_section("CUSTOM_PRESET_4", s, True)
        self.predefinedBoardPara[4] = { k: int(v) if isinstance(v, str) and v.isdigit() else v for (k, v) in s }
        s = [
            ("gamemode", 5),
            ("row", 16),
            ("column", 30),
            ("pixsize", 20),
            ("mine_num", 120),
            ("board_constraint", ""),
            ("attempt_times_limit", 100000),
            ]
        s = self.game_setting.get_or_set_section("CUSTOM_PRESET_5", s, True)
        self.predefinedBoardPara[5] = { k: int(v) if isinstance(v, str) and v.isdigit() else v for (k, v) in s }
        s = [
            ("gamemode", 5),
            ("row", 24),
            ("column", 36),
            ("pixsize", 20),
            ("mine_num", 200),
            ("board_constraint", ""),
            ("attempt_times_limit", 100000),
            ]
        s = self.game_setting.get_or_set_section("CUSTOM_PRESET_6", s, True)
        self.predefinedBoardPara[6] = { k: int(v) if isinstance(v, str) and v.isdigit() else v for (k, v) in s }


    def minimumWindow(self):
        # 最小化展示窗口，并固定尺寸
        self.label.setFixedSize(QtCore.QSize(self.pixSize*self.column,
                                             self.pixSize*self.row))
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
        self.game_setting.set_value("DEFAULT/language", language)
        self.game_setting.sync()
        # mm.updata_ini(self.game_setting_path, [("DEFAULT", "language", language)])
        self.language = language


    def read_or_create_game_setting(self):
        '''
        读取或创建游戏设置。
        '''
        transparency = self.game_setting.get_or_set_value('DEFAULT/transparency', 100, int)
        self.mainWindow.setWindowOpacity(transparency / 100)
        mainWinTop = self.game_setting.get_or_set_value("DEFAULT/mainwintop", 100, int)
        mainWinLeft = self.game_setting.get_or_set_value("DEFAULT/mainwinleft", 200, int)
        
        window_width = self.mainWindow.width()
        window_height = self.mainWindow.height()
        screen = QtGui.QGuiApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        if mainWinLeft < 0:
            mainWinLeft = 0
        elif mainWinLeft + window_width > screen_width:
            mainWinLeft = screen_width - window_width
        if mainWinTop < 0:
            mainWinTop = 0
        elif mainWinTop + window_height > screen_height:
            mainWinTop = screen_height - window_height
        # 考虑设置导致窗口移出屏幕外（例如使用拓展屏）。然而执行此初始化方法时，屏幕尚未
        # 画局面，因此尺寸较完全初始化后偏小，仍有可能有半个窗口在屏幕外，当然这不影响使用。
        self.mainWindow.move(mainWinLeft, mainWinTop)
        
        self._row = self.game_setting.get_or_set_value("DEFAULT/row", 16, int)
        self._column = self.game_setting.get_or_set_value("DEFAULT/column", 30, int)
        self._minenum = self.game_setting.get_or_set_value("DEFAULT/minenum", 99, int)
        self.mineUnFlagedNum = self.minenum
        # “自动重开比例”，大于等于该比例时，不自动重开。负数表示禁用。0相当于禁用，但可以编辑。
        self.auto_replay = self.game_setting.get_or_set_value("DEFAULT/auto_replay", 30, int)
        # self.allow_auto_replay = self.game_setting.get_or_set_value("DEFAULT/allow_auto_replay", True, bool)
        self.auto_notification = self.game_setting.get_or_set_value("DEFAULT/auto_notification", True, bool)
        self.player_identifier = self.game_setting.get_or_set_value("DEFAULT/player_identifier", "匿名玩家(anonymous player)", str)
        self.race_identifier = self.game_setting.get_or_set_value("DEFAULT/race_identifier", "", str)
        self.unique_identifier = self.game_setting.get_or_set_value("DEFAULT/unique_identifier", "", str)
        self.country = self.game_setting.get_or_set_value("DEFAULT/country", "", str)
        self.autosave_video = self.game_setting.get_or_set_value("DEFAULT/autosave_video", True, bool)
        self.autosave_video_set = self.game_setting.get_or_set_value("DEFAULT/autosave_video_set", False, bool)
        self.filter_forever = self.game_setting.get_or_set_value("DEFAULT/filter_forever", False, bool)
        self.language = self.game_setting.get_or_set_value("DEFAULT/language", "en_US", str)
        self.end_then_flag = self.game_setting.get_or_set_value("DEFAULT/end_then_flag", True, bool)
        self.cursor_limit = self.game_setting.get_or_set_value("DEFAULT/cursor_limit", False, bool)
        match (self.row, self.column, self.minenum):
            case (8, 8, 10):
                level = "BEGINNER"
            case (16, 16, 40):
                level = "INTERMEDIATE"
            case (16, 30, 99):
                level = "EXPERT"
            case _:
                level = "CUSTOM"
        self.pixSize = self.game_setting.get_or_set_value(f"{level}/pixsize", 20, int)
        self.label.set_rcp(self.row, self.column, self.pixSize)
        self.gameMode = self.game_setting.get_or_set_value(f"{level}/gamemode", 0, int)
        self.board_constraint = self.game_setting.get_or_set_value(f"{level}/board_constraint", "", str)
        self.attempt_times_limit = self.game_setting.get_or_set_value(f"{level}/attempt_times_limit", 100000, int)
        self.game_setting.sync()

    def read_or_create_record(self):
        record_key_name_list = ["BFLAG", "BNF", "BWIN7", "BSS", "BWS", "BCS", "BTBS", "BSG",
                                "BWG", "IFLAG", "INF", "IWIN7", "ISS", "IWS", "ICS", "ITBS",
                                "ISG", "IWG", "EFLAG", "ENF", "EWIN7", "ESS", "EWS", "ECS",
                                "ETBS", "ESG", "EWG"]
        self.record_key_name_list = record_key_name_list + ["BEGINNER", "INTERMEDIATE", "EXPERT"]
        # self.record = {}
        record_norm = [
            ('rtime', 999.999),
            ('bbbv_s', 0.000),
            ('stnb', 0.000),
            ('ioe', 0.000),
            ('path', 999999.999),
            ('rqp', 999999.999),
            ]
        for k in record_key_name_list:
            self.record_setting.get_or_set_section(k, record_norm, True)
        self.record_setting.get_or_set_section("BEGINNER", 
                                               [(i, 999.999) for i in range(1, 55)],
                                               True)
        self.record_setting.get_or_set_section("INTERMEDIATE",
                                               [(i, 999.999) for i in range(1, 217)], 
                                               True)
        self.record_setting.get_or_set_section("EXPERT", 
                                               [(i, 999.999) for i in range(1, 382)], 
                                               True)
        self.record_setting.sync()

    def set_country_flag(self, country = None):
        '''
        设置右下角国旗图案。尽一切可能解析录像中的国旗。
        例如，在vsweep中，国家是用户手动输入的，可能出现”中国“、”China“、”china“、”CN“、
        ”cn“等情况，全部应该要正确解析。
        不修改self.country变量
        '''
        if country == None:
            country = self.country
        if country == None:
            self.label_flag.clear()
            self.label_flag.update()
            return
        if country not in country_name:
            country = country.capitalize()
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

    def _can_write_to(self, path: Path) -> bool:
        """检查是否有权限写入目标路径"""
        try:
            # 若文件不存在则尝试新建
            if not path.exists():
                path.touch(exist_ok=True)
                path.unlink()  # 删掉临时文件
            else:
                # 若文件存在则尝试写入一行
                with open(path, 'a', encoding='utf-8') as f:
                    f.write('')
            return True
        except:
            return False






