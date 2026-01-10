from PyQt5 import QtCore, QtGui
from ui.ui_record_pop import Ui_Form
from ui.uiComponents import RoundQDialog
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence

class ui_Form(Ui_Form):
    def __init__(self, r_path, del_items: list, pb_bbbv, nf_items, parent):
        self.Dialog = RoundQDialog(parent)
        self.setupUi(self.Dialog)
        self.Dialog.setWindowIcon (QtGui.QIcon (str(r_path.with_name('media').joinpath('cat.ico'))))
        
        # 空格键快捷键关闭这个窗口。回车不需要设置，在ui文件中已经设置。
        QShortcut(QKeySequence("Space"),  self.Dialog, activated=self.pushButton.click)
        
        for i in nf_items:
            eval(f"self.label_{i}.setText('NF ' + self.label_{i}.text())")
        for i in del_items:
            eval("self.widget" + str(i) + ".setHidden(True)")
            
        # self.verticalLayout = QtWidgets.QVBoxLayout(self.Dialog)
        # self.verticalLayout.setObjectName("verticalLayout")
            
        
        self.label1.setStyleSheet("border-image: url(" +\
                                  str(r_path.with_name('media').\
                                      joinpath('rtime.svg')).replace("\\", "/") + ");")
        self.label3.setStyleSheet("border-image: url(" +\
                                  str(r_path.with_name('media').\
                                      joinpath('bbbv_s.svg')).replace("\\", "/") + ");")
        self.label5.setStyleSheet("border-image: url(" +\
                                  str(r_path.with_name('media').\
                                      joinpath('stnb.svg')).replace("\\", "/") + ");")
        self.label7.setStyleSheet("border-image: url(" +\
                                  str(r_path.with_name('media').\
                                      joinpath('ioe.svg')).replace("\\", "/") + ");")
        self.label9.setStyleSheet("border-image: url(" +\
                                  str(r_path.with_name('media').\
                                      joinpath('path.svg')).replace("\\", "/") + ");")
        self.label11.setStyleSheet("border-image: url(" +\
                                  str(r_path.with_name('media').\
                                      joinpath('rqp.svg')).replace("\\", "/") + ");")
        self.label13.setStyleSheet("border-image: url(" +\
                                  str(r_path.with_name('media').\
                                      joinpath('pb.svg')).replace("\\", "/") + ");")
        self.label14.setStyleSheet("border-image: url(" +\
                                  str(r_path.with_name('media').\
                                      joinpath('pb.svg')).replace("\\", "/") + ");")
        self.label15.setStyleSheet("border-image: url(" +\
                                  str(r_path.with_name('media').\
                                      joinpath('pb.svg')).replace("\\", "/") + ");")
            
        self.label__13.setText(str(pb_bbbv) + " bv")
        self.label__14.setText(str(pb_bbbv) + " bv")
        self.label__15.setText(str(pb_bbbv) + " bv")

        # self.Dialog.setFixedSize(self.Dialog.minimumSize())

