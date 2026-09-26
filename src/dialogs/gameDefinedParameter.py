# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_defined_parameter.ui'
# 自定义

from PySide6 import QtGui
from ui.ui_defined_parameter import Ui_Form
from ui.uiComponents import RoundQDialog


class ui_Form(Ui_Form):
    def __init__(self, r_path, row, column, num, parent):
        self.row = row
        self.column = column
        self.minenum = num
        self.alter = False
        self.Dialog = RoundQDialog(parent)
        self.setupUi(self.Dialog)
        self.setParameter()
        self.pushButton_3.clicked.connect(self.processParameter)

    def setParameter(self):
        self.spinBox.setValue(self.row)
        self.spinBox_2.setValue(self.column)
        self.spinBox_3.setValue(self.minenum)
        self.change_minenum_limit()
        self.spinBox.valueChanged.connect(self.change_minenum_limit)
        self.spinBox_2.valueChanged.connect(self.change_minenum_limit)

    def change_minenum_limit(self):
        minenum_limit = self.spinBox.value() * self.spinBox_2.value() - 1
        self.spinBox_3.setValue(min(self.spinBox_3.value(), minenum_limit))
        self.spinBox_3.setMaximum(minenum_limit)

    def processParameter(self):
        r = self.spinBox.value()
        c = self.spinBox_2.value()
        n = self.spinBox_3.value()
        if r != self.row or c != self.column or n != self.minenum:
            self.alter = True
            self.row = r
            self.column = c
            self.minenum = min(max(n, 1), r * c - 1)
        self.Dialog.close()
