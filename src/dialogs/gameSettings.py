from PySide6 import QtGui
import configparser
from ui.ui_gameSettings import Ui_Form
from ui.uiComponents import RoundQDialog
from country_name import country_name
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from PySide6.QtCore import QSortFilterProxyModel
from PySide6.QtWidgets import QComboBox
from config.constants import BOARD_BEGINNER, BOARD_INTERMEDIATE, BOARD_EXPERT
from utils.path_utils import resource_path


class ui_Form(Ui_Form):
    def __init__(self, mainWindow):
        # 设置界面的参数，不能用快捷键修改的从配置文件里来；能用快捷键修改的从mainWindow来
        self.game_setting = mainWindow.game_setting
        # config = configparser.ConfigParser()
        # config.read(self.game_setting_path, encoding='utf-8')
        self.gameMode = mainWindow.gameMode
        self.pixSize = mainWindow.pixSize
        self.row = mainWindow.row
        self.column = mainWindow.column
        self.minenum = mainWindow.minenum

        self.auto_replay = self.game_setting.value(
            'DEFAULT/auto_replay', None, int)
        self.auto_notification = self.game_setting.value(
            'DEFAULT/auto_notification', None, bool)
        self.player_identifier = self.game_setting.value(
            'DEFAULT/player_identifier', None, str)
        self.race_identifier = self.game_setting.value(
            'DEFAULT/race_identifier', None, str)
        self.unique_identifier = self.game_setting.value(
            'DEFAULT/unique_identifier', None, str)
        self.country = self.game_setting.value('DEFAULT/country', None, str)
        self.autosave_video = self.game_setting.value(
            'DEFAULT/autosave_video', None, bool)
        self.autosave_video_set = self.game_setting.value(
            'DEFAULT/autosave_video_set', None, bool)
        self.end_then_flag = self.game_setting.value(
            'DEFAULT/end_then_flag', None, bool)
        self.cursor_limit = self.game_setting.value(
            'DEFAULT/cursor_limit', None, bool)
        self.board_constraint = mainWindow.board_constraint
        self.attempt_times_limit = mainWindow.attempt_times_limit

        self.alter = False

        self.Dialog = RoundQDialog(mainWindow.mainWindow)
        self.setupUi(self.Dialog)
        for combo_box in self.Dialog.findChildren(QComboBox):
            combo_box.view().setStyleSheet("""
                QListView {
                    background-color: #f4f4f4;
                    color: #3d3d3d;
                }
                QListView::item:selected {
                    background-color: #c7e3fa;
                    color: #3d3d3d;
                }
                QListView::item:hover {
                    background-color: #dceeff;
                    color: #3d3d3d;
                }
            """)
        # self.Dialog.setWindowIcon(QtGui.QIcon (str(self.r_path.with_name('media').joinpath('cat.ico'))))

        self.pushButton_yes.clicked.connect(self.processParameter)
        self.pushButton_no.clicked.connect(self.Dialog.close)
        # self.comboBox_country.activated['QString'].connect(lambda x: self.onchange_combobox_country(x))
        self.country_name = list(country_name.keys())
        self.comboBox_country.lineEdit().setAlignment(Qt.AlignCenter)
        self.comboBox_country.editTextChanged.connect(
            self.onchange_combobox_country)
        self.comboBox_country.lineEdit().setText(self.country)
        self.comboBox_country.addItems(self.country_name)

        self.setParameter()

    def set_country_flag(self, flag_name):
        # 设置国旗图案
        if flag_name not in country_name:
            self.label_national_flag.clear()
            self.label_national_flag.update()
        else:
            fn = country_name[flag_name]
            pixmap = QPixmap(str(resource_path('media') /
                                 (fn + ".svg"))).scaled(51, 31)
            self.label_national_flag.setPixmap(pixmap)
            self.label_national_flag.update()

    # 修改comboBox_country里的国家选项的回调

    def onchange_combobox_country(self, qtext):
        # 记录光标位置
        line_edit = self.comboBox_country.lineEdit()
        cursor_position = line_edit.cursorPosition()

        self.comboBox_country.blockSignals(True)  # 避免清空时再次触发信号
        self.comboBox_country.clear()
        # 过滤逻辑：只保留包含输入的国家（不区分大小写）
        filtered = [c for c in self.country_name if qtext.lower() in c.lower()]
        # 重新填充
        self.comboBox_country.addItems(filtered)
        # 恢复用户已输入的文本
        self.comboBox_country.setEditText(qtext)
        line_edit.setCursorPosition(cursor_position)
        self.comboBox_country.blockSignals(False)
        self.set_country_flag(qtext)

    def setParameter(self):
        self.spinBox_pixsize.setValue(self.pixSize)
        self.spinBox_auto_replay.setValue(abs(self.auto_replay))
        self.checkBox_auto_replay.setChecked(self.auto_replay >= 0)
        self.checkBox_auto_notification.setChecked(self.auto_notification)
        self.checkBox_autosave_video.setChecked(self.autosave_video)
        self.checkBox_autosave_video_set.setChecked(self.autosave_video_set)
        self.lineEdit_constraint.setText(self.board_constraint)
        self.spinBox_attempt_times_limit.setValue(self.attempt_times_limit)
        self.lineEdit_label.setText(self.player_identifier)
        self.lineEdit_race_label.setText(self.race_identifier)
        self.lineEdit_unique_label.setText(self.unique_identifier)
        # self.lineEdit_country.setText(self.country)
        # self.onchange_combobox_country(self.country)
        self.comboBox_country.setCurrentText(self.country)
        self.checkBox_end_then_flag.setChecked(self.end_then_flag)
        self.checkBox_cursor_limit.setChecked(self.cursor_limit)

        if not self.checkBox_auto_replay.isChecked():
            self.spinBox_auto_replay.setEnabled(False)
            self.label_auto_replay_percent.setEnabled(False)
        # gameMode = 0，4, 5, 6, 7, 8, 9, 10代表：
        # 标准、win7、经典无猜、强无猜、弱无猜、准无猜、强可猜、弱可猜
        self.comboBox_gamemode.setCurrentIndex(
            [0, 999, 999, 999, 1, 4, 2, 3, 5, 6, 7][self.gameMode])

    def processParameter(self):
        # 只有点确定才能进来

        self.alter = True
        self.pixSize = self.spinBox_pixsize.value()
        v = self.spinBox_auto_replay.value()
        self.auto_replay = v if self.checkBox_auto_replay.isChecked() else -v
        self.auto_notification = self.checkBox_auto_notification.isChecked()
        self.player_identifier = self.lineEdit_label.text().strip()
        self.race_identifier = self.lineEdit_race_label.text().strip()
        self.unique_identifier = self.lineEdit_unique_label.text().strip()
        self.country = self.comboBox_country.currentText()
        self.autosave_video = self.checkBox_autosave_video.isChecked()
        self.autosave_video_set = self.checkBox_autosave_video_set.isChecked()
        self.board_constraint = self.lineEdit_constraint.text()
        self.attempt_times_limit = self.spinBox_attempt_times_limit.value()
        self.end_then_flag = self.checkBox_end_then_flag.isChecked()  # 游戏结束后自动标雷
        self.cursor_limit = self.checkBox_cursor_limit.isChecked()
        self.gameMode = [0, 4, 6, 7, 5, 8, 9,
                         10][self.comboBox_gamemode.currentIndex()]
        # gameMode = 0，4, 5, 6, 7, 8, 9, 10代表：
        # 标准、win7、经典无猜、强无猜、弱无猜、准无猜、强可猜、弱可猜

        self.game_setting.set_value("DEFAULT/auto_replay", self.auto_replay)
        self.game_setting.set_value(
            "DEFAULT/end_then_flag", self.end_then_flag)
        self.game_setting.set_value("DEFAULT/cursor_limit", self.cursor_limit)
        self.game_setting.set_value(
            "DEFAULT/auto_notification", self.auto_notification)
        self.game_setting.set_value(
            "DEFAULT/autosave_video", self.autosave_video)
        self.game_setting.set_value(
            "DEFAULT/autosave_video_set", self.autosave_video_set)
        self.game_setting.set_value(
            "DEFAULT/player_identifier", self.player_identifier)
        self.game_setting.set_value(
            "DEFAULT/race_identifier", self.race_identifier)
        self.game_setting.set_value(
            "DEFAULT/unique_identifier", self.unique_identifier)
        self.game_setting.set_value("DEFAULT/country", self.country)
        if (self.row, self.column, self.minenum) == BOARD_BEGINNER:
            self.game_setting.set_value("BEGINNER/gamemode", self.gameMode)
            self.game_setting.set_value(
                "BEGINNER/board_constraint", self.board_constraint)
            self.game_setting.set_value(
                "BEGINNER/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("BEGINNER/pixsize", self.pixSize)
        elif (self.row, self.column, self.minenum) == BOARD_INTERMEDIATE:
            self.game_setting.set_value("INTERMEDIATE/gamemode", self.gameMode)
            self.game_setting.set_value(
                "INTERMEDIATE/board_constraint", self.board_constraint)
            self.game_setting.set_value(
                "INTERMEDIATE/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("INTERMEDIATE/pixsize", self.pixSize)
        elif (self.row, self.column, self.minenum) == BOARD_EXPERT:
            self.game_setting.set_value("EXPERT/gamemode", self.gameMode)
            self.game_setting.set_value(
                "EXPERT/board_constraint", self.board_constraint)
            self.game_setting.set_value(
                "EXPERT/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("EXPERT/pixsize", self.pixSize)
        else:
            self.game_setting.set_value("CUSTOM/gamemode", self.gameMode)
            self.game_setting.set_value(
                "CUSTOM/board_constraint", self.board_constraint)
            self.game_setting.set_value(
                "CUSTOM/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("CUSTOM/pixsize", self.pixSize)

        self.game_setting.sync()
        self.Dialog.close()
