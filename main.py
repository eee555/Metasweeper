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



#bug:点击时笑脸不会张嘴，加强无猜模式
#    自定义模式的鲁棒性
#    切模式时窗口重新打开一下影响体验,增加高难度功能
    #  失败后点击仍然有阴影效果
    #