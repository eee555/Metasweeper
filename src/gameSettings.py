from PyQt5 import QtGui
import configparser
from ui.ui_gameSettings import Ui_Form
from ui.uiComponents import RoundQDialog
from country_name import country_name
from PyQt5.QtGui import QPixmap

class ui_Form(Ui_Form):
    def __init__(self, mainWindow):
        # 设置界面的参数，不能用快捷键修改的从配置文件里来；能用快捷键修改的从mainWindow来
        self.game_setting = mainWindow.game_setting
        self.r_path = mainWindow.r_path
        # config = configparser.ConfigParser()
        # config.read(self.game_setting_path, encoding='utf-8')
        self.gameMode = mainWindow.gameMode
        self.transparency = self.game_setting.value('DEFAULT/transparency', None, int)
        # self.transparency = config.getint('DEFAULT','transparency')
        self.pixSize = mainWindow.pixSize
        self.row = mainWindow.row
        self.column = mainWindow.column
        self.mineNum = mainWindow.mineNum
        
        self.auto_replay = self.game_setting.value('DEFAULT/auto_replay', None, int)
        self.auto_notification = self.game_setting.value('DEFAULT/auto_notification', None, bool)
        self.player_identifier = self.game_setting.value('DEFAULT/player_identifier', None, str)
        self.race_identifier = self.game_setting.value('DEFAULT/race_identifier', None, str)
        self.unique_identifier = self.game_setting.value('DEFAULT/unique_identifier', None, str)
        self.country = self.game_setting.value('DEFAULT/country', None, str)
        self.autosave_video = self.game_setting.value('DEFAULT/autosave_video', None, bool)
        self.filter_forever = self.game_setting.value('DEFAULT/filter_forever', None, bool)
        self.end_then_flag = self.game_setting.value('DEFAULT/end_then_flag', None, bool)
        self.cursor_limit = self.game_setting.value('DEFAULT/cursor_limit', None, bool)
        self.board_constraint = mainWindow.board_constraint
        self.attempt_times_limit = mainWindow.attempt_times_limit
        
        self.alter = False
        
        self.Dialog = RoundQDialog(mainWindow.mainWindow)
        self.setupUi(self.Dialog)
        self.setParameter()
        self.Dialog.setWindowIcon(QtGui.QIcon (str(self.r_path.with_name('media').joinpath('cat.ico'))))
        self.pushButton_yes.clicked.connect(self.processParameter)
        self.pushButton_no.clicked.connect(self.Dialog.close)
        self.comboBox_country.resize.connect(self.set_lineedit_country_geometry)
        self.lineEdit_country.textEdited.connect(lambda x: self.set_combobox_country(x))
        self.comboBox_country.activated['QString'].connect(lambda x: self.set_country_flag(x))
        self.lineEdit_country.textEdited.connect(lambda x: self.set_country_flag(x))
        
        self.country_name = list(country_name.keys())
        self.set_combobox_country(self.lineEdit_country.text())
        self.set_country_flag(self.lineEdit_country.text())
        
    def set_country_flag(self, flag_name):
        # 设置国旗图案
        if flag_name not in country_name:
            self.label_national_flag.clear()
            self.label_national_flag.update()
        else:
            fn = country_name[flag_name]
            pixmap = QPixmap(str(self.r_path.with_name('media') / \
                                 (fn + ".svg"))).scaled(51, 31)
            self.label_national_flag.setPixmap(pixmap)
            self.label_national_flag.update()
            
        
    def set_lineedit_country_geometry(self):
        # 把lineEdit_country重叠到comboBox_country上
        QRect1 = self.comboBox_country.geometry()
        QRect2 = self.horizontalWidget_country.geometry()
        self.lineEdit_country.setGeometry(QRect1.x() + QRect2.x(),
                                          QRect1.y() + QRect2.y(),
                                          QRect1.width() - 30, # 把箭头露出来
                                          QRect1.height())
        
    def set_combobox_country(self, qtext):
        # 修改comboBox_country里的国家选项
        self.comboBox_country.clear()
        self.comboBox_country.addItems(filter(lambda x: qtext in x, self.country_name))
        

    def setParameter(self):
        self.spinBox_pixsize.setValue (self.pixSize)
        self.spinBox_auto_replay.setValue (abs(self.auto_replay))
        self.checkBox_auto_replay.setChecked(self.auto_replay >= 0)
        self.checkBox_auto_notification.setChecked(self.auto_notification)
        self.checkBox_autosave_video.setChecked(self.autosave_video)
        self.checkBox_filter_forever.setChecked(self.filter_forever)
        self.lineEdit_constraint.setText(self.board_constraint)
        self.spinBox_attempt_times_limit.setValue (self.attempt_times_limit)
        self.lineEdit_label.setText(self.player_identifier)
        self.lineEdit_race_label.setText(self.race_identifier)
        self.lineEdit_unique_label.setText(self.unique_identifier)
        self.lineEdit_country.setText(self.country)
        self.checkBox_end_then_flag.setChecked(self.end_then_flag)
        self.checkBox_cursor_limit.setChecked(self.cursor_limit)
        self.horizontalSlider_transparency.setValue (self.transparency)
        self.label_transparency_percent_value.setText(str(self.transparency))
        
        if not self.checkBox_auto_replay.isChecked():
            self.spinBox_auto_replay.setEnabled(False)
            self.label_auto_replay_percent.setEnabled(False)
        # gameMode = 0，4, 5, 6, 7, 8, 9, 10代表：
        # 标准、win7、经典无猜、强无猜、弱无猜、准无猜、强可猜、弱可猜
        self.comboBox_gamemode.setCurrentIndex([0, 999, 999, 999, 1, 4, 2, 3, 5, 6, 7][self.gameMode])
        
        self.pushButton_yes.setStyleSheet("border-image: url(" + str(self.r_path.with_name('media').joinpath('button.png')).replace("\\", "/") + ");\n"
"font: 16pt \"黑体\";\n"
"color:white;font: bold;")
        self.pushButton_no.setStyleSheet("border-image: url(" + str(self.r_path.with_name('media').joinpath('button.png')).replace("\\", "/") + ");\n"
"font: 16pt \"黑体\";\n"
"color:white;font: bold;")
        
    def processParameter(self):
        #只有点确定才能进来

        self.alter = True
        self.transparency = self.horizontalSlider_transparency.value()
        self.pixSize = self.spinBox_pixsize.value()
        v = self.spinBox_auto_replay.value()
        self.auto_replay = v if self.checkBox_auto_replay.isChecked() else -v
        self.auto_notification = self.checkBox_auto_notification.isChecked()
        self.player_identifier = self.lineEdit_label.text()
        self.race_identifier = self.lineEdit_race_label.text()
        self.unique_identifier = self.lineEdit_unique_label.text()
        self.country = self.lineEdit_country.text()
        self.autosave_video = self.checkBox_autosave_video.isChecked()
        self.filter_forever = self.checkBox_filter_forever.isChecked()
        self.board_constraint = self.lineEdit_constraint.text()
        self.attempt_times_limit = self.spinBox_attempt_times_limit.value()
        self.end_then_flag = self.checkBox_end_then_flag.isChecked() # 游戏结束后自动标雷
        self.cursor_limit = self.checkBox_cursor_limit.isChecked()
        self.gameMode = [0, 4, 6, 7, 5, 8, 9, 10][self.comboBox_gamemode.currentIndex()]
        # gameMode = 0，4, 5, 6, 7, 8, 9, 10代表：
        # 标准、win7、经典无猜、强无猜、弱无猜、准无猜、强可猜、弱可猜
        
        
        self.game_setting.set_value("DEFAULT/transparency", self.transparency)
        self.game_setting.set_value("DEFAULT/auto_replay", self.auto_replay)
        self.game_setting.set_value("DEFAULT/end_then_flag", self.end_then_flag)
        self.game_setting.set_value("DEFAULT/cursor_limit", self.cursor_limit)
        self.game_setting.set_value("DEFAULT/auto_notification", self.auto_notification)
        self.game_setting.set_value("DEFAULT/autosave_video", self.autosave_video)
        self.game_setting.set_value("DEFAULT/filter_forever", self.filter_forever)
        self.game_setting.set_value("DEFAULT/player_identifier", self.player_identifier)
        self.game_setting.set_value("DEFAULT/race_identifier", self.race_identifier)
        self.game_setting.set_value("DEFAULT/unique_identifier", self.unique_identifier)
        self.game_setting.set_value("DEFAULT/country", self.country)
        if (self.row, self.column, self.mineNum) == (8, 8, 10):
            self.game_setting.set_value("BEGINNER/gamemode", self.gameMode)
            self.game_setting.set_value("BEGINNER/board_constraint", self.board_constraint)
            self.game_setting.set_value("BEGINNER/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("BEGINNER/pixsize", self.pixSize)
        elif (self.row, self.column, self.mineNum) == (16, 16, 40):
            self.game_setting.set_value("INTERMEDIATE/gamemode", self.gameMode)
            self.game_setting.set_value("INTERMEDIATE/board_constraint", self.board_constraint)
            self.game_setting.set_value("INTERMEDIATE/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("INTERMEDIATE/pixsize", self.pixSize)
        elif (self.row, self.column, self.mineNum) == (16, 30, 99):
            self.game_setting.set_value("EXPERT/gamemode", self.gameMode)
            self.game_setting.set_value("EXPERT/board_constraint", self.board_constraint)
            self.game_setting.set_value("EXPERT/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("EXPERT/pixsize", self.pixSize)
        elif (self.row, self.column, self.mineNum) ==\
            (self.game_setting.value("CUSTOM_PRESET_4/row", None, int),
             self.game_setting.value("CUSTOM_PRESET_4/column", None, int),
             self.game_setting.value("CUSTOM_PRESET_4/mine_num", None, int)):
            self.game_setting.set_value("CUSTOM_PRESET_4/gamemode", self.gameMode)
            self.game_setting.set_value("CUSTOM_PRESET_4/board_constraint", self.board_constraint)
            self.game_setting.set_value("CUSTOM_PRESET_4/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("CUSTOM_PRESET_4/pixsize", self.pixSize)
        elif (self.row, self.column, self.mineNum) ==\
            (self.game_setting.value("CUSTOM_PRESET_5/row", None, int),
             self.game_setting.value("CUSTOM_PRESET_5/column", None, int),
             self.game_setting.value("CUSTOM_PRESET_5/mine_num", None, int)):
            self.game_setting.set_value("CUSTOM_PRESET_5/gamemode", self.gameMode)
            self.game_setting.set_value("CUSTOM_PRESET_5/board_constraint", self.board_constraint)
            self.game_setting.set_value("CUSTOM_PRESET_5/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("CUSTOM_PRESET_5/pixsize", self.pixSize)
        elif (self.row, self.column, self.mineNum) ==\
            (self.game_setting.value("CUSTOM_PRESET_6/row", None, int),
             self.game_setting.value("CUSTOM_PRESET_6/column", None, int),
             self.game_setting.value("CUSTOM_PRESET_6/mine_num", None, int)):
            self.game_setting.set_value("CUSTOM_PRESET_6/gamemode", self.gameMode)
            self.game_setting.set_value("CUSTOM_PRESET_6/board_constraint", self.board_constraint)
            self.game_setting.set_value("CUSTOM_PRESET_6/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("CUSTOM_PRESET_6/pixsize", self.pixSize)
        else:
            self.game_setting.set_value("CUSTOM/gamemode", self.gameMode)
            self.game_setting.set_value("CUSTOM/board_constraint", self.board_constraint)
            self.game_setting.set_value("CUSTOM/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("CUSTOM/pixsize", self.pixSize)

        self.game_setting.sync()
        self.Dialog.close ()

















