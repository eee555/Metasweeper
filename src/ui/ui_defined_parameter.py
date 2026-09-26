# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'ui_defined_parameter.ui'
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
from PySide6.QtWidgets import (QApplication, QGridLayout, QLabel, QPushButton,
                               QSizePolicy, QSpinBox, QWidget)


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(600, 220)
        Form.setMinimumSize(QSize(600, 220))
        Form.setMaximumSize(QSize(600, 220))
        Form.setSizeIncrement(QSize(0, 0))
        icon = QIcon()
        icon.addFile(u"media/cat.ico", QSize(),
                     QIcon.Mode.Normal, QIcon.State.Off)
        Form.setWindowIcon(icon)
        Form.setWindowOpacity(10.000000000000000)
        self.pushButton_2 = QPushButton(Form)
        self.pushButton_2.setObjectName(u"pushButton_2")
        self.pushButton_2.setGeometry(QRect(390, 130, 181, 51))
        self.pushButton_2.setFocusPolicy(Qt.NoFocus)
        self.pushButton_3 = QPushButton(Form)
        self.pushButton_3.setObjectName(u"pushButton_3")
        self.pushButton_3.setGeometry(QRect(390, 50, 181, 51))
        self.pushButton_3.setFocusPolicy(Qt.NoFocus)
        self.pushButton_3.setAutoDefault(False)
        self.pushButton_3.setFlat(False)
        self.layoutWidget = QWidget(Form)
        self.layoutWidget.setObjectName(u"layoutWidget")
        self.layoutWidget.setGeometry(QRect(30, 30, 309, 157))
        self.gridLayout = QGridLayout(self.layoutWidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setHorizontalSpacing(7)
        self.gridLayout.setVerticalSpacing(23)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self.layoutWidget)
        self.label.setObjectName(u"label")
        font = QFont()
        font.setFamilies([u"\u9ed1\u4f53"])
        font.setPointSize(16)
        font.setBold(False)
        font.setItalic(False)
        self.label.setFont(font)
        self.label.setStyleSheet(u"font: 16pt \"\u9ed1\u4f53\";\n"
                                 "color:black;")

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.spinBox = QSpinBox(self.layoutWidget)
        self.spinBox.setObjectName(u"spinBox")
        self.spinBox.setFont(font)
        self.spinBox.setStyleSheet(u"font: 16pt \"\u9ed1\u4f53\";\n"
                                   "color:black;")
        self.spinBox.setAlignment(Qt.AlignCenter)
        self.spinBox.setMinimum(6)
        self.spinBox.setMaximum(255)
        self.spinBox.setDisplayIntegerBase(10)

        self.gridLayout.addWidget(self.spinBox, 0, 1, 1, 2)

        self.label_2 = QLabel(self.layoutWidget)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setFont(font)
        self.label_2.setStyleSheet(u"font: 16pt \"\u9ed1\u4f53\";\n"
                                   "color:black;")

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.spinBox_2 = QSpinBox(self.layoutWidget)
        self.spinBox_2.setObjectName(u"spinBox_2")
        self.spinBox_2.setFont(font)
        self.spinBox_2.setStyleSheet(u"font: 16pt \"\u9ed1\u4f53\";\n"
                                     "color:black;")
        self.spinBox_2.setAlignment(Qt.AlignCenter)
        self.spinBox_2.setMinimum(6)
        self.spinBox_2.setMaximum(255)
        self.spinBox_2.setDisplayIntegerBase(10)

        self.gridLayout.addWidget(self.spinBox_2, 1, 1, 1, 2)

        self.label_3 = QLabel(self.layoutWidget)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setFont(font)
        self.label_3.setStyleSheet(u"font: 16pt \"\u9ed1\u4f53\";\n"
                                   "color:black;")

        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)

        self.spinBox_3 = QSpinBox(self.layoutWidget)
        self.spinBox_3.setObjectName(u"spinBox_3")
        self.spinBox_3.setFont(font)
        self.spinBox_3.setStyleSheet(u"font: 16pt \"\u9ed1\u4f53\";\n"
                                     "color:black;")
        self.spinBox_3.setAlignment(Qt.AlignCenter)
        self.spinBox_3.setMinimum(1)
        self.spinBox_3.setMaximum(1000000)
        self.spinBox_3.setDisplayIntegerBase(10)

        self.gridLayout.addWidget(self.spinBox_3, 2, 1, 1, 2)

        self.retranslateUi(Form)
        self.pushButton_2.clicked.connect(Form.close)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate(
            "Form", u"\u81ea\u5b9a\u4e49\u8bbe\u7f6e", None))
        self.pushButton_2.setText(
            QCoreApplication.translate("Form", u"\u53d6\u6d88", None))
        self.pushButton_3.setText(
            QCoreApplication.translate("Form", u"\u786e\u5b9a", None))
# if QT_CONFIG(shortcut)
        self.pushButton_3.setShortcut(
            QCoreApplication.translate("Form", u"Return", None))
# endif // QT_CONFIG(shortcut)
        self.label.setText(QCoreApplication.translate(
            "Form", u"\u884c\u6570(row)", None))
        self.label_2.setText(QCoreApplication.translate(
            "Form", u"\u5217\u6570(column)", None))
        self.label_3.setText(QCoreApplication.translate(
            "Form", u"\u96f7\u6570(number)", None))
    # retranslateUi
