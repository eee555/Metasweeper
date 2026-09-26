# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'ui_advanced.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QGroupBox,
                               QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(580, 283)
        self.verticalLayout = QVBoxLayout(Form)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(18, 18, 18, 18)
        self.groupBox_plugin = QGroupBox(Form)
        self.groupBox_plugin.setObjectName(u"groupBox_plugin")
        self.verticalLayout_plugin = QVBoxLayout(self.groupBox_plugin)
        self.verticalLayout_plugin.setObjectName(u"verticalLayout_plugin")
        self.label_info_text = QLabel(self.groupBox_plugin)
        self.label_info_text.setObjectName(u"label_info_text")
        self.label_info_text.setTextFormat(Qt.RichText)
        self.label_info_text.setWordWrap(True)

        self.verticalLayout_plugin.addWidget(self.label_info_text)

        self.widget_auth_container = QWidget(self.groupBox_plugin)
        self.widget_auth_container.setObjectName(u"widget_auth_container")
        self.verticalLayout_auth_items = QVBoxLayout(
            self.widget_auth_container)
        self.verticalLayout_auth_items.setObjectName(
            u"verticalLayout_auth_items")
        self.verticalLayout_auth_items.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_plugin.addWidget(self.widget_auth_container)

        self.verticalLayout.addWidget(self.groupBox_plugin)

        self.groupBox_algo = QGroupBox(Form)
        self.groupBox_algo.setObjectName(u"groupBox_algo")
        self.verticalLayout_algo = QVBoxLayout(self.groupBox_algo)
        self.verticalLayout_algo.setObjectName(u"verticalLayout_algo")
        self.checkBox_filter_forever = QCheckBox(self.groupBox_algo)
        self.checkBox_filter_forever.setObjectName(u"checkBox_filter_forever")
        self.checkBox_filter_forever.setMinimumSize(QSize(0, 32))

        self.verticalLayout_algo.addWidget(self.checkBox_filter_forever)

        self.verticalLayout.addWidget(self.groupBox_algo)

        self.line = QFrame(Form)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout.addWidget(self.line)

        self.widget_buttons = QWidget(Form)
        self.widget_buttons.setObjectName(u"widget_buttons")
        self.horizontalLayout_buttons = QHBoxLayout(self.widget_buttons)
        self.horizontalLayout_buttons.setSpacing(10)
        self.horizontalLayout_buttons.setObjectName(
            u"horizontalLayout_buttons")
        self.horizontalLayout_buttons.setContentsMargins(0, 0, 0, 0)
        self.pushButton_yes = QPushButton(self.widget_buttons)
        self.pushButton_yes.setObjectName(u"pushButton_yes")
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.pushButton_yes.sizePolicy().hasHeightForWidth())
        self.pushButton_yes.setSizePolicy(sizePolicy)
        self.pushButton_yes.setMinimumSize(QSize(184, 36))
        self.pushButton_yes.setMaximumSize(QSize(16777215, 16777215))
        self.pushButton_yes.setFocusPolicy(Qt.NoFocus)

        self.horizontalLayout_buttons.addWidget(self.pushButton_yes)

        self.pushButton_no = QPushButton(self.widget_buttons)
        self.pushButton_no.setObjectName(u"pushButton_no")
        sizePolicy.setHeightForWidth(
            self.pushButton_no.sizePolicy().hasHeightForWidth())
        self.pushButton_no.setSizePolicy(sizePolicy)
        self.pushButton_no.setMinimumSize(QSize(184, 36))
        self.pushButton_no.setMaximumSize(QSize(16777215, 16777215))
        self.pushButton_no.setFocusPolicy(Qt.NoFocus)

        self.horizontalLayout_buttons.addWidget(self.pushButton_no)

        self.verticalLayout.addWidget(self.widget_buttons)

        self.retranslateUi(Form)
        self.pushButton_no.clicked.connect(Form.close)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate(
            "Form", u"\u9ad8\u7ea7\u8bbe\u7f6e", None))
        self.groupBox_plugin.setTitle(QCoreApplication.translate(
            "Form", u"\u63d2\u4ef6\u7c7b", None))
        self.label_info_text.setText(QCoreApplication.translate("Form", u"\u5141\u8bb8\u63d2\u4ef6\u7684\u63a7\u5236\u7c7b\u547d\u4ee4\u540e\uff08\u5982\u70b9\u51fb\u683c\u5b50\u3001\u91cd\u5f00\u65b0\u5c40\u7b49\uff09\uff0c\u5f53\u524d\u5c40\u9762\u7684\u5f55\u50cf\u5c06\u81ea\u52a8\u6807\u8bb0\u4e3a\"\u975e\u6b63\u5f0f\"\uff0c\u4e0d\u8ba1\u5165\u4efb\u4f55\u6392\u540d\u4e0e\u7edf\u8ba1\u6570\u636e\u3002\u5404\u547d\u4ee4\u9700\u8981\u5728<a href=\"plugin:manager\" style=\"color:#00A2E8; text-decoration:underline;\">\u63d2\u4ef6\u7ba1\u7406\u5668</a>\u4e2d\u5b8c\u6210\u6388\u6743\u540e\u624d\u751f\u6548\u3002", None))
        self.groupBox_algo.setTitle(QCoreApplication.translate(
            "Form", u"\u7b97\u6cd5\u7c7b", None))
# if QT_CONFIG(tooltip)
        self.checkBox_filter_forever.setToolTip(QCoreApplication.translate(
            "Form", u"\u52fe\u9009\u540e\u6c38\u8fdc\u4f7f\u7528\u7b5b\u9009\u6cd5\u57cb\u96f7\uff0c\u5426\u5219\u4f1a\u9002\u65f6\u6539\u7528\u8c03\u6574\u6cd5", None))
# endif // QT_CONFIG(tooltip)
        self.checkBox_filter_forever.setText(QCoreApplication.translate(
            "Form", u"\u6c38\u8fdc\u4f7f\u7528\u7b5b\u9009\u6cd5\u57cb\u96f7\uff08\u4e0d\u63a8\u8350\uff09", None))
        self.pushButton_yes.setText(
            QCoreApplication.translate("Form", u"\u786e\u5b9a", None))
# if QT_CONFIG(shortcut)
        self.pushButton_yes.setShortcut(
            QCoreApplication.translate("Form", u"Return", None))
# endif // QT_CONFIG(shortcut)
        self.pushButton_no.setText(
            QCoreApplication.translate("Form", u"\u53d6\u6d88", None))
    # retranslateUi
