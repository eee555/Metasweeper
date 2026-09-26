# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'ui_record_pop.ui'
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
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLayout,
                               QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout,
                               QWidget)


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(361, 738)
        Form.setMinimumSize(QSize(361, 382))
        Form.setMaximumSize(QSize(361, 1080))
        Form.setSizeIncrement(QSize(0, 0))
        Form.setWindowOpacity(10.000000000000000)
        Form.setAutoFillBackground(False)
        self.verticalLayout = QVBoxLayout(Form)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setSizeConstraint(QLayout.SetFixedSize)
        self.label_race_label_3 = QLabel(Form)
        self.label_race_label_3.setObjectName(u"label_race_label_3")
        self.label_race_label_3.setMinimumSize(QSize(0, 41))
        self.label_race_label_3.setStyleSheet(u"font-size: 16pt;")
        self.label_race_label_3.setScaledContents(False)
        self.label_race_label_3.setWordWrap(False)

        self.verticalLayout.addWidget(
            self.label_race_label_3, 0, Qt.AlignHCenter)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalSpacer_33 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_33)

        self.label = QLabel(Form)
        self.label.setObjectName(u"label")
        self.label.setStyleSheet(u"font-size: 16pt;")

        self.horizontalLayout_2.addWidget(self.label)

        self.label_16 = QLabel(Form)
        self.label_16.setObjectName(u"label_16")
        self.label_16.setStyleSheet(u"font-size: 16pt;")

        self.horizontalLayout_2.addWidget(self.label_16)

        self.horizontalSpacer_34 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_34)

        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.widget1 = QWidget(Form)
        self.widget1.setObjectName(u"widget1")
        self.widget1.setMinimumSize(QSize(0, 41))
        self.horizontalLayout_3 = QHBoxLayout(self.widget1)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer)

        self.label1 = QLabel(self.widget1)
        self.label1.setObjectName(u"label1")
        self.label1.setMinimumSize(QSize(36, 36))
        self.label1.setMaximumSize(QSize(36, 36))
        self.label1.setStyleSheet(u"border-image: url(media/rtime.svg);")

        self.horizontalLayout_3.addWidget(self.label1)

        self.label_1 = QLabel(self.widget1)
        self.label_1.setObjectName(u"label_1")
        self.label_1.setStyleSheet(u"font-size: 14pt;")
        self.label_1.setScaledContents(False)
        self.label_1.setWordWrap(False)

        self.horizontalLayout_3.addWidget(self.label_1)

        self.horizontalSpacer_2 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)

        self.verticalLayout.addWidget(self.widget1)

        self.widget3 = QWidget(Form)
        self.widget3.setObjectName(u"widget3")
        self.widget3.setMinimumSize(QSize(0, 41))
        self.horizontalLayout_6 = QHBoxLayout(self.widget3)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_7 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_6.addItem(self.horizontalSpacer_7)

        self.label3 = QLabel(self.widget3)
        self.label3.setObjectName(u"label3")
        self.label3.setMinimumSize(QSize(36, 36))
        self.label3.setMaximumSize(QSize(36, 36))
        self.label3.setStyleSheet(u"border-image: url(media/bbbv_s.svg);")

        self.horizontalLayout_6.addWidget(self.label3)

        self.label_3 = QLabel(self.widget3)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setStyleSheet(u"font-size: 14pt;")
        self.label_3.setScaledContents(False)
        self.label_3.setWordWrap(False)

        self.horizontalLayout_6.addWidget(self.label_3)

        self.horizontalSpacer_8 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_6.addItem(self.horizontalSpacer_8)

        self.verticalLayout.addWidget(self.widget3)

        self.widget5 = QWidget(Form)
        self.widget5.setObjectName(u"widget5")
        self.widget5.setMinimumSize(QSize(0, 41))
        self.horizontalLayout_7 = QHBoxLayout(self.widget5)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.horizontalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_9 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_7.addItem(self.horizontalSpacer_9)

        self.label5 = QLabel(self.widget5)
        self.label5.setObjectName(u"label5")
        self.label5.setMinimumSize(QSize(36, 36))
        self.label5.setMaximumSize(QSize(36, 36))
        self.label5.setStyleSheet(u"border-image: url(media/stnb.svg);")

        self.horizontalLayout_7.addWidget(self.label5)

        self.label_5 = QLabel(self.widget5)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setStyleSheet(u"font-size: 14pt;")
        self.label_5.setScaledContents(False)
        self.label_5.setWordWrap(False)

        self.horizontalLayout_7.addWidget(self.label_5)

        self.horizontalSpacer_10 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_7.addItem(self.horizontalSpacer_10)

        self.verticalLayout.addWidget(self.widget5)

        self.widget7 = QWidget(Form)
        self.widget7.setObjectName(u"widget7")
        self.widget7.setMinimumSize(QSize(0, 41))
        self.horizontalLayout_10 = QHBoxLayout(self.widget7)
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.horizontalLayout_10.setSizeConstraint(
            QLayout.SetDefaultConstraint)
        self.horizontalLayout_10.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_15 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_10.addItem(self.horizontalSpacer_15)

        self.label7 = QLabel(self.widget7)
        self.label7.setObjectName(u"label7")
        self.label7.setMinimumSize(QSize(36, 36))
        self.label7.setMaximumSize(QSize(36, 36))
        self.label7.setStyleSheet(u"border-image: url(media/ioe.svg);")

        self.horizontalLayout_10.addWidget(self.label7)

        self.label_7 = QLabel(self.widget7)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setStyleSheet(u"font-size: 14pt;")
        self.label_7.setScaledContents(False)
        self.label_7.setWordWrap(False)

        self.horizontalLayout_10.addWidget(self.label_7)

        self.horizontalSpacer_16 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_10.addItem(self.horizontalSpacer_16)

        self.verticalLayout.addWidget(self.widget7)

        self.widget9 = QWidget(Form)
        self.widget9.setObjectName(u"widget9")
        self.widget9.setMinimumSize(QSize(0, 41))
        self.horizontalLayout_12 = QHBoxLayout(self.widget9)
        self.horizontalLayout_12.setObjectName(u"horizontalLayout_12")
        self.horizontalLayout_12.setSizeConstraint(
            QLayout.SetDefaultConstraint)
        self.horizontalLayout_12.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_19 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_12.addItem(self.horizontalSpacer_19)

        self.label9 = QLabel(self.widget9)
        self.label9.setObjectName(u"label9")
        self.label9.setMinimumSize(QSize(36, 36))
        self.label9.setMaximumSize(QSize(36, 36))
        self.label9.setStyleSheet(u"border-image: url(media/path_record.svg);")

        self.horizontalLayout_12.addWidget(self.label9)

        self.label_9 = QLabel(self.widget9)
        self.label_9.setObjectName(u"label_9")
        self.label_9.setStyleSheet(u"font-size: 14pt;")
        self.label_9.setScaledContents(False)
        self.label_9.setWordWrap(False)

        self.horizontalLayout_12.addWidget(self.label_9)

        self.horizontalSpacer_20 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_12.addItem(self.horizontalSpacer_20)

        self.verticalLayout.addWidget(self.widget9)

        self.widget11 = QWidget(Form)
        self.widget11.setObjectName(u"widget11")
        self.widget11.setMinimumSize(QSize(0, 41))
        self.horizontalLayout_13 = QHBoxLayout(self.widget11)
        self.horizontalLayout_13.setObjectName(u"horizontalLayout_13")
        self.horizontalLayout_13.setSizeConstraint(
            QLayout.SetDefaultConstraint)
        self.horizontalLayout_13.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_21 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_13.addItem(self.horizontalSpacer_21)

        self.label11 = QLabel(self.widget11)
        self.label11.setObjectName(u"label11")
        self.label11.setMinimumSize(QSize(36, 36))
        self.label11.setMaximumSize(QSize(36, 36))
        self.label11.setStyleSheet(u"border-image: url(media/rqp.svg);")

        self.horizontalLayout_13.addWidget(self.label11)

        self.label_11 = QLabel(self.widget11)
        self.label_11.setObjectName(u"label_11")
        self.label_11.setStyleSheet(u"font-size: 14pt;")
        self.label_11.setScaledContents(False)
        self.label_11.setWordWrap(False)

        self.horizontalLayout_13.addWidget(self.label_11)

        self.horizontalSpacer_22 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_13.addItem(self.horizontalSpacer_22)

        self.verticalLayout.addWidget(self.widget11)

        self.widget13 = QWidget(Form)
        self.widget13.setObjectName(u"widget13")
        self.widget13.setMinimumSize(QSize(0, 41))
        self.horizontalLayout_15 = QHBoxLayout(self.widget13)
        self.horizontalLayout_15.setObjectName(u"horizontalLayout_15")
        self.horizontalLayout_15.setSizeConstraint(
            QLayout.SetDefaultConstraint)
        self.horizontalLayout_15.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_27 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_15.addItem(self.horizontalSpacer_27)

        self.label13 = QLabel(self.widget13)
        self.label13.setObjectName(u"label13")
        self.label13.setMinimumSize(QSize(36, 36))
        self.label13.setMaximumSize(QSize(36, 36))
        self.label13.setStyleSheet(u"border-image: url(media/pb.svg);")

        self.horizontalLayout_15.addWidget(self.label13)

        self.label_13 = QLabel(self.widget13)
        self.label_13.setObjectName(u"label_13")
        self.label_13.setStyleSheet(u"font-size: 14pt;")
        self.label_13.setScaledContents(False)
        self.label_13.setWordWrap(False)

        self.horizontalLayout_15.addWidget(self.label_13)

        self.label__13 = QLabel(self.widget13)
        self.label__13.setObjectName(u"label__13")
        self.label__13.setStyleSheet(u"font-size: 14pt;")
        self.label__13.setText(u"148")
        self.label__13.setScaledContents(False)
        self.label__13.setWordWrap(False)

        self.horizontalLayout_15.addWidget(self.label__13)

        self.label___13 = QLabel(self.widget13)
        self.label___13.setObjectName(u"label___13")
        self.label___13.setStyleSheet(u"font-size: 14pt;")
        self.label___13.setScaledContents(False)
        self.label___13.setWordWrap(False)

        self.horizontalLayout_15.addWidget(self.label___13)

        self.horizontalSpacer_28 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_15.addItem(self.horizontalSpacer_28)

        self.verticalLayout.addWidget(self.widget13)

        self.widget14 = QWidget(Form)
        self.widget14.setObjectName(u"widget14")
        self.widget14.setMinimumSize(QSize(0, 41))
        self.horizontalLayout_16 = QHBoxLayout(self.widget14)
        self.horizontalLayout_16.setObjectName(u"horizontalLayout_16")
        self.horizontalLayout_16.setSizeConstraint(
            QLayout.SetDefaultConstraint)
        self.horizontalLayout_16.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_29 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_16.addItem(self.horizontalSpacer_29)

        self.label14 = QLabel(self.widget14)
        self.label14.setObjectName(u"label14")
        self.label14.setMinimumSize(QSize(36, 36))
        self.label14.setMaximumSize(QSize(36, 36))
        self.label14.setStyleSheet(u"border-image: url(media/pb.svg);")

        self.horizontalLayout_16.addWidget(self.label14)

        self.label_14 = QLabel(self.widget14)
        self.label_14.setObjectName(u"label_14")
        self.label_14.setStyleSheet(u"font-size: 14pt;")
        self.label_14.setScaledContents(False)
        self.label_14.setWordWrap(False)

        self.horizontalLayout_16.addWidget(self.label_14)

        self.label__14 = QLabel(self.widget14)
        self.label__14.setObjectName(u"label__14")
        self.label__14.setStyleSheet(u"font-size: 14pt;")
        self.label__14.setText(u"148")
        self.label__14.setScaledContents(False)
        self.label__14.setWordWrap(False)

        self.horizontalLayout_16.addWidget(self.label__14)

        self.label___14 = QLabel(self.widget14)
        self.label___14.setObjectName(u"label___14")
        self.label___14.setStyleSheet(u"font-size: 14pt;")
        self.label___14.setScaledContents(False)
        self.label___14.setWordWrap(False)

        self.horizontalLayout_16.addWidget(self.label___14)

        self.horizontalSpacer_30 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_16.addItem(self.horizontalSpacer_30)

        self.verticalLayout.addWidget(self.widget14)

        self.widget15 = QWidget(Form)
        self.widget15.setObjectName(u"widget15")
        self.widget15.setMinimumSize(QSize(0, 41))
        self.horizontalLayout_17 = QHBoxLayout(self.widget15)
        self.horizontalLayout_17.setObjectName(u"horizontalLayout_17")
        self.horizontalLayout_17.setSizeConstraint(
            QLayout.SetDefaultConstraint)
        self.horizontalLayout_17.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_31 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_17.addItem(self.horizontalSpacer_31)

        self.label15 = QLabel(self.widget15)
        self.label15.setObjectName(u"label15")
        self.label15.setMinimumSize(QSize(36, 36))
        self.label15.setMaximumSize(QSize(36, 36))
        self.label15.setStyleSheet(u"border-image: url(media/pb.svg);")

        self.horizontalLayout_17.addWidget(self.label15)

        self.label_15 = QLabel(self.widget15)
        self.label_15.setObjectName(u"label_15")
        self.label_15.setStyleSheet(u"font-size: 14pt;")
        self.label_15.setScaledContents(False)
        self.label_15.setWordWrap(False)

        self.horizontalLayout_17.addWidget(self.label_15)

        self.label__15 = QLabel(self.widget15)
        self.label__15.setObjectName(u"label__15")
        self.label__15.setStyleSheet(u"font-size: 14pt;")
        self.label__15.setText(u"148")
        self.label__15.setScaledContents(False)
        self.label__15.setWordWrap(False)

        self.horizontalLayout_17.addWidget(self.label__15)

        self.label___15 = QLabel(self.widget15)
        self.label___15.setObjectName(u"label___15")
        self.label___15.setStyleSheet(u"font-size: 14pt;")
        self.label___15.setScaledContents(False)
        self.label___15.setWordWrap(False)

        self.horizontalLayout_17.addWidget(self.label___15)

        self.horizontalSpacer_32 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_17.addItem(self.horizontalSpacer_32)

        self.verticalLayout.addWidget(self.widget15)

        self.widget = QWidget(Form)
        self.widget.setObjectName(u"widget")
        self.widget.setMinimumSize(QSize(0, 41))
        self.horizontalLayout = QHBoxLayout(self.widget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalSpacer_25 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_25)

        self.pushButton = QPushButton(self.widget)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setMinimumSize(QSize(271, 41))
        self.pushButton.setMaximumSize(QSize(271, 41))
        self.pushButton.setMouseTracking(False)
        self.pushButton.setFocusPolicy(Qt.NoFocus)
        self.pushButton.setLayoutDirection(Qt.RightToLeft)
        self.pushButton.setAutoDefault(False)
        self.pushButton.setFlat(False)

        self.horizontalLayout.addWidget(self.pushButton)

        self.horizontalSpacer_26 = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_26)

        self.verticalLayout.addWidget(self.widget)

        self.retranslateUi(Form)
        self.pushButton.clicked.connect(Form.close)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate(
            "Form", u"\u5173\u4e8e", None))
        self.label_race_label_3.setText(QCoreApplication.translate(
            "Form", u"\u606d\u559c\u6253\u7834\uff1a", None))
        self.label.setText(QCoreApplication.translate(
            "Form", u"\u6a21\u5f0f\uff1a", None))
        self.label_16.setText(QCoreApplication.translate(
            "Form", u"\u672a\u6807\u96f7\uff08\u6807\u51c6\uff09", None))
        self.label1.setText("")
        self.label_1.setText(QCoreApplication.translate(
            "Form", u"Time\u6210\u7ee9\uff01", None))
        self.label3.setText("")
        self.label_3.setText(QCoreApplication.translate(
            "Form", u"3BV/s\u6210\u7ee9\uff01", None))
        self.label5.setText("")
        self.label_5.setText(QCoreApplication.translate(
            "Form", u"STNB\u6210\u7ee9\uff01", None))
        self.label7.setText("")
        self.label_7.setText(QCoreApplication.translate(
            "Form", u"IOE\u6210\u7ee9\uff01", None))
        self.label9.setText("")
        self.label_9.setText(QCoreApplication.translate(
            "Form", u"Path\u6210\u7ee9\uff01", None))
        self.label11.setText("")
        self.label_11.setText(QCoreApplication.translate(
            "Form", u"RQP\u6210\u7ee9\uff01", None))
        self.label13.setText("")
        self.label_13.setText(QCoreApplication.translate(
            "Form", u"\u521d\u7ea7", None))
        self.label___13.setText(QCoreApplication.translate(
            "Form", u"\u4e2a\u4eba\u6700\u4f73\uff01", None))
        self.label14.setText("")
        self.label_14.setText(QCoreApplication.translate(
            "Form", u"\u4e2d\u7ea7", None))
        self.label___14.setText(QCoreApplication.translate(
            "Form", u"\u4e2a\u4eba\u6700\u4f73\uff01", None))
        self.label15.setText("")
        self.label_15.setText(QCoreApplication.translate(
            "Form", u"\u9ad8\u7ea7", None))
        self.label___15.setText(QCoreApplication.translate(
            "Form", u"\u4e2a\u4eba\u6700\u4f73\uff01", None))
        self.pushButton.setText(QCoreApplication.translate(
            "Form", u"\u786e\u5b9a", None))
# if QT_CONFIG(shortcut)
        self.pushButton.setShortcut(
            QCoreApplication.translate("Form", u"Return", None))
# endif // QT_CONFIG(shortcut)
    # retranslateUi
