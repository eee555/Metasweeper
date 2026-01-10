from ui.uiComponents import RoundQWidget
from ui.ui_video_control import Ui_Form
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel, QCheckBox,\
    QSizePolicy, QHBoxLayout, QMenu, QAction, QMessageBox
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5 import QtCore, QtGui
from pathlib import Path
import os
import ms_toollib as ms


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
    clicked = pyqtSignal()  # 单击信号
    doubleClicked = pyqtSignal()  # 双击信号
    def __init__(self, parent, text, middle = True):
        super(CommentLabel, self).__init__(parent)
        if not isinstance(text, str):
            text = "%.2f"%text
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
        self.customContextMenuRequested.connect(self.show_context_menu)  # 连接右键菜单信号[1,5](@ref)
    
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
        
        # 视频标题标签
        self.label_video = QLabel(self.scrollAreaWidgetContents)
        self.label_video.setGeometry(QRect(120, 0, 367, 42))
        font = QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        self.label_video.setFont(font)
        self.label_video.setAlignment(Qt.AlignCenter)
        self.label_video.setObjectName("label_video")
        self.label_video.setText(_translate("Form", "录像"))
        
        # 选择复选框
        self.checkBox_choose = QCheckBox(self.scrollAreaWidgetContents)
        self.checkBox_choose.setGeometry(QRect(10, 0, 91, 42))
        font = QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        self.checkBox_choose.setFont(font)
        self.checkBox_choose.setObjectName("checkBox_choose")
        self.checkBox_choose.setText(_translate("Form", "全选"))
        
        # 确保控件层次正确
        self.checkBox_choose.raise_()
        self.label_video.raise_()
        
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
        action = menu.exec_(self.mapToGlobal(pos))
        if action == export_action:
            self.export_data()  # 调用导出方法
    
    def export_data(self):
        """导出数据的具体实现"""
        checkboxes = self.scrollAreaWidgetContents.findChildren(CommentCheckBox)  # 请将CommentCheckBox替换为你的实际复选框类名
    
        # 按控件在父容器中的y坐标（垂直位置）进行排序
        ordered_checkboxes = sorted(checkboxes, key=lambda cb: cb.y())
        
        # self.video_set.file_name是带evfs后缀的绝对路径
        path = Path(self.video_set.file_name)
        folder_name = path.stem
        target_folder = path.parent / folder_name
        try:
            target_folder.mkdir(parents=True, exist_ok=True)
        except:
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
        checkboxes = self.scrollAreaWidgetContents.findChildren(CommentCheckBox)
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
        
        # 创建标题栏字体
        font = QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(12)
        
        # 时间标签
        self.label_time = QLabel(self.scrollAreaWidgetContents)
        self.label_time.setGeometry(QRect(0, 0, 68, 42))
        self.label_time.setFont(font)
        self.label_time.setAlignment(Qt.AlignCenter)
        self.label_time.setObjectName("label_time")
        self.label_time.setText(_translate("Form", "时间"))
        
        # 事件标签
        self.label_event = QLabel(self.scrollAreaWidgetContents)
        self.label_event.setGeometry(QRect(68, 0, 90, 42))
        self.label_event.setFont(font)
        self.label_event.setAlignment(Qt.AlignCenter)
        self.label_event.setObjectName("label_event")
        self.label_event.setText(_translate("Form", "事件"))
        
        # 分类标签
        self.label_tag = QLabel(self.scrollAreaWidgetContents)
        self.label_tag.setGeometry(QRect(158, 0, 300, 42))
        self.label_tag.setFont(font)
        self.label_tag.setAlignment(Qt.AlignCenter)
        self.label_tag.setObjectName("label_tag")
        self.label_tag.setText(_translate("Form", "标签"))
        
        # 设置滚动区域的内容
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.verticalLayout_4.addWidget(self.scrollArea)
    
    # 公共方法 - 标签文本设置
    def set_time_label(self, text):
        """设置时间标签文本"""
        self.label_time.setText(text)
        self.time_label = text
    
    def set_event_label(self, text):
        """设置事件标签文本"""
        self.label_event.setText(text)
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
        return self.label_event.text()
    
    def get_tag_label(self):
        """获取分类标签文本"""
        return self.label_tag.text()
    
    # 公共方法 - 动态添加事件行
    def add_event_row(self, time_text, event_text, tag_text, row_height=42, row_index=1):
        """
        动态添加事件行
        row_index: 行索引（从1开始，0被标题占用）
        """
        # 计算Y坐标位置
        y_position = row_index * row_height
        
        # 创建时间标签
        time_label = QLabel(time_text, self.scrollAreaWidgetContents)
        time_label.setGeometry(QRect(0, y_position, 68, row_height))
        font = QFont()
        font.setFamily("微软雅黑")
        font.setPointSize(10)
        time_label.setFont(font)
        time_label.setAlignment(Qt.AlignCenter)
        time_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ddd;")
        
        # 创建事件标签
        event_label = QLabel(event_text, self.scrollAreaWidgetContents)
        event_label.setGeometry(QRect(68, y_position, 90, row_height))
        event_label.setFont(font)
        event_label.setAlignment(Qt.AlignCenter)
        event_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ddd;")
        
        # 创建分类标签
        tag_label = QLabel(tag_text, self.scrollAreaWidgetContents)
        tag_label.setGeometry(QRect(158, y_position, 300, row_height))
        tag_label.setFont(font)
        tag_label.setAlignment(Qt.AlignCenter)
        tag_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ddd;")
        
        # 调整滚动区域内容的高度
        current_height = self.scrollAreaWidgetContents.height()
        new_height = max(current_height, y_position + row_height + 10)
        self.scrollAreaWidgetContents.setMinimumHeight(new_height)
    
    def clear_events(self):
        """清除所有事件行（保留标题行）"""
        # 获取所有子控件
        children = self.scrollAreaWidgetContents.children()
        for child in children:
            # 只删除动态添加的事件行，保留标题标签
            if (isinstance(child, QLabel) and 
                child not in [self.label_time, self.label_event, self.label_tag]):
                child.deleteLater()
        
        # 重置内容区域高度
        self.scrollAreaWidgetContents.setMinimumHeight(448)
    
    def set_tab_text(self, text):
        """设置标签页显示文本"""
        self.tab_text = text
    
    def get_tab_text(self):
        """获取标签页显示文本"""
        return self.tab_text
    
    

class ui_Form(QWidget, Ui_Form):
    videoSetTime = QtCore.pyqtSignal(int)
    videoSetTimePeriod = QtCore.pyqtSignal(int)
    videoTabClicked = QtCore.pyqtSignal(str, int)
    videoTabDoubleClicked = QtCore.pyqtSignal(str, int)
    # barSetMineNumCalPoss = QtCore.pyqtSignal(int)
    # time_current = 0.0
    
    def __init__(self, r_path, game_setting, parent):
        super (ui_Form, self).__init__()
        self.tab_id = 0
        self.QWidget = RoundQWidget(parent)
        self.setupUi(self.QWidget)
        self.game_setting = game_setting
        self.QWidget.closeEvent_.connect(self.close)
        # self.horizontalSlider_time.setMaximum(int(video.video_end_time * 1000))
        # self.horizontalSlider_time.setMinimum(int(video.video_start_time * 1000))
        
        self.horizontalSlider_time.valueChanged[int].connect(self.set_double_spin_box_time)
        self.doubleSpinBox_time.valueChanged[float].connect(self.set_horizontal_slider_time)
        self.QWidget.move(game_setting.value("DEFAULT/videocontroltop", 100, int),
                          game_setting.value("DEFAULT/videocontrolleft", 300, int))
        self.tabWidget.tabCloseRequested.connect(self.close_tab)
        
        
    def add_new_video_tab(self, video):
        # 组织录像评论
        comments = []
        for event in video.events:
            t = event.time
            comment = event.comments
            if comment:
                comments.append((t, [i.split(': ')
                                for i in comment.split(';')[:-1]]))
                
        
        self.tab_id += 1
        tab = VideoTabWidget(self, video=video, tab_name=f"tab_{self.tab_id}", file_name=video.file_name)
        tab.setAttribute(Qt.WA_DeleteOnClose)
        
        comment_row = 1
        for comment in comments:
            time_value = int(comment[0] * 1000)
            c1 = CommentLabel(tab.scrollAreaWidgetContents, comment[0])
            c1.setGeometry(QtCore.QRect(0, 42 * comment_row, 68, 42))
            c1.clicked.connect(lambda t=time_value: self.videoSetTimePeriod.emit(t))
            for list_ in comment[1]:
                c2 = CommentLabel(tab.scrollAreaWidgetContents, list_[0])
                c2.setGeometry(QtCore.QRect(68, 42 * comment_row, 90, 42))
                c3 = CommentLabel(tab.scrollAreaWidgetContents, list_[1])
                c3.setGeometry(QtCore.QRect(158, 42 * comment_row, 300, 42))
                c3.setWordWrap(True)
                comment_row += 1
                c2.clicked.connect(lambda t=time_value: self.videoSetTimePeriod.emit(t))
                c3.clicked.connect(lambda t=time_value: self.videoSetTimePeriod.emit(t))
            
            
        tab.scrollAreaWidgetContents.setFixedHeight(42 * (comment_row + 1))
        
        self.tabWidget.addTab(tab, f"录像({self.tab_id})")
        ...
        
        
    def add_new_video_set_tab(self, video_set):
        self.tab_id += 1
        tab_name = f"tab_{self.tab_id}"
        tab = VideoSetTabWidget(self, video_set=video_set, tab_name=tab_name, file_name=video_set.file_name)
        tab.setAttribute(Qt.WA_DeleteOnClose)
        # video_labels = []
        comment_row = 1
        for idv in range(video_set.len()):
            cell = video_set[idv]
            video = cell.evf_video
            c1 = CommentCheckBox(tab.scrollAreaWidgetContents, idv)
            c1.setGeometry(QtCore.QRect(0, 42 * comment_row, 91, 42))
            c2 = CommentLabel(tab.scrollAreaWidgetContents,
                              video.file_name.split("\\")[-1] + ".evf", middle=False)
            c2.setGeometry(QtCore.QRect(91, 42 * comment_row, 367, 42))
            # video_labels.append((idv, c2))
            c2.clicked.connect(lambda v=idv: self.videoTabClicked.emit(tab_name, v))
            c2.doubleClicked.connect(lambda v=idv: self.videoTabDoubleClicked.emit(tab_name, v))
            comment_row += 1
        
        # for idv, video_label in video_labels:
        #     video_label.clicked.connect(lambda: self.videoTabClicked.emit(idv))
            # video_label.mouseReleaseEvent.connect(self.videoTabDoubleClicked.emit)
            
        tab.scrollAreaWidgetContents.setFixedHeight(42 * (comment_row + 1))
        
        
        self.tabWidget.addTab(tab, f"目录({self.tab_id})")


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
        self.game_setting.set_value("DEFAULT/videocontroltop", self.QWidget.x())
        self.game_setting.set_value("DEFAULT/videocontrolleft", self.QWidget.y())
        self.game_setting.sync()

