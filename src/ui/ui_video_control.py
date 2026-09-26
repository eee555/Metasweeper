# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'ui_video_control.ui'
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
from PySide6.QtWidgets import (QApplication, QDoubleSpinBox, QHBoxLayout, QPushButton,
                               QSizePolicy, QSlider, QSpacerItem, QTabWidget,
                               QVBoxLayout, QWidget)

from ui.uiComponents import SpeedLabel


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(520, 640)
        Form.setMinimumSize(QSize(480, 640))
        Form.setMaximumSize(QSize(600, 640))
        Form.setSizeIncrement(QSize(0, 0))
        Form.setWindowTitle(u"")
        self.verticalLayout = QVBoxLayout(Form)
        self.verticalLayout.setSpacing(5)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(20, 30, 20, 20)
        self.horizontalSlider_time = QSlider(Form)
        self.horizontalSlider_time.setObjectName(u"horizontalSlider_time")
        self.horizontalSlider_time.setFocusPolicy(Qt.NoFocus)
        self.horizontalSlider_time.setAutoFillBackground(False)
        self.horizontalSlider_time.setStyleSheet(u"QSlider::groove {\n"
                                                 "    border: 0px solid #bbbbbb;\n"
                                                 "    background-color: #50A6EA;\n"
                                                 "    border-radius: 4px;\n"
                                                 "}\n"
                                                 "QSlider::groove:horizontal {\n"
                                                 "    height: 16px;\n"
                                                 "}\n"
                                                 "QSlider::groove:vertical {\n"
                                                 "    width: 0px;\n"
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
                                                 ""
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
        self.horizontalSlider_time.setOrientation(Qt.Horizontal)
        self.horizontalSlider_time.setInvertedAppearance(False)
        self.horizontalSlider_time.setInvertedControls(False)
        self.horizontalSlider_time.setTickPosition(QSlider.NoTicks)
        self.horizontalSlider_time.setTickInterval(0)

        self.verticalLayout.addWidget(self.horizontalSlider_time)

        self.widget = QWidget(Form)
        self.widget.setObjectName(u"widget")
        self.horizontalLayout = QHBoxLayout(self.widget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.pushButton_replay = QPushButton(self.widget)
        self.pushButton_replay.setObjectName(u"pushButton_replay")
        self.pushButton_replay.setMinimumSize(QSize(40, 40))
        self.pushButton_replay.setMaximumSize(QSize(40, 40))
        self.pushButton_replay.setToolTipDuration(0)
        self.pushButton_replay.setStyleSheet(u"QPushButton {\n"
                                             "    background-color: rgba(0,0,0,0);\n"
                                             "    border: none;\n"
                                             "    image: url(media/replay.svg);\n"
                                             "}")

        self.horizontalLayout.addWidget(self.pushButton_replay)

        self.pushButton_play = QPushButton(self.widget)
        self.pushButton_play.setObjectName(u"pushButton_play")
        self.pushButton_play.setMinimumSize(QSize(40, 40))
        self.pushButton_play.setMaximumSize(QSize(40, 40))
        self.pushButton_play.setToolTipDuration(0)
        self.pushButton_play.setStyleSheet(u"QPushButton {\n"
                                           "    background-color: rgba(0,0,0,0);\n"
                                           "    border: none;\n"
                                           "    image: url(media/play.svg);\n"
                                           "}")

        self.horizontalLayout.addWidget(self.pushButton_play)

        self.label_speed = SpeedLabel(self.widget)
        self.label_speed.setObjectName(u"label_speed")
        self.label_speed.setMinimumSize(QSize(60, 40))
        self.label_speed.setMaximumSize(QSize(60, 40))
        font = QFont()
        font.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font.setPointSize(16)
        font.setBold(False)
        font.setItalic(False)
        self.label_speed.setFont(font)
        self.label_speed.setStyleSheet(u"QLabel {border-image: url(media/speed.svg);\n"
                                       "font: 16pt \"\u5fae\u8f6f\u96c5\u9ed1\";\n"
                                       "color: #50A6EA;}")
        self.label_speed.setText(u"1\u00d7")
        self.label_speed.setAlignment(Qt.AlignCenter)

        self.horizontalLayout.addWidget(self.label_speed)

        self.pushButton_path = QPushButton(self.widget)
        self.pushButton_path.setObjectName(u"pushButton_path")
        self.pushButton_path.setMinimumSize(QSize(40, 40))
        self.pushButton_path.setMaximumSize(QSize(40, 40))
        self.pushButton_path.setStyleSheet(u"QPushButton {\n"
                                           "    background-color: rgba(0,0,0,0);\n"
                                           "    border: none;\n"
                                           "    image: url(media/path.svg);\n"
                                           "}")
        self.pushButton_path.setCheckable(True)

        self.horizontalLayout.addWidget(self.pushButton_path)

        self.pushButton_op = QPushButton(self.widget)
        self.pushButton_op.setObjectName(u"pushButton_op")
        self.pushButton_op.setMinimumSize(QSize(40, 40))
        self.pushButton_op.setMaximumSize(QSize(40, 40))
        self.pushButton_op.setStyleSheet(u"QPushButton {\n"
                                         "    background-color: rgba(0,0,0,0);\n"
                                         "    border: none;\n"
                                         "    image: url(media/op.svg);\n"
                                         "}")
        self.pushButton_op.setCheckable(True)

        self.horizontalLayout.addWidget(self.pushButton_op)

        self.horizontalSpacer = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.doubleSpinBox_time = QDoubleSpinBox(self.widget)
        self.doubleSpinBox_time.setObjectName(u"doubleSpinBox_time")
        font1 = QFont()
        font1.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font1.setPointSize(20)
        font1.setBold(False)
        font1.setItalic(False)
        self.doubleSpinBox_time.setFont(font1)
        self.doubleSpinBox_time.setContextMenuPolicy(Qt.NoContextMenu)
        self.doubleSpinBox_time.setStyleSheet(u"font: 20pt \"\u5fae\u8f6f\u96c5\u9ed1\";\n"
                                              "color: #50A6EA;\n"
                                              "background-color: rgb(240, 240, 240);")
        self.doubleSpinBox_time.setWrapping(False)
        self.doubleSpinBox_time.setFrame(False)
        self.doubleSpinBox_time.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox_time.setDecimals(3)
        self.doubleSpinBox_time.setMinimum(-999.990000000000009)
        self.doubleSpinBox_time.setMaximum(999.990000000000009)
        self.doubleSpinBox_time.setSingleStep(0.001000000000000)

        self.horizontalLayout.addWidget(self.doubleSpinBox_time)

        self.verticalLayout.addWidget(self.widget)

        self.tabWidget = QTabWidget(Form)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setContextMenuPolicy(Qt.NoContextMenu)
        self.tabWidget.setStyleSheet(u"QTabWidget::pane { margin: 0px; border: 0px; }\n"
                                     "QTabBar::tab {\n"
                                     "    font-family: \"Microsoft YaHei\", \"\u5fae\u8f6f\u96c5\u9ed1\", \"Segoe UI\", Arial, sans-serif;\n"
                                     "    font-size: 9pt;\n"
                                     "    height: 22px;\n"
                                     "}\n"
                                     "")
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.setMovable(True)
        self.tabWidget.setTabBarAutoHide(True)

        self.verticalLayout.addWidget(self.tabWidget)

        self.retranslateUi(Form)

        self.tabWidget.setCurrentIndex(-1)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        # if QT_CONFIG(tooltip)
        self.pushButton_replay.setToolTip(
            QCoreApplication.translate("Form", u"\u91cd\u64ad", None))
# endif // QT_CONFIG(tooltip)
        self.pushButton_replay.setText("")
# if QT_CONFIG(tooltip)
        self.pushButton_play.setToolTip(QCoreApplication.translate(
            "Form", u"\u64ad\u653e/\u6682\u505c", None))
# endif // QT_CONFIG(tooltip)
        self.pushButton_play.setText("")
# if QT_CONFIG(tooltip)
        self.label_speed.setToolTip(QCoreApplication.translate(
            "Form", u"\u6ed1\u52a8\u6eda\u8f6e\u4fee\u6539\u64ad\u653e\u901f\u5ea6", None))
# endif // QT_CONFIG(tooltip)
# if QT_CONFIG(tooltip)
        self.pushButton_path.setToolTip(QCoreApplication.translate(
            "Form", u"\u663e\u793a\u9f20\u6807\u8f68\u8ff9", None))
# endif // QT_CONFIG(tooltip)
        self.pushButton_path.setText("")
# if QT_CONFIG(tooltip)
        self.pushButton_op.setToolTip(QCoreApplication.translate(
            "Form", u"\u663e\u793a\u7a7a", None))
# endif // QT_CONFIG(tooltip)
        self.pushButton_op.setText("")
        pass
    # retranslateUi
