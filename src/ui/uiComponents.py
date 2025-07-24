# -*- coding: utf-8 -*-
"""
Created on Wed Aug 11 20:04:25 2021

@author: jia32
"""
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import  QWidget, QDialog, QComboBox
from PyQt5.QtCore import Qt, QRectF
# from PyQt5.Qt import  QApplication, QDialog
from PyQt5.QtGui import QPainter, QPainterPath
# from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QImage, QPainterPath
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtGui import QPixmap
import configparser
from PyQt5.QtCore import pyqtSignal 
from PyQt5.QtCore import QEvent
# ui相关的小组件，非窗口

class RoundQDialog(QDialog):
    closeEvent_ = QtCore.pyqtSignal()
    def __init__(self, parent=None):
        # 可以随意拖动的圆角、阴影对话框
        super(RoundQDialog, self).__init__(parent)
        self.border_width = 5
        self.m_drag = False
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

    def paintEvent(self, event):
   	# # 阴影
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)

        pat = QPainter(self)
        pat.setRenderHint(pat.Antialiasing)
        pat.fillPath(path, QBrush(Qt.white))

        color = QColor(192, 192, 192, 50)

        for i in range(10):
            i_path = QPainterPath()
            i_path.setFillRule(Qt.WindingFill)
            ref = QRectF(10-i, 10-i, self.width()-(10-i)*2, self.height()-(10-i)*2)
            # i_path.addRect(ref)
            i_path.addRoundedRect(ref, self.border_width, self.border_width)
            color.setAlpha(150 - int(i**0.5*50)) # 为什么这个公式？
            pat.setPen(color)
            pat.drawPath(i_path)

        # 圆角
        pat2 = QPainter(self)
        pat2.setRenderHint(pat2.Antialiasing)  # 抗锯齿
        pat2.setBrush(QtGui.QColor(242, 242, 242, 255))
        pat2.setPen(Qt.transparent)

        rect = self.rect()
        rect.setLeft(9)
        rect.setTop(9)
        rect.setWidth(rect.width()-9)
        rect.setHeight(rect.height()-9)
        pat2.drawRoundedRect(rect, 10, 10)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_DragPosition = e.globalPos() - self.pos()
            e.accept()
            # self.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.m_drag = False
            # self.setCursor(QCursor(Qt.ArrowCursor))

    def mouseMoveEvent(self, e):
        if Qt.LeftButton and self.m_drag:
            self.move(e.globalPos() - self.m_DragPosition)
            e.accept()

    def closeEvent(self, event):
        self.closeEvent_.emit()

class RoundQWidget(QWidget):
    barSetMineNum = QtCore.pyqtSignal(int)
    barSetMineNumCalPoss = QtCore.pyqtSignal()
    closeEvent_ = QtCore.pyqtSignal()
    def __init__(self, parent=None):
        # 可以随意拖动的圆角、阴影对话框
        super(RoundQWidget, self).__init__(parent)
        self.border_width = 5
        self.m_drag = False
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

    def paintEvent(self, event):
   	# # 阴影
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)

        pat = QPainter(self)
        pat.setRenderHint(pat.Antialiasing)
        pat.fillPath(path, QBrush(Qt.white))

        color = QColor(192, 192, 192, 50)

        for i in range(10):
            i_path = QPainterPath()
            i_path.setFillRule(Qt.WindingFill)
            ref = QRectF(10-i, 10-i, self.width()-(10-i)*2, self.height()-(10-i)*2)
            # i_path.addRect(ref)
            i_path.addRoundedRect(ref, self.border_width, self.border_width)
            color.setAlpha(int(150 - i**0.5*50))
            pat.setPen(color)
            pat.drawPath(i_path)

        # 圆角
        pat2 = QPainter(self)
        pat2.setRenderHint(pat2.Antialiasing)  # 抗锯齿
        pat2.setBrush(QtGui.QColor(242, 242, 242, 255))
        pat2.setPen(Qt.transparent)

        rect = self.rect()
        rect.setLeft(9)
        rect.setTop(9)
        rect.setWidth(rect.width()-9)
        rect.setHeight(rect.height()-9)
        pat2.drawRoundedRect(rect, 10, 10)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_DragPosition = e.globalPos() - self.pos()
            e.accept()
            # self.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.m_drag = False
            # self.setCursor(QCursor(Qt.ArrowCursor))

    def mouseMoveEvent(self, e):
        if Qt.LeftButton and self.m_drag:
            self.move(e.globalPos() - self.m_DragPosition)
            e.accept()

    def closeEvent(self, event):
        self.closeEvent_.emit()


class StatusLabel (QtWidgets.QLabel):
    # 最上面的脸的控件，在这里重写一些方法
    leftRelease = QtCore.pyqtSignal ()  # 定义信号

    def __init__(self, parent=None):
        super (StatusLabel, self).__init__ (parent)

        self.setFrameShape (QtWidgets.QFrame.Panel)
        self.setFrameShadow (QtWidgets.QFrame.Raised)
        self.setLineWidth(1)
        self.setAlignment (QtCore.Qt.AlignCenter)


    def reloadFace(self, pixSize):
        # 重新修改脸的大小，叫rescale_face更妥
        self.pixSize = pixSize
        self.pixmap1 = QPixmap(self.smilefacedown_path).scaled(int(pixSize * 1.5), int(pixSize * 1.5))
        self.pixmap2 = QPixmap(self.smileface_path).scaled(int(pixSize * 1.5), int(pixSize * 1.5))
        self.setMinimumSize(QtCore.QSize(int(pixSize * 1.5), int(pixSize * 1.5)))
        self.setMaximumSize(QtCore.QSize(int(pixSize * 1.5), int(pixSize * 1.5)))

    def setPath(self, r_path):
        # 告诉脸，相对路径
        # game_setting_path = str(r_path.with_name('gameSetting.ini'))
        self.smileface_path = str(r_path.with_name('media').joinpath('smileface.svg'))
        self.smilefacedown_path = str(r_path.with_name('media').joinpath('smilefacedown.svg'))

        # config = configparser.ConfigParser()
        # config.read(game_setting_path, encoding='utf-8')
        # self.pixSize = config.getint('DEFAULT','pixSize')
        # self.pixSize = 5
        self.pixmap1_svg = QPixmap(self.smilefacedown_path)
        self.pixmap2_svg = QPixmap(self.smileface_path)
        # self.reloadFace(self.pixSize)
        # self.resize(QtCore.QSize(int(self.pixSize * 1.5), int(self.pixSize * 1.5)))

    def mousePressEvent(self, e):  ##重载一下鼠标点击事件
        if e.button () == QtCore.Qt.LeftButton:
            self.setPixmap(self.pixmap1)

    def mouseReleaseEvent(self, e):
        if e.button () == QtCore.Qt.LeftButton:
            self.setPixmap(self.pixmap2)
            if self.pixSize * 1.5 >= e.localPos().x() >= 0 and 0 <= e.localPos().y() <= self.pixSize*1.5:
                self.leftRelease.emit()


# 录像播放控制面板上的调节速度的标签
class SpeedLabel(QtWidgets.QLabel):
    speed_gear_id = 7
    speed_gear = ['0.01', '0.02', '0.05', '0.1', '0.2', '0.5', '0.8', '1', '1.2',
                  '1.5', '2', '3', '5', '8', '10', '15', '20']
    wEvent = QtCore.pyqtSignal(float)
    def wheelEvent(self, event):
        angle = event.angleDelta()
        v = angle.y()
        if v > 0:
            self.speed_gear_id += 1
            if self.speed_gear_id > 16:
                self.speed_gear_id = 16
        elif v < 0:
            self.speed_gear_id -= 1
            if self.speed_gear_id < 0:
                self.speed_gear_id = 0
        text = self.speed_gear[self.speed_gear_id]
        self.setText(text)
        self.wEvent.emit(float(text))

# 录像播放控制面板上的事件标签
class CommentLabel(QtWidgets.QLabel):
    Release = QtCore.pyqtSignal(int)
    def __init__(self, parent, text, time_100, middle = True):
        super(CommentLabel, self).__init__(parent)
        if not isinstance(text, str):
            text = "%.2f"%text
        self.setText(text)
        self.time_100 = time_100

        font = QtGui.QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        self.setFont(font)
        # self.setMinimumSize(QtCore.QSize(height, width))
        if middle:
            self.setAlignment(QtCore.Qt.AlignCenter)
    def mouseReleaseEvent(self, e):
        self.Release.emit(self.time_100)

class ScoreTable(QtWidgets.QTableWidget):
    ...

# 可编辑、阻止输入框部分点击事件冒泡
class BetterQCombox(QComboBox):
    resize = pyqtSignal()
    def __init__(self, parent=None):
        super(BetterQCombox, self).__init__(parent)
        
    def mousePressEvent(self, event):
        # 拦截鼠标按下事件，阻止事件冒泡
        super().mousePressEvent(event)
        event.accept()

    def mouseReleaseEvent(self, event):
        # 拦截鼠标释放事件，阻止事件冒泡
        super().mouseReleaseEvent(event)
        event.accept()

    def resizeEvent(self, e):
        self.resize.emit()








