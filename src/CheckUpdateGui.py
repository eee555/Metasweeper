from PyQt5.QtCore import QObject, pyqtSlot, Qt, pyqtSignal, QUrl, QPropertyAnimation, \
    QSize, QVariantAnimation, QDateTime, QEvent, QEasingCurve
from PyQt5.QtGui import QDesktopServices, QFont, QMouseEvent, QPainter, QPixmap, QEnterEvent
from PyQt5.QtWidgets import QWidget, QDialog, QScrollArea, QLabel, QVBoxLayout, QHBoxLayout, QSpacerItem, \
    QSizePolicy, QPushButton, QFrame, QMessageBox, QFormLayout, QProgressDialog, QTextEdit, QComboBox

from githubApi import GitHub, ReleaseInfo, PingThread


class AnimationButton(QPushButton):
    def __init__(self, parent=None):
        """
        :param parent: QWidget
        AnimationButton的构造函数
       ."""
        super().__init__(parent)
        self.pixmap: QPixmap = None
        self.clicked.connect(self.animationStart)
        self.animation = QVariantAnimation(self)
        self.animation.valueChanged.connect(self.setRotate)
        self.__rotate = 0
        self.setFixedSize(20, 20)

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
            painter.setRenderHint(QPainter.Antialiasing)
            painter.translate(self.width() // 2, self.height() // 2)
            size = self.width() if self.width() < self.height() else self.height()
            painter.rotate(self.rotate())
            painter.drawPixmap(-size // 2, -size //
                               2, self.pixmap.scaled(size, size))
            self.setMask(self.pixmap.scaled(size, size).mask())

    def animationStart(self, check):
        """
        :param check: bool
        点击按钮时，开始动画。
        check为True时，从0度到90度，否则从90度到0度，持续时间300ms。
        """
        if check:
            self.animation.setStartValue(0)
            self.animation.setEndValue(90)
        else:
            self.animation.setStartValue(90)
            self.animation.setEndValue(0)
        self.animation.setDuration(300)
        self.animation.start()


class ReleaseFrame(QFrame):
    downLoadFile = pyqtSignal(ReleaseInfo)

    def __init__(self, release: ReleaseInfo, mode=">", parent=None, r_path=""):
        super().__init__(parent)
        self.release: ReleaseInfo = release
        self.showButton = AnimationButton()
        self.showButton.setToolTip(self.tr("unfold"))
        self.showButton.setCheckable(True)
        self.showButton.pixmap = QPixmap(str(r_path.with_name(
            'media').joinpath('unfold.png')).replace("\\", "/"))
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
        self.dateTimeLabel.hide()
        if self.release.assets_created_at != "":
            self.dateTimeLabel.setText(QDateTime.fromString(
                self.release.assets_created_at, "yyyy-MM-ddThh:mm:ssZ").toString("yyyy-MM-dd hh:mm:ss"))
            self.dateTimeLabel.show()
        row1.addWidget(self.dateTimeLabel)
        row1.addItem(QSpacerItem(
            20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.downloadButton.setEnabled(self.mode == ">")
        row1.addWidget(self.downloadButton)
        self.titleWidget.setLayout(row1)
        self.titleWidget.setContentsMargins(0, 0, 0, 0)
        formLayout = QFormLayout()
        formLayout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        dataLayout = QVBoxLayout()
        if self.release.html_url != "":
            urlLabel = QLabel()
            urlLabel.setText("<a href='" + self.release.html_url +
                             "'>" + QObject.tr(self, "open external links") + "</a>")
            urlLabel.setOpenExternalLinks(True)
            formLayout.addRow(QObject.tr(self, "html_url"), urlLabel)
        formLayout.addRow(QObject.tr(self, "name"),
                          QLabel(self.release.assets_name))
        if self.release.assets_content_type != "":
            formLayout.addRow(QObject.tr(self, "content_type"),
                              QLabel(self.release.assets_content_type))
        if self.release.assets_size > 0:
            formLayout.addRow(QObject.tr(self, "size"), QLabel(
                str(f"{self.release.assets_size / 1000000:.2f} MB")))
        if self.release.assets_download_count != "":
            formLayout.addRow(QObject.tr(self, "download_count"),
                              QLabel(str(self.release.assets_download_count)))
        if self.release.assets_created_at != "":
            formLayout.addRow(QObject.tr(self, "created_at"),
                              QLabel(QDateTime.fromString(self.release.assets_created_at, "yyyy-MM-ddThh:mm:ssZ").toString(
                                  "yyyy-MM-dd hh:mm:ss")))
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
        self.bodyEdit.setFixedHeight(150)
        self.bodyEdit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        dataLayout.addWidget(self.bodyEdit)
        self.formWidget.setLayout(dataLayout)

        layout.addWidget(self.titleWidget)
        layout.addWidget(self.formWidget)
        self.setLayout(layout)
        self.__setStyleSheet(False)

    def initConnect(self):
        self.showButton.clicked.connect(self.showButtonClicked)
        self.downloadButton.clicked.connect(self.downLoadButtonClicked)

    def showButtonClicked(self, checked: bool):
        """
        切换显示和隐藏的按钮点击事件处理函数。

        根据参数checked的值，切换formWidget的可见性，并执行相应的展开或折叠动画。
        当checked为True时，展开formWidget并设置按钮提示为"fold"，
        否则折叠formWidget并设置按钮提示为"unfold"。

        Args:
            checked (bool): 指示按钮是否被选中的布尔值。
        """
        self.formWidget.setVisible(True)
        animation = QPropertyAnimation(self.formWidget, b"size", self)
        easingCurveType = QEasingCurve.Type.OutBack if checked else QEasingCurve.Type.InBack
        animation.setEasingCurve(easingCurveType)
        animation2 = QPropertyAnimation(self, b"size", self)
        animation2.setEasingCurve(easingCurveType)
        animation.setDuration(300)
        animation2.setDuration(300)
        if checked:
            self.showButton.setToolTip(QObject.tr(self, "fold"))
            start = QSize(self.width(), 0)
            start1 = QSize(self.width(), self.titleWidget.height())
            end = QSize(self.width(), self.formWidget.sizeHint().height())
            end1 = QSize(self.width(), self.sizeHint().height())
        else:
            self.showButton.setToolTip(QObject.tr(self, "unfold"))
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
        # animation.finished.connect(lambda: self.resWidth())

    def downLoadButtonClicked(self):
        self.downLoadFile.emit(self.release)

    def resWidth(self):
        area: QScrollArea = self.parentWidget().parentWidget().parentWidget()
        width = area.verticalScrollBar().width(
        ) if area.verticalScrollBar().isVisible() else 0
        self.resize(area.width() - width, self.height())

    def mousePressEvent(self, a0: QMouseEvent) -> None:
        super().mousePressEvent(a0)
        if self.titleWidget.geometry().contains(a0.pos()) and a0.button() == Qt.LeftButton:
            self.showButton.click()

    def __setStyleSheet(self, isEnter: bool):
        if self.mode == ">":
            # 样式表绿色
            rgbStr = "rgb(200,255,250)"
        elif self.mode == "=":
            # 样式表蓝色
            rgbStr = "rgb(200,216,230)"
        else:
            # 样式表红色背景
            rgbStr = "rgb(249, 179, 163)"

        if isEnter:
            # label字体微软雅黑Ui,大小13,圆角 8,1px的蓝色边框,只针对ReleaseFrame
            self.setStyleSheet(
                f"""QFrame{{background-color:{rgbStr}; font-family:Microsoft YaHei UI; font-size:14px; border-radius: 5px;}}
                ReleaseFrame{{border: 1px solid blue;}}
                """)
        else:
            # label字体微软雅黑Ui,大小13,圆角 8
            self.setStyleSheet(
                f"""QFrame{{background-color:{rgbStr}; font-family:Microsoft YaHei UI; font-size:14px; border-radius: 5px;}}
                ReleaseFrame{{border: 1px solid transparent;}}
                """)

    def enterEvent(self, a0: QEnterEvent) -> None:
        self.__setStyleSheet(True)
        return super().enterEvent(a0)

    def leaveEvent(self, a0: QEvent) -> None:
        self.__setStyleSheet(False)
        return super().leaveEvent(a0)


class CheckUpdateGui(QDialog):
    def __init__(self, github: GitHub, parent=None):
        super().__init__(parent.mainWindow)
        self.setWindowTitle(QObject.tr(self, "CheckUpdate"))
        # 去掉问号
        self.setWindowFlags(self.windowFlags() & ~
                            Qt.WindowContextHelpButtonHint)
        self.r_path = parent.r_path
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
        self.releaseArea.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
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
        self.pingThread = PingThread(
            source, self.github.sourceManager.sources[source]['url'])
        self.sourceSpeedLabel.setText("---ms")
        self.pingThread.pingSignal.connect(
            lambda x, y: self.sourceSpeedLabel.setText(f"{int(y)}ms"))
        self.pingThread.start()
        self.github.sourceManager.currentSource = source
        self.checkUpdateButton.click()

    @pyqtSlot(list)
    def checkUpdate(self, releases: list[ReleaseInfo]):
        widget = self.releaseArea.widget()
        if widget is not None:
            widget.deleteLater()
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        # 间隔设置为2px
        layout.setSpacing(2)
        for release in releases:
            frame = ReleaseFrame(
                release, self.github.compareVersion(release.tag_name), r_path=self.r_path)
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
        widget = self.releaseArea.widget()
        if widget is not None:
            widget.deleteLater()
        QMessageBox.critical(self, QObject.tr(self, "Error"), msg)

    def showDownloadDialog(self, release: ReleaseInfo):
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
                f'{a / 1000000: .2f}/{b / 1000000: .2f} MB')

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
# if __name__ == '__main__':
#     import sys
#     app = QApplication(sys.argv)
#     data = {
#         "Github": "https://api.github.com/repos/",
#         "openms": "https://openms.top/",
#     }
#     w = CheckUpdateGui(GitHub(SourceManager(data), "eee555",
#                        "Solvable-Minesweeper", "3.1.9", "(\d+\.\d+\.\d+)"))
#     w.show()
#     sys.exit(app.exec_())
