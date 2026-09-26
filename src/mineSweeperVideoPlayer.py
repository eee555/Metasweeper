from PySide6 import QtCore
from PySide6.QtCore import QTimer, QCoreApplication, Qt, QRect
from PySide6.QtGui import QPixmap

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QProgressDialog, QWidget
from dialogs import gameDefinedParameter
from dialogs import videoControl
import ms_toollib as ms
from config.constants import DISPLAY, FACE_SMILE, FACE_CLICK
from shared_types.enums import MouseState
from mineSweeperGUIEvent import MineSweeperGUIEvent
from mainWindowGUI import MainWindow
from utils.app_logger import logger


_translate = QCoreApplication.translate


class MineSweeperVideoPlayer(MineSweeperGUIEvent):
    def __init__(self, MainWindow: MainWindow, args):
        super(MineSweeperVideoPlayer, self).__init__(MainWindow, args)
        self.ui_video_control = videoControl.ui_Form(self.game_setting,
                                                     self.mainWindow)
        self.video_time_step = 0.01  # 录像时间的步长，定时器始终是10毫秒

        self.ui_video_control.pushButton_play.clicked.connect(self.video_play)
        self.ui_video_control.pushButton_replay.clicked.connect(
            self.video_replay)
        self.ui_video_control.videoSetTime.connect(self.video_set_time)
        self.ui_video_control.videoSetTimePeriod.connect(self.video_set_a_time)
        self.ui_video_control.label_speed.wEvent.connect(self.video_set_speed)
        self.ui_video_control.tabWidget.tabBar().tabBarClicked.connect(self.on_tab_clicked)
        self.ui_video_control.pushButton_path.clicked[bool].connect(
            self.toggle_path_trace)
        self.ui_video_control.pushButton_op.clicked[bool].connect(
            self.toggle_op)
        self.ui_video_control.videoTabClicked.connect(
            self.play_video_tab_name_id)
        self.ui_video_control.videoTabDoubleClicked.connect(
            lambda a, b: self.play_video_tab_name_id(a, b, True))
        self.ui_video_control.videoCellsHovered.connect(
            self.highlight_video_cells)
        self.ui_video_control.videoCellHoverCleared.connect(
            self.clear_video_cell_highlight)
        self.show_path_trace = False
        self.mouse_trace_points = []
        self.path_trace_left_clicks = set()
        self.path_trace_right_clicks = set()
        self.path_trace_double_clicks = set()
        self.original_pix_size = 0
        self.timer_video = QTimer()
        self.timer_video.timeout.connect(self.video_playing_step)
        self._video_loading = False
        self._video_load_file_name = ""
        self._video_load_progress_dialog = None

    # 打开录像文件的回调

    def action_OpenFile(self, openfile_name=None):
        if self._video_loading:
            if self._video_load_progress_dialog:
                self._video_load_progress_dialog.show()
                self._video_load_progress_dialog.raise_()
            return

        self.unlimit_cursor()
        if not openfile_name:
            _translate = QCoreApplication.translate
            openfile_name = QFileDialog.\
                getOpenFileName(self.mainWindow, _translate("Form", "打开文件"), str(self.setting_path / 'replay'),
                                _translate("Form", "All(*.avf *.evf *.rmv *.mvf *.evfs);;Arbiter video(*.avf);;Metasweeper video(*.evf);;Vienna MineSweeper video(*.rmv);;Minesweeper Clone 0.97(*.mvf);;Metasweeper video set(*.evfs)"))
            openfile_name = openfile_name[0]
        # 实例化
        if not openfile_name:
            if self.cursor_limit:
                self.limit_cursor()
            return
        self.set_face(FACE_SMILE)
        self._start_video_load(openfile_name)

    def _start_video_load(self, openfile_name):
        self._video_loading = True
        self._video_load_file_name = openfile_name
        self._show_video_load_progress(openfile_name)
        try:
            self._on_video_load_progress(0, 100, _translate(
                "VideoLoadProgress", "正在创建录像对象..."))
            video, video_set = self._create_video(openfile_name)

            if video_set:
                self._on_video_load_progress(
                    5, 100, _translate("VideoLoadProgress", "正在解析录像集..."))
                video_set.parse()
                self._on_video_load_progress(
                    35, 100, _translate("VideoLoadProgress", "录像集解析完成"))

                self._on_video_load_progress(
                    40, 100, _translate("VideoLoadProgress", "正在分析录像集..."))
                video_set.analyse()
                self._on_video_load_progress(
                    75, 100, _translate("VideoLoadProgress", "录像集分析完成"))

                self._on_video_load_progress(80, 100, _translate(
                    "VideoLoadProgress", "正在计算 pluck..."))
                video_set.analyse_for_features(["pluck"])
                video = video_set[0].evf_video
            else:
                self._on_video_load_progress(
                    5, 100, _translate("VideoLoadProgress", "正在解析录像..."))
                video.parse()
                self._on_video_load_progress(
                    35, 100, _translate("VideoLoadProgress", "录像解析完成"))

                self._on_video_load_progress(
                    40, 100, _translate("VideoLoadProgress", "正在分析录像..."))
                video.analyse()
                self._on_video_load_progress(
                    75, 100, _translate("VideoLoadProgress", "录像分析完成"))

                self._on_video_load_progress(80, 100, _translate(
                    "VideoLoadProgress", "正在计算 pluck..."))
                video.analyse_for_features(["pluck"])

            self._on_video_load_finished(video, video_set)
        except Exception as exc:
            logger.exception(f"Failed to load video file: {openfile_name}")
            self._on_video_load_failed(str(exc))
        finally:
            self._video_loading = False
            self._video_load_file_name = ""

    def _create_video(self, openfile_name):
        name = openfile_name.lower()
        if name.endswith(".avf"):
            return ms.AvfVideo(openfile_name), None
        if name.endswith(".rmv"):
            return ms.RmvVideo(openfile_name), None
        if name.endswith(".evf"):
            return ms.EvfVideo(openfile_name), None
        if name.endswith(".mvf"):
            return ms.MvfVideo(openfile_name), None
        if name.endswith(".evfs"):
            return None, ms.Evfs(openfile_name)
        raise ValueError(f"Unsupported video file type: {openfile_name}")

    def _show_video_load_progress(self, openfile_name):
        dialog = QProgressDialog(
            _translate("VideoLoadProgress", "正在打开录像..."),
            "",
            0,
            0,
            self.mainWindow,
        )
        dialog.setWindowTitle(_translate("VideoLoadProgress", "打开录像"))
        dialog.setCancelButton(None)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setLabelText(_translate("VideoLoadProgress",
                            "正在打开录像...") + f"\n{openfile_name}")
        dialog.show()
        self._video_load_progress_dialog = dialog

    def _on_video_load_progress(self, value, maximum, text):
        dialog = self._video_load_progress_dialog
        if not dialog:
            return
        if self._video_load_file_name:
            dialog.setLabelText(f"{text}\n{self._video_load_file_name}")
        else:
            dialog.setLabelText(text)
        if maximum <= 0:
            dialog.setRange(0, 0)
        else:
            dialog.setRange(0, maximum)
            dialog.setValue(min(value, maximum))
        QApplication.processEvents()

    def _on_video_load_finished(self, video, video_set):
        if video_set:
            self._on_video_load_progress(95, 100, _translate(
                "VideoLoadProgress", "正在创建录像目录..."))
            self.ui_video_control.add_new_video_set_tab(video_set)
            # self.tab_data.append(video_set)
        else:
            self._add_new_video_tab_with_progress(video)
            # self.tab_data.append(video)
        tab_count = self.ui_video_control.tabWidget.count()
        self.ui_video_control.tabWidget.setCurrentIndex(tab_count - 1)
        self._on_video_load_progress(
            100, 100, _translate("VideoLoadProgress", "录像加载完成"))
        if self._video_load_progress_dialog:
            self._video_load_progress_dialog.close()
            self._video_load_progress_dialog = None
        self.play_video(video)

    def _add_new_video_tab_with_progress(self, video):
        created_dialog = False
        previous_file_name = self._video_load_file_name
        if not self._video_load_progress_dialog:
            self._video_load_file_name = getattr(video, "file_name", "")
            self._show_video_load_progress(self._video_load_file_name)
            created_dialog = True

        try:
            self._on_video_load_progress(85, 100, _translate(
                "VideoLoadProgress", "正在分析本地事件..."))
            self.ui_video_control.add_new_video_tab(
                video,
                progress_callback=self._on_local_event_analysis_progress,
            )
            self._on_video_load_progress(
                97, 100, _translate("VideoLoadProgress", "事件列表创建完成"))
        finally:
            if created_dialog and self._video_load_progress_dialog:
                self._video_load_progress_dialog.close()
                self._video_load_progress_dialog = None
                self._video_load_file_name = previous_file_name

    def _on_local_event_analysis_progress(self, current, total):
        if total <= 0:
            value = 97
            text = _translate("VideoLoadProgress", "正在分析本地事件...")
        else:
            current = min(current, total)
            value = 85 + int((97 - 85) * current / total)
            text = _translate(
                "VideoLoadProgress",
                "正在分析本地事件... ({current}/{total})",
            )
            text = text.replace("{current}", str(
                current)).replace("{total}", str(total))
        self._on_video_load_progress(value, 100, text)

    def _on_video_load_failed(self, message):
        if self._video_load_progress_dialog:
            self._video_load_progress_dialog.close()
            self._video_load_progress_dialog = None
        QMessageBox.warning(
            self.mainWindow,
            _translate("VideoLoadProgress", "打开录像失败"),
            _translate("VideoLoadProgress", "录像解析失败：") + message,
        )

    # 播放新录像，调整局面尺寸等
    # 控制台中，不添加新标签、连接信号。假如关闭就展示
    # 播放AvfVideo、RmvVideo、EvfVideo、MvfVideo或BaseVideo

    def play_video(self, video, new_tab=False):
        if self.game_state != DISPLAY:
            self.game_state = DISPLAY
        self.video_playing = False
        self.timer_video.stop()

        # 添加新标签并切换过去
        if new_tab:
            tab_count = self.ui_video_control.tabWidget.count()
            for index in range(tab_count):
                tab_widget = self.ui_video_control.tabWidget.widget(index)
                if video.file_name == tab_widget.file_name:
                    self.ui_video_control.tabWidget.setCurrentIndex(index)
                    break
            else:
                self._add_new_video_tab_with_progress(video)
                self.ui_video_control.tabWidget.setCurrentIndex(tab_count)

        # 检查evf的checksum，其余录像没有鉴定能力
        # if isinstance(video, ms.EvfVideo):
        #     self.score_board_manager.with_namespace({
        #         "checksum_ok": self.checksum_guard.
        #         valid_checksum(video.raw_data[:-(len(video.checksum) + 2)], video.checksum),
        #     })
        # else:
        #     self.score_board_manager.with_namespace({
        #         "checksum_ok": False,
        #     })
        self.score_board_manager.with_namespace({
            "is_official": video.is_official,
            "is_fair": video.is_fair,
            "mode": video.mode,
            "row": video.row,
            "column": video.column,
            "minenum": video.mine_num,
        })
        # 调整窗口
        if (video.row, video.column) != (self.row, self.column):
            self.set_board_params(video.row, video.column, video.mine_num)
            self.label.paintProbability = False
            self.label.set_rcp(self.row, self.column, self.pixSize)
            # self.label.reloadCellPic(self.pixSize)
            self.label.setMinimumSize(QtCore.QSize(
                self.pixSize*self.column + 8, self.pixSize*self.row + 8))
            self.label.setMaximumSize(QtCore.QSize(
                self.pixSize*self.column + 8, self.pixSize*self.row + 8))
            self.label_2.reloadFace(self.pixSize)
            self.minimumWindow()

        self.ui_video_control.QWidget.show()

        t_end = video.video_end_time
        t_start = video.video_start_time

        # 重新设置进度条的最大值、最小值，要临时屏蔽信号发送
        self.ui_video_control.horizontalSlider_time.blockSignals(True)
        self.ui_video_control.horizontalSlider_time.setValue(0)
        self.ui_video_control.horizontalSlider_time.setMaximum(
            int(t_end * 1000))
        self.ui_video_control.horizontalSlider_time.setMinimum(
            int(t_start * 1000))
        self.ui_video_control.horizontalSlider_time.blockSignals(False)

        # self.video_time = t_start  # 录像当前时间
        # self.video_stop_time = t_end  # 录像停止时间
        self.label.paint_cursor = True
        # self.video_playing = True  # 录像正在播放
        # 禁用双击修改指标名称公式
        self.score_board_manager.editing_row = -2

        video.video_playing_pix_size = self.label.pixSize
        self.label.ms_board = video
        self.label.clear_highlight_cell()
        # 改成录像的标识
        # print(self.label.ms_board.player_identifier)
        self.label_info.setText(self.label.ms_board.player_identifier)
        # 改成录像的国旗
        self.set_country_flag(self.label.ms_board.country)

        # 更新左上角雷数显示
        self.minenum = video.mine_num
        self.mineUnFlagedNum = self.minenum
        self.showMineNum(self.mineUnFlagedNum)

        self.cache_mouse_trace(video)
        if self.show_path_trace and self.original_pix_size:
            scale = self.label.pixSize / self.original_pix_size
            self.label.path_trace_enabled = True
            self.label.path_trace_points = [
                (int(x * scale), int(y * scale)) for (x, y) in self.mouse_trace_points]
            self.label.path_trace_left_clicks = self.path_trace_left_clicks
            self.label.path_trace_right_clicks = self.path_trace_right_clicks
            self.label.path_trace_double_clicks = self.path_trace_double_clicks

        # self.timer_video.start(10)
        self.video_replay()

    # 根据标签名和索引播放录像

    def play_video_tab_name_id(self, tab_name, idv, new_tab=False):
        tab_count = self.ui_video_control.tabWidget.count()
        for index in range(tab_count):
            tab_widget = self.ui_video_control.tabWidget.widget(index)
            if tab_widget.tab_name == tab_name:
                self.play_video(tab_widget.video_set[idv].evf_video, new_tab)
                return

    # 切换标签时，播放标签中的录像

    def on_tab_clicked(self, idt):
        if isinstance(self.ui_video_control.tabWidget.widget(idt), videoControl.VideoTabWidget):
            self.play_video(self.ui_video_control.tabWidget.widget(idt).video)
        elif isinstance(self.ui_video_control.tabWidget.widget(idt), videoControl.VideoSetTabWidget):
            ...

    def cache_mouse_trace(self, video):
        self.mouse_trace_points.clear()
        self.path_trace_left_clicks.clear()
        self.path_trace_right_clicks.clear()
        self.path_trace_double_clicks.clear()
        self.original_pix_size = video.pix_size
        last_pos = (0, 0)
        for i, rec in enumerate(video.events):
            if rec.event.is_mouse:
                m = rec.event.unwrap_mouse()
                last_pos = (m.x, m.y)
                if m.mouse == 'lc':
                    self.path_trace_left_clicks.add(i)
                elif m.mouse == 'rc':
                    self.path_trace_right_clicks.add(i)
                elif m.mouse == 'cc':
                    self.path_trace_double_clicks.add(i)
            self.mouse_trace_points.append(last_pos)

    def toggle_path_trace(self, checked):
        self.show_path_trace = checked
        self.label.path_trace_enabled = checked
        if checked and self.mouse_trace_points and self.original_pix_size:
            scale = self.label.pixSize / self.original_pix_size
            self.label.path_trace_points = [
                (int(x * scale), int(y * scale)) for (x, y) in self.mouse_trace_points]
            self.label.path_trace_left_clicks = self.path_trace_left_clicks
            self.label.path_trace_right_clicks = self.path_trace_right_clicks
            self.label.path_trace_double_clicks = self.path_trace_double_clicks
            self.label.current_trace_event_id = self.label.ms_board.current_event_id
        else:
            self.label.path_trace_points = []
        self.label.update()

    def toggle_op(self, checked):
        self.label.show_opening = checked
        self.label.update()

    def highlight_video_cells(self, cells):
        self.label.highlight_cells(cells)

    def clear_video_cell_highlight(self):
        self.label.clear_highlight_cell()

    def video_playing_step(self):
        # 播放录像时定时器的回调
        self.label.ms_board.current_time = self.video_time
        if self.show_path_trace and self.mouse_trace_points:
            self.label.current_trace_event_id = self.label.ms_board.current_event_id
        if self.video_time >= self.video_stop_time:
            self.timer_video.stop()
            self.video_playing = False
        self.label.update()

        # 回放时修改小黄脸，使用了一个变量做工具箱的补丁
        match self.label.ms_board.mouse_state:
            case MouseState.UpUp.value | MouseState.DownUpAfterChording.value:
                self.set_face(FACE_SMILE)
            case MouseState.UpDown.value | MouseState.DownUp.value | MouseState.Chording.value | MouseState.ChordingNotFlag.value:
                self.set_face(FACE_CLICK)
            case MouseState.UpDownNotFlag.value:
                if self.last_mouse_state_video_playing_step in {MouseState.Chording.value, MouseState.ChordingNotFlag.value}:
                    self.set_face(FACE_SMILE)
                else:
                    self.set_face(FACE_CLICK)
        self.last_mouse_state_video_playing_step = self.label.ms_board.mouse_state

        self.score_board_manager.show(self.label.ms_board, index_type=3)
        self.mineUnFlagedNum = self.minenum - self.label.ms_board.flag
        self.showMineNum(self.mineUnFlagedNum)
        self.video_time += self.video_time_step
        self.showTime(int(self.video_time))
        self.ui_video_control.horizontalSlider_time.blockSignals(True)
        self.ui_video_control.horizontalSlider_time.setValue(
            int(self.video_time * 1000))
        self.ui_video_control.horizontalSlider_time.blockSignals(False)
        self.ui_video_control.doubleSpinBox_time.blockSignals(True)
        self.ui_video_control.doubleSpinBox_time.setValue(
            self.label.ms_board.time)
        self.ui_video_control.doubleSpinBox_time.blockSignals(False)

    def video_play(self):
        # 点播放、暂停键的回调
        if self.video_playing:
            self.video_playing = False
            self.timer_video.stop()
        else:
            self.video_playing = True
            self.timer_video.start(10)
            self.video_stop_time = self.label.ms_board.video_end_time

    def video_replay(self):
        self.video_playing = True
        self.video_time = self.label.ms_board.video_start_time
        self.timer_video.start(10)
        self.video_stop_time = self.label.ms_board.video_end_time

    def video_set_speed(self, speed):
        self.video_time_step = speed * 0.01

    def video_set_time(self, t):
        # 把录像定位到某一个时刻。是拖动进度条的回调
        self.video_time = t / 1000
        self.label.ms_board.current_time = self.video_time
        if self.show_path_trace and self.mouse_trace_points:
            self.label.current_trace_event_id = self.label.ms_board.current_event_id
        self.label.update()
        self.score_board_manager.show(self.label.ms_board, index_type=3)
        self.mineUnFlagedNum = self.minenum - self.label.ms_board.flag
        self.showMineNum(self.mineUnFlagedNum)

    def video_set_a_time(self, t):
        # 把录像定位到某一段时间，默认前后一秒，自动播放。是点录像事件的回调
        self.video_time = (t - 1000) / 1000
        self.video_stop_time = (t + 1000) / 1000  # 大了也没关系，ms_toollib自动处理
        self.timer_video.start()
        self.video_playing = True
