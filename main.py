from PyQt5 import QtCore, QtGui, QtWidgets
import sys
import mineSweeperGUI

# import sweeper
if __name__ == "__main__":
    app = QtWidgets.QApplication (sys.argv)
#    app.aboutToQuit.connect(app.deleteLater)
    MainWindow = QtWidgets.QMainWindow ()
    ui = mineSweeperGUI.MineSweeperGUI (MainWindow)
    MainWindow.show()
    sys.exit (app.exec_())



#bug:点击时笑脸不会张嘴,踩中的雷不能标成红雷，加鼠标移动事件，加强无猜模式，
#    自定义模式的鲁棒性
#    切模式时窗口重新打开一下影响体验,鼠标按下后移出窗口会数组越界