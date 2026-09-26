# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'ui_score_board.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QApplication, QFrame,
                               QHeaderView, QLabel, QLayout, QPushButton,
                               QSizePolicy, QTableWidgetItem, QVBoxLayout, QWidget)

from ui.uiComponents import ScoreTable


class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(264, 492)
        Form.setMinimumSize(QSize(264, 30))
        Form.setMaximumSize(QSize(264, 1000))
        Form.setSizeIncrement(QSize(0, 0))
        Form.setWindowTitle(u"")
        icon = QIcon()
        icon.addFile(u"media/cat.ico", QSize(),
                     QIcon.Mode.Normal, QIcon.State.Off)
        Form.setWindowIcon(icon)
        Form.setWindowOpacity(10.000000000000000)
        Form.setStyleSheet(u"")
        self.verticalLayout = QVBoxLayout(Form)
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setSizeConstraint(QLayout.SetFixedSize)
        self.verticalLayout.setContentsMargins(16, 12, 16, 12)
        self.label_counter = QLabel(Form)
        self.label_counter.setObjectName(u"label_counter")
        self.label_counter.setMinimumSize(QSize(0, 27))
        self.label_counter.setMaximumSize(QSize(16777215, 27))
        font = QFont()
        font.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font.setPointSize(12)
        self.label_counter.setFont(font)
        self.label_counter.setScaledContents(False)
        self.label_counter.setAlignment(
            Qt.AlignBottom | Qt.AlignLeading | Qt.AlignLeft)
        self.label_counter.setWordWrap(False)

        self.verticalLayout.addWidget(self.label_counter, 0, Qt.AlignHCenter)

        self.tableWidget = ScoreTable(Form)
        if (self.tableWidget.columnCount() < 2):
            self.tableWidget.setColumnCount(2)
        font1 = QFont()
        font1.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        __qtablewidgetitem = QTableWidgetItem()
        __qtablewidgetitem.setFont(font1)
        self.tableWidget.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        __qtablewidgetitem1.setFont(font1)
        self.tableWidget.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        self.tableWidget.setObjectName(u"tableWidget")
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.tableWidget.sizePolicy().hasHeightForWidth())
        self.tableWidget.setSizePolicy(sizePolicy)
        self.tableWidget.setMinimumSize(QSize(202, 0))
        self.tableWidget.setMaximumSize(QSize(232, 16777215))
        self.tableWidget.setSizeIncrement(QSize(232, 0))
        self.tableWidget.setBaseSize(QSize(232, 0))
# if QT_CONFIG(tooltip)
        self.tableWidget.setToolTip(u"")
# endif // QT_CONFIG(tooltip)
# if QT_CONFIG(statustip)
        self.tableWidget.setStatusTip(u"")
# endif // QT_CONFIG(statustip)
# if QT_CONFIG(whatsthis)
        self.tableWidget.setWhatsThis(u"")
# endif // QT_CONFIG(whatsthis)
# if QT_CONFIG(accessibility)
        self.tableWidget.setAccessibleName(u"")
# endif // QT_CONFIG(accessibility)
# if QT_CONFIG(accessibility)
        self.tableWidget.setAccessibleDescription(u"")
# endif // QT_CONFIG(accessibility)
        self.tableWidget.setStyleSheet(u"font-size: 15px;")
        self.tableWidget.setFrameShape(QFrame.StyledPanel)
        self.tableWidget.setFrameShadow(QFrame.Plain)
        self.tableWidget.setLineWidth(1)
        self.tableWidget.setMidLineWidth(1)
        self.tableWidget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tableWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tableWidget.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableWidget.setProperty(u"showDropIndicator", False)
        self.tableWidget.setDragEnabled(True)
        self.tableWidget.setDragDropOverwriteMode(True)
        self.tableWidget.setDragDropMode(QAbstractItemView.DragDrop)
        self.tableWidget.setSelectionMode(QAbstractItemView.NoSelection)
        self.tableWidget.setTextElideMode(Qt.ElideMiddle)
        self.tableWidget.setShowGrid(True)
        self.tableWidget.setGridStyle(Qt.DashLine)
        self.tableWidget.horizontalHeader().setVisible(False)
        self.tableWidget.horizontalHeader().setCascadingSectionResizes(False)
        self.tableWidget.horizontalHeader().setHighlightSections(False)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.verticalHeader().setHighlightSections(False)

        self.verticalLayout.addWidget(self.tableWidget, 0, Qt.AlignHCenter)

        self.pushButton_add = QPushButton(Form)
        self.pushButton_add.setObjectName(u"pushButton_add")
        self.pushButton_add.setMinimumSize(QSize(0, 15))
        self.pushButton_add.setMaximumSize(QSize(2000, 15))
        font2 = QFont()
        font2.setFamilies([u"\u5fae\u8f6f\u96c5\u9ed1"])
        font2.setBold(True)
        self.pushButton_add.setFont(font2)
        self.pushButton_add.setStyleSheet(u"QPushButton{\n"
                                          "    background-color:rgba(0,0,0,0);\n"
                                          "    color:rgba(0,0,0,0);\n"
                                          "}\n"
                                          "QPushButton:hover{\n"
                                          "    background-color:#00a2e8;\n"
                                          "    border-radius:3px;\n"
                                          "    color:white;\n"
                                          "}")
        self.pushButton_add.setText(u"+")
# if QT_CONFIG(shortcut)
        self.pushButton_add.setShortcut(u"")
# endif // QT_CONFIG(shortcut)

        self.verticalLayout.addWidget(self.pushButton_add)

        self.retranslateUi(Form)

        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        self.label_counter.setText(QCoreApplication.translate(
            "Form", u"\u8ba1\u6570\u5668", None))
        pass
    # retranslateUi
