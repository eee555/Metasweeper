# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'ui_gs.ui'
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
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QCheckBox, QComboBox,
                               QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSizePolicy, QSpacerItem, QSpinBox,
                               QVBoxLayout, QWidget)

from ui.uiComponents import CountryComboBox


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.setWindowModality(Qt.NonModal)
        Form.resize(554, 644)
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Form.sizePolicy().hasHeightForWidth())
        Form.setSizePolicy(sizePolicy)
        Form.setMinimumSize(QSize(0, 0))
        Form.setMaximumSize(QSize(16777215, 16777215))
        Form.setMouseTracking(True)
        Form.setFocusPolicy(Qt.ClickFocus)
        Form.setWindowTitle(u"")
        self.verticalLayout = QVBoxLayout(Form)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(18, 18, 18, 18)
        self.widget_3 = QWidget(Form)
        self.widget_3.setObjectName(u"widget_3")
        self.widget_3.setMinimumSize(QSize(0, 32))
        self.horizontalLayout_10 = QHBoxLayout(self.widget_3)
        self.horizontalLayout_10.setSpacing(6)
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.horizontalLayout_10.setContentsMargins(0, 0, 0, 0)
        self.label_gamemode = QLabel(self.widget_3)
        self.label_gamemode.setObjectName(u"label_gamemode")
        self.label_gamemode.setScaledContents(False)
        self.label_gamemode.setWordWrap(False)

        self.horizontalLayout_10.addWidget(self.label_gamemode)

        self.comboBox_gamemode = QComboBox(self.widget_3)
        self.comboBox_gamemode.addItem("")
        self.comboBox_gamemode.addItem("")
        self.comboBox_gamemode.addItem("")
        self.comboBox_gamemode.addItem("")
        self.comboBox_gamemode.addItem("")
        self.comboBox_gamemode.addItem("")
        self.comboBox_gamemode.addItem("")
        self.comboBox_gamemode.addItem("")
        self.comboBox_gamemode.setObjectName(u"comboBox_gamemode")
        sizePolicy1 = QSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(
            self.comboBox_gamemode.sizePolicy().hasHeightForWidth())
        self.comboBox_gamemode.setSizePolicy(sizePolicy1)
        self.comboBox_gamemode.setMinimumSize(QSize(0, 32))
        self.comboBox_gamemode.setMaximumSize(QSize(16777215, 32))
        self.comboBox_gamemode.setFocusPolicy(Qt.ClickFocus)
        self.comboBox_gamemode.setSizeAdjustPolicy(QComboBox.AdjustToContents)

        self.horizontalLayout_10.addWidget(self.comboBox_gamemode)

        self.horizontalSpacer_2 = QSpacerItem(
            0, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_10.addItem(self.horizontalSpacer_2)

        self.label_pixsize = QLabel(self.widget_3)
        self.label_pixsize.setObjectName(u"label_pixsize")
        self.label_pixsize.setMinimumSize(QSize(0, 0))
        self.label_pixsize.setMaximumSize(QSize(16777215, 16777215))
        self.label_pixsize.setScaledContents(False)
        self.label_pixsize.setWordWrap(False)

        self.horizontalLayout_10.addWidget(self.label_pixsize)

        self.spinBox_pixsize = QSpinBox(self.widget_3)
        self.spinBox_pixsize.setObjectName(u"spinBox_pixsize")
        sizePolicy2 = QSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(
            self.spinBox_pixsize.sizePolicy().hasHeightForWidth())
        self.spinBox_pixsize.setSizePolicy(sizePolicy2)
        self.spinBox_pixsize.setMinimumSize(QSize(130, 32))
        self.spinBox_pixsize.setMaximumSize(QSize(16777215, 32))
        self.spinBox_pixsize.setFocusPolicy(Qt.ClickFocus)
        self.spinBox_pixsize.setFrame(True)
        self.spinBox_pixsize.setAlignment(Qt.AlignCenter)
        self.spinBox_pixsize.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinBox_pixsize.setKeyboardTracking(True)
        self.spinBox_pixsize.setProperty(u"showGroupSeparator", False)
        self.spinBox_pixsize.setMinimum(5)
        self.spinBox_pixsize.setMaximum(255)
        self.spinBox_pixsize.setValue(20)

        self.horizontalLayout_10.addWidget(self.spinBox_pixsize)

        self.verticalLayout.addWidget(self.widget_3)

        self.line_3 = QFrame(Form)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.Shape.HLine)
        self.line_3.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout.addWidget(self.line_3)

        self.frame = QFrame(Form)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Plain)
        self.frame.setLineWidth(0)
        self.horizontalLayout_6 = QHBoxLayout(self.frame)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.frame_2 = QFrame(self.frame)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Plain)
        self.frame_2.setLineWidth(0)
        self.verticalLayout_3 = QVBoxLayout(self.frame_2)
        self.verticalLayout_3.setSpacing(5)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.label_label = QLabel(self.frame_2)
        self.label_label.setObjectName(u"label_label")
        sizePolicy.setHeightForWidth(
            self.label_label.sizePolicy().hasHeightForWidth())
        self.label_label.setSizePolicy(sizePolicy)
        self.label_label.setMinimumSize(QSize(120, 32))
        self.label_label.setScaledContents(False)
        self.label_label.setWordWrap(False)

        self.verticalLayout_3.addWidget(self.label_label)

        self.label_unique_label = QLabel(self.frame_2)
        self.label_unique_label.setObjectName(u"label_unique_label")
        sizePolicy.setHeightForWidth(
            self.label_unique_label.sizePolicy().hasHeightForWidth())
        self.label_unique_label.setSizePolicy(sizePolicy)
        self.label_unique_label.setMinimumSize(QSize(120, 32))
        self.label_unique_label.setScaledContents(False)
        self.label_unique_label.setWordWrap(False)

        self.verticalLayout_3.addWidget(self.label_unique_label)

        self.label_race_label = QLabel(self.frame_2)
        self.label_race_label.setObjectName(u"label_race_label")
        sizePolicy.setHeightForWidth(
            self.label_race_label.sizePolicy().hasHeightForWidth())
        self.label_race_label.setSizePolicy(sizePolicy)
        self.label_race_label.setMinimumSize(QSize(120, 32))
        self.label_race_label.setScaledContents(False)
        self.label_race_label.setWordWrap(False)

        self.verticalLayout_3.addWidget(self.label_race_label)

        self.label_country = QLabel(self.frame_2)
        self.label_country.setObjectName(u"label_country")
        sizePolicy.setHeightForWidth(
            self.label_country.sizePolicy().hasHeightForWidth())
        self.label_country.setSizePolicy(sizePolicy)
        self.label_country.setMinimumSize(QSize(120, 32))
        self.label_country.setScaledContents(False)
        self.label_country.setWordWrap(False)

        self.verticalLayout_3.addWidget(self.label_country)

        self.horizontalLayout_6.addWidget(self.frame_2)

        self.frame_3 = QFrame(self.frame)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setFrameShape(QFrame.NoFrame)
        self.frame_3.setFrameShadow(QFrame.Plain)
        self.frame_3.setLineWidth(0)
        self.verticalLayout_4 = QVBoxLayout(self.frame_3)
        self.verticalLayout_4.setSpacing(5)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.lineEdit_label = QLineEdit(self.frame_3)
        self.lineEdit_label.setObjectName(u"lineEdit_label")
        self.lineEdit_label.setMinimumSize(QSize(0, 33))
        self.lineEdit_label.setMaximumSize(QSize(16777215, 33))
        self.lineEdit_label.setFocusPolicy(Qt.ClickFocus)
        self.lineEdit_label.setText(u"")
        self.lineEdit_label.setMaxLength(1024)
        self.lineEdit_label.setAlignment(Qt.AlignCenter)

        self.verticalLayout_4.addWidget(self.lineEdit_label)

        self.lineEdit_unique_label = QLineEdit(self.frame_3)
        self.lineEdit_unique_label.setObjectName(u"lineEdit_unique_label")
        self.lineEdit_unique_label.setMinimumSize(QSize(0, 33))
        self.lineEdit_unique_label.setMaximumSize(QSize(16777215, 33))
        self.lineEdit_unique_label.setFocusPolicy(Qt.ClickFocus)
        self.lineEdit_unique_label.setText(u"")
        self.lineEdit_unique_label.setMaxLength(1024)
        self.lineEdit_unique_label.setAlignment(Qt.AlignCenter)

        self.verticalLayout_4.addWidget(self.lineEdit_unique_label)

        self.lineEdit_race_label = QLineEdit(self.frame_3)
        self.lineEdit_race_label.setObjectName(u"lineEdit_race_label")
        self.lineEdit_race_label.setMinimumSize(QSize(0, 33))
        self.lineEdit_race_label.setMaximumSize(QSize(16777215, 33))
        self.lineEdit_race_label.setFocusPolicy(Qt.ClickFocus)
        self.lineEdit_race_label.setText(u"")
        self.lineEdit_race_label.setMaxLength(1024)
        self.lineEdit_race_label.setAlignment(Qt.AlignCenter)

        self.verticalLayout_4.addWidget(self.lineEdit_race_label)

        self.horizontalWidget_country = QWidget(self.frame_3)
        self.horizontalWidget_country.setObjectName(
            u"horizontalWidget_country")
        self.horizontalLayout_2 = QHBoxLayout(self.horizontalWidget_country)
        self.horizontalLayout_2.setSpacing(3)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.comboBox_country = CountryComboBox(self.horizontalWidget_country)
        self.comboBox_country.setObjectName(u"comboBox_country")
        sizePolicy3 = QSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(
            self.comboBox_country.sizePolicy().hasHeightForWidth())
        self.comboBox_country.setSizePolicy(sizePolicy3)
        self.comboBox_country.setMinimumSize(QSize(0, 31))
        self.comboBox_country.setMaximumSize(QSize(16777215, 31))
        self.comboBox_country.setFocusPolicy(Qt.ClickFocus)
        self.comboBox_country.setAutoFillBackground(False)
        self.comboBox_country.setEditable(True)
        self.comboBox_country.setCurrentText(u"")
        self.comboBox_country.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.comboBox_country.setFrame(True)
        self.comboBox_country.setModelColumn(0)

        self.horizontalLayout_2.addWidget(self.comboBox_country)

        self.label_national_flag = QLabel(self.horizontalWidget_country)
        self.label_national_flag.setObjectName(u"label_national_flag")
        self.label_national_flag.setMinimumSize(QSize(51, 31))
        self.label_national_flag.setMaximumSize(QSize(51, 31))
        font = QFont()
        font.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font.setPointSize(16)
        self.label_national_flag.setFont(font)
        self.label_national_flag.setStyleSheet(u"QLabel{\n"
                                               "background-color:rgb(255, 255, 255)\n"
                                               "}")
        self.label_national_flag.setAlignment(Qt.AlignCenter)
        self.label_national_flag.setWordWrap(False)

        self.horizontalLayout_2.addWidget(self.label_national_flag)

        self.verticalLayout_4.addWidget(self.horizontalWidget_country)

        self.horizontalLayout_6.addWidget(self.frame_3)

        self.verticalLayout.addWidget(self.frame)

        self.line_4 = QFrame(Form)
        self.line_4.setObjectName(u"line_4")
        self.line_4.setFrameShape(QFrame.Shape.HLine)
        self.line_4.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout.addWidget(self.line_4)

        self.widget_2 = QWidget(Form)
        self.widget_2.setObjectName(u"widget_2")
        self.verticalLayout_2 = QVBoxLayout(self.widget_2)
        self.verticalLayout_2.setSpacing(6)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.frame_4 = QFrame(self.widget_2)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setFrameShape(QFrame.StyledPanel)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.verticalLayout_5 = QVBoxLayout(self.frame_4)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(6, 0, 0, 0)
        self.checkBox_autosave_video = QCheckBox(self.frame_4)
        self.checkBox_autosave_video.setObjectName(u"checkBox_autosave_video")
        self.checkBox_autosave_video.setMinimumSize(QSize(0, 32))
        self.checkBox_autosave_video.setStyleSheet(u"")

        self.verticalLayout_5.addWidget(self.checkBox_autosave_video)

        self.checkBox_autosave_video_set = QCheckBox(self.frame_4)
        self.checkBox_autosave_video_set.setObjectName(
            u"checkBox_autosave_video_set")
        self.checkBox_autosave_video_set.setMinimumSize(QSize(0, 32))
        self.checkBox_autosave_video_set.setMaximumSize(QSize(16777215, 32))

        self.verticalLayout_5.addWidget(self.checkBox_autosave_video_set)

        self.checkBox_end_then_flag = QCheckBox(self.frame_4)
        self.checkBox_end_then_flag.setObjectName(u"checkBox_end_then_flag")
        self.checkBox_end_then_flag.setMinimumSize(QSize(0, 32))
        self.checkBox_end_then_flag.setStyleSheet(u"")

        self.verticalLayout_5.addWidget(self.checkBox_end_then_flag)

        self.checkBox_cursor_limit = QCheckBox(self.frame_4)
        self.checkBox_cursor_limit.setObjectName(u"checkBox_cursor_limit")
        self.checkBox_cursor_limit.setMinimumSize(QSize(0, 32))
        self.checkBox_cursor_limit.setStyleSheet(u"")

        self.verticalLayout_5.addWidget(self.checkBox_cursor_limit)

        self.widget_4 = QWidget(self.frame_4)
        self.widget_4.setObjectName(u"widget_4")
        self.widget_4.setMinimumSize(QSize(0, 32))
        self.horizontalLayout_7 = QHBoxLayout(self.widget_4)
        self.horizontalLayout_7.setSpacing(0)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.checkBox_auto_replay = QCheckBox(self.widget_4)
        self.checkBox_auto_replay.setObjectName(u"checkBox_auto_replay")
        self.checkBox_auto_replay.setStyleSheet(u"")

        self.horizontalLayout_7.addWidget(self.checkBox_auto_replay)

        self.spinBox_auto_replay = QSpinBox(self.widget_4)
        self.spinBox_auto_replay.setObjectName(u"spinBox_auto_replay")
        sizePolicy2.setHeightForWidth(
            self.spinBox_auto_replay.sizePolicy().hasHeightForWidth())
        self.spinBox_auto_replay.setSizePolicy(sizePolicy2)
        self.spinBox_auto_replay.setMinimumSize(QSize(130, 32))
        self.spinBox_auto_replay.setMaximumSize(QSize(16777215, 32))
        self.spinBox_auto_replay.setFocusPolicy(Qt.ClickFocus)
        self.spinBox_auto_replay.setFrame(True)
        self.spinBox_auto_replay.setAlignment(Qt.AlignCenter)
        self.spinBox_auto_replay.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinBox_auto_replay.setKeyboardTracking(True)
        self.spinBox_auto_replay.setProperty(u"showGroupSeparator", False)
        self.spinBox_auto_replay.setMinimum(0)
        self.spinBox_auto_replay.setMaximum(100)
        self.spinBox_auto_replay.setValue(30)

        self.horizontalLayout_7.addWidget(self.spinBox_auto_replay)

        self.label_auto_replay_percent = QLabel(self.widget_4)
        self.label_auto_replay_percent.setObjectName(
            u"label_auto_replay_percent")
        font1 = QFont()
        font1.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font1.setPointSize(12)
        self.label_auto_replay_percent.setFont(font1)
# if QT_CONFIG(tooltip)
        self.label_auto_replay_percent.setToolTip(u"")
# endif // QT_CONFIG(tooltip)
# if QT_CONFIG(statustip)
        self.label_auto_replay_percent.setStatusTip(u"")
# endif // QT_CONFIG(statustip)
# if QT_CONFIG(whatsthis)
        self.label_auto_replay_percent.setWhatsThis(u"")
# endif // QT_CONFIG(whatsthis)
        self.label_auto_replay_percent.setText(u" %")
        self.label_auto_replay_percent.setScaledContents(False)
        self.label_auto_replay_percent.setWordWrap(False)

        self.horizontalLayout_7.addWidget(self.label_auto_replay_percent)

        self.horizontalSpacer = QSpacerItem(
            0, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_7.addItem(self.horizontalSpacer)

        self.verticalLayout_5.addWidget(self.widget_4)

        self.checkBox_auto_notification = QCheckBox(self.frame_4)
        self.checkBox_auto_notification.setObjectName(
            u"checkBox_auto_notification")
        self.checkBox_auto_notification.setMinimumSize(QSize(0, 32))
        self.checkBox_auto_notification.setStyleSheet(u"")

        self.verticalLayout_5.addWidget(self.checkBox_auto_notification)

        self.verticalLayout_2.addWidget(self.frame_4)

        self.widget_5 = QWidget(self.widget_2)
        self.widget_5.setObjectName(u"widget_5")
        self.widget_5.setMinimumSize(QSize(0, 32))
        self.horizontalLayout = QHBoxLayout(self.widget_5)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.label_constraint = QLabel(self.widget_5)
        self.label_constraint.setObjectName(u"label_constraint")
        self.label_constraint.setMinimumSize(QSize(100, 0))
        self.label_constraint.setScaledContents(False)
        self.label_constraint.setWordWrap(False)

        self.horizontalLayout.addWidget(self.label_constraint)

        self.lineEdit_constraint = QLineEdit(self.widget_5)
        self.lineEdit_constraint.setObjectName(u"lineEdit_constraint")
        self.lineEdit_constraint.setMinimumSize(QSize(0, 32))
        self.lineEdit_constraint.setMaximumSize(QSize(16777215, 32))
        self.lineEdit_constraint.setFocusPolicy(Qt.ClickFocus)
        self.lineEdit_constraint.setAlignment(Qt.AlignCenter)

        self.horizontalLayout.addWidget(self.lineEdit_constraint)

        self.verticalLayout_2.addWidget(self.widget_5)

        self.widget_6 = QWidget(self.widget_2)
        self.widget_6.setObjectName(u"widget_6")
        self.widget_6.setMinimumSize(QSize(0, 32))
        self.horizontalLayout_8 = QHBoxLayout(self.widget_6)
        self.horizontalLayout_8.setSpacing(0)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.label_attempt_times_limit = QLabel(self.widget_6)
        self.label_attempt_times_limit.setObjectName(
            u"label_attempt_times_limit")
        self.label_attempt_times_limit.setMinimumSize(QSize(100, 0))
        self.label_attempt_times_limit.setScaledContents(False)
        self.label_attempt_times_limit.setWordWrap(False)

        self.horizontalLayout_8.addWidget(self.label_attempt_times_limit)

        self.spinBox_attempt_times_limit = QSpinBox(self.widget_6)
        self.spinBox_attempt_times_limit.setObjectName(
            u"spinBox_attempt_times_limit")
        sizePolicy2.setHeightForWidth(
            self.spinBox_attempt_times_limit.sizePolicy().hasHeightForWidth())
        self.spinBox_attempt_times_limit.setSizePolicy(sizePolicy2)
        self.spinBox_attempt_times_limit.setMinimumSize(QSize(130, 32))
        self.spinBox_attempt_times_limit.setMaximumSize(QSize(16777215, 32))
        self.spinBox_attempt_times_limit.setFocusPolicy(Qt.ClickFocus)
        self.spinBox_attempt_times_limit.setFrame(True)
        self.spinBox_attempt_times_limit.setAlignment(Qt.AlignCenter)
        self.spinBox_attempt_times_limit.setButtonSymbols(
            QAbstractSpinBox.NoButtons)
        self.spinBox_attempt_times_limit.setKeyboardTracking(True)
        self.spinBox_attempt_times_limit.setProperty(
            u"showGroupSeparator", False)
        self.spinBox_attempt_times_limit.setMinimum(0)
        self.spinBox_attempt_times_limit.setMaximum(99999999)
        self.spinBox_attempt_times_limit.setValue(99999999)

        self.horizontalLayout_8.addWidget(self.spinBox_attempt_times_limit)

        self.horizontalSpacer_3 = QSpacerItem(
            0, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_8.addItem(self.horizontalSpacer_3)

        self.verticalLayout_2.addWidget(self.widget_6)

        self.verticalLayout.addWidget(self.widget_2)

        self.line_2 = QFrame(Form)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.Shape.HLine)
        self.line_2.setFrameShadow(QFrame.Shadow.Sunken)

        self.verticalLayout.addWidget(self.line_2)

        self.widget_7 = QWidget(Form)
        self.widget_7.setObjectName(u"widget_7")
        self.horizontalLayout_11 = QHBoxLayout(self.widget_7)
        self.horizontalLayout_11.setSpacing(10)
        self.horizontalLayout_11.setObjectName(u"horizontalLayout_11")
        self.horizontalLayout_11.setContentsMargins(0, 0, 0, 0)
        self.pushButton_yes = QPushButton(self.widget_7)
        self.pushButton_yes.setObjectName(u"pushButton_yes")
        sizePolicy3.setHeightForWidth(
            self.pushButton_yes.sizePolicy().hasHeightForWidth())
        self.pushButton_yes.setSizePolicy(sizePolicy3)
        self.pushButton_yes.setMinimumSize(QSize(100, 36))
        self.pushButton_yes.setMaximumSize(QSize(16777215, 16777215))
        self.pushButton_yes.setFocusPolicy(Qt.NoFocus)
        self.pushButton_yes.setAutoDefault(False)
        self.pushButton_yes.setFlat(False)

        self.horizontalLayout_11.addWidget(self.pushButton_yes)

        self.pushButton_no = QPushButton(self.widget_7)
        self.pushButton_no.setObjectName(u"pushButton_no")
        sizePolicy3.setHeightForWidth(
            self.pushButton_no.sizePolicy().hasHeightForWidth())
        self.pushButton_no.setSizePolicy(sizePolicy3)
        self.pushButton_no.setMinimumSize(QSize(100, 36))
        self.pushButton_no.setMaximumSize(QSize(16777215, 16777215))
        self.pushButton_no.setFocusPolicy(Qt.NoFocus)

        self.horizontalLayout_11.addWidget(self.pushButton_no)

        self.verticalLayout.addWidget(self.widget_7)

        self.line_2.raise_()
        self.line_3.raise_()
        self.line_4.raise_()
        self.widget_3.raise_()
        self.widget_2.raise_()
        self.widget_7.raise_()
        self.frame.raise_()

        self.retranslateUi(Form)
        self.checkBox_auto_replay.toggled.connect(
            self.spinBox_auto_replay.setEnabled)
        self.checkBox_auto_replay.toggled.connect(
            self.label_auto_replay_percent.setEnabled)
        self.pushButton_no.clicked.connect(Form.close)

        self.comboBox_gamemode.setCurrentIndex(0)
        self.comboBox_country.setCurrentIndex(-1)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        self.label_gamemode.setText(QCoreApplication.translate(
            "Form", u"\u6e38\u620f\u6a21\u5f0f\uff1a", None))
        self.comboBox_gamemode.setItemText(
            0, QCoreApplication.translate("Form", u"\u6807\u51c6", None))
        self.comboBox_gamemode.setItemText(
            1, QCoreApplication.translate("Form", u"Win7", None))
        self.comboBox_gamemode.setItemText(
            2, QCoreApplication.translate("Form", u"\u5f3a\u65e0\u731c", None))
        self.comboBox_gamemode.setItemText(
            3, QCoreApplication.translate("Form", u"\u5f31\u65e0\u731c", None))
        self.comboBox_gamemode.setItemText(4, QCoreApplication.translate(
            "Form", u"\u7ecf\u5178\u65e0\u731c", None))
        self.comboBox_gamemode.setItemText(
            5, QCoreApplication.translate("Form", u"\u51c6\u65e0\u731c", None))
        self.comboBox_gamemode.setItemText(
            6, QCoreApplication.translate("Form", u"\u5f3a\u53ef\u731c", None))
        self.comboBox_gamemode.setItemText(
            7, QCoreApplication.translate("Form", u"\u5f31\u53ef\u731c", None))

        self.label_pixsize.setText(QCoreApplication.translate(
            "Form", u"\u65b9\u683c\u8fb9\u957f\uff1a", None))
# if QT_CONFIG(tooltip)
        self.label_label.setToolTip("")
# endif // QT_CONFIG(tooltip)
        self.label_label.setText(QCoreApplication.translate(
            "Form", u"\u6807\u8bc6\uff1a", None))
# if QT_CONFIG(tooltip)
        self.label_unique_label.setToolTip(QCoreApplication.translate(
            "Form", u"\u7528\u4e8e\u4e0e\u5176\u4ed6\u4eba\u76f8\u533a\u5206\uff0c\u4f46\u4e0d\u5e0c\u671b\u6392\u540d\u7f51\u7ad9\u548c\u8f6f\u4ef6\u5c55\u793a\u51fa\u6765", None))
# endif // QT_CONFIG(tooltip)
        self.label_unique_label.setText(QCoreApplication.translate(
            "Form", u"\u4e2a\u6027\u6807\u8bc6\uff1a", None))
# if QT_CONFIG(tooltip)
        self.label_race_label.setToolTip(QCoreApplication.translate(
            "Form", u"\u7528\u4e8e\u53c2\u52a0\u6bd4\u8d5b", None))
# endif // QT_CONFIG(tooltip)
        self.label_race_label.setText(QCoreApplication.translate(
            "Form", u"\u6bd4\u8d5b\u6807\u8bc6\uff1a", None))
        self.label_country.setText(QCoreApplication.translate(
            "Form", u"\u56fd\u5bb6\u6216\u5730\u533a\uff1a", None))
        self.label_national_flag.setText("")
# if QT_CONFIG(tooltip)
        self.checkBox_autosave_video.setToolTip(QCoreApplication.translate(
            "Form", u"\u5b8c\u6210\u540e\u81ea\u52a8\u5c06\u5f55\u50cf\u4fdd\u5b58\u5230replay\u6587\u4ef6\u5939\u4e0b", None))
# endif // QT_CONFIG(tooltip)
        self.checkBox_autosave_video.setText(QCoreApplication.translate(
            "Form", u"\u81ea\u52a8\u4fdd\u5b58\u5f55\u50cf\uff08\u63a8\u8350\uff09", None))
        self.checkBox_autosave_video_set.setText(QCoreApplication.translate(
            "Form", u"\u81ea\u52a8\u4fdd\u5b58\u5f55\u50cf\u96c6", None))
# if QT_CONFIG(tooltip)
        self.checkBox_end_then_flag.setToolTip("")
# endif // QT_CONFIG(tooltip)
        self.checkBox_end_then_flag.setText(QCoreApplication.translate(
            "Form", u"\u7ed3\u675f\u540e\u6807\u96f7", None))
# if QT_CONFIG(tooltip)
        self.checkBox_cursor_limit.setToolTip("")
# endif // QT_CONFIG(tooltip)
        self.checkBox_cursor_limit.setText(QCoreApplication.translate(
            "Form", u"\u5149\u6807\u4e0d\u80fd\u8d85\u51fa\u8fb9\u6846", None))
# if QT_CONFIG(tooltip)
        self.checkBox_auto_replay.setToolTip("")
# endif // QT_CONFIG(tooltip)
        self.checkBox_auto_replay.setText(QCoreApplication.translate(
            "Form", u"\u81ea\u52a8\u91cd\u5f00\uff1a", None))
# if QT_CONFIG(tooltip)
        self.checkBox_auto_notification.setToolTip("")
# endif // QT_CONFIG(tooltip)
        self.checkBox_auto_notification.setText(QCoreApplication.translate(
            "Form", u"\u5141\u8bb8\u7eaa\u5f55\u5f39\u7a97\uff08\u63a8\u8350\uff09", None))
        self.label_constraint.setText(QCoreApplication.translate(
            "Form", u"\u5c40\u9762\u7ea6\u675f\uff1a", None))
        self.lineEdit_constraint.setText("")
        self.label_attempt_times_limit.setText(QCoreApplication.translate(
            "Form", u"\u5c1d\u8bd5\u6b21\u6570\uff1a", None))
        self.pushButton_yes.setText(
            QCoreApplication.translate("Form", u"\u786e\u5b9a", None))
# if QT_CONFIG(shortcut)
        self.pushButton_yes.setShortcut(
            QCoreApplication.translate("Form", u"Return", None))
# endif // QT_CONFIG(shortcut)
        self.pushButton_no.setText(
            QCoreApplication.translate("Form", u"\u53d6\u6d88", None))
        pass
    # retranslateUi
