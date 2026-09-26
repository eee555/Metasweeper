# -*- coding: utf-8 -*-
"""
Created on Sat Aug 14 00:34:24 2021

@author: jia32
"""

# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_gs.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PySide6 import QtCore
from ui.uiComponents import RoundQWidget
from ui.ui_mine_num_bar import Ui_Form


class ui_Form(Ui_Form):
    # barSetMineNum = QtCore.pyqtSignal(int)
    # barSetMineNumCalPoss = QtCore.pyqtSignal(int)
    def __init__(self, mine_num, size, parent):
        self.QWidget = RoundQWidget(parent)
        self.setupUi(self.QWidget)
        # self.setParameter ()

        # _translate = QtCore.QCoreApplication.translate
        self.label_4.setText(str(mine_num[0]))
        self.label_5.setText(str(mine_num[2]))
        self.verticalSlider.setMinimum(mine_num[0])
        self.verticalSlider.setMaximum(mine_num[2])
        self.verticalSlider.setValue(mine_num[1])
        self.spinBox.setMinimum(mine_num[0])
        self.spinBox.setMaximum(mine_num[2])
        self.spinBox.setValue(mine_num[1])
        # setSingleStep

        # 重新设置尺寸
        self.QWidget.resize(80, size)
        self.QWidget.setMinimumSize(QtCore.QSize(138, size))
        self.QWidget.setMaximumSize(QtCore.QSize(138, size))
        self.verticalSlider.setGeometry(QtCore.QRect(
            32, int(min(size * 0.2, 44)), 22, int(max(size * 0.6, size - 88))))
        self.label_4.setGeometry(QtCore.QRect(
            3, int(max(size * 0.85, size - 39)), 81, 31))
        self.label_5.setGeometry(QtCore.QRect(
            3, int(min(size * 0.1, 8)), 81, 31))
        self.spinBox.setGeometry(QtCore.QRect(
            60, int(max(size * 0.5 - 20, 3)), 60, 40))

        # self.verticalSlider.valueChanged['int'].connect(self.QWidget.barSetMineNum.emit())
        # self.verticalSlider.sliderReleased['int'].connect(self.QWidget.barSetMineNumCalPoss.emit())

    def setSignal(self):
        # self.verticalSlider.valueChanged = self.QWidget.barSetMineNum.emit
        # self.verticalSlider.sliderReleased = self.QWidget.barSetMineNumCalPoss.emit
        self.verticalSlider.valueChanged['int'].connect(
            self.QWidget.barSetMineNum.emit)
        self.verticalSlider.sliderReleased.connect(
            self.QWidget.barSetMineNumCalPoss.emit)
        self.spinBox.valueChanged.connect(
            lambda _: self.QWidget.barSetMineNumCalPoss.emit())

    def setParameter(self):
        ...

    def processParameter(self):
        ...
