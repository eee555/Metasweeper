from ui.ui_gameSettingShortcuts import Ui_Form
import configparser
from PyQt5 import QtGui
from ui.uiComponents import RoundQDialog

# 继承自ui文件生成的原始的.py
# 减少ui文件生成的原始的.py的改动

class myGameSettingShortcuts(Ui_Form):
    def __init__(self, game_setting, ico_path, r_path, parent):
        self.game_setting = game_setting
        self.r_path = r_path
        self.Dialog = RoundQDialog(parent)
        self.setupUi(self.Dialog)
        self.setParameter()
        self.Dialog.setWindowIcon(QtGui.QIcon (ico_path))
        self.pushButton.clicked.connect(self.processParameter)
        self.pushButton_2.clicked.connect(self.Dialog.close)
        self.alter = False

    def setParameter(self):
        # modTable = [0,1,4,2,3,5,6,7]
        modTable = [0,0,0,0,1,4,2,3,5,6,7]
        self.comboBox_gamemode4.setCurrentIndex(modTable[self.game_setting.value("CUSTOM_PRESET_4/gamemode", None, int)])
        self.spinBox_height4.setProperty("value", self.game_setting.value("CUSTOM_PRESET_4/row", None, int))
        self.spinBox_width4.setProperty("value", self.game_setting.value("CUSTOM_PRESET_4/column", None, int))
        self.spinBox_pixsize4.setProperty("value", self.game_setting.value("CUSTOM_PRESET_4/pixsize", None, int))
        self.spinBox_attempt_times_limit4.setProperty("value", self.game_setting.value("CUSTOM_PRESET_4/attempt_times_limit", None, int))
        self.spinBox_minenum4.setProperty("value", self.game_setting.value("CUSTOM_PRESET_4/mine_num", None, int))
        self.lineEdit_constraint4.setProperty("value", self.game_setting.value("CUSTOM_PRESET_4/board_constraint", None, str))

        self.comboBox_gamemode5.setCurrentIndex(modTable[self.game_setting.value("CUSTOM_PRESET_5/gamemode", None, int)])
        self.spinBox_height5.setProperty("value", self.game_setting.value("CUSTOM_PRESET_5/row", None, int))
        self.spinBox_width5.setProperty("value", self.game_setting.value("CUSTOM_PRESET_5/column", None, int))
        self.spinBox_pixsize5.setProperty("value", self.game_setting.value("CUSTOM_PRESET_5/pixsize", None, int))
        self.spinBox_attempt_times_limit5.setProperty("value", self.game_setting.value("CUSTOM_PRESET_5/attempt_times_limit", None, int))
        self.spinBox_minenum5.setProperty("value", self.game_setting.value("CUSTOM_PRESET_5/mine_num", None, int))
        self.lineEdit_constraint5.setProperty("value", self.game_setting.value("CUSTOM_PRESET_5/board_constraint", None, str))

        self.comboBox_gamemode6.setCurrentIndex(modTable[self.game_setting.value("CUSTOM_PRESET_6/gamemode", None, int)])
        self.spinBox_height6.setProperty("value", self.game_setting.value("CUSTOM_PRESET_6/row", None, int))
        self.spinBox_width6.setProperty("value", self.game_setting.value("CUSTOM_PRESET_6/column", None, int))
        self.spinBox_pixsize6.setProperty("value", self.game_setting.value("CUSTOM_PRESET_6/pixsize", None, int))
        self.spinBox_attempt_times_limit6.setProperty("value", self.game_setting.value("CUSTOM_PRESET_6/attempt_times_limit", None, int))
        self.spinBox_minenum6.setProperty("value", self.game_setting.value("CUSTOM_PRESET_6/mine_num", None, int))
        self.lineEdit_constraint6.setProperty("value", self.game_setting.value("CUSTOM_PRESET_6/board_constraint", None, str))

        self.pushButton.setStyleSheet("border-image: url(" + str(self.r_path.with_name('media').joinpath('button.png')).replace("\\", "/") + ");\n"
"font: 16pt \"黑体\";\n"
"color:white;font: bold;")
        self.pushButton_2.setStyleSheet("border-image: url(" + str(self.r_path.with_name('media').joinpath('button.png')).replace("\\", "/") + ");\n"
"font: 16pt \"黑体\";\n"
"color:white;font: bold;")
        
    def processParameter(self):
        #只有点确定才能进来
        self.alter = True

        # modTable = [0,1,3,4,2,5,6,7]
        modTable = [0,4,6,7,5,8,9,10]
        self.game_setting.set_value("CUSTOM_PRESET_4/gamemode", modTable[self.comboBox_gamemode4.currentIndex()])
        self.game_setting.set_value("CUSTOM_PRESET_4/board_constraint", self.lineEdit_constraint4.text())
        self.game_setting.set_value("CUSTOM_PRESET_4/attempt_times_limit", self.spinBox_attempt_times_limit4.value())
        self.game_setting.set_value("CUSTOM_PRESET_4/pixsize", self.spinBox_pixsize4.value())
        self.game_setting.set_value("CUSTOM_PRESET_4/row", self.spinBox_height4.value())
        self.game_setting.set_value("CUSTOM_PRESET_4/column", self.spinBox_width4.value())
        self.game_setting.set_value("CUSTOM_PRESET_4/mine_num", self.spinBox_minenum4.value())

        self.game_setting.set_value("CUSTOM_PRESET_5/gamemode", modTable[self.comboBox_gamemode5.currentIndex()])
        self.game_setting.set_value("CUSTOM_PRESET_5/board_constraint", self.lineEdit_constraint5.text())
        self.game_setting.set_value("CUSTOM_PRESET_5/attempt_times_limit", self.spinBox_attempt_times_limit5.value())
        self.game_setting.set_value("CUSTOM_PRESET_5/pixsize", self.spinBox_pixsize5.value())
        self.game_setting.set_value("CUSTOM_PRESET_5/row", self.spinBox_height5.value())
        self.game_setting.set_value("CUSTOM_PRESET_5/column", self.spinBox_width5.value())
        self.game_setting.set_value("CUSTOM_PRESET_5/mine_num", self.spinBox_minenum5.value())

        self.game_setting.set_value("CUSTOM_PRESET_6/gamemode", modTable[self.comboBox_gamemode6.currentIndex()])
        self.game_setting.set_value("CUSTOM_PRESET_6/board_constraint", self.lineEdit_constraint6.text())
        self.game_setting.set_value("CUSTOM_PRESET_6/attempt_times_limit", self.spinBox_attempt_times_limit6.value())
        self.game_setting.set_value("CUSTOM_PRESET_6/pixsize", self.spinBox_pixsize6.value())
        self.game_setting.set_value("CUSTOM_PRESET_6/row", self.spinBox_height6.value())
        self.game_setting.set_value("CUSTOM_PRESET_6/column", self.spinBox_width6.value())
        self.game_setting.set_value("CUSTOM_PRESET_6/mine_num", self.spinBox_minenum6.value())

        self.Dialog.close ()








