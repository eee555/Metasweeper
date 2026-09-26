# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'ui_about.ui'
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
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QSpacerItem, QTabWidget, QVBoxLayout,
                               QWidget)


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(600, 382)
        Form.setMinimumSize(QSize(600, 382))
        Form.setMaximumSize(QSize(600, 580))
        Form.setSizeIncrement(QSize(0, 0))
        Form.setWindowTitle(u"")
        icon = QIcon()
        icon.addFile(u"media/cat.ico", QSize(),
                     QIcon.Mode.Normal, QIcon.State.Off)
        Form.setWindowIcon(icon)
        Form.setWindowOpacity(10.000000000000000)
        self.verticalLayout_7 = QVBoxLayout(Form)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(20, 20, 20, -1)
        self.tabWidget = QTabWidget(Form)
        self.tabWidget.setObjectName(u"tabWidget")
        font = QFont()
        font.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font.setPointSize(14)
        self.tabWidget.setFont(font)
        self.tabWidget.setUsesScrollButtons(True)
        self.tabWidget.setDocumentMode(False)
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.verticalLayout_2 = QVBoxLayout(self.tab)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.label = QLabel(self.tab)
        self.label.setObjectName(u"label")
        self.label.setWordWrap(True)

        self.verticalLayout_2.addWidget(self.label)

        self.label_3 = QLabel(self.tab)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setWordWrap(True)

        self.verticalLayout_2.addWidget(self.label_3)

        self.label_2 = QLabel(self.tab)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.label_2.setMouseTracking(True)
# if QT_CONFIG(tooltip)
        self.label_2.setToolTip(u"")
# endif // QT_CONFIG(tooltip)
# if QT_CONFIG(statustip)
        self.label_2.setStatusTip(u"")
# endif // QT_CONFIG(statustip)
# if QT_CONFIG(whatsthis)
        self.label_2.setWhatsThis(u"")
# endif // QT_CONFIG(whatsthis)
# if QT_CONFIG(accessibility)
        self.label_2.setAccessibleName(u"")
# endif // QT_CONFIG(accessibility)
# if QT_CONFIG(accessibility)
        self.label_2.setAccessibleDescription(u"")
# endif // QT_CONFIG(accessibility)
        self.label_2.setText(
            u"<html><head/><body><p><a href=\"https://github.com/eee555/Metasweeper\"><span style=\" text-decoration: underline; color:#0000ff;\">https://github.com/eee555/Metasweeper</span></a></p></body></html>")
        self.label_2.setTextFormat(Qt.RichText)
        self.label_2.setWordWrap(True)
        self.label_2.setOpenExternalLinks(True)

        self.verticalLayout_2.addWidget(self.label_2)

        self.verticalSpacer = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)

        self.tabWidget.addTab(self.tab, "")
        self.tab_5 = QWidget()
        self.tab_5.setObjectName(u"tab_5")
        self.verticalLayout_3 = QVBoxLayout(self.tab_5)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.label_4 = QLabel(self.tab_5)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.label_4.setMouseTracking(True)
# if QT_CONFIG(tooltip)
        self.label_4.setToolTip(u"")
# endif // QT_CONFIG(tooltip)
# if QT_CONFIG(statustip)
        self.label_4.setStatusTip(u"")
# endif // QT_CONFIG(statustip)
# if QT_CONFIG(whatsthis)
        self.label_4.setWhatsThis(u"")
# endif // QT_CONFIG(whatsthis)
# if QT_CONFIG(accessibility)
        self.label_4.setAccessibleName(u"")
# endif // QT_CONFIG(accessibility)
# if QT_CONFIG(accessibility)
        self.label_4.setAccessibleDescription(u"")
# endif // QT_CONFIG(accessibility)
        self.label_4.setLayoutDirection(Qt.LeftToRight)
        self.label_4.setText(
            u"<html><head/><body><p><a href=\"https://openms.top/#/guide/[80.\u6559\u7a0b.\u8f6f\u4ef6]\u5143\u626b\u96f7\u4f7f\u7528\u6559\u7a0b\"><span style=\" text-decoration: underline; color:#0000ff;\">https://openms.top/#/guide/[80.\u6559\u7a0b.\u8f6f\u4ef6]\u5143\u626b\u96f7\u4f7f\u7528\u6559\u7a0b</span></a></p></body></html>")
        self.label_4.setTextFormat(Qt.RichText)
        self.label_4.setWordWrap(True)
        self.label_4.setOpenExternalLinks(True)

        self.verticalLayout_3.addWidget(self.label_4)

        self.label_11 = QLabel(self.tab_5)
        self.label_11.setObjectName(u"label_11")
        self.label_11.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.label_11.setMouseTracking(True)
# if QT_CONFIG(tooltip)
        self.label_11.setToolTip(u"")
# endif // QT_CONFIG(tooltip)
# if QT_CONFIG(statustip)
        self.label_11.setStatusTip(u"")
# endif // QT_CONFIG(statustip)
# if QT_CONFIG(whatsthis)
        self.label_11.setWhatsThis(u"")
# endif // QT_CONFIG(whatsthis)
# if QT_CONFIG(accessibility)
        self.label_11.setAccessibleName(u"")
# endif // QT_CONFIG(accessibility)
# if QT_CONFIG(accessibility)
        self.label_11.setAccessibleDescription(u"")
# endif // QT_CONFIG(accessibility)
        self.label_11.setLayoutDirection(Qt.LeftToRight)
        self.label_11.setText(
            u"<html><head/><body><p><a href=\"https://openms.top/#/guide/[5.\u6559\u7a0b.\u672f\u8bed]\u626b\u96f7\u672f\u8bed\u4ecb\u7ecd.md\"><span style=\" text-decoration: underline; color:#0000ff;\">https://openms.top/#/guide/[5.\u6559\u7a0b.\u672f\u8bed]\u626b\u96f7\u672f\u8bed\u4ecb\u7ecd.md</span></a></p></body></html>")
        self.label_11.setTextFormat(Qt.RichText)
        self.label_11.setWordWrap(True)
        self.label_11.setOpenExternalLinks(True)

        self.verticalLayout_3.addWidget(self.label_11)

        self.verticalSpacer_2 = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_3.addItem(self.verticalSpacer_2)

        self.tabWidget.addTab(self.tab_5, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.verticalLayout_4 = QVBoxLayout(self.tab_2)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.label_5 = QLabel(self.tab_2)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setWordWrap(True)

        self.verticalLayout_4.addWidget(self.label_5)

        self.label_6 = QLabel(self.tab_2)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setWordWrap(True)

        self.verticalLayout_4.addWidget(self.label_6)

        self.label_8 = QLabel(self.tab_2)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setWordWrap(True)

        self.verticalLayout_4.addWidget(self.label_8)

        self.verticalSpacer_3 = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer_3)

        self.tabWidget.addTab(self.tab_2, "")
        self.tab_3 = QWidget()
        self.tab_3.setObjectName(u"tab_3")
        self.verticalLayout_5 = QVBoxLayout(self.tab_3)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.label_7 = QLabel(self.tab_3)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.label_7.setMouseTracking(True)
# if QT_CONFIG(tooltip)
        self.label_7.setToolTip(u"")
# endif // QT_CONFIG(tooltip)
# if QT_CONFIG(statustip)
        self.label_7.setStatusTip(u"")
# endif // QT_CONFIG(statustip)
# if QT_CONFIG(whatsthis)
        self.label_7.setWhatsThis(u"")
# endif // QT_CONFIG(whatsthis)
# if QT_CONFIG(accessibility)
        self.label_7.setAccessibleName(u"")
# endif // QT_CONFIG(accessibility)
# if QT_CONFIG(accessibility)
        self.label_7.setAccessibleDescription(u"")
# endif // QT_CONFIG(accessibility)
        self.label_7.setLayoutDirection(Qt.LeftToRight)
        self.label_7.setText(u"<html><head/><body><p>Github\uff1a<a href=\"https://github.com/eee555/Metasweeper/issues\"><span style=\" text-decoration: underline; color:#0000ff;\">https://github.com/eee555/Metasweeper/issues</span></a></p><p>Gitee\uff1a<a href=\"https://gitee.com/ee55/Metasweeper/issues\"><span style=\" text-decoration: underline; color:#0000ff;\">https://gitee.com/ee55/Metasweeper/issues</span></a></p><p>Discord\uff1a<a href=\"https://discord.gg/ks8ngPX5bT\"><span style=\" text-decoration: underline; color:#0000ff;\">https://discord.gg/ks8ngPX5bT</span></a></p><p>QQ\u7fa4\uff1a<a href=\"https://qm.qq.com/q/hNShGUQkJG\"><span style=\" text-decoration: underline; color:#0000ff;\">https://qm.qq.com/q/hNShGUQkJG</span></a></p></body></html>")
        self.label_7.setTextFormat(Qt.RichText)
        self.label_7.setWordWrap(True)
        self.label_7.setOpenExternalLinks(True)

        self.verticalLayout_5.addWidget(self.label_7)

        self.verticalSpacer_4 = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_5.addItem(self.verticalSpacer_4)

        self.tabWidget.addTab(self.tab_3, "")
        self.tab_6 = QWidget()
        self.tab_6.setObjectName(u"tab_6")
        self.verticalLayout_6 = QVBoxLayout(self.tab_6)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.label_9 = QLabel(self.tab_6)
        self.label_9.setObjectName(u"label_9")
        self.label_9.setWordWrap(True)

        self.verticalLayout_6.addWidget(self.label_9)

        self.widget = QWidget(self.tab_6)
        self.widget.setObjectName(u"widget")
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.widget.sizePolicy().hasHeightForWidth())
        self.widget.setSizePolicy(sizePolicy)
        self.horizontalLayout = QHBoxLayout(self.widget)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.label_10 = QLabel(self.widget)
        self.label_10.setObjectName(u"label_10")
        self.label_10.setMinimumSize(QSize(120, 120))
        self.label_10.setMaximumSize(QSize(120, 120))
        self.label_10.setStyleSheet(u"border-image: url(media/wxskm.png);")
        self.label_10.setTextFormat(Qt.PlainText)
        self.label_10.setScaledContents(False)
        self.label_10.setAlignment(Qt.AlignCenter)
        self.label_10.setWordWrap(False)

        self.horizontalLayout.addWidget(self.label_10)

        self.label_12 = QLabel(self.widget)
        self.label_12.setObjectName(u"label_12")
        self.label_12.setMinimumSize(QSize(120, 120))
        self.label_12.setMaximumSize(QSize(120, 120))
        self.label_12.setStyleSheet(u"border-image: url(media/zfbskm.png);")
        self.label_12.setAlignment(Qt.AlignCenter)

        self.horizontalLayout.addWidget(self.label_12)

        self.verticalLayout_6.addWidget(self.widget)

        self.verticalSpacer_6 = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_6.addItem(self.verticalSpacer_6)

        self.tabWidget.addTab(self.tab_6, "")
        self.tab_4 = QWidget()
        self.tab_4.setObjectName(u"tab_4")
        font1 = QFont()
        font1.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font1.setPointSize(12)
        font1.setBold(False)
        font1.setItalic(False)
        self.tab_4.setFont(font1)
        self.verticalLayout = QVBoxLayout(self.tab_4)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(11, 11, 11, 11)
        self.label_13 = QLabel(self.tab_4)
        self.label_13.setObjectName(u"label_13")
        self.label_13.setWordWrap(True)

        self.verticalLayout.addWidget(self.label_13)

        self.label_15 = QLabel(self.tab_4)
        self.label_15.setObjectName(u"label_15")
        self.label_15.setWordWrap(True)

        self.verticalLayout.addWidget(self.label_15)

        self.label_14 = QLabel(self.tab_4)
        self.label_14.setObjectName(u"label_14")
        self.label_14.setTextFormat(Qt.RichText)
        self.label_14.setScaledContents(False)
        self.label_14.setWordWrap(True)
        self.label_14.setOpenExternalLinks(True)

        self.verticalLayout.addWidget(self.label_14)

        self.verticalSpacer_5 = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_5)

        self.tabWidget.addTab(self.tab_4, "")

        self.verticalLayout_7.addWidget(self.tabWidget)

        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(-1, -1, -1, 10)
        self.pushButton = QPushButton(Form)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setMinimumSize(QSize(521, 41))
        self.pushButton.setMaximumSize(QSize(521, 41))
        self.pushButton.setMouseTracking(False)
        self.pushButton.setFocusPolicy(Qt.NoFocus)
        self.pushButton.setLayoutDirection(Qt.RightToLeft)
        self.pushButton.setAutoDefault(False)
        self.pushButton.setFlat(False)

        self.horizontalLayout_4.addWidget(self.pushButton)

        self.verticalLayout_7.addLayout(self.horizontalLayout_4)

        self.retranslateUi(Form)
        self.pushButton.clicked.connect(Form.close)

        self.tabWidget.setCurrentIndex(0)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        self.label.setText(QCoreApplication.translate(
            "Form", u"\u5143\u626b\u96f7\u662f\u7531\u8d44\u6df1\u626b\u96f7\u73a9\u5bb6\u4e0e\u8f6f\u4ef6\u5de5\u7a0b\u5e08\u5171\u540c\u6253\u9020\u7684\u4e00\u6b3e\u73b0\u4ee3\u5316\u590d\u523b\u3002", None))
        self.label_3.setText(QCoreApplication.translate(
            "Form", u"Copyright \u00a9 2020-2025 \u5143\u626b\u96f7\u5f00\u53d1\u56e2\u961f, \u7248\u6743\u6240\u6709", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(
            self.tab), QCoreApplication.translate("Form", u"\u5173\u4e8e", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(
            self.tab_5), QCoreApplication.translate("Form", u"\u6559\u7a0b", None))
        self.label_5.setText(QCoreApplication.translate(
            "Form", u"\u5f00\u53d1\uff1a\u738b\u5609\u5b81\u3001\u674e\u4eac\u5fd7", None))
        self.label_6.setText(QCoreApplication.translate(
            "Form", u"\u81f4\u8c22\uff1a\u6fee\u5929\u7fbf\u3001\u5411\u98de\u5b87\u3001\u949f\u8a00\u3001\u7fc1\u9038\u6770\u3001\u5f20\u7837\u9553\u3001Thomas Kolar", None))
        self.label_8.setText(QCoreApplication.translate(
            "Form", u"\u5143\u626b\u96f7\u63a5\u53d7\u6709\u76ca\u7684\u8d21\u732e\uff0c\u5305\u62ec\u65b0\u7684\u73a9\u6cd5\u3001\u89c4\u5219\u3001\u63d2\u4ef6\u7b49\u3002", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(
            self.tab_2), QCoreApplication.translate("Form", u"\u4f5c\u8005", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(
            self.tab_3), QCoreApplication.translate("Form", u"\u53cd\u9988", None))
        self.label_9.setText(QCoreApplication.translate("Form", u"\u611f\u8c22\u60a8\u8003\u8651\u652f\u6301\u6211\u4eec\u7684\u5f00\u6e90\u9879\u76ee\uff0c\u8d5e\u52a9\u65f6\u8bf7\u5907\u6ce8\u9879\u76ee\u540d\u79f0+\u60a8\u7684\u79f0\u547c+\u5176\u4ed6\u8981\u6c42\uff0c\u4f8b\u5982\u5143\u626b\u96f7+\u5f20\u5148\u751f+\u5efa\u8bae\u6dfb\u52a0**\u529f\u80fd\u3002\u60a8\u7684\u8d5e\u52a9\u5c06\u6709\u52a9\u4e8e\u9879\u76ee\u7684\u6301\u7eed\u53d1\u5c55\u548c\u6539\u8fdb\uff0c\u4f7f\u6211\u4eec\u80fd\u591f\u7ee7\u7eed\u63d0\u9ad8\u8f6f\u4ef6\u7684\u8d28\u91cf\u3002", None))
        self.label_10.setText("")
        self.label_12.setText("")
        self.tabWidget.setTabText(self.tabWidget.indexOf(
            self.tab_6), QCoreApplication.translate("Form", u"\u8d5e\u52a9", None))
        self.label_13.setText(QCoreApplication.translate(
            "Form", u"1. \u5728\u975e\u5546\u4e1a\u7528\u9014\u524d\u63d0\u4e0b\uff0c\u7528\u6237\u6709\u6743\u4e0d\u53d7\u4efb\u4f55\u9650\u5236\u5730\u5bf9\u201c\u5143\u626b\u96f7\u201d\u8f6f\u4ef6\u8fdb\u884c\u590d\u5236\u3001\u5b58\u50a8\u53ca\u4f20\u64ad\u3002", None))
        self.label_15.setText(QCoreApplication.translate(
            "Form", u"2. \u7531\u201c\u5143\u626b\u96f7\u201d\u8f6f\u4ef6\u751f\u6210\u7684\u5f55\u50cf\u6587\u4ef6\uff0c\u5176\u5168\u90e8\u6240\u6709\u6743\u5f52\u5bf9\u5e94\u73a9\u5bb6\u672c\u4eba\u6240\u6709\u3002", None))
        self.label_14.setText(QCoreApplication.translate("Form", u"<html><head/><body><p>3. \u672c\u9879\u76ee\u6e90\u4ee3\u7801\u9075\u5faaGPLv3\u5e76\u9644\u52a0\u989d\u5916\u6761\u6b3e\u53d1\u5e03\u3002\u8be5\u989d\u5916\u6761\u6b3e\u7279\u522b\u7981\u6b62\u4efb\u4f55\u672a\u7ecf\u5f00\u53d1\u56e2\u961f\u6388\u6743\u7684\u5546\u4e1a\u4f7f\u7528\u884c\u4e3a\uff0c\u5e76\u5bf9\u9879\u76ee\u76f8\u5173\u6536\u76ca\u7684\u5206\u914d\u65b9\u5f0f\u4f5c\u51fa\u660e\u786e\u7ea6\u5b9a\u3002\u5177\u4f53\u5185\u5bb9\u8be6\u89c1<a href=\"https://github.com/eee555/Metasweeper/blob/master/LICENSE\"><span style=\" text-decoration: underline; color:#0000ff;\">LICENSE</span></a></p></body></html>", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(
            self.tab_4), QCoreApplication.translate("Form", u"\u534f\u8bae", None))
        self.pushButton.setText(QCoreApplication.translate(
            "Form", u"\u786e\u5b9a", None))
# if QT_CONFIG(shortcut)
        self.pushButton.setShortcut(
            QCoreApplication.translate("Form", u"Return", None))
# endif // QT_CONFIG(shortcut)
        pass
    # retranslateUi
