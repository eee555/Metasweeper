# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'ui_mine_num_bar.ui'
##
# Created by: Qt User Interface Compiler version 6.11.1
##
# WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
                            QMetaObject, QObject, QPoint, QRect,
                            QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
                           QFont, QFontDatabase, QGradient, QIcon,
                           QImage, QKeySequence, QLinearGradient, QPainter,
                           QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QSizePolicy, QSlider,
                               QSpinBox, QWidget)


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(140, 382)
        Form.setMinimumSize(QSize(140, 382))
        Form.setMaximumSize(QSize(140, 382))
        Form.setSizeIncrement(QSize(0, 0))
        Form.setWindowTitle(u"")
        Form.setWindowOpacity(10.000000000000000)
        self.verticalSlider = QSlider(Form)
        self.verticalSlider.setObjectName(u"verticalSlider")
        self.verticalSlider.setGeometry(QRect(30, 60, 22, 261))
        self.verticalSlider.setStyleSheet(u"QSlider::groove:vertical {\n"
                                          "    border: 0px solid #bbbbbb;\n"
                                          "    background-color: #50A6EA;\n"
                                          "    border-radius: 4px;\n"
                                          "    width: 16px;\n"
                                          "}\n"
                                          "\n"
                                          "QSlider::handle:vertical {\n"
                                          "    background: #ffffff;\n"
                                          "    border: 1px solid rgb(207,207,207);\n"
                                          "    height: 12px;\n"
                                          "    margin: 0 -5px;\n"
                                          "    border-radius: 7px;\n"
                                          "}\n"
                                          "\n"
                                          "/* \u5df2\u6ed1\u8fc7\u7684\u90e8\u5206\uff08\u4e0b\u65b9 \u2192 \u6ed1\u5757\u4f4d\u7f6e\uff09 */\n"
                                          "QSlider::sub-page:vertical {\n"
                                          "    background: qlineargradient(\n"
                                          "        spread:pad,\n"
                                          "        x1:0, y1:0,\n"
                                          "        x2:0, y2:1,\n"
                                          "        stop:0 #ddd5d5,\n"
                                          "        stop:0.5 #dad3d3,\n"
                                          "        stop:1 #ddd5d5\n"
                                          "    );\n"
                                          "    border-radius: 4px;\n"
                                          "}\n"
                                          "\n"
                                          "/* \u672a\u6ed1\u8fc7\u7684\u90e8\u5206\uff08\u6ed1\u5757\u4f4d\u7f6e \u2192 \u9876\u90e8\uff09 */\n"
                                          "QSlider::add-page:vertical {\n"
                                          "    background: qlineargradient(\n"
                                          "        spread:pad,\n"
                                          "        x1:0, y1:1,\n"
                                          "        x2:0, y2:0,\n"
                                          "        stop:0 #50A6EA,\n"
                                          "        stop:0.5 #87C1"
                                          "F1,\n"
                                          "        stop:1 #50A6EA\n"
                                          "    );\n"
                                          "    \n"
                                          "    border-radius: 4px;\n"
                                          "}\n"
                                          "\n"
                                          "/* \u7981\u7528\u6001 */\n"
                                          "QSlider::add-page:vertical:disabled,\n"
                                          "QSlider::sub-page:vertical:disabled {\n"
                                          "    background: #b9b9b9;\n"
                                          "}\n"
                                          "")
        self.verticalSlider.setOrientation(Qt.Vertical)
        self.verticalSlider.setInvertedAppearance(False)
        self.verticalSlider.setInvertedControls(False)
        self.label_4 = QLabel(Form)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setGeometry(QRect(10, 350, 51, 31))
        font = QFont()
        font.setFamilies([u"\u9ed1\u4f53"])
        font.setPointSize(16)
        font.setBold(True)
        self.label_4.setFont(font)
        self.label_4.setContextMenuPolicy(Qt.PreventContextMenu)
        self.label_4.setText(u"20")
        self.label_4.setAlignment(Qt.AlignCenter)
        self.label_5 = QLabel(Form)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setGeometry(QRect(10, 10, 51, 31))
        self.label_5.setFont(font)
        self.label_5.setText(u"32")
        self.label_5.setAlignment(Qt.AlignCenter)
        self.spinBox = QSpinBox(Form)
        self.spinBox.setObjectName(u"spinBox")
        self.spinBox.setGeometry(QRect(70, 160, 61, 61))
        self.spinBox.setStyleSheet(u"font: 16pt \"\u9ed1\u4f53\";\n"
                                   "background-color: rgb(238, 238, 238, 0);\n"
                                   "")
        self.spinBox.setFrame(False)
        self.spinBox.setAlignment(
            Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.retranslateUi(Form)
        self.verticalSlider.valueChanged.connect(self.spinBox.setValue)
        self.spinBox.valueChanged.connect(self.verticalSlider.setValue)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        pass
    # retranslateUi
