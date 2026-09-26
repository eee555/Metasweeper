from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QPainter, QColor, QPixmap, QFont
from PySide6.QtWidgets import QWidget
import ms_toollib as ms


class mineNumLabel(QtWidgets.QLabel):
    # 左上角的显示雷数的标签控件，一共有三个
    mousewheelEvent = QtCore.Signal(int)

    def __init__(self, parent):
        super(mineNumLabel, self).__init__(parent)
        self.resize(QtCore.QSize(1, 1))

    def wheelEvent(self, event):
        # 滚轮事件
        angle = event.angleDelta()
        angleY = angle.y()
        self.mousewheelEvent.emit(angleY)
