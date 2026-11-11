from PySide6 import QtGui
import configparser
import sys
from ui.ui_gameSettings import Ui_Form
from ui.uiComponents import RoundQDialog
from country_name import country_name
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QTimer
from PySide6.QtCore import QSortFilterProxyModel
from PySide6.QtWidgets import QComboBox, QApplication, QToolTip
from config.constants import BOARD_BEGINNER, BOARD_INTERMEDIATE, BOARD_EXPERT
from utils.path_utils import resource_path


class _MacToolTipFallback:
    """macOS 上无边框半透明窗口的 tooltip 兜底。

    Qt 原生 tooltip 链路要求：自发（系统投递的）MouseMove 无按键事件 ->
    QApplication 启动唤醒定时器 -> 窗口是 active window（或窗口设置了
    WA_AlwaysShowToolTips）-> 才向控件发送 QEvent.ToolTip。本项目的对话框
    是 Qt.FramelessWindowHint + WA_TranslucentBackground 的圆角窗口（见
    uiComponents.RoundMixin），在 macOS 上这条链路不可靠：hover 时不产生
    tooltip，而 Windows 上正常。故在 macOS 上改为轮询兜底：光标落在带
    tooltip 的控件上时，直接调用 QToolTip.showText 显示（不依赖 hover 事件链，
    QCursor.pos / widgetAt / showText 均为常规 API，在无边框窗口上实测可用）。
    仅 darwin 平台启用，Windows 行为保持不变。
    """

    # 轮询间隔（ms），同时充当原生 tooltip 的"延迟感"
    INTERVAL_MS = 300

    def __init__(self, window, cursor_pos=None):
        self._window = window
        # cursor_pos 可注入，便于测试时模拟光标位置
        self._cursor_pos = cursor_pos or (lambda: QtGui.QCursor.pos())
        self._cur = None
        self._timer = QTimer(window)
        self._timer.setInterval(self.INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    def start(self):
        self._timer.start()

    def _poll(self):
        if not self._window.isVisible():
            self._timer.stop()
            return
        pos = self._cursor_pos()
        w = QApplication.widgetAt(pos)
        if w is not None and w.window().windowType() == Qt.ToolTip:
            # 光标落在了 tooltip 弹窗自身（贴近屏幕边缘时 Qt 会把 tip 翻转到
            # 光标上方）——此时既不重设也不隐藏，避免 hide/show 来回抖动
            return
        # 只认本对话框内的控件（QToolTip 自己的弹窗是独立顶层窗口，天然被排除）
        tip_w = None
        if w is not None and self._window.isAncestorOf(w) and w.toolTip():
            tip_w = w
        if tip_w is not None:
            if tip_w is not self._cur:
                # 换了控件才重设，避免同一控件内反复触发
                self._cur = tip_w
                QToolTip.showText(pos, tip_w.toolTip(), tip_w, tip_w.rect())
        elif self._cur is not None:
            self._cur = None
            QToolTip.hideText()


class ui_Form(Ui_Form):
    def __init__(self, mainWindow):
        # 设置界面的参数，不能用快捷键修改的从配置文件里来；能用快捷键修改的从mainWindow来
        self.game_setting = mainWindow.game_setting
        # config = configparser.ConfigParser()
        # config.read(self.game_setting_path, encoding='utf-8')
        self.gameMode = mainWindow.gameMode
        self.pixSize = mainWindow.pixSize
        self.row = mainWindow.row
        self.column = mainWindow.column
        self.minenum = mainWindow.minenum

        self.auto_replay = self.game_setting.value(
            'DEFAULT/auto_replay', None, int)
        self.auto_notification = self.game_setting.value(
            'DEFAULT/auto_notification', None, bool)
        self.player_identifier = self.game_setting.value(
            'DEFAULT/player_identifier', None, str)
        self.race_identifier = self.game_setting.value(
            'DEFAULT/race_identifier', None, str)
        self.unique_identifier = self.game_setting.value(
            'DEFAULT/unique_identifier', None, str)
        self.country = self.game_setting.value('DEFAULT/country', None, str)
        self.autosave_video = self.game_setting.value(
            'DEFAULT/autosave_video', None, bool)
        self.autosave_video_set = self.game_setting.value(
            'DEFAULT/autosave_video_set', None, bool)
        self.end_then_flag = self.game_setting.value(
            'DEFAULT/end_then_flag', None, bool)
        self.cursor_limit = self.game_setting.value(
            'DEFAULT/cursor_limit', None, bool)
        self.double_click_restart = self.game_setting.value(
            'DEFAULT/double_click_restart', False, bool)
        self.board_shake = self.game_setting.value(
            'DEFAULT/board_shake', None, bool)
        self.board_constraint = mainWindow.board_constraint
        self.attempt_times_limit = mainWindow.attempt_times_limit

        self.alter = False

        self.Dialog = RoundQDialog(mainWindow.mainWindow)
        self.setupUi(self.Dialog)
        # macOS（Fusion 样式 + 全局圆角边框 QSS + 高 DPR）下，QSpinBox 的
        # 内部 QLineEdit 会被布局坍缩成 1px 宽：数字渲染不出来（看起来
        # 「不显示」），键入的内容也进不去（看起来「无法输入」）。
        # 实测 sizeHint=39 而 spinBox 被拉宽到 130，多余宽度全被边框吃掉。
        # 给内部 QLineEdit 设最小宽度即可根治，两个数字框一并处理。
        self.spinBox_pixsize.lineEdit().setMinimumWidth(100)
        self.spinBox_auto_replay.lineEdit().setMinimumWidth(100)
        # 数字直通模式：中文输入法激活时数字键不被候选词拦截
        self.spinBox_pixsize.setInputMethodHints(Qt.ImhDigitsOnly)
        # ClickFocus 下 Tab 键进不来；StrongFocus 同时支持点击与 Tab 聚焦
        self.spinBox_pixsize.setFocusPolicy(Qt.StrongFocus)
        # 无边框窗口在 macOS 上可能不成为 key window（键盘事件全被丢弃），
        # show 时强制激活窗口
        orig_show = self.Dialog.show

        def _show_and_activate():
            orig_show()
            self.Dialog.activateWindow()

        self.Dialog.show = _show_and_activate
        # macOS 修复：hover 标签不出 tooltip。无边框半透明窗口上 Qt 原生
        # tooltip 链路（自发 MouseMove -> 唤醒定时器 -> active window 检查）
        # 不可靠，两道保险：
        # 1) WA_AlwaysShowToolTips 放行原生链路的 active window 检查；
        # 2) _MacToolTipFallback 轮询光标位置直接 showText，不依赖 hover 事件。
        # 仅 darwin 启用，Windows 行为保持不变。
        if sys.platform == "darwin":
            self.Dialog.setAttribute(Qt.WA_AlwaysShowToolTips)
            self._mac_tooltip = _MacToolTipFallback(self.Dialog)
            self._mac_tooltip.start()
        for combo_box in self.Dialog.findChildren(QComboBox):
            combo_box.view().setStyleSheet("""
                QListView {
                    background-color: #f4f4f4;
                    color: #3d3d3d;
                }
                QListView::item:selected {
                    background-color: #c7e3fa;
                    color: #3d3d3d;
                }
                QListView::item:hover {
                    background-color: #dceeff;
                    color: #3d3d3d;
                }
            """)
        # self.Dialog.setWindowIcon(QtGui.QIcon (str(self.r_path.with_name('media').joinpath('cat.ico'))))

        self.pushButton_yes.clicked.connect(self.processParameter)
        self.pushButton_no.clicked.connect(self.Dialog.close)
        # self.comboBox_country.activated['QString'].connect(lambda x: self.onchange_combobox_country(x))
        self.country_name = list(country_name.keys())
        self.comboBox_country.lineEdit().setAlignment(Qt.AlignCenter)
        self.comboBox_country.editTextChanged.connect(
            self.onchange_combobox_country)
        self.comboBox_country.lineEdit().setText(self.country)
        self.comboBox_country.addItems(self.country_name)

        self.setParameter()

        # 主界面缩放（拖拽边缘/Ctrl+滚轮/换级别）时，实时同步「方格边长」
        # 显示；对话框自身正被编辑时不覆盖用户输入。
        # 对话框每次打开都新建、关闭即废弃，关闭时必须退订，防止回调悬挂。
        self._on_pix_size = None
        subscribe = getattr(mainWindow, "on_pix_size_changed", None)
        if subscribe is not None:
            self._on_pix_size = self.on_pix_size_changed
            subscribe(self._on_pix_size)

    def on_pix_size_changed(self, pix_size: int):
        # 只有数值真的变了才回写，避免打断正在输入的用户
        if self.spinBox_pixsize.value() != pix_size:
            self.spinBox_pixsize.setValue(pix_size)

    def set_country_flag(self, flag_name):
        # 设置国旗图案
        if flag_name not in country_name:
            self.label_national_flag.clear()
            self.label_national_flag.update()
        else:
            fn = country_name[flag_name]
            pixmap = QPixmap(str(resource_path('media') /
                                 (fn + ".svg"))).scaled(51, 31)
            self.label_national_flag.setPixmap(pixmap)
            self.label_national_flag.update()

    # 修改comboBox_country里的国家选项的回调

    def onchange_combobox_country(self, qtext):
        # 记录光标位置
        line_edit = self.comboBox_country.lineEdit()
        cursor_position = line_edit.cursorPosition()

        self.comboBox_country.blockSignals(True)  # 避免清空时再次触发信号
        self.comboBox_country.clear()
        # 过滤逻辑：只保留包含输入的国家（不区分大小写）
        filtered = [c for c in self.country_name if qtext.lower() in c.lower()]
        # 重新填充
        self.comboBox_country.addItems(filtered)
        # 恢复用户已输入的文本
        self.comboBox_country.setEditText(qtext)
        line_edit.setCursorPosition(cursor_position)
        self.comboBox_country.blockSignals(False)
        self.set_country_flag(qtext)

    def setParameter(self):
        self.spinBox_pixsize.setValue(self.pixSize)
        self.spinBox_auto_replay.setValue(abs(self.auto_replay))
        self.checkBox_auto_replay.setChecked(self.auto_replay >= 0)
        self.checkBox_auto_notification.setChecked(self.auto_notification)
        self.checkBox_autosave_video.setChecked(self.autosave_video)
        self.checkBox_autosave_video_set.setChecked(self.autosave_video_set)
        self.lineEdit_constraint.setText(self.board_constraint)
        self.spinBox_attempt_times_limit.setValue(self.attempt_times_limit)
        self.lineEdit_label.setText(self.player_identifier)
        self.lineEdit_race_label.setText(self.race_identifier)
        self.lineEdit_unique_label.setText(self.unique_identifier)
        # self.lineEdit_country.setText(self.country)
        # self.onchange_combobox_country(self.country)
        self.comboBox_country.setCurrentText(self.country)
        self.checkBox_end_then_flag.setChecked(self.end_then_flag)
        self.checkBox_cursor_limit.setChecked(self.cursor_limit)
        self.checkBox_double_click_restart.setChecked(self.double_click_restart)
        self.checkBox_board_shake.setChecked(self.board_shake)

        if not self.checkBox_auto_replay.isChecked():
            self.spinBox_auto_replay.setEnabled(False)
            self.label_auto_replay_percent.setEnabled(False)
        # gameMode = 0，4, 5, 6, 7, 8, 9, 10, 11–16代表：
        # 标准、win7、经典无猜、强无猜、弱无猜、准无猜、强可猜、弱可猜、
        # 双击递归、标雷递归、双击标雷递归、无猜双击递归、无猜标雷递归、无猜双击标雷递归
        self.comboBox_gamemode.setCurrentIndex(
            [0, 999, 999, 999, 1, 4, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13][self.gameMode])

    def processParameter(self):
        # 只有点确定才能进来

        self.alter = True
        self.pixSize = self.spinBox_pixsize.value()
        v = self.spinBox_auto_replay.value()
        self.auto_replay = v if self.checkBox_auto_replay.isChecked() else -v
        self.auto_notification = self.checkBox_auto_notification.isChecked()
        self.player_identifier = self.lineEdit_label.text().strip()
        self.race_identifier = self.lineEdit_race_label.text().strip()
        self.unique_identifier = self.lineEdit_unique_label.text().strip()
        self.country = self.comboBox_country.currentText()
        self.autosave_video = self.checkBox_autosave_video.isChecked()
        self.autosave_video_set = self.checkBox_autosave_video_set.isChecked()
        self.board_constraint = self.lineEdit_constraint.text()
        self.attempt_times_limit = self.spinBox_attempt_times_limit.value()
        self.end_then_flag = self.checkBox_end_then_flag.isChecked()  # 游戏结束后自动标雷
        self.cursor_limit = self.checkBox_cursor_limit.isChecked()
        self.double_click_restart = self.checkBox_double_click_restart.isChecked()
        self.board_shake = self.checkBox_board_shake.isChecked()
        self.gameMode = [0, 4, 6, 7, 5, 8, 9,
                         10, 11, 12, 13, 14, 15, 16][self.comboBox_gamemode.currentIndex()]
        # gameMode = 0，4, 5, 6, 7, 8, 9, 10, 11–16代表：
        # 标准、win7、经典无猜、强无猜、弱无猜、准无猜、强可猜、弱可猜、
        # 双击递归、标雷递归、双击标雷递归、无猜双击递归、无猜标雷递归、无猜双击标雷递归

        self.game_setting.set_value("DEFAULT/auto_replay", self.auto_replay)
        self.game_setting.set_value(
            "DEFAULT/end_then_flag", self.end_then_flag)
        self.game_setting.set_value("DEFAULT/cursor_limit", self.cursor_limit)
        self.game_setting.set_value("DEFAULT/board_shake", self.board_shake)
        self.game_setting.set_value(
            'DEFAULT/double_click_restart', self.double_click_restart)
        self.game_setting.set_value(
            "DEFAULT/auto_notification", self.auto_notification)
        self.game_setting.set_value(
            "DEFAULT/autosave_video", self.autosave_video)
        self.game_setting.set_value(
            "DEFAULT/autosave_video_set", self.autosave_video_set)
        self.game_setting.set_value(
            "DEFAULT/player_identifier", self.player_identifier)
        self.game_setting.set_value(
            "DEFAULT/race_identifier", self.race_identifier)
        self.game_setting.set_value(
            "DEFAULT/unique_identifier", self.unique_identifier)
        self.game_setting.set_value("DEFAULT/country", self.country)
        if (self.row, self.column, self.minenum) == BOARD_BEGINNER:
            self.game_setting.set_value("BEGINNER/gamemode", self.gameMode)
            self.game_setting.set_value(
                "BEGINNER/board_constraint", self.board_constraint)
            self.game_setting.set_value(
                "BEGINNER/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("BEGINNER/pixsize", self.pixSize)
        elif (self.row, self.column, self.minenum) == BOARD_INTERMEDIATE:
            self.game_setting.set_value("INTERMEDIATE/gamemode", self.gameMode)
            self.game_setting.set_value(
                "INTERMEDIATE/board_constraint", self.board_constraint)
            self.game_setting.set_value(
                "INTERMEDIATE/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("INTERMEDIATE/pixsize", self.pixSize)
        elif (self.row, self.column, self.minenum) == BOARD_EXPERT:
            self.game_setting.set_value("EXPERT/gamemode", self.gameMode)
            self.game_setting.set_value(
                "EXPERT/board_constraint", self.board_constraint)
            self.game_setting.set_value(
                "EXPERT/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("EXPERT/pixsize", self.pixSize)
        else:
            self.game_setting.set_value("CUSTOM/gamemode", self.gameMode)
            self.game_setting.set_value(
                "CUSTOM/board_constraint", self.board_constraint)
            self.game_setting.set_value(
                "CUSTOM/attempt_times_limit", self.attempt_times_limit)
            self.game_setting.set_value("CUSTOM/pixsize", self.pixSize)

        self.game_setting.sync()
        self.Dialog.close()
