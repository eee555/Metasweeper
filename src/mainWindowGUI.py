from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer, QFileInfo
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QDragEnterEvent, QDropEvent
import sys
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
    _aspect_fixing = False
    _drag_aspect = 1.0
    _last_drag_w = 0
    _last_drag_h = 0
    _drag_release_timer = None
    _native_aspect = False

    def __init__(self):
        super(MainWindow, self).__init__()
        self.setAcceptDrops(True)
        # macOS 上优先用 NSWindow.setAspectRatio 让窗口管理器在拖拽期间
        # 原生强制等比缩放；没有 pyobjc 时退回 resizeEvent 反馈修正
        if sys.platform == "darwin":
            try:
                import objc
                self._objc = objc
                self._native_aspect = True
            except ImportError:
                pass

    def set_interface_aspect(self, w, h):
        # 把界面固有宽高比交给窗口管理器强制，保证拖拽等比缩放
        if w <= 0 or h <= 0:
            return
        if self._native_aspect:
            try:
                # winId() 是 NSView（QNSView），需经 window() 拿到 NSWindow；
                # 用 contentAspectRatio 精确约束内容区比例（10.13+），旧系统回退
                view = self._objc.objc_object(c_void_p=int(self.winId()))
                nswin = view.window()
                if hasattr(nswin, 'setContentAspectRatio_'):
                    nswin.setContentAspectRatio_((w, h))
                else:
                    nswin.setAspectRatio_((w, h))
                return
            except Exception:
                pass  # 窗口句柄暂不可用（如未 show）时保持原生路径，下次再试
        self._drag_aspect = w / h

    def closeEvent(self, event):
        self.closeEvent_.emit()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self.keyRelease.emit('Space')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 拖拽边缘调整窗口大小。缩放处理不能依赖定时器：macOS 实时拖拽期间
        # 事件循环处于 tracking 模式，QTimer 不会触发，只能在 resizeEvent 里
        # 直接处理；释放检查定时器同样在拖拽期间不会触发，松手后恢复触发
        if self._aspect_fixing:
            return
        left = Qt.MouseButton.LeftButton
        buttons = QApplication.mouseButtons()
        if buttons & left:
            if not self.flag_drag_border:
                self.flag_drag_border = True
                self._drag_aspect = self.width() / max(1, self.height())
                self._last_drag_w = self.width()
                self._last_drag_h = self.height()
                self._drag_release_timer = QTimer(self)
                self._drag_release_timer.timeout.connect(self.__check_drag_release)
                self._drag_release_timer.start(150)
            self.__enforce_drag_aspect()
            self.dragResize.emit()
        elif self.flag_drag_border:
            self.__finish_drag()

    def __check_drag_release(self):
        if QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            return
        self.__finish_drag()

    def __finish_drag(self):
        if self._drag_release_timer is not None:
            self._drag_release_timer.stop()
            self._drag_release_timer = None
        if not self.flag_drag_border:
            return
        self.flag_drag_border = False
        self.dragResizeFinished.emit()

    def __enforce_drag_aspect(self):
        # 拖拽过程中锁定宽高比（以拖拽开始时的窗口比例为准），保证等比缩放
        w, h = self.width(), self.height()
        dw = w - self._last_drag_w
        dh = h - self._last_drag_h
        self._last_drag_w = w
        self._last_drag_h = h
        if dw == 0 and dh == 0:
            return
        min_w = max(1, self.minimumSize().width())
        min_h = max(1, self.minimumSize().height())
        if abs(dw) >= abs(dh):
            nh = max(min_h, round(w / self._drag_aspect))
            if nh != h:
                self._aspect_fixing = True
                self.resize(w, nh)
                self._aspect_fixing = False
        else:
            nw = max(min_w, round(h * self._drag_aspect))
            if nw != w:
                self._aspect_fixing = True
                self.resize(nw, h)
                self._aspect_fixing = False

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
