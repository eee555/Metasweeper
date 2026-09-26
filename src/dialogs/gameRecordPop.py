from PySide6 import QtCore, QtGui
from ui.ui_record_pop import Ui_Form
from ui.uiComponents import RoundQDialog
from PySide6.QtGui import QKeySequence, QShortcut
from utils.path_utils import resource_path


class ui_Form(Ui_Form):
    def __init__(self, del_items: list, pb_bbbv, nf_items, parent):
        self.Dialog = RoundQDialog(parent)
        self.setupUi(self.Dialog)
        self.Dialog.setWindowIcon(QtGui.QIcon(
            str(resource_path('media') / 'cat.ico')))

        # 空格键快捷键关闭这个窗口。回车不需要设置，在ui文件中已经设置。
        QShortcut(QKeySequence("Space"),  self.Dialog,
                  activated=self.pushButton.click)

        for i in nf_items:
            eval(f"self.label_{i}.setText('NF ' + self.label_{i}.text())")
        for i in del_items:
            eval("self.widget" + str(i) + ".setHidden(True)")

        # self.verticalLayout = QtWidgets.QVBoxLayout(self.Dialog)
        # self.verticalLayout.setObjectName("verticalLayout")

        m = resource_path('media')
        self.label1.setStyleSheet("border-image: url(" +
                                  str(m.joinpath('rtime.svg')).replace("\\", "/") + ");")
        self.label3.setStyleSheet("border-image: url(" +
                                  str(m.joinpath('bbbv_s.svg')).replace("\\", "/") + ");")
        self.label5.setStyleSheet("border-image: url(" +
                                  str(m.joinpath('stnb.svg')).replace("\\", "/") + ");")
        self.label7.setStyleSheet("border-image: url(" +
                                  str(m.joinpath('ioe.svg')).replace("\\", "/") + ");")
        self.label9.setStyleSheet("border-image: url(" +
                                  str(m.joinpath('path_record.svg')).replace("\\", "/") + ");")
        self.label11.setStyleSheet("border-image: url(" +
                                   str(m.joinpath('rqp.svg')).replace("\\", "/") + ");")
        self.label13.setStyleSheet("border-image: url(" +
                                   str(m.joinpath('pb.svg')).replace("\\", "/") + ");")
        self.label14.setStyleSheet("border-image: url(" +
                                   str(m.joinpath('pb.svg')).replace("\\", "/") + ");")
        self.label15.setStyleSheet("border-image: url(" +
                                   str(m.joinpath('pb.svg')).replace("\\", "/") + ");")

        self.label__13.setText(str(pb_bbbv) + " bv")
        self.label__14.setText(str(pb_bbbv) + " bv")
        self.label__15.setText(str(pb_bbbv) + " bv")

        # self.Dialog.setFixedSize(self.Dialog.minimumSize())
