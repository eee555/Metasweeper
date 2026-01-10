from PyQt5 import QtGui
from ui.ui_about import Ui_Form
from ui.uiComponents import RoundQDialog
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt

class ui_Form(Ui_Form):
    def __init__(self, r_path, parent):
        # 关于界面，继承一下就好
        self.Dialog = RoundQDialog(parent)
        self.setupUi (self.Dialog)
        
        # 空格键快捷键关闭这个窗口。回车不需要设置，在ui文件中已经设置。
        QShortcut(QKeySequence("Space"),  self.Dialog, activated=self.pushButton.click)

