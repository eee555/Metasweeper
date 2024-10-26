from PyQt5.QtWidgets import QWidget, QScrollArea, QLabel, QVBoxLayout, QApplication, QHBoxLayout, QSpacerItem, \
    QSizePolicy, QPushButton, QFrame, QMessageBox, QFormLayout, QProgressDialog, QTextEdit, QComboBox
from githubApi import GitHub, Release, SourceManager, PingThread
from PyQt5.QtCore import QObject, pyqtSlot, Qt, pyqtSignal, QUrl, QPropertyAnimation, \
    QRect, QSize, pyqtProperty, QVariantAnimation,QDateTime
from PyQt5.QtGui import QDesktopServices, QFont, QIcon, QPainter, QPixmap, QPaintEvent


class AnimationButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap: QPixmap = None
        self.clicked.connect(self.animationStart)
        self.animation = QVariantAnimation(self)
        self.animation.valueChanged.connect(self.setRotate)
        self.__rotate = 0

    def rotate(self):
        return self.__rotate

    def setRotate(self, rotate):
        self.__rotate = rotate
        self.update()
    # rotate = property(int,rotate, setRotate)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pixmap is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.translate(self.width() / 2, self.height() / 2)
            painter.rotate(self.rotate())
            painter.drawPixmap(-(self.width()-10) // 2, -(self.height()-10) //
                               2, self.pixmap.scaled(self.width() - 10, self.height() - 10))

    def animationStart(self, check):
        if check:
            self.animation.setStartValue(0)
            self.animation.setEndValue(90)
        else:
            self.animation.setStartValue(90)
            self.animation.setEndValue(0)
        self.animation.setDuration(300)
        self.animation.start()


class ReleaseFrame(QFrame):
    downLoadFile = pyqtSignal(Release)

    def __init__(self, release: Release, mode=">", parent=None):
        super().__init__(parent)
        self.release: Release = release
        self.showButton = AnimationButton()
        self.showButton.setCheckable(True)
        self.showButton.pixmap = QPixmap("media/unfold.png")
        self.dateTimeLabel = QLabel()
        self.titleWidget = QWidget()
        self.formWidget = QWidget()
        self.downloadButton = QPushButton(QObject.tr(self, "Download"))
        self.bodyEdit = QTextEdit()
        self.mode = mode
        self.initUi()
        self.initConnect()
        self.formWidget.setVisible(False)

    def initUi(self):

        # self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        row1 = QHBoxLayout()
        row1.addWidget(self.showButton)
        row1.addWidget(QLabel(self.release.tag_name))
        row1.addItem(QSpacerItem(
            20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.dateTimeLabel.setText(QDateTime.fromString(self.release.assets_created_at, "yyyy-MM-ddThh:mm:ssZ").toString("yyyy-MM-dd hh:mm:ss"))
        row1.addWidget(self.dateTimeLabel)
        row1.addItem(QSpacerItem(
            20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.downloadButton.setEnabled(self.mode == ">")
        row1.addWidget(self.downloadButton)
        self.titleWidget.setLayout(row1)
        self.titleWidget.setContentsMargins(0, 0, 0, 0)
        formLayout = QFormLayout()
        urlLabel = QLabel()
        urlLabel.setText("<a href='" + self.release.html_url +
                         "'>" + QObject.tr(self, "open external links") + "</a>")
        urlLabel.setOpenExternalLinks(True)
        dataLayout = QVBoxLayout()
        formLayout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        formLayout.addRow(QObject.tr(self, "html_url"), urlLabel)
        formLayout.addRow(QObject.tr(self, "name"),
                          QLabel(self.release.assets_name))
        formLayout.addRow(QObject.tr(self, "content_type"),
                          QLabel(self.release.assets_content_type))
        formLayout.addRow(QObject.tr(self, "size"), QLabel(
            str(f"{self.release.assets_size / 1000000:.2f} MB")))
        formLayout.addRow(QObject.tr(self, "download_count"),
                          QLabel(str(self.release.assets_download_count)))
        formLayout.addRow(QObject.tr(self, "created_at"),
                          QLabel(QDateTime.fromString(self.release.assets_created_at, "yyyy-MM-ddThh:mm:ssZ").toString("yyyy-MM-dd hh:mm:ss")))
        downloadUrlLabel = QLabel()
        downloadUrlLabel.setText("<a href='" + self.release.assets_browser_download_url +
                                 "'>" + QObject.tr(self, "open download links") + "</a>")
        downloadUrlLabel.setOpenExternalLinks(True)
        formLayout.addRow(QObject.tr(
            self, "browser_download_url"), downloadUrlLabel)
        dataLayout.addLayout(formLayout)
        self.bodyEdit.setMarkdown(self.release.body)
        self.bodyEdit.setReadOnly(True)
        font = QFont("Microsoft YaHei UI", 13)
        font.setBold(True)
        self.bodyEdit.setFont(font)
        self.bodyEdit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        dataLayout.addWidget(self.bodyEdit)
        self.formWidget.setLayout(dataLayout)

        layout.addWidget(self.titleWidget)
        layout.addWidget(self.formWidget)
        self.setLayout(layout)
        rgbStr = ""
        if self.mode == ">":
            # 样式表绿色
            rgbStr = "rgb(200,255,250)"
        elif self.mode == "=":
            # 样式表蓝色
            rgbStr = "rgb(200,216,230)"
        else:
            # 样式表红色背景
            rgbStr = "rgb(249, 179, 163)"
        # label字体微软雅黑Ui,大小13
        self.setStyleSheet(
            f"QFrame{{background-color:{rgbStr}; font-family:Microsoft YaHei UI; font-size:14px;}}")

    def initConnect(self):
        self.showButton.clicked.connect(self.showButtonClicked)
        self.downloadButton.clicked.connect(self.downLoadButtonClicked)

    def showButtonClicked(self, checked: bool):
        self.formWidget.setVisible(True)
        animation = QPropertyAnimation(self.formWidget, b"size", self)
        animation2 = QPropertyAnimation(self, b"size", self)
        animation.setDuration(300)
        animation2.setDuration(300)
        start: QSize = None
        end: QSize = None
        start1: QSize = None
        end1: QSize = None
        if checked:
            start = QSize(self.width(), 0)
            start1 = QSize(self.width(), self.titleWidget.height())
            end = QSize(self.width(), self.formWidget.sizeHint().height())
            end1 = QSize(self.width(), self.sizeHint().height())
        else:
            start = QSize(self.width(), self.formWidget.sizeHint().height())
            start1 = QSize(self.width(), self.sizeHint().height())
            end = QSize(self.width(), 0)
            end1 = QSize(self.width(), self.titleWidget.height())
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation2.setStartValue(start1)
        animation2.setEndValue(end1)
        animation2.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        animation.finished.connect(lambda: self.formWidget.setVisible(checked))

    def downLoadButtonClicked(self):
        self.downLoadFile.emit(self.release)


class CheckUpdateGui(QWidget):
    def __init__(self, github: GitHub, parent=None):
        super().__init__(parent)
        self.github: GitHub = github
        self.github.setParent(self)
        self.checkUpdateButton = QPushButton(
            QObject.tr(self, "CheckUpdate"), self)
        self.releaseArea = QScrollArea()
        self.releaseArea.setWidgetResizable(True)
        # 禁用横向滚动条
        self.releaseArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.pingThread = None
        self.sourceSpeedLabel = QLabel()
        self.sourceCombo = QComboBox()
        self.sourceCombo.addItems(self.github.sourceManager.sources.keys())
        self.sourceCombo.setCurrentText(
            self.github.sourceManager.currentSource)
        self.currentVersionLabel = QLabel(
            f"Current Version:{self.github.version}")
        self.processDialog = None
        self.initUi()
        self.initConnect()
        self.resize(450, 600)
        self.checkUpdateButton.click()
        self.changeSource(self.github.sourceManager.currentSource)

    def initUi(self):
        font = QFont("Microsoft YaHei UI", 13)
        font.setBold(True)
        self.currentVersionLabel.setFont(font)
        font.setBold(False)
        font.setPointSize(12)
        self.sourceSpeedLabel.setFont(font)
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.addWidget(self.currentVersionLabel)
        row1.addItem(QSpacerItem(
            20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        row1.addWidget(self.sourceSpeedLabel)
        row1.addWidget(self.sourceCombo)
        row1.addWidget(self.checkUpdateButton)

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)

        row2.addWidget(self.releaseArea)

        layout.addLayout(row1)
        layout.addLayout(row2)

        self.setLayout(layout)

    def initConnect(self):
        self.checkUpdateButton.clicked.connect(lambda: self.github.releases())
        self.github.releasesAsyncSignal.connect(self.checkUpdate)
        self.github.errorSignal.connect(self.showError)
        self.github.downloadReleaseAsyncStartSignal.connect(
            self.showDownloadDialog)
        self.github.downloadReleaseAsyncProgressSignal.connect(
            self.updateDownloadDialog)
        self.github.downloadReleaseAsyncFinishSignal.connect(
            self.hideDownloadDialog)
        self.sourceCombo.currentTextChanged.connect(self.changeSource)
    def changeSource(self, source: str):
        self.pingThread = PingThread(source, self.github.sourceManager.sources[source])
        self.sourceSpeedLabel.setText("---ms")
        self.pingThread.pingSignal.connect(lambda x,y: self.sourceSpeedLabel.setText(f"{int(y)}ms"))
        self.pingThread.start()
        self.github.sourceManager.currentSource = source
        self.checkUpdateButton.click()
    @pyqtSlot(list)
    def checkUpdate(self, releases: list):
        widget = self.releaseArea.widget()
        if widget is not None:
            widget.deleteLater()
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        for release in releases:
            frame = ReleaseFrame(
                release, self.github.compareVersion(release.tag_name))
            layout.addWidget(frame)
            frame.downLoadFile.connect(self.github.downloadRelease)
        # 底部加一个空白区域
        panel = QWidget()
        panel.setContentsMargins(0, 0, 0, 0)
        panel.setFixedHeight(100)
        layout.addWidget(panel)
        layout.addItem(QSpacerItem(
            20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        widget.setLayout(layout)
        self.releaseArea.setWidget(widget)

    def showError(self, msg: str):
        QMessageBox.critical(self, QObject.tr(self, "Error"), msg)

    def showDownloadDialog(self, release: Release):
        if self.processDialog is not None:
            self.processDialog.close()
        self.processDialog = QProgressDialog(self)
        # 取消信号
        self.processDialog.canceled.connect(
            self.downloadCancel
        )
        self.processDialog.setWindowTitle(QObject.tr(
            self, f"{release.tag_name} Downloading..."))

    def updateDownloadDialog(self, a: int, b: int):
        if self.processDialog is not None:
            self.processDialog.setValue(a)
            self.processDialog.setMaximum(b)
            self.processDialog.setLabelText(
                f'{a/1000000 : .2f}/{b/1000000 : .2f} MB')

    def hideDownloadDialog(self, path: str):
        if self.processDialog is not None:
            self.processDialog.close()
            self.processDialog = None
        # 使用系统默认方式打开文件
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def downloadCancel(self):
        self.github.closeAllRequest()
        if self.processDialog is not None:
            self.processDialog.close()
            self.processDialog = None

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    data = {
        "Github": "https://api.github.com/repos/",
        "fff666": "https://fff666.top/",
    }
    w = CheckUpdateGui(GitHub(SourceManager(data), "eee555",
                       "Solvable-Minesweeper", "3.1.9", "(\d+\.\d+\.\d+)"))
    w.show()
    sys.exit(app.exec_())
