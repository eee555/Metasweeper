# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_mine_num_bar.ui'
#
# Created by: PyQt5 UI code generator 5.15.11
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(140, 382)
        Form.setMinimumSize(QtCore.QSize(140, 382))
        Form.setMaximumSize(QtCore.QSize(140, 382))
        Form.setSizeIncrement(QtCore.QSize(0, 0))
        Form.setWindowTitle("")
        Form.setWindowOpacity(10.0)
        self.verticalSlider = QtWidgets.QSlider(Form)
        self.verticalSlider.setGeometry(QtCore.QRect(30, 60, 22, 261))
        self.verticalSlider.setStyleSheet("QSlider {\n"
"    padding: 2px;\n"
"    height: 40px;\n"
"}\n"
"")
        self.verticalSlider.setOrientation(QtCore.Qt.Vertical)
        self.verticalSlider.setInvertedAppearance(False)
        self.verticalSlider.setInvertedControls(False)
        self.verticalSlider.setObjectName("verticalSlider")
        self.label_4 = QtWidgets.QLabel(Form)
        self.label_4.setGeometry(QtCore.QRect(10, 350, 51, 31))
        font = QtGui.QFont()
        font.setFamily("黑体")
        font.setPointSize(16)
        font.setBold(True)
        font.setWeight(75)
        self.label_4.setFont(font)
        self.label_4.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.label_4.setText("32")
        self.label_4.setAlignment(QtCore.Qt.AlignCenter)
        self.label_4.setObjectName("label_4")
        self.label_5 = QtWidgets.QLabel(Form)
        self.label_5.setGeometry(QtCore.QRect(10, 10, 51, 31))
        font = QtGui.QFont()
        font.setFamily("黑体")
        font.setPointSize(16)
        font.setBold(True)
        font.setWeight(75)
        self.label_5.setFont(font)
        self.label_5.setText("32")
        self.label_5.setAlignment(QtCore.Qt.AlignCenter)
        self.label_5.setObjectName("label_5")
        self.spinBox = QtWidgets.QSpinBox(Form)
        self.spinBox.setGeometry(QtCore.QRect(70, 160, 61, 61))
        self.spinBox.setStyleSheet("font: 16pt \"黑体\";\n"
"background-color: rgb(238, 238, 238, 0);\n"
"")
        self.spinBox.setFrame(False)
        self.spinBox.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.spinBox.setObjectName("spinBox")

        self.retranslateUi(Form)
        self.verticalSlider.valueChanged['int'].connect(self.spinBox.setValue) # type: ignore
        self.spinBox.valueChanged['int'].connect(self.verticalSlider.setValue) # type: ignore
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        pass
