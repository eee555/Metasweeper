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
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCompleter
from PyQt5.QtCore import QStringListModel, QSortFilterProxyModel
# ui相关的小组件，非窗口

GLOBAL_QSS = """
QSpinBox, QLineEdit {
    border-width: 2px;
    border-radius: 8px;
    border-style: solid;
    border-top-color: qlineargradient(spread:pad, x1:0.5, y1:1, x2:0.5, y2:0, stop:0 #85b7e3, stop:1 #9ec1db);
    border-right-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #85b7e3, stop:1 #9ec1db);
    border-bottom-color: qlineargradient(spread:pad, x1:0.5, y1:0, x2:0.5, y2:1, stop:0 #85b7e3, stop:1 #9ec1db);
    border-left-color: qlineargradient(spread:pad, x1:1, y1:0, x2:0, y2:0, stop:0 #85b7e3, stop:1 #9ec1db);
    background-color: #f4f4f4;
    color: #3d3d3d;
    font-family: "Microsoft YaHei", "微软雅黑", "Segoe UI", Arial, sans-serif;
    font-size: 14pt;
}
                                   
QPushButton {
    background-color: #00A2E8;
    color: white;
    border: none;
    color:white;
    font-family: "Microsoft YaHei", "微软雅黑", "Segoe UI", Arial, sans-serif;
    font-size: 16pt;
    font-weight: bold;
}

QComboBox {
    border-width: 2px;
    border-radius: 8px;
    border-style: solid;
    border-top-color: qlineargradient(spread:pad, x1:0.5, y1:1, x2:0.5, y2:0, stop:0 #85b7e3, stop:1 #9ec1db);
    border-right-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #85b7e3, stop:1 #9ec1db);
    border-bottom-color: qlineargradient(spread:pad, x1:0.5, y1:0, x2:0.5, y2:1, stop:0 #85b7e3, stop:1 #9ec1db);
    border-left-color: qlineargradient(spread:pad, x1:1, y1:0, x2:0, y2:0, stop:0 #85b7e3, stop:1 #9ec1db);
    background-color: rgba(244,244,244,0);
    color: #3d3d3d;
    font-family: "Microsoft YaHei", "微软雅黑", "Segoe UI", Arial, sans-serif;
    font-size: 14pt;
}
QComboBox::drop-down {
    width: 26px;
}

QLabel, QCheckBox {
    font-family: "Microsoft YaHei", "微软雅黑", "Segoe UI", Arial, sans-serif;
    font-size: 14pt;
}


QTabBar::tab
{
    font-family: "Microsoft YaHei", "微软雅黑", "Segoe UI", Arial, sans-serif;
    font-size: 14pt;
}

"""

class RoundMixin:
    def _init_round(self):
        # 可以随意拖动的圆角、阴影对话框的行为类
        self.border_width = 5
        self._dragging = False
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

    def paintEvent(self, event):
        # 阴影

        p = QPainter(self)
        p.setRenderHint(p.Antialiasing)
        # p.fillPath(path, QBrush(Qt.white))

        color = QColor(192, 192, 192, 50)

        for i in range(10):
            i_path = QPainterPath()
            i_path.setFillRule(Qt.WindingFill)
            ref = QRectF(10-i, 10-i, self.width()-(10-i)*2, self.height()-(10-i)*2)
            # i_path.addRect(ref)
            i_path.addRoundedRect(ref, self.border_width, self.border_width)
            color.setAlpha(int(150 - i**0.5*50))
            p.setPen(color)
            p.drawPath(i_path)

        # 圆角
        p.setBrush(QtGui.QColor(242, 242, 242, 255))
        p.setPen(Qt.transparent)

        rect = self.rect()
        rect.setLeft(9)
        rect.setTop(9)
        rect.setWidth(rect.width()-9)
        rect.setHeight(rect.height()-9)
        p.drawRoundedRect(rect, 10, 10)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = e.globalPos() - self.pos()
            e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = False

    def mouseMoveEvent(self, e):
        if self._dragging and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag_offset)
            e.accept()


class RoundQWidget(QWidget, RoundMixin):
    barSetMineNum = QtCore.pyqtSignal(int)
    barSetMineNumCalPoss = QtCore.pyqtSignal()
    closeEvent_ = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_round()
        self.setStyleSheet(GLOBAL_QSS)

    def closeEvent(self, event):
        self.closeEvent_.emit()
        event.accept()



class RoundQDialog(QDialog, RoundMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_round()
        self.setStyleSheet(GLOBAL_QSS)
        
        
        

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



class ScoreTable(QtWidgets.QTableWidget):
    ...


class CountryComboBox(QComboBox):
    def __init__(self, countries, parent=None):
        super().__init__(parent)

        # 1. 基础设置
        self.setEditable(True)
        self.lineEdit().setAlignment(Qt.AlignCenter)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.view().setTextElideMode(Qt.ElideNone)
        self.view().setSpacing(2)
        self.view().setLayoutDirection(Qt.LeftToRight)

        # 2. 设置 model
        self._model = QStringListModel(countries)
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(0)

        self.setModel(self._model)

        # 3. 设置补全器
        self._completer = QCompleter(self._proxy_model, self)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setFilterMode(Qt.MatchContains)  # 包含搜索
        self._completer.popup().setTextElideMode(Qt.ElideNone)
        self._completer.popup().setLayoutDirection(Qt.LeftToRight)
        self._completer.popup().setStyleSheet("QListView { text-align: center; color: #3d3d3d; font: 12pt '微软雅黑';}")
        self.setCompleter(self._completer)

        # 4. 居中补全框中的文字
        self._completer.popup().setUniformItemSizes(True)
        self._completer.popup().setWordWrap(False)

        # 5. 信号绑定：输入时过滤
        self.lineEdit().textEdited.connect(self._on_text_edited)

        # 6. 居中下拉框中的文字
        self.setStyleSheet("""
            QComboBox QAbstractItemView {
                text-align: center;
            }
            QComboBox {
                qproperty-alignment: 'AlignCenter';
            }
        """)

    def _on_text_edited(self, text):
        self._proxy_model.setFilterFixedString(text)
        self._completer.complete()  # 打开补全框



