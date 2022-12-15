# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_video_control.ui'
#
# Created by: PyQt5 UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(520, 640)
        Form.setMinimumSize(QtCore.QSize(480, 640))
        Form.setMaximumSize(QtCore.QSize(600, 640))
        Form.setSizeIncrement(QtCore.QSize(0, 0))
        Form.setWindowOpacity(10.0)
        self.horizontalSlider_time = QtWidgets.QSlider(Form)
        self.horizontalSlider_time.setGeometry(QtCore.QRect(20, 40, 481, 31))
        self.horizontalSlider_time.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.horizontalSlider_time.setAutoFillBackground(False)
        self.horizontalSlider_time.setStyleSheet("QSlider::groove {\n"
"    border: 0px solid #bbbbbb;\n"
"    background-color: #50A6EA;\n"
"    border-radius: 4px;\n"
"}\n"
"QSlider::groove:horizontal {\n"
"    height: 16px;\n"
"}\n"
"QSlider::groove:vertical {\n"
"    width: 16px;\n"
"}\n"
"QSlider::handle:horizontal {\n"
"    background: #ffffff;\n"
"    border-style: solid;\n"
"    border-width: 1px;\n"
"    border-color: rgb(207,207,207);\n"
"    width: 12px;\n"
"    margin: -5px 0;\n"
"    border-radius: 7px;\n"
"}\n"
"QSlider::handle:vertical {\n"
"    background: #ffffff;\n"
"    border-style: solid;\n"
"    border-width: 1px;\n"
"    border-color: rgb(207,207,207);\n"
"    height: 12px;\n"
"    margin: 0 -5px;\n"
"    border-radius: 7px;\n"
"}\n"
"QSlider::add-page, QSlider::sub-page {\n"
"    border: 1px transparent;\n"
"    background-color: #50A6EA;\n"
"    border-radius: 4px;\n"
"}\n"
"QSlider::add-page:horizontal {\n"
"    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #ddd5d5, stop:0.5 #dad3d3, stop:1 #ddd5d5);\n"
"}\n"
"QSlider::sub-page:horizontal {\n"
"    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #50A6EA, stop:0.5 #87C1F1, stop:1 #50A6EA);\n"
"}\n"
"QSlider::add-page:vertical {\n"
"    background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 #50A6EA, stop:0.5 #3b88fc, stop:1 #467dd1);\n"
"}\n"
"QSlider::sub-page:vertical {\n"
"    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #ddd5d5, stop:0.5 #dad3d3, stop:1 #ddd5d5);\n"
"}\n"
"QSlider::add-page:horizontal:disabled, QSlider::sub-page:horizontal:disabled, QSlider::add-page:vertical:disabled, QSlider::sub-page:vertical:disabled {\n"
"    background: #b9b9b9;\n"
"}")
        self.horizontalSlider_time.setMaximum(1000)
        self.horizontalSlider_time.setSingleStep(0)
        self.horizontalSlider_time.setPageStep(10)
        self.horizontalSlider_time.setSliderPosition(0)
        self.horizontalSlider_time.setTracking(True)
        self.horizontalSlider_time.setOrientation(QtCore.Qt.Horizontal)
        self.horizontalSlider_time.setInvertedAppearance(False)
        self.horizontalSlider_time.setInvertedControls(False)
        self.horizontalSlider_time.setTickPosition(QtWidgets.QSlider.NoTicks)
        self.horizontalSlider_time.setTickInterval(0)
        self.horizontalSlider_time.setObjectName("horizontalSlider_time")
        self.pushButton_replay = QtWidgets.QPushButton(Form)
        self.pushButton_replay.setGeometry(QtCore.QRect(20, 90, 41, 41))
        self.pushButton_replay.setStyleSheet("border-image: url(media/replay.svg);\n"
"QPushButton::hover{\n"
"    background-color: rgb(170, 255, 255);\n"
"}")
        self.pushButton_replay.setText("")
        self.pushButton_replay.setObjectName("pushButton_replay")
        self.pushButton_play = QtWidgets.QPushButton(Form)
        self.pushButton_play.setGeometry(QtCore.QRect(70, 90, 41, 41))
        self.pushButton_play.setStyleSheet("border-image: url(media/play.svg);")
        self.pushButton_play.setText("")
        self.pushButton_play.setObjectName("pushButton_play")
        self.label_speed = SpeedLabel(Form)
        self.label_speed.setGeometry(QtCore.QRect(142, 90, 51, 41))
        self.label_speed.setStyleSheet("border-image: url(media/speed.svg);\n"
"font: 12pt \"微软雅黑\";\n"
"color: #50A6EA;")
        self.label_speed.setAlignment(QtCore.Qt.AlignCenter)
        self.label_speed.setObjectName("label_speed")
        self.label_2 = QtWidgets.QLabel(Form)
        self.label_2.setGeometry(QtCore.QRect(120, 102, 16, 16))
        self.label_2.setStyleSheet("border-image: url(media/mul.svg);\n"
"font: 12pt \"微软雅黑\";\n"
"color: #50A6EA;")
        self.label_2.setText("")
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)
        self.label_2.setObjectName("label_2")
        self.doubleSpinBox_time = QtWidgets.QDoubleSpinBox(Form)
        self.doubleSpinBox_time.setGeometry(QtCore.QRect(370, 80, 131, 61))
        font = QtGui.QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(20)
        font.setBold(False)
        font.setItalic(False)
        font.setWeight(50)
        self.doubleSpinBox_time.setFont(font)
        self.doubleSpinBox_time.setStyleSheet("font: 20pt \"微软雅黑\";\n"
"color: #50A6EA;\n"
"background-color: rgb(240, 240, 240);")
        self.doubleSpinBox_time.setFrame(False)
        self.doubleSpinBox_time.setAlignment(QtCore.Qt.AlignCenter)
        self.doubleSpinBox_time.setSingleStep(0.01)
        self.doubleSpinBox_time.setObjectName("doubleSpinBox_time")
        self.scrollArea = QtWidgets.QScrollArea(Form)
        self.scrollArea.setGeometry(QtCore.QRect(20, 150, 481, 471))
        self.scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.scrollArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scrollArea.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 458, 500))
        self.scrollAreaWidgetContents.setMinimumSize(QtCore.QSize(0, 500))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.label_time = QtWidgets.QLabel(self.scrollAreaWidgetContents)
        self.label_time.setGeometry(QtCore.QRect(0, 0, 68, 42))
        font = QtGui.QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        self.label_time.setFont(font)
        self.label_time.setAlignment(QtCore.Qt.AlignCenter)
        self.label_time.setObjectName("label_time")
        self.label_tag = QtWidgets.QLabel(self.scrollAreaWidgetContents)
        self.label_tag.setGeometry(QtCore.QRect(158, 0, 300, 42))
        font = QtGui.QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        self.label_tag.setFont(font)
        self.label_tag.setAlignment(QtCore.Qt.AlignCenter)
        self.label_tag.setObjectName("label_tag")
        self.label_event = QtWidgets.QLabel(self.scrollAreaWidgetContents)
        self.label_event.setGeometry(QtCore.QRect(68, 0, 90, 42))
        font = QtGui.QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        self.label_event.setFont(font)
        self.label_event.setAlignment(QtCore.Qt.AlignCenter)
        self.label_event.setObjectName("label_event")
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "雷数设置"))
        self.label_speed.setText(_translate("Form", "1"))
        self.label_time.setText(_translate("Form", "时间"))
        self.label_tag.setText(_translate("Form", "标签"))
        self.label_event.setText(_translate("Form", "事件"))
from ui.uiComponents import SpeedLabel