# 左侧计时器
import minesweeper_master as mm
from ui.ui_score_board import Ui_Form
from ui.uiComponents import RoundQWidget
from safe_eval import safe_eval
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QShortcut, QHeaderView

class ui_Form(Ui_Form):
    # barSetMineNum = QtCore.pyqtSignal(int)
    # barSetMineNumCalPoss = QtCore.pyqtSignal(int)
    # doubleClick = QtCore.pyqtSignal (int, int)
    # leftClick = QtCore.pyqtSignal (int, int)
    def __init__(self, r_path, pix_size, parent):
        self.pix_size = pix_size
        self.QWidget = RoundQWidget(parent)
        self.setupUi(self.QWidget)
        
        self.tableWidget.setColumnWidth(0, 80)
        self.tableWidget.setColumnWidth(1, 150)
        self.tableWidget.verticalHeader().setDefaultSectionSize(25)
        self.tableWidget.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        
        self.QWidget.setWindowIcon (QtGui.QIcon (str(r_path.with_name('media').joinpath('cat.ico'))))
        
        # self.setParameter ()
    
    def show(self, index_value_list: list[str]):
        # 更新数值,指标数量不变
        for idx in range(self.tableWidget.rowCount()):
            self.tableWidget.setItem(idx, 1, QTableWidgetItem(index_value_list[idx]))
        
        
    def reshow(self, index_name_list: list[str], index_value_list: list[str]):
        # 更新数值、指标。指标数量可能变
        table_height = len(index_name_list)*24
        self.tableWidget.setRowCount(len(index_name_list))
        # self.tableWidget.setMinimumWidth(232)
        # self.tableWidget.setMaximumWidth(232)
        self.tableWidget.setMaximumHeight(table_height + len(index_name_list) + 2)
        self.tableWidget.setMinimumHeight(table_height + len(index_name_list) + 2)
        
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
    # video_dynamic = ["etime", "stnb", "rqp", "qg", "ioe", "thrp", "corr", "ce",
    #                  "ce_s", "bbbv_solved", "bbbv_s", "op_solved", "isl_solved"]
    game_index = ["race_designator", "mode", "rtime", "left", "right", "double",
                  "cl", "left_s", "right_s", "double_s", "path", "flag", "flag_s"]
    video_index = ["bbbv", "op", "isl", "cell0", "cell1", "cell2", "cell3",
                    "cell4", "cell5", "cell6", "cell7", "cell8", "fps", "etime",
                    "stnb", "rqp", "qg", "ioe", "thrp", "corr", "ce",
                     "ce_s", "bbbv_solved", "bbbv_s", "op_solved", "isl_solved", "pluck"]
    
    # is_visible = False
    # 5、错误的表达式，一旦算出报错，永远不再算，显示error
    def __init__(self, r_path, score_board_setting, game_setting, pix_size, parent):
        # 从文件中读取指标并设置
        # self.ms_board = None
        self.pix_size = pix_size
        self.namespace = {}
        
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
        self.ui = ui_Form(r_path, pix_size, parent)
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
        # 埋雷结束后调用，固化参数
        # self.pix_size = pix_size
        # self.board = board
        if "mode" in namespace:
            self._game_mode_code: int = namespace["mode"]
            namespace["mode"] = mm.trans_game_mode(namespace["mode"])
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
                except:
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
        
    
    def update_namespace(self, ms_board, index_type):
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
                })
        if index_type >= 3:
            self.namespace.update({
                "pluck": ms_board.pluck,
                })
        
        
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
            if self.ms_board.game_board_state == 1\
                or self.ms_board.game_board_state == 2\
                    or self.ms_board.game_board_state == 5:
                index_type = 1
            else:
                # 3、4为win和loss
                index_type = 2
            
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
        # 编辑完成后的回调，e == None表示是回车键结束的
        if e == None or (self.editing_row >= 0 and self.editing_column >= 0 and (self.editing_row != e.row() or\
                                                    self.editing_column != e.column())):
            # 编辑完成后修改指标值
            # self.ui.tableWidget.setDisabled(True)
            # self.ui.tableWidget.setDisabled(False)
            new_formula = self.ui.tableWidget.item(self.editing_row, self.editing_column).text()
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
        self.game_setting.sync()





