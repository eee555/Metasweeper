import sys
from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtCore import Qt, qAbs, QRect
from PyQt5.QtGui import QPen, QPainter, QColor, QGuiApplication
from struct import Struct
# import matplotlib.pyplot as plt
import ms_toollib

class CaptureScreen(QDialog):
    # 初始化变量
    beginPosition = None
    endPosition = None
    fullScreenImage = None
    captureImage = None
    isMousePressLeft = None
    painter = QPainter()

    def __init__(self):
        super(CaptureScreen, self).__init__()
        # self.setWindowModality(Qt.ApplicationModal)
        self.initWindow()   # 初始化窗口
        self.captureFullScreen()    # 获取全屏

    def initWindow(self):
        self.setMouseTracking(True)     # 鼠标追踪
        self.setCursor(Qt.CrossCursor)  # 设置光标
        self.setWindowFlag(Qt.FramelessWindowHint)  # 窗口无边框
        self.setWindowState(Qt.WindowFullScreen)    # 窗口全屏

    def captureFullScreen(self):
        self.fullScreenImage = QGuiApplication.primaryScreen().grabWindow(QApplication.desktop().winId())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.beginPosition = event.pos()
            self.isMousePressLeft = True
        if event.button() == Qt.RightButton:
            # 如果选取了图片,则按一次右键开始重新截图
            if self.captureImage is not None:
                self.captureImage = None
                self.paintBackgroundImage()
                self.update()
            else:
                self.close()

    def mouseMoveEvent(self, event):
        if self.isMousePressLeft is True:
            self.endPosition = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        self.endPosition = event.pos()
        
        
        import sys
        f = open("output.txt", "w")
        t = sys.stdout
        sys.stdout = f
        sys.stdout.write("14")
        sys.stdout = t
        f.close()
        
        
        self.isMousePressLeft = False
        if self.captureImage is not None:
            self.getBoard()
            
            
            f = open("output.txt", "w")
            t = sys.stdout
            sys.stdout = f
            sys.stdout.write("13")
            sys.stdout = t
            f.close()
            
            
            self.close()

    def paintBackgroundImage(self):
        shadowColor = QColor(0, 0, 0, 100)  # 黑色半透明
        self.painter.drawPixmap(0, 0, self.fullScreenImage)
        self.painter.fillRect(self.fullScreenImage.rect(), shadowColor)     # 填充矩形阴影

    def paintEvent(self, event):
        self.painter.begin(self)    # 开始重绘
        self.paintBackgroundImage()
        penColor = QColor(30, 144, 245)     # 画笔颜色
        self.painter.setPen(QPen(penColor, 1, Qt.SolidLine, Qt.RoundCap))    # 设置画笔,蓝色,1px大小,实线,圆形笔帽
        if self.isMousePressLeft is True:
            pickRect = self.getRectangle(self.beginPosition, self.endPosition)   # 获得要截图的矩形框
            self.captureImage = self.fullScreenImage.copy(pickRect)         # 捕获截图矩形框内的图片
            self.painter.drawPixmap(pickRect.topLeft(), self.captureImage)  # 填充截图的图片
            self.painter.drawRect(pickRect)     # 画矩形边框
        self.painter.end()  # 结束重绘

    def getRectangle(self, beginPoint, endPoint):
        pickRectWidth = int(qAbs(beginPoint.x() - endPoint.x()))
        pickRectHeight = int(qAbs(beginPoint.y() - endPoint.y()))
        pickRectTop = beginPoint.x() if beginPoint.x() < endPoint.x() else endPoint.x()
        pickRectLeft = beginPoint.y() if beginPoint.y() < endPoint.y() else endPoint.y()
        pickRect = QRect(pickRectTop, pickRectLeft, pickRectWidth, pickRectHeight)
        # 避免高度宽度为0时候报错
        if pickRectWidth == 0:
            pickRect.setWidth(2)
        if pickRectHeight == 0:
            pickRect.setHeight(2)
        return pickRect

    def getBoard(self):
        image = self.captureImage.toImage()
        self.width = image.rect().width()
        self.height = image.rect().height()
        pp = image.colorTable()

        bits = image.bits()
        bits.setsize(image.byteCount())
        byteCount = image.byteCount()
        s = Struct(str(byteCount) + 'B')
        self.data = s.unpack(bits[0:])
        
        import sys
        f = open("output.txt", "w")
        t = sys.stdout
        sys.stdout = f
        sys.stdout.write("11")
        sys.stdout = t
        f.close()
        
        self.board = ms_toollib.py_OBR_board(self.data, self.height, self.width)
        
        import sys
        f = open("output.txt", "w")
        t = sys.stdout
        sys.stdout = f
        sys.stdout.write("12")
        sys.stdout = t
        f.close()

        # print(ms_toollib.py_OBR_board(self.data, self.height, self.width))


        # import numpy as np
        # np.savetxt('frame.csv', self.data, fmt='%d', delimiter=None)
        # print(self.height)
        # print(self.width)
        # d = np.zeros((self.height, self.width, 3))
        # C = [2, 1, 0]
        # for k in range(3):
        #     for i in range(self.height):
        #         for j in range(self.width):
        #             d[i, j, k] = self.data[(i * self.width + j) * 4 + C[k]]
        # plt.imshow(d/255)
        # plt.show()

if __name__ == "__main__":

    app = QApplication(sys.argv)
    windows = CaptureScreen()
    windows.show()
    sys.exit(app.exec_())
