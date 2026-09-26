# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'ui_import.ui'
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
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit,
                               QProgressBar, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(580, 269)
        Form.setMinimumSize(QSize(580, 269))
        Form.setMaximumSize(QSize(580, 269))
        icon = QIcon()
        icon.addFile(u"media/cat.ico", QSize(),
                     QIcon.Mode.Normal, QIcon.State.Off)
        Form.setWindowIcon(icon)
        Form.setWindowOpacity(10.000000000000000)
        self.verticalLayout = QVBoxLayout(Form)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(24, 24, 24, 24)
        self.horizontalLayout_exe = QHBoxLayout()
        self.horizontalLayout_exe.setSpacing(10)
        self.horizontalLayout_exe.setObjectName(u"horizontalLayout_exe")
        self.label_exe = QLabel(Form)
        self.label_exe.setObjectName(u"label_exe")
        self.label_exe.setMinimumSize(QSize(80, 0))

        self.horizontalLayout_exe.addWidget(self.label_exe)

        self.lineEdit_exe = QLineEdit(Form)
        self.lineEdit_exe.setObjectName(u"lineEdit_exe")
        self.lineEdit_exe.setMinimumSize(QSize(0, 42))

        self.horizontalLayout_exe.addWidget(self.lineEdit_exe)

        self.pushButton_browse_exe = QPushButton(Form)
        self.pushButton_browse_exe.setObjectName(u"pushButton_browse_exe")
        self.pushButton_browse_exe.setMinimumSize(QSize(80, 42))
        self.pushButton_browse_exe.setMaximumSize(QSize(80, 42))
        self.pushButton_browse_exe.setFocusPolicy(Qt.NoFocus)
        self.pushButton_browse_exe.setStyleSheet(u"QPushButton {\n"
                                                 "    background: transparent;\n"
                                                 "    border: 1px solid #999;\n"
                                                 "    border-radius: 6px;\n"
                                                 "    color: #444;\n"
                                                 "    font-weight: normal;\n"
                                                 "    font-family: \"Microsoft YaHei\", \"\u5fae\u8f6f\u96c5\u9ed1\", \"Segoe UI\", Arial, sans-serif;\n"
                                                 "    font-size: 9pt;\n"
                                                 "}\n"
                                                 "QPushButton:hover {\n"
                                                 "    background: #eee;\n"
                                                 "}")

        self.horizontalLayout_exe.addWidget(self.pushButton_browse_exe)

        self.verticalLayout.addLayout(self.horizontalLayout_exe)

        self.horizontalLayout_replay = QHBoxLayout()
        self.horizontalLayout_replay.setSpacing(10)
        self.horizontalLayout_replay.setObjectName(u"horizontalLayout_replay")
        self.label_replay = QLabel(Form)
        self.label_replay.setObjectName(u"label_replay")
        self.label_replay.setMinimumSize(QSize(80, 0))

        self.horizontalLayout_replay.addWidget(self.label_replay)

        self.lineEdit_replay = QLineEdit(Form)
        self.lineEdit_replay.setObjectName(u"lineEdit_replay")
        self.lineEdit_replay.setMinimumSize(QSize(0, 42))

        self.horizontalLayout_replay.addWidget(self.lineEdit_replay)

        self.pushButton_browse_file = QPushButton(Form)
        self.pushButton_browse_file.setObjectName(u"pushButton_browse_file")
        self.pushButton_browse_file.setMinimumSize(QSize(80, 42))
        self.pushButton_browse_file.setMaximumSize(QSize(80, 42))
        font = QFont()
        font.setFamilies(
            [u"Microsoft YaHei,\u5fae\u8f6f\u96c5\u9ed1,Segoe UI,Arial,sans-serif"])
        font.setPointSize(9)
        font.setBold(False)
        self.pushButton_browse_file.setFont(font)
        self.pushButton_browse_file.setFocusPolicy(Qt.NoFocus)
        self.pushButton_browse_file.setStyleSheet(u"QPushButton {\n"
                                                  "    background: transparent;\n"
                                                  "    border: 1px solid #999;\n"
                                                  "    border-radius: 6px;\n"
                                                  "    color: #444;\n"
                                                  "    font-weight: normal;\n"
                                                  "    font-family: \"Microsoft YaHei\", \"\u5fae\u8f6f\u96c5\u9ed1\", \"Segoe UI\", Arial, sans-serif;\n"
                                                  "    font-size: 9pt;\n"
                                                  "}\n"
                                                  "QPushButton:hover {\n"
                                                  "    background: #eee;\n"
                                                  "}")

        self.horizontalLayout_replay.addWidget(self.pushButton_browse_file)

        self.pushButton_browse_folder = QPushButton(Form)
        self.pushButton_browse_folder.setObjectName(
            u"pushButton_browse_folder")
        self.pushButton_browse_folder.setMinimumSize(QSize(80, 42))
        self.pushButton_browse_folder.setMaximumSize(QSize(80, 42))
        self.pushButton_browse_folder.setFocusPolicy(Qt.NoFocus)
        self.pushButton_browse_folder.setStyleSheet(u"QPushButton {\n"
                                                    "    background: transparent;\n"
                                                    "    border: 1px solid #999;\n"
                                                    "    border-radius: 6px;\n"
                                                    "    color: #444;\n"
                                                    "    font-weight: normal;\n"
                                                    "    font-family: \"Microsoft YaHei\", \"\u5fae\u8f6f\u96c5\u9ed1\", \"Segoe UI\", Arial, sans-serif;\n"
                                                    "    font-size: 9pt;\n"
                                                    "}\n"
                                                    "QPushButton:hover {\n"
                                                    "    background: #eee;\n"
                                                    "}")

        self.horizontalLayout_replay.addWidget(self.pushButton_browse_folder)

        self.verticalLayout.addLayout(self.horizontalLayout_replay)

        self.progressBar = QProgressBar(Form)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setMinimumSize(QSize(0, 28))
        self.progressBar.setMaximumSize(QSize(16777215, 28))
        self.progressBar.setVisible(True)
        self.progressBar.setStyleSheet(u"QProgressBar {\n"
                                       "    border: 1px solid #bbb;\n"
                                       "    border-radius: 6px;\n"
                                       "    text-align: center;\n"
                                       "    font-size: 11pt;\n"
                                       "    height: 24px;\n"
                                       "}\n"
                                       "QProgressBar::chunk {\n"
                                       "    background-color: #00A2E8;\n"
                                       "    border-radius: 4px;\n"
                                       "}")
        self.progressBar.setValue(0)

        self.verticalLayout.addWidget(self.progressBar)

        self.label_progress = QLabel(Form)
        self.label_progress.setObjectName(u"label_progress")
        self.label_progress.setMinimumSize(QSize(200, 0))
        self.label_progress.setVisible(True)

        self.verticalLayout.addWidget(self.label_progress)

        self.horizontalLayout_buttons = QHBoxLayout()
        self.horizontalLayout_buttons.setSpacing(10)
        self.horizontalLayout_buttons.setObjectName(
            u"horizontalLayout_buttons")
        self.pushButton_ok = QPushButton(Form)
        self.pushButton_ok.setObjectName(u"pushButton_ok")
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.pushButton_ok.sizePolicy().hasHeightForWidth())
        self.pushButton_ok.setSizePolicy(sizePolicy)
        self.pushButton_ok.setMinimumSize(QSize(184, 51))
        self.pushButton_ok.setMaximumSize(QSize(16777215, 51))
        self.pushButton_ok.setFocusPolicy(Qt.NoFocus)
        self.pushButton_ok.setAutoDefault(False)

        self.horizontalLayout_buttons.addWidget(self.pushButton_ok)

        self.pushButton_cancel = QPushButton(Form)
        self.pushButton_cancel.setObjectName(u"pushButton_cancel")
        sizePolicy.setHeightForWidth(
            self.pushButton_cancel.sizePolicy().hasHeightForWidth())
        self.pushButton_cancel.setSizePolicy(sizePolicy)
        self.pushButton_cancel.setMinimumSize(QSize(184, 51))
        self.pushButton_cancel.setMaximumSize(QSize(16777215, 51))
        self.pushButton_cancel.setFocusPolicy(Qt.NoFocus)

        self.horizontalLayout_buttons.addWidget(self.pushButton_cancel)

        self.verticalLayout.addLayout(self.horizontalLayout_buttons)

        self.retranslateUi(Form)
        self.pushButton_cancel.clicked.connect(Form.close)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate(
            "Form", u"\u5bfc\u5165\u5f55\u50cf", None))
        self.label_exe.setText(QCoreApplication.translate(
            "Form", u"\u9a8c\u8bc1\u7a0b\u5e8f:", None))
        self.lineEdit_exe.setPlaceholderText(QCoreApplication.translate(
            "Form", u"\u9009\u62e9\u9a8c\u8bc1\u7a0b\u5e8f...", None))
        self.pushButton_browse_exe.setText(
            QCoreApplication.translate("Form", u"\u6d4f\u89c8", None))
        self.label_replay.setText(QCoreApplication.translate(
            "Form", u"\u5f55\u50cf\u8def\u5f84:", None))
        self.lineEdit_replay.setPlaceholderText(QCoreApplication.translate(
            "Form", u"\u9009\u62e9\u5f55\u50cf\u6587\u4ef6\u6216\u6587\u4ef6\u5939...", None))
        self.pushButton_browse_file.setText(QCoreApplication.translate(
            "Form", u"\u9009\u62e9\u6587\u4ef6", None))
        self.pushButton_browse_folder.setText(QCoreApplication.translate(
            "Form", u"\u9009\u62e9\u6587\u4ef6\u5939", None))
        self.label_progress.setText("")
        self.pushButton_ok.setText(
            QCoreApplication.translate("Form", u"\u786e\u8ba4", None))
# if QT_CONFIG(shortcut)
        self.pushButton_ok.setShortcut(
            QCoreApplication.translate("Form", u"Return", None))
# endif // QT_CONFIG(shortcut)
        self.pushButton_cancel.setText(
            QCoreApplication.translate("Form", u"\u53d6\u6d88", None))
    # retranslateUi
