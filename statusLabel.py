from PyQt5 import QtWidgets, QtCore

class StatusLabel (QtWidgets.QLabel):
    leftRelease = QtCore.pyqtSignal ()  # 定义信号

    def __init__(self, parent=None):
        super (StatusLabel, self).__init__ (parent)
        self.setFrameShape (QtWidgets.QFrame.Panel)
        self.setFrameShadow (QtWidgets.QFrame.Raised)
        self.setLineWidth(1)
        self.setAlignment (QtCore.Qt.AlignCenter)

    def mousePressEvent(self, e):  ##重载一下鼠标点击事件
        if e.button () == QtCore.Qt.LeftButton:
            self.setFrameShadow (QtWidgets.QFrame.Sunken)

    def mouseReleaseEvent(self, e):
        if e.button () == QtCore.Qt.LeftButton:
            self.setFrameShadow (QtWidgets.QFrame.Raised)
            self.leftRelease.emit ()
    
