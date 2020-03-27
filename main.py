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



#bug:点击时笑脸不会张嘴,计时精度不够,踩中的雷不能标成红雷