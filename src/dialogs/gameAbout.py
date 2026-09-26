from PySide6 import QtGui
from ui.ui_about import Ui_Form
from ui.uiComponents import RoundQDialog
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import Qt
from utils.path_utils import resource_path


class ui_Form(Ui_Form):
    def __init__(self, parent):
        self.Dialog = RoundQDialog(parent)
        self.setupUi(self.Dialog)

        m = resource_path('media').as_posix()
        self.label_10.setStyleSheet(
            self.label_10.styleSheet().replace("url(media/", f"url({m}/"))
        self.label_12.setStyleSheet(
            self.label_12.styleSheet().replace("url(media/", f"url({m}/"))
        icon_path = str(resource_path('media') / 'cat.ico')
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(icon_path),
                       QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.Dialog.setWindowIcon(icon)

        # 空格键快捷键关闭这个窗口。回车不需要设置，在ui文件中已经设置。
        QShortcut(QKeySequence("Space"), self.Dialog,
                  activated=self.pushButton.click)
