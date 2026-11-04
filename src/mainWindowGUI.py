from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer, QFileInfo
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QDragEnterEvent, QDropEvent
# 重写QMainWindow


class MainWindow(QtWidgets.QMainWindow):
    keyRelease = QtCore.Signal(str)
    closeEvent_ = QtCore.Signal()
    dropFileSignal = QtCore.Signal(str)
    # 拖拽边缘调整窗口大小时发出：界面比例应跟随窗口尺寸变化
    dragResize = QtCore.Signal()
    # 拖拽结束：吸附到与界面比例精确匹配的窗口尺寸
    dragResizeFinished = QtCore.Signal()
    flag_drag_border = False

    def __init__(self):
        super(MainWindow, self).__init__()
        self.setAcceptDrops(True)

    def closeEvent(self, event):
        self.closeEvent_.emit()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self.keyRelease.emit('Space')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 拖拽边缘调整窗口大小（仅在按住左键的用户拖拽中触发）
        left = Qt.MouseButton.LeftButton
        if QApplication.mouseButtons() & left and not self.flag_drag_border:
            self.flag_drag_border = True
            self.dragResize.emit()
            self._drag_tick_timer = QTimer(self)
            self._drag_tick_timer.timeout.connect(self.dragResize)
            self._drag_tick_timer.start(100)
            self._drag_release_timer = QTimer(self)
            self._drag_release_timer.timeout.connect(self.__check_drag_release)
            self._drag_release_timer.start(100)

    def __check_drag_release(self):
        if QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            return
        self._drag_tick_timer.stop()
        self._drag_release_timer.stop()
        self.flag_drag_border = False
        self.dragResizeFinished.emit()

    def dragEnterEvent(self, event: QDragEnterEvent):
        super().dragEnterEvent(event)
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            if url.isLocalFile():
                fileType = QFileInfo(url.toLocalFile()).suffix()
                if fileType in ('evf', 'avf', 'rmv', 'mvf', 'evfs'):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        super().dropEvent(event)
        files = event.mimeData().urls()
        if len(files) > 0:
            url = files[0]
            if url.isLocalFile():
                filePath = url.toLocalFile()
                self.dropFileSignal.emit(filePath)
