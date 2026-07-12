# 左侧计时器
import utils
from ui.ui_score_board import Ui_Form
from ui.uiComponents import RoundQWidget
from utils.safe_eval import safe_eval
from config.constants import BOARD_READY, BOARD_PLAYING, BOARD_WIN, BOARD_LOSS, MIN_PIX_SIZE, MAX_PIX_SIZE
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QTableWidgetItem, QShortcut, QAbstractItemDelegate, QApplication
from PyQt5 import QtCore, QtGui
from utils.path_utils import resource_path


class ScoreBoardWidget(RoundQWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on_ctrl_wheel = None

    def set_ctrl_wheel_handler(self, handler):
        self._on_ctrl_wheel = handler

    def wheelEvent(self, event):
        if self._on_ctrl_wheel and QApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
            angle = event.angleDelta().y()
            if angle > 0:
                self._on_ctrl_wheel(1)
            elif angle < 0:
                self._on_ctrl_wheel(-1)
            event.accept()
            return
        super().wheelEvent(event)


class ui_Form(Ui_Form):
    # barSetMineNum = QtCore.pyqtSignal(int)
    # barSetMineNumCalPoss = QtCore.pyqtSignal(int)
    # doubleClick = QtCore.pyqtSignal (int, int)
    # leftClick = QtCore.pyqtSignal (int, int)
    # 设计基准：主界面 pixSize = 16 时，计时器各尺寸（80,150,25...）为基准值
    BASE_PIX = 26
    
    def __init__(self, pix_size, parent):
        self.QWidget = ScoreBoardWidget(parent)
        self.setupUi(self.QWidget)
        
        self.QWidget.setWindowIcon (QtGui.QIcon (str(resource_path('media') / 'cat.ico')))
        self.apply_scale(pix_size)
    
    def apply_scale(self, pix_size):
        self.pix_size = pix_size
        # 最小缩放：最小号基准字号(12) 不小于 10px
        scale = max(pix_size / self.BASE_PIX, 10 / 12)
        
        col0 = max(1, int(80 * scale))
        col1 = max(1, int(150 * scale))
        fs_label = max(1, int(12 * scale))
        fs_table = max(1, int(15 * scale))
        btn_h = max(1, int(15 * scale))
        label_h = max(1, int(27 * scale))
        
        self.tableWidget.setColumnWidth(0, col0)
        self.tableWidget.setColumnWidth(1, col1)
        font = self.tableWidget.font()
        font.setPointSize(fs_table)
        fm = QtGui.QFontMetrics(font)
        row_h = fm.height() + 2
        vh = self.tableWidget.verticalHeader()
        vh.setDefaultSectionSize(row_h)
        vh.show()
        for r in range(self.tableWidget.rowCount()):
            vh.resizeSection(r, row_h)
        vh.hide()
        
        font = self.label_counter.font()
        font.setPointSize(fs_label)
        self.label_counter.setFont(font)
        self.label_counter.setMinimumHeight(label_h)
        self.label_counter.setMaximumHeight(label_h)
        
        self.tableWidget.setStyleSheet(f"font-size: {fs_table}px;")
        
        self.pushButton_add.setMinimumHeight(btn_h)
        self.pushButton_add.setMaximumHeight(btn_h)
        
        self._fix_widget_size()
    
    def _fix_widget_size(self):
        self.QWidget.setMinimumSize(0, 0)
        self.QWidget.setMaximumSize(99999, 99999)
        self.QWidget.layout().setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        m = self.QWidget.layout().contentsMargins()
        sp = self.QWidget.layout().spacing() or 0
        fw = self.tableWidget.frameWidth()
        n_rows = self.tableWidget.rowCount()
        col0 = self.tableWidget.columnWidth(0)
        col1 = self.tableWidget.columnWidth(1)
        row_h = self.tableWidget.verticalHeader().defaultSectionSize()
        table_w = col0 + col1 + 2 * fw
        table_h = n_rows * row_h + 2 * fw
        self.tableWidget.setFixedSize(table_w, table_h)
        total_w = m.left() + table_w + m.right()
        total_h = (m.top()
                   + self.label_counter.minimumHeight() + sp
                   + table_h + sp
                   + self.pushButton_add.minimumHeight()
                   + m.bottom())
        self.QWidget.setFixedSize(total_w, total_h)
    
    def show(self, index_value_list: list[str]):
        # 更新数值,指标数量不变
        for idx in range(self.tableWidget.rowCount()):
            self.tableWidget.setItem(idx, 1, QTableWidgetItem(index_value_list[idx]))
        
        
    def reshow(self, index_name_list: list[str], index_value_list: list[str]):
        # 更新数值、指标。指标数量可能变
        self.tableWidget.setRowCount(len(index_name_list))
        self._fix_widget_size()
        for idx, i in enumerate(index_name_list):
            self.tableWidget.setItem(idx, 0, QTableWidgetItem(i))
        self.show(index_value_list)
        
        
    def setSignal(self):
        ...

    def setParameter(self):
        ...

    def processParameter(self):
        ...
        
        
        
class gameScoreBoardManager():
    # 管理精确定时器
    # 5种表达式
    # game_static = ["race_designator", "mode"]
    # game_dynamic = ["rtime", "left", "right", "double", "cl", "left_s", 
    #                 "right_s", "double_s", "path", "flag", "flag_s"]
    # video_static = ["bbbv", "op", "isl", "cell0", "cell1", "cell2", "cell3",
    #                 "cell4", "cell5", "cell6", "cell7", "cell8", "fps"]
    # video_dynamic = ["etime", "stnb", "rqp", "ioe", "thrp", "corr", "ce",
    #                  "ce_s", "bbbv_solved", "bbbv_s", "op_solved", "isl_solved"]
    game_index = ["race_designator", "mode", "rtime", "left", "right", "double",
                  "cl", "left_s", "right_s", "double_s", "path", "flag", "flag_s"]
    video_index = ["bbbv", "op", "isl", "cell0", "cell1", "cell2", "cell3",
                    "cell4", "cell5", "cell6", "cell7", "cell8", "fps", "etime",
                    "stnb", "rqp", "qg", "ioe", "thrp", "corr", "ce",
                     "ce_s", "bbbv_solved", "bbbv_s", "op_solved", "isl_solved", 
                     "pluck", "zini", "hzini"]
    
    # is_visible = False
    # 5、错误的表达式，一旦算出报错，永远不再算，显示error
    def __init__(self, score_board_setting, game_setting, pix_size, parent):
        # 从文件中读取指标并设置
        # self.ms_board = None
        self.namespace = {}
        self.scoreboard_pixsize = game_setting.value("DEFAULT/scoreboard_pixsize", pix_size, int)
        self.scoreboard_pixsize = max(MIN_PIX_SIZE, min(MAX_PIX_SIZE, self.scoreboard_pixsize))
        
        # 时间与定时器
        self.total_time = 0.0 # total_time = delta_time + rtime
        self.delta_time = 0.0
        
        self.initialized = False
        self.game_setting = game_setting
        self.score_board_setting = score_board_setting
        default_config = [
                ("游戏模式", "mode"),
                ("RTime", "f'{time:.3f}'"),
                ("Est RTime", "f'{etime:.3f}'"),
                ("3BV", "f'{bbbv_solved}/{bbbv}'"),
                ("3BV/s", "f'{bbbv_s:.3f}'"),
                ("ZiNi", "f'{zini}@{zini/max(etime,1e-6):.3f}'"),
                ("Ops", "op"),
                ("Isls", "isl"),
                ("Left", "f'{left}@{left_s:.3f}'"),
                ("Right", "f'{right}@{right_s:.3f}'"),
                ("Double", "f'{double}@{double_s:.3f}'"),
                ("STNB", "f'{stnb:.3f}'"),
                ("IOE", "f'{ioe:.3f}'"),
                ("Thrp", "f'{thrp:.3f}'"),
                ("Corr", "f'{corr:.3f}'"),
                ("Path", "f'{path:.1f}'"),
                ("Pluck", "f'{pluck:.3f}'"),
                ]
        self.score_board_items = self.score_board_setting.get_or_set_section("DEFAULT", default_config)

        self.score_board_setting.sync()

        self.update_score_board_items_type()
        self.index_num = len(self.score_board_items_type)
        self.ui = ui_Form(self.scoreboard_pixsize, parent)
        self.ui.QWidget.set_ctrl_wheel_handler(self.adjust_scale)
        self.ui.tableWidget.doubleClicked.connect(self.__table_change)
        self.ui.tableWidget.clicked.connect(self.__table_ok)
        # self.ui.tableWidget.cellChanged.connect(self.__cell_changed)
        self.ui.pushButton_add.clicked.connect(self.__add_blank_line)
        self.ui.QWidget.closeEvent_.connect(self.close)
        QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Return), self.ui.QWidget).\
            activated.connect(self.__table_ok)
        self.ui.QWidget.move(game_setting.value("DEFAULT/scoreboardtop", 100, int),
                             game_setting.value("DEFAULT/scoreboardleft", 200, int))
        self.editing_row = -1 # -1不在编辑状态，-2不能编辑（正在游戏）
        self.editing_column = -1
        

    def update_score_board_items_type(self):
        self.score_board_items_type = []
        # 整理出计时器上各指标的类型，1表示游戏时更新，2表示录像、游戏时更新
        for i in self.score_board_items:
            expression_i = i[1]
            for j in self.video_index:
                if j in expression_i:
                    self.score_board_items_type.append(2)
                    break
            else:
                self.score_board_items_type.append(1)

    def with_namespace(self, namespace: dict):
        '''
        给计数器添加变量和值。非覆盖，而是可以叠加。
        '''
        if "mode" in namespace:
            self._game_mode_code: int = namespace["mode"]
            namespace["mode"] = utils.trans_game_mode(namespace["mode"])
        self.namespace.update(namespace)
        # race_designator, mode .etc
        # self.ms_board = ms.BaseVideo(board, pix_size)
        # self.initialized = True
        ...
        
    def reset(self):
        # 清零到默认
        ...
        
    def cal_index_value(self, ms_board, index_type):
        # 原地修改指标数值
        self.update_namespace(ms_board, index_type)
        index_value = []
        # for (idx, (_, expression), _type) in enumerate(zip(self.score_board_items, self.score_board_items_type)):
        for idx in range(len(self.score_board_items)):
            _type = self.score_board_items_type[idx]
            expression = self.score_board_items[idx][1]
            if _type <= index_type:
                # print(expression)
                try:
                    expression_result = safe_eval(expression, self.namespace)
                except Exception:
                    self.score_board_items_type[idx] = 5
                    index_value.append('error')
                else:
                    index_value.append(str(expression_result))
                ...
            elif _type == 5:
                index_value.append('error')
            else:
                index_value.append('--')
        return index_value
        
    # def set_current_time(self, current_time):
    #     # 
    #     self.current_time = current_time
    #     self.ms_board.set_current_time(current_time)
    
    def visible(self):
        # 仅控制可见性
        self.ui.QWidget.show()
        
    def invisible(self):
        # 仅控制可见性
        self.ui.QWidget.hide()

    def adjust_scale(self, delta: int):
        new_size = self.scoreboard_pixsize + delta
        new_size = max(MIN_PIX_SIZE, min(MAX_PIX_SIZE, new_size))
        if new_size == self.scoreboard_pixsize:
            return
        self.scoreboard_pixsize = new_size
        self.ui.apply_scale(self.scoreboard_pixsize)
        if hasattr(self, 'ms_board') and self.ms_board is not None:
            self.reshow(self.ms_board)

    def update_namespace(self, ms_board, index_type):
        try:
            # 全部更新，以后优化方向就是部分更新, index_type现在没用
            self.namespace.update({
                "time": ms_board.time,
                "left": ms_board.left,
                "right": ms_board.right,
                "double": ms_board.double,
                "cl": ms_board.cl,
                "left_s": ms_board.left_s,
                "right_s": ms_board.right_s,
                "double_s": ms_board.double_s,
                "cl_s": ms_board.cl_s,
                "path": ms_board.path,
                "flag": ms_board.flag,
                "flag_s": ms_board.flag_s,
                })
            if index_type >= 2:
                self.namespace.update({
                    "rtime": ms_board.rtime,
                    "etime": ms_board.etime,
                    "bbbv": ms_board.bbbv,
                    "bbbv_s": ms_board.bbbv_s,
                    "zini": ms_board.zini,
                    "hzini": ms_board.hzini,
                    "bbbv_solved": ms_board.bbbv_solved,
                    "op": ms_board.op,
                    "isl": ms_board.isl,
                    "stnb": ms_board.stnb,
                    "ioe": ms_board.ioe,
                    "thrp": ms_board.thrp,
                    "corr": ms_board.corr,
                    "ce": ms_board.ce,
                    "ce_s": ms_board.ce_s,
                    "rce": ms_board.rce,
                    "lce": ms_board.lce,
                    "dce": ms_board.dce,
                    "rqp": ms_board.rqp,
                    "qg": ms_board.qg,
                    "pluck": ms_board.pluck,
                    })
        except Exception:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "错误", traceback.format_exc())
        # if index_type >= 3:
        #     self.namespace.update({
        #         "pluck": ms_board.pluck,
        #         })
        
        
    def show(self, ms_board, index_type):
        # 刷新，指标数量不变。游戏过程中用。index_type是2
        # race_designator", "mode"]
        # game_dynamic = ["rtime", "left", "right", "double", "cl", "left_s", 
        #                 "right_s", "double_s", "path", "flag", "flag_s"]
        # video_static = ["bbbv", "op", "isl", "cell0", "cell1", "cell2", "cell3",
        #                 "cell4", "cell5", "cell6", "cell7", "cell8", "fps"]
        # video_dynamic = ["etime", "stnb", "rqp", "qg", "ioe", "thrp", "corr", "ce",
        #                  "ce_s", "bbbv_solved", "bbbv_s", "op_solved", "isl_solved
        self.ms_board = ms_board
        index_value_list = self.cal_index_value(ms_board, index_type)
        self.ui.show(index_value_list)
        # if self.ui.QWidget.isVisible():
        #     self.visible()
        
    def reshow(self, ms_board, index_type = 0):
        if not index_type:
            if self.ms_board.game_board_state == BOARD_READY\
                or self.ms_board.game_board_state == BOARD_PLAYING\
                    or self.ms_board.game_board_state == 5:
                index_type = 1
            elif self.ms_board.game_board_state == BOARD_WIN\
                or self.ms_board.game_board_state == BOARD_LOSS:
                index_type = 2
            elif self.ms_board.game_board_state == 6:
                index_type = 3
            
        # 指标数量有变。增删指标用。游戏开始前。index_type是2
        self.ms_board = ms_board
        index_value_list = self.cal_index_value(ms_board, index_type)
        self.ui.reshow([i[0] for i in self.score_board_items], index_value_list)
        # self.visible()
        ...
        
    def time_step(self):
        # 游戏过程中时间步进
        self.total_time += 0.001
        
        
        self.show()
    
    # 重写窗口的翻译方法。主要是模式的翻译问题
    def retranslateUi(self, Form):
        self.ui.retranslateUi(Form)
        if hasattr(self, "ms_board"):
            self.with_namespace({
                "mode": self._game_mode_code,
                })
            self.show(self.ms_board, index_type = 1)
            
    def __table_change(self, e):
        # 编辑开始时，把数值换成公式
        if e.column() == 1 and self.editing_row == -1:
            r = e.row()
            self.editing_row = r
            self.editing_column = 1
            self.ui.tableWidget.editItem(self.ui.tableWidget.item(r, 1))
            self.ui.tableWidget.setItem(r, 1, 
                                        QTableWidgetItem(self.score_board_items[r][1]))
        elif e.column() == 0 and self.editing_row == -1:
            r = e.row()
            self.editing_row = r
            self.editing_column = 0
            self.ui.tableWidget.editItem(self.ui.tableWidget.item(r, 0))
            
    def __table_ok(self, e = None):
        # 编辑完成后的回调，e is None表示是回车键结束的
        if e is None or (self.editing_row >= 0 and self.editing_column >= 0 and (self.editing_row != e.row() or\
                                                    self.editing_column != e.column())):
            # 编辑完成后修改指标值
            editor = self.ui.tableWidget.focusWidget()
            if editor is not None and hasattr(editor, 'text'):
                new_formula = editor.text()
                self.ui.tableWidget.closeEditor(editor, QAbstractItemDelegate.SubmitModelCache)
            else:
                item = self.ui.tableWidget.item(self.editing_row, self.editing_column)
                new_formula = item.text() if item is not None else ''

            if self.editing_column == 0:
                if not new_formula:
                    # 删除键名后并完成编辑后，删除此指标
                    self.score_board_items.pop(self.editing_row)
                    self.score_board_items_type.pop(self.editing_row)
                else:
                    # 正常修改键名
                    self.score_board_items[self.editing_row] = (new_formula, self.score_board_items[self.editing_row][1])
            else:
                # 正常修改公式
                self.score_board_items[self.editing_row] = (self.score_board_items[self.editing_row][0], new_formula)
                self.update_score_board_items_type()
            self.reshow(self.ms_board)
            self.editing_row = -1
            self.editing_column = -1
        
    # def __cell_changed(self, x, y):
    #     # 把计数器里的公式改成新设置的公式
    #     if y == 0:
    #         t = self.ui.tableWidget.item(x, y).text()
    #         if self.score_board_items[x][0] != t:
    #             self.score_board_items[x][0] = self.ui.tableWidget.item(x, 0).text()
                
    def __add_blank_line(self):
        # 添加一个空开的行，并刷新显示
        self.score_board_items.append(["", ""])
        self.score_board_items_type.append(1)
        self.reshow(self.ms_board)
                
    def close(self):
        self.score_board_setting.set_section("DEFAULT", self.score_board_items)
        self.score_board_setting.sync()
        self.game_setting.set_value("DEFAULT/scoreboardtop", self.ui.QWidget.x())
        self.game_setting.set_value("DEFAULT/scoreboardleft", self.ui.QWidget.y())
        self.game_setting.set_value("DEFAULT/scoreboard_pixsize", self.scoreboard_pixsize)
        self.game_setting.sync()





