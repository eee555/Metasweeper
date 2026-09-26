# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_scores.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtGui import QPainter, QPen, QBrush, QPalette, QFont, QImage, QPainterPath, QPolygon, QPixmap, QRadialGradient, QGradient, QLinearGradient, QConicalGradient
import math

# 单局游戏结束后的分数的弹窗，已弃用。


class Ui_Form(QtWidgets.QDialog):
    def __init__(self, scores, scoresValue):
        super(Ui_Form, self).__init__()
        self.scores = scores
        self.scoresValue = scoresValue
        # self = QtWidgets.QDialog()
        self.setupUi()

    def setupUi(self):
        # self.setPalette(QPalette(QtCore.Qt.white))

        self.setObjectName("Form")
        self.setWindowModality(QtCore.Qt.NonModal)
        self.resize(900, 556)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.setMinimumSize(QtCore.QSize(900, 556))
        self.setMaximumSize(QtCore.QSize(900, 556))
        self.setMouseTracking(True)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("media/cat.ico"),
                       QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)
        self.setWindowOpacity(1.0)
        self.setToolTip("")
        self.setToolTipDuration(-1)
        self.line_5 = QtWidgets.QFrame(self)
        self.line_5.setGeometry(QtCore.QRect(21, 470, 861, 20))
        self.line_5.setFrameShadow(QtWidgets.QFrame.Raised)
        self.line_5.setLineWidth(2)
        self.line_5.setMidLineWidth(0)
        self.line_5.setFrameShape(QtWidgets.QFrame.HLine)
        self.line_5.setObjectName("line_5")
        self.horizontalFrame = QtWidgets.QFrame(self)
        self.horizontalFrame.setGeometry(QtCore.QRect(0, 484, 901, 62))
        self.horizontalFrame.setObjectName("horizontalFrame")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.horizontalFrame)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.pushButton_2 = QtWidgets.QPushButton(self.horizontalFrame)
        self.pushButton_2.setMinimumSize(QtCore.QSize(250, 40))
        font = QtGui.QFont()
        font.setFamily("黑体")
        font.setPointSize(16)
        font.setBold(True)
        font.setItalic(False)
        font.setWeight(75)
        self.pushButton_2.setFont(font)
        self.pushButton_2.setMouseTracking(False)
        self.pushButton_2.setStyleSheet("border-image: url(media/button.png);\n"
                                        "font: 16pt \"黑体\";\n"
                                        "color:white;font: bold;")
        self.pushButton_2.setAutoDefault(False)
        self.pushButton_2.setFlat(False)
        self.pushButton_2.setObjectName("pushButton_2")
        self.horizontalLayout.addWidget(self.pushButton_2)
        spacerItem1 = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem1)
        self.label_2 = QtWidgets.QLabel(self)
        self.label_2.setGeometry(QtCore.QRect(290, 10, 271, 51))
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy)
        self.label_2.setStyleSheet("font: 18pt \"微软雅黑\";")
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)
        self.label_2.setObjectName("label_2")
        self.label_6 = QtWidgets.QLabel(self)
        self.label_6.setGeometry(QtCore.QRect(280, 10, 291, 52))
        self.label_6.setFrameShape(QtWidgets.QFrame.Panel)
        self.label_6.setFrameShadow(QtWidgets.QFrame.Raised)
        self.label_6.setLineWidth(7)
        self.label_6.setText("")
        self.label_6.setObjectName("label_6")

        self.pen1 = QPen(QtCore.Qt.DashDotLine)
        self.pen1.setColor(QtGui.QColor(170, 170, 170, 100))
        self.pen1.setWidth(2)

        self.pen2 = QPen(QtCore.Qt.SolidLine)
        self.pen2.setColor(QtGui.QColor(255, 180, 60, 255))
        self.pen2.setWidth(3)

        self.pen3 = QPen(QtCore.Qt.SolidLine)
        self.pen3.setColor(QtGui.QColor(0, 0, 0, 255))
        self.pen3.setWidth(3)

        self.brush = QBrush()
        self.brush.setStyle(QtCore.Qt.SolidPattern)
        self.brush.setColor(QtGui.QColor(255, 180, 60, 100))

        self.retranslateUi()
        self.pushButton_2.clicked.connect(self.close)
        QtCore.QMetaObject.connectSlotsByName(self)

    def retranslateUi(self):
        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle(_translate("Form", "成绩"))
        self.pushButton_2.setText(_translate("Form", "确定"))
        self.pushButton_2.setShortcut(_translate("Form", "Space"))
        self.label_2.setText(_translate(
            "Form", self.scores['Mode'] + " @ " + self.scores['Difficulty']))

    def paintEvent(self, QPaintEvent):
        self.paintRadarChart(self.scores, self.scoresValue)
        self.paintIndex(self.scores)

    def paintRadarChart(self, scores, scoresValue, x=255, y=270, r=160, n=6, m=5):
        # (x, y)为中心画雷达图，r为大小，n为边数，m为几等分
        # scoresValue在0到1之间，展示雷达图用
        painter = QPainter(self)
        angle_0 = 0  # 起始位置弧度，向上为0，顺时针为正
        scoresName = ['Ce/s', '3BV/s', 'RTime', 'STNB', 'IOE', 'RQP']

        painter.setPen(self.pen1)
        painter.setFont(QFont('Arial', 16))  # 设置字体和大小

        for j in range(1, m + 1):
            points = []
            for i in range(n):
                angle_s = angle_0 + i * 6.2831853 / n
                angle_t = angle_0 + (i + 1) * 6.2831853 / n
                r0 = j / m * r
                x_s = int(x + r0 * math.cos(angle_s))
                y_s = int(y - r0 * math.sin(angle_s))
                points.append(QtCore.QPoint(x_s, y_s))
            painter.drawPolygon(QPolygon(points))

        points = []
        for i in range(n):
            angle_s = angle_0 + i * 6.2831853 / n
            # angle_t = angle_0 + (i + 1) * 6.2831853 / n

            x_s = int(x + r * math.cos(angle_s))
            y_s = int(y - r * math.sin(angle_s))
            painter.setPen(self.pen1)
            painter.drawLine(x, y, x_s, y_s)
            x_s = int(x + r0 * 1.23 * math.cos(angle_s))
            y_s = int(y - r0 * 1.23 * math.sin(angle_s))
            painter.setPen(self.pen3)
            painter.drawText(QtCore.QRectF(x_s-65, y_s-30, 120, 60),
                             QtCore.Qt.AlignCenter, scoresName[i] + "\n" + scores[scoresName[i]])
            # painter.drawText(QtCore.QRectF(50,70,100,130), QtCore.Qt.AlignCenter, "abcdefg\nhijklmn")
            x_s = int(x + scoresValue[i] * r * math.cos(angle_s))
            y_s = int(y - scoresValue[i] * r * math.sin(angle_s))
            points.append(QtCore.QPoint(x_s, y_s))
        painter.setPen(self.pen2)

        painter.setBrush(self.brush)
        painter.drawPolygon(QPolygon(points))

    def paintIndex(self, scores):
        # 画其他指标
        index = ['EstTime', '3BV', 'Ops', 'Isls', 'Thrp', 'Corr',
                 'Left', 'Right', 'Double', 'Cl', 'Ces']

        painter = QPainter(self)
        painter.setFont(QFont('Arial', 12))  # 设置字体和大小

        for i in range(6):
            painter.drawText(510, 140+i*56, index[i] + ': ' + scores[index[i]])
        for i in range(6, 11):
            painter.drawText(690, 140+(i-6)*56,
                             index[i] + ': ' + scores[index[i]])


if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import sys
    scores = {'Ce/s': '2.724', '3BV/s': '2.704', 'RTime': '23.474',
              'STNB': '100.251', 'IOE': '1.245', 'RQP': '23.574',
              'EstTime': '52.247', '3BV': '123/200', 'Ops': '12',
              'Isls': '10', 'Thrp': '0.968', 'Corr': '0.963',
              'Left': '123@3.21', 'Right': '123@3.21', 'Double': '123@3.21',
              'Cl': '123@3.21', 'Ces': '123@3.21', 'Mode': '经典无猜',
              'Difficulty': '高级'}
    scoresValue = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    app = QApplication(sys.argv)
    demo = Ui_Form(scores, scoresValue)
    demo.show()
    sys.exit(app.exec())
