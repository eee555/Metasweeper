import os
from pathlib import Path

from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import QFont
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel, QCheckBox, \
    QSizePolicy, QHBoxLayout, QMenu, QMessageBox, QGridLayout, QSizeGrip, QComboBox, QSpacerItem

from replay_analysis import analyse_replay_events, unwrap_board_event, unwrap_mouse_event
from ui.uiComponents import RoundQWidget
from ui.ui_video_control import Ui_Form
from utils.app_logger import logger
from utils.path_utils import resource_path


class VideoControlWindow(RoundQWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)
        self.size_grip.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        grip_size = self.size_grip.sizeHint()
        self.size_grip.move(
            self.width() - grip_size.width() - 8,
            self.height() - grip_size.height() - 8,
        )


class CommentCheckBox(QWidget):
    # toggled = QtCore.pyqtSignal(int)

    def __init__(self, parent, signal_int):
        super(CommentCheckBox, self).__init__(parent)
        self.signal_int = signal_int

        # 创建水平布局管理器
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 去除边距

        # 创建实际的QCheckBox
        self.checkbox = QCheckBox()
        self.checkbox.setText("")  # 不显示文本

        # 设置字体（保持与原有风格一致）
        font = QtGui.QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        self.checkbox.setFont(font)

        # 将复选框添加到布局并居中
        layout.addWidget(self.checkbox)
        layout.setAlignment(QtCore.Qt.AlignCenter)  # 居中对齐

        # 设置大小策略以确保正确显示
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 连接复选框的点击信号
        # self.checkbox.toggled.connect(self.on_toggled)

    # def on_toggled(self):
    #     # 发送int信号
    #     self.toggled.emit(self.signal_int)

    # 提供与QCheckBox兼容的方法
    def isChecked(self):
        return self.checkbox.isChecked()

    def setChecked(self, checked):
        self.checkbox.setChecked(checked)


# 录像播放控制面板上的标签，点击发送一个整数信号
class CommentLabel(QLabel):
    # Release = QtCore.pyqtSignal(int)
    clicked = Signal()  # 单击信号
    doubleClicked = Signal()  # 双击信号
    hovered = Signal()
    unhovered = Signal()

    def __init__(self, parent, text, middle=True):
        super(CommentLabel, self).__init__(parent)
        if not isinstance(text, str):
            text = "%.2f" % text
        self.setText(text)
        # self.signal_int = signal_int

        font = QtGui.QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        self.setFont(font)
        # self.setMinimumSize(QtCore.QSize(height, width))
        if middle:
            self.setAlignment(QtCore.Qt.AlignCenter)

    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件，主要用于单击检测"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()  # 发射单击信号
        super().mouseReleaseEvent(event)  # 确保调用父类方法

    def mouseDoubleClickEvent(self, event):
        """处理鼠标双击事件"""
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()  # 发射双击信号
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        self.hovered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.unhovered.emit()
        super().leaveEvent(event)


class VideoSetTabWidget(QWidget):
    """
    可复用的视频标签页组件
    封装了滚动区域、标题标签和选择复选框
    """

    def __init__(self, parent=None, video_set=None, tab_name="", file_name=""):
        super().__init__(parent)
        self.tab_name = tab_name
        self.file_name = file_name
        self.video_set = video_set
        self.setup_ui()

        # 添加右键菜单功能
        self.setContextMenuPolicy(Qt.CustomContextMenu)  # 设置右键菜单策略[1,2](@ref)
        self.customContextMenuRequested.connect(
            self.show_context_menu)  # 连接右键菜单信号[1,5](@ref)

    def setup_ui(self):
        """初始化UI界面"""
        _translate = QtCore.QCoreApplication.translate
        # 设置对象名
        self.setObjectName(self.tab_name)

        # 主布局 - 使用边距为0，间距为0的垂直布局
        self.verticalLayout_2 = QVBoxLayout(self)
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName("verticalLayout_2")

        # 创建滚动区域
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setSizeAdjustPolicy(QScrollArea.AdjustToContents)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")

        # 滚动区域的内容部件
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 457, 459))
        self.scrollAreaWidgetContents.setMinimumSize(QSize(0, 0))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.tableLayout = QGridLayout(self.scrollAreaWidgetContents)
        self.tableLayout.setContentsMargins(0, 0, 0, 0)
        self.tableLayout.setSpacing(0)
        self.tableLayout.setColumnMinimumWidth(0, 91)
        self.tableLayout.setColumnStretch(0, 0)
        self.tableLayout.setColumnStretch(1, 1)

        # 视频标题标签
        self.label_video = QLabel(self.scrollAreaWidgetContents)
        font = QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        self.label_video.setFont(font)
        self.label_video.setAlignment(Qt.AlignCenter)
        self.label_video.setObjectName("label_video")
        self.label_video.setText(_translate("Form", "录像"))

        # 选择复选框
        self.checkBox_choose = QCheckBox(self.scrollAreaWidgetContents)
        font = QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        self.checkBox_choose.setFont(font)
        self.checkBox_choose.setObjectName("checkBox_choose")
        self.checkBox_choose.setText(_translate("Form", "全选"))
        self.checkBox_choose.setMinimumHeight(42)
        self.checkBox_choose.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.label_video.setMinimumHeight(42)
        self.label_video.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Minimum)

        # 确保控件层次正确
        self.checkBox_choose.raise_()
        self.label_video.raise_()
        self.tableLayout.addWidget(self.checkBox_choose, 0, 0)
        self.tableLayout.addWidget(self.label_video, 0, 1)

        # 设置滚动区域的内容
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.verticalLayout_2.addWidget(self.scrollArea)

        self.checkBox_choose.toggled.connect(self.on_select_all_toggled)

    def show_context_menu(self, pos):
        """显示右键菜单"""
        _translate = QtCore.QCoreApplication.translate
        menu = QMenu(self)  # 创建菜单[1,2](@ref)
        export_action = menu.addAction(_translate("Form", "导出选中的录像"))

        # 处理菜单项选择
        action = menu.exec(self.mapToGlobal(pos))
        if action == export_action:
            self.export_data()  # 调用导出方法

    def export_data(self):
        """导出数据的具体实现"""
        checkboxes = self.scrollAreaWidgetContents.findChildren(
            CommentCheckBox)  # 请将CommentCheckBox替换为你的实际复选框类名

        # 布局会动态撑高行，导出顺序按录像集索引确定。
        ordered_checkboxes = sorted(checkboxes, key=lambda cb: cb.signal_int)

        # self.video_set.file_name是带evfs后缀的绝对路径
        path = Path(self.video_set.file_name)
        folder_name = path.stem
        target_folder = path.parent / folder_name
        try:
            target_folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.exception("Failed to create directory: %s", target_folder)
            return

        # 合理的video.file_name是不带后缀的相对路径evf文件名
        # 考虑潜在的风险，此处仍然做了绝对路径转相对路径的处理
        for idx, box in enumerate(ordered_checkboxes):
            if box.isChecked():
                video = self.video_set[idx].evf_video
                video_name = Path(video.file_name)
                video.save_to_evf_file(str(target_folder / video_name.name))

    def on_select_all_toggled(self, checked):
        """全选复选框状态变化时的槽函数"""
        # 查找scrollAreaWidgetContents中的所有CommentCheckBox组件
        checkboxes = []
        checkboxes = self.scrollAreaWidgetContents.findChildren(
            CommentCheckBox)
        # 设置所有CommentCheckBox的选中状态与全选复选框一致
        for checkbox_widget in checkboxes:
            checkbox_widget.setChecked(checked)

    # 提供公共方法供外部访问

    def get_video_title(self):
        """获取视频标题文本"""
        return self.label_video.text()

    def set_video_title(self, title):
        """设置视频标题"""
        self.label_video.setText(title)
        self.video_title = title

    def is_checked(self):
        """返回复选框是否被选中"""
        return self.checkBox_choose.isChecked()

    def set_checked(self, checked):
        """设置复选框状态"""
        self.checkBox_choose.setChecked(checked)

    def get_checkbox_text(self):
        """获取复选框文本"""
        return self.checkBox_choose.text()

    def set_checkbox_text(self, text):
        """设置复选框文本"""
        self.checkBox_choose.setText(text)
        self.checkbox_text = text

    def connect_checkbox_changed(self, callback):
        """连接复选框状态改变信号"""
        self.checkBox_choose.stateChanged.connect(callback)

    def add_video_row(self, index, video_name, row_index):
        font = QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)

        checkbox = CommentCheckBox(self.scrollAreaWidgetContents, index)
        checkbox.setMinimumHeight(42)
        checkbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        label = CommentLabel(self.scrollAreaWidgetContents,
                             video_name, middle=False)
        label.setFont(font)
        label.setWordWrap(True)
        label.setMinimumHeight(42)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        self.tableLayout.addWidget(checkbox, row_index, 0)
        self.tableLayout.addWidget(label, row_index, 1)
        return checkbox, label


class VideoTabWidget(QWidget):
    """
    可复用的事件标签页组件
    封装了滚动区域、时间标签、事件标签和分类标签
    """

    def __init__(self, parent=None, video=None, tab_name="", file_name=""):
        super().__init__(parent)
        self.tab_name = tab_name
        self.file_name = file_name
        self.video = video
        self.event_rows = []
        self.replay_comments = []
        self.event_types = set()
        self.bottom_spacer = None
        self.bottom_spacer_row = 1
        self.setup_ui()

    def setup_ui(self):
        """初始化UI界面"""
        _translate = QtCore.QCoreApplication.translate
        # 设置对象名
        self.setObjectName(self.tab_name)

        # 主布局 - 使用边距为0，间距为0的垂直布局
        self.verticalLayout_4 = QVBoxLayout(self)
        self.verticalLayout_4.setContentsMargins(0, 0, 0, -1)
        self.verticalLayout_4.setSpacing(0)
        self.verticalLayout_4.setObjectName("verticalLayout_4")

        # 创建滚动区域
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setSizeAdjustPolicy(QScrollArea.AdjustToContents)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")

        # 滚动区域的内容部件
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 457, 448))
        self.scrollAreaWidgetContents.setMinimumSize(QSize(0, 0))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.tableLayout = QGridLayout(self.scrollAreaWidgetContents)
        self.tableLayout.setContentsMargins(0, 0, 0, 0)
        self.tableLayout.setSpacing(0)
        self.tableLayout.setColumnMinimumWidth(0, 68)
        self.tableLayout.setColumnMinimumWidth(1, 70)
        self.tableLayout.setColumnMinimumWidth(2, 72)
        self.tableLayout.setColumnStretch(0, 0)
        self.tableLayout.setColumnStretch(1, 0)
        self.tableLayout.setColumnStretch(2, 0)
        self.tableLayout.setColumnStretch(3, 1)

        # 创建标题栏字体
        font = QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)

        # 时间标签
        self.label_time = self._make_table_label(
            _translate("Form", "时间"), font)
        self.label_time.setObjectName("label_time")

        # 坐标标签
        self.label_position = self._make_table_label(
            _translate("Form", "坐标"), font)
        self.label_position.setObjectName("label_position")

        # 类型筛选
        self.label_event = QComboBox(self.scrollAreaWidgetContents)
        self.label_event.setFont(font)
        self.label_event.setObjectName("label_event")
        self.label_event.setMinimumHeight(42)
        self.label_event.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.label_event.setStyleSheet(self._row_style())
        self.label_event.addItem(_translate("Form", "类型"))
        self.label_event.currentTextChanged.connect(
            self._apply_event_type_filter)

        # 详情标签
        self.label_tag = self._make_table_label(_translate("Form", "详情"), font)
        self.label_tag.setObjectName("label_tag")
        self.label_tag.setWordWrap(True)

        self.tableLayout.addWidget(self.label_time, 0, 0)
        self.tableLayout.addWidget(self.label_position, 0, 1)
        self.tableLayout.addWidget(self.label_event, 0, 2)
        self.tableLayout.addWidget(self.label_tag, 0, 3)
        self.tableLayout.setRowStretch(0, 0)
        self._place_bottom_spacer(1)

        # 设置滚动区域的内容
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.verticalLayout_4.addWidget(self.scrollArea)

    def _make_table_label(self, text, font, status=None):
        label = CommentLabel(self.scrollAreaWidgetContents, text)
        label.setFont(font)
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumHeight(42)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        label.setStyleSheet(self._row_style(status))
        return label

    def _row_style(self, status=None):
        colors = {
            "success": "#e8f5e9",
            "info": "#eef4ff",
            "warning": "#fff8df",
            "error": "#fdecec",
        }
        background = colors.get(status, "#f0f0f0")
        return f"background-color: {background}; border: 1px solid #ddd;"

    def retranslate_headers(self):
        _translate = QtCore.QCoreApplication.translate
        self.label_time.setText(_translate("Form", "时间"))
        self.label_position.setText(_translate("Form", "坐标"))
        self.label_event.blockSignals(True)
        self.label_event.setItemText(0, _translate("Form", "类型"))
        self.label_event.blockSignals(False)
        self.label_tag.setText(_translate("Form", "详情"))

    # 公共方法 - 标签文本设置
    def set_time_label(self, text):
        """设置时间标签文本"""
        self.label_time.setText(text)
        self.time_label = text

    def set_event_label(self, text):
        """设置事件标签文本"""
        self.label_event.setItemText(0, text)
        self.event_label = text

    def set_tag_label(self, text):
        """设置分类标签文本"""
        self.label_tag.setText(text)
        self.tag_label = text

    def get_time_label(self):
        """获取时间标签文本"""
        return self.label_time.text()

    def get_event_label(self):
        """获取事件标签文本"""
        return self.label_event.currentText()

    def get_tag_label(self):
        """获取分类标签文本"""
        return self.label_tag.text()

    # 公共方法 - 动态添加事件行
    def add_event_row(
        self,
        time_text,
        coordinate_text,
        event_type_text,
        tag_text,
        status="info",
        row_height=42,
        row_index=1,
    ):
        """
        动态添加事件行
        row_index: 行索引（从1开始，0被标题占用）
        """
        font = QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(10)
        time_label = self._make_table_label(time_text, font, status)
        coordinate_label = self._make_table_label(
            coordinate_text, font, status)
        event_type_label = self._make_table_label(
            event_type_text, font, status)
        tag_label = self._make_table_label(tag_text, font, status)
        tag_label.setWordWrap(True)
        tag_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        tag_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._remove_bottom_spacer()
        self.tableLayout.addWidget(time_label, row_index, 0)
        self.tableLayout.addWidget(coordinate_label, row_index, 1)
        self.tableLayout.addWidget(event_type_label, row_index, 2)
        self.tableLayout.addWidget(tag_label, row_index, 3)
        self.tableLayout.setRowStretch(row_index, 0)
        self._place_bottom_spacer(row_index + 1)

        row_widgets = (time_label, coordinate_label,
                       event_type_label, tag_label)
        self.event_rows.append((event_type_text, row_widgets))
        self._add_event_type_filter_option(event_type_text)
        self._set_event_row_visible(
            row_widgets, self._event_type_filter_accepts(event_type_text))
        return time_label, coordinate_label, event_type_label, tag_label

    def _place_bottom_spacer(self, row_index):
        if self.bottom_spacer is None:
            self.bottom_spacer = QSpacerItem(
                0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.bottom_spacer_row = row_index
        self.tableLayout.addItem(self.bottom_spacer, row_index, 0, 1, 4)
        self.tableLayout.setRowStretch(row_index, 1)

    def _remove_bottom_spacer(self):
        if self.bottom_spacer is None:
            return
        self.tableLayout.setRowStretch(self.bottom_spacer_row, 0)
        self.tableLayout.removeItem(self.bottom_spacer)

    def _add_event_type_filter_option(self, event_type_text):
        if not event_type_text or event_type_text in self.event_types:
            return
        self.event_types.add(event_type_text)
        self.label_event.addItem(event_type_text)

    def _apply_event_type_filter(self, selected_type):
        for event_type_text, row_widgets in self.event_rows:
            self._set_event_row_visible(
                row_widgets,
                self._event_type_filter_accepts(
                    event_type_text, selected_type),
            )

    def _event_type_filter_accepts(self, event_type_text, selected_type=None):
        if selected_type is None:
            selected_type = self.label_event.currentText()
        return selected_type == self.label_event.itemText(0) or event_type_text == selected_type

    def _set_event_row_visible(self, row_widgets, visible):
        for widget in row_widgets:
            widget.setVisible(visible)

    def clear_events(self):
        """清除所有事件行（保留标题行）"""
        self.event_rows = []
        self.event_types = set()
        self._remove_bottom_spacer()
        for index in reversed(range(self.tableLayout.count())):
            item = self.tableLayout.itemAt(index)
            widget = item.widget()
            if widget and widget not in [
                self.label_time,
                self.label_position,
                self.label_event,
                self.label_tag,
            ]:
                self.tableLayout.removeWidget(widget)
                widget.deleteLater()
        while self.label_event.count() > 1:
            self.label_event.removeItem(1)
        self._place_bottom_spacer(1)

    def set_tab_text(self, text):
        """设置标签页显示文本"""
        self.tab_text = text

    def get_tab_text(self):
        """获取标签页显示文本"""
        return self.tab_text


class ui_Form(QWidget, Ui_Form):
    videoSetTime = QtCore.Signal(int)
    videoSetTimePeriod = QtCore.Signal(int)
    videoTabClicked = QtCore.Signal(str, int)
    videoTabDoubleClicked = QtCore.Signal(str, int)
    videoCellsHovered = QtCore.Signal(object)
    videoCellHoverCleared = QtCore.Signal()
    # barSetMineNumCalPoss = QtCore.pyqtSignal(int)
    # time_current = 0.0

    def __init__(self, game_setting, parent):
        super(ui_Form, self).__init__()
        self.tab_id = 0
        self.QWidget = VideoControlWindow(parent)
        self.setupUi(self.QWidget)
        self.QWidget.setMinimumSize(QtCore.QSize(480, 360))
        self.QWidget.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.QWidget.resize(
            game_setting.value("DEFAULT/videocontrolwidth", 520, int),
            game_setting.value("DEFAULT/videocontrolheight", 640, int),
        )
        self.game_setting = game_setting

        m = resource_path('media').as_posix()
        self.pushButton_replay.setStyleSheet(
            self.pushButton_replay.styleSheet().replace("url(media/", f"url({m}/"))
        self.pushButton_play.setStyleSheet(
            self.pushButton_play.styleSheet().replace("url(media/", f"url({m}/"))
        # self.label_2.setStyleSheet(self.label_2.styleSheet().replace("url(media/", f"url({m}/"))
        self.label_speed.setStyleSheet(
            self.label_speed.styleSheet().replace("url(media/", f"url({m}/"))
        self.pushButton_path.setStyleSheet(
            self.pushButton_path.styleSheet().replace("url(media/", f"url({m}/"))
        self.pushButton_op.setStyleSheet(
            self.pushButton_op.styleSheet().replace("url(media/", f"url({m}/"))

        self.QWidget.closeEvent_.connect(self.close)
        # self.horizontalSlider_time.setMaximum(int(video.video_end_time * 1000))
        # self.horizontalSlider_time.setMinimum(int(video.video_start_time * 1000))

        self.horizontalSlider_time.valueChanged[int].connect(
            self.set_double_spin_box_time)
        self.doubleSpinBox_time.valueChanged[float].connect(
            self.set_horizontal_slider_time)
        self.QWidget.move(game_setting.value("DEFAULT/videocontroltop", 100, int),
                          game_setting.value("DEFAULT/videocontrolleft", 300, int))
        self.tabWidget.tabCloseRequested.connect(self.close_tab)

    def add_new_video_tab(self, video, progress_callback=None):
        _translate = QtCore.QCoreApplication.translate
        comments = self._analyse_video_comments(video, progress_callback)

        self.tab_id += 1
        tab = VideoTabWidget(
            self, video=video, tab_name=f"tab_{self.tab_id}", file_name=video.file_name)
        tab.setAttribute(Qt.WA_DeleteOnClose)
        tab.replay_comments = comments

        self._populate_video_event_tab(tab, video, comments)

        self.tabWidget.addTab(tab, _translate(
            "Form", "录像") + f"({self.tab_id})")
        ...

    def _analyse_video_comments(self, video, progress_callback=None):
        comments = []
        for row in analyse_replay_events(video, progress_callback=progress_callback):
            if row.annotations:
                comments.append((row.time, row.event_index,
                                row.events or row.annotations))
        return comments

    def _populate_video_event_tab(self, tab, video, comments):
        comment_row = 1
        for time, event_index, annotations in comments:
            time_value = int(time * 1000)
            coordinate = self._event_coordinate(video, event_index)
            coordinate_text = self._event_coordinate_text(coordinate)
            for replay_event in annotations:
                annotation = (
                    replay_event.to_annotation()
                    if hasattr(replay_event, "to_annotation")
                    else replay_event
                )
                status = self._normalise_event_status(annotation.severity)
                event_type_text = self._event_type_text(
                    video, event_index, annotation)
                c1, c2, c3, c4 = tab.add_event_row(
                    time,
                    coordinate_text,
                    event_type_text,
                    annotation.text,
                    status=status,
                    row_index=comment_row,
                )
                comment_row += 1
                c1.clicked.connect(
                    lambda t=time_value: self.videoSetTimePeriod.emit(t))
                c2.clicked.connect(
                    lambda t=time_value: self.videoSetTimePeriod.emit(t))
                c3.clicked.connect(
                    lambda t=time_value: self.videoSetTimePeriod.emit(t))
                c4.clicked.connect(
                    lambda t=time_value: self.videoSetTimePeriod.emit(t))
                highlight_cells = tuple(
                    getattr(annotation, "highlight_cells", ()) or ())
                if highlight_cells:
                    for cell in (c1, c2, c3, c4):
                        cell.hovered.connect(
                            lambda cells=highlight_cells: self.videoCellsHovered.emit(
                                cells)
                        )
                        cell.unhovered.connect(self.videoCellHoverCleared.emit)

    def retranslate_dynamic_ui(self):
        _translate = QtCore.QCoreApplication.translate
        for index in range(self.tabWidget.count()):
            tab = self.tabWidget.widget(index)
            if isinstance(tab, VideoTabWidget):
                tab.retranslate_headers()
                tab.clear_events()
                self._populate_video_event_tab(
                    tab, tab.video, tab.replay_comments)
                self.tabWidget.setTabText(index, _translate(
                    "Form", "录像") + f"({tab.tab_name.split('_')[-1]})")
            elif isinstance(tab, VideoSetTabWidget):
                self.tabWidget.setTabText(index, _translate(
                    "Form", "目录") + f"({tab.tab_name.split('_')[-1]})")

    def _normalise_event_status(self, severity):
        status = str(severity or "info").strip().lower()
        if status in {"success", "info", "warning", "error"}:
            return status
        if status in {"warn"}:
            return "warning"
        if status in {"fail", "failure", "danger"}:
            return "error"
        return "info"

    def _event_coordinate(self, video, event_index):
        record = self._video_event_record(video, event_index)
        if record is None:
            return None

        event = getattr(record, "event", None)
        mouse = unwrap_mouse_event(event, getattr(video, "pix_size", 0))
        if mouse is not None and mouse.row is not None and mouse.column is not None:
            return mouse.row, mouse.column

        board_event = unwrap_board_event(event)
        if board_event is not None:
            return board_event.row, board_event.column

        return None

    def _event_coordinate_text(self, coordinate):
        if coordinate is None:
            return ""
        row, column = coordinate
        return f"{row + 1},{column + 1}"

    def _event_type_text(self, video, event_index, annotation):
        if annotation.key:
            return annotation.key

        record = self._video_event_record(video, event_index)
        if record is None:
            return ""

        event = getattr(record, "event", None)
        mouse = unwrap_mouse_event(event, getattr(video, "pix_size", 0))
        if mouse is not None:
            return mouse.mouse

        board_event = unwrap_board_event(event)
        if board_event is not None:
            return board_event.board

        return ""

    def _video_event_record(self, video, event_index):
        try:
            return video.events[event_index]
        except (AttributeError, IndexError, TypeError):
            return None

    def add_new_video_set_tab(self, video_set):
        _translate = QtCore.QCoreApplication.translate
        self.tab_id += 1
        tab_name = f"tab_{self.tab_id}"
        tab = VideoSetTabWidget(self, video_set=video_set,
                                tab_name=tab_name, file_name=video_set.file_name)
        tab.setAttribute(Qt.WA_DeleteOnClose)
        # video_labels = []
        comment_row = 1
        for idv in range(video_set.len()):
            cell = video_set[idv]
            video = cell.evf_video
            c1, c2 = tab.add_video_row(
                idv,
                video.file_name.split("\\")[-1] + ".evf",
                comment_row,
            )
            # video_labels.append((idv, c2))
            c2.clicked.connect(
                lambda v=idv: self.videoTabClicked.emit(tab_name, v))
            c2.doubleClicked.connect(
                lambda v=idv: self.videoTabDoubleClicked.emit(tab_name, v))
            comment_row += 1

        # for idv, video_label in video_labels:
        #     video_label.clicked.connect(lambda: self.videoTabClicked.emit(idv))
            # video_label.mouseReleaseEvent.connect(self.videoTabDoubleClicked.emit)

        self.tabWidget.addTab(tab, _translate(
            "Form", "目录") + f"({self.tab_id})")

    def set_double_spin_box_time(self, int_time):
        self.doubleSpinBox_time.setValue(int_time / 1000)
        self.horizontalSlider_time.blockSignals(True)
        self.horizontalSlider_time.setValue(int_time)
        self.horizontalSlider_time.blockSignals(False)
        self.videoSetTime.emit(int_time)
        # self.time_current = int_time / 100

    def set_horizontal_slider_time(self, float_time):
        self.doubleSpinBox_time.blockSignals(True)
        self.horizontalSlider_time.setValue(int(float_time * 1000))
        self.doubleSpinBox_time.blockSignals(False)
        self.videoSetTime.emit(int(float_time * 1000))
        # self.time_current = float_time

    def close_tab(self, index):
        # 使用 removeTab 方法移除指定索引的选项卡
        self.tabWidget.removeTab(index)

    def close(self):
        self.tabWidget.clear()
        self.tab_id = 0
        self.game_setting.set_value(
            "DEFAULT/videocontroltop", self.QWidget.x())
        self.game_setting.set_value(
            "DEFAULT/videocontrolleft", self.QWidget.y())
        self.game_setting.set_value(
            "DEFAULT/videocontrolwidth", self.QWidget.width())
        self.game_setting.set_value(
            "DEFAULT/videocontrolheight", self.QWidget.height())
        self.game_setting.sync()
