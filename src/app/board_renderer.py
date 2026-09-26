import ctypes
from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap
import win32con
import win32gui


class BoardRenderer:
    def __init__(self):
        self.label_2 = None
        self.label_11 = None
        self.label_12 = None
        self.label_13 = None
        self.label_31 = None
        self.label_32 = None
        self.label_33 = None
        self.pixmapNum: dict[int, str] = {}
        self.pixmapLEDNum: dict[int, str] = {}

    def set_face(self, face_type: int) -> None:
        pixmap = QPixmap(self.pixmapNum[face_type])
        if self.label_2:
            self.label_2.setPixmap(pixmap)
            self.label_2.setScaledContents(True)

    def showMineNum(self, n: int) -> None:
        if n >= 0 and n <= 999:
            self.label_11.setPixmap(self.pixmapLEDNum[n // 100])
            self.label_12.setPixmap(self.pixmapLEDNum[n // 10 % 10])
            self.label_13.setPixmap(self.pixmapLEDNum[n % 10])
        elif n < 0:
            self.label_11.setPixmap(self.pixmapLEDNum[0])
            self.label_12.setPixmap(self.pixmapLEDNum[0])
            self.label_13.setPixmap(self.pixmapLEDNum[0])
        elif n >= 1000:
            self.label_11.setPixmap(self.pixmapLEDNum[9])
            self.label_12.setPixmap(self.pixmapLEDNum[9])
            self.label_13.setPixmap(self.pixmapLEDNum[9])

    def showTime(self, t: int) -> None:
        if 0 <= t <= 999:
            self.label_31.setPixmap(self.pixmapLEDNum[t // 100])
            self.label_32.setPixmap(self.pixmapLEDNum[t // 10 % 10])
            self.label_33.setPixmap(self.pixmapLEDNum[t % 10])

    def limit_cursor(self, label, mainWindow) -> None:
        widget_pos = label.mapToGlobal(label.rect().topLeft())
        widget_size = label.size()
        rect = QRect(widget_pos, widget_size)
        self._clip_mouse(rect)
        hwnd = mainWindow.winId()
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    def unlimit_cursor(self, mainWindow) -> None:
        ctypes.windll.user32.ClipCursor(None)
        hwnd = mainWindow.winId()
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    @staticmethod
    def _clip_mouse(rect: QRect) -> None:
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long),
                        ("top", ctypes.c_long),
                        ("right", ctypes.c_long),
                        ("bottom", ctypes.c_long)]
        r = RECT(rect.left(), rect.top(), rect.right(), rect.bottom())
        ctypes.windll.user32.ClipCursor(ctypes.byref(r))
