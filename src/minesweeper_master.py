# author : Wang Jianing(18201)
from random import shuffle, choice
# from random import randint, seed, sample
from typing import List, Tuple, Union
# import time
from safe_eval import safe_eval
import configparser
from PyQt5 import QtCore

import ms_toollib as ms
import math

# OutputEnable = 0
# seedNum = 60223
EnuLimit = 50
assert EnuLimit >= 50

def choose_3BV(board_constraint, attempt_times_limit, params):
    def choose_3BV_laymine(laymine):
        if not board_constraint:
            b = laymine(params)
            if isinstance(b, tuple):
                b, success_flag = b
            else:
                success_flag = True
            return (b, success_flag)
        t = 0
        while t < attempt_times_limit:
            b = laymine(params)
            if isinstance(b, tuple):
                b, success_flag = b
            else:
                success_flag = True
                
            constraints = {
                "sin": math.sin,
                "tan": math.tan,
                "cos": math.cos,
                "log": math.log,
                } # 也许还要加row, column, mine_num, level, mode
            wrapper_b = ms.Board(b)
            if "bbbv" in board_constraint:
                constraints.update({"bbbv": wrapper_b.bbbv})
            if "op" in board_constraint:
                constraints.update({"op": wrapper_b.op})
            if "isl" in board_constraint:
                constraints.update({"isl": wrapper_b.isl})
            if "cell0" in board_constraint:
                constraints.update({"cell0": wrapper_b.cell0})
            if "cell1" in board_constraint:
                constraints.update({"cell1": wrapper_b.cell1})
            if "cell2" in board_constraint:
                constraints.update({"cell2": wrapper_b.cell2})
            if "cell3" in board_constraint:
                constraints.update({"cell3": wrapper_b.cell3})
            if "cell4" in board_constraint:
                constraints.update({"cell4": wrapper_b.cell4})
            if "cell5" in board_constraint:
                constraints.update({"cell5": wrapper_b.cell5})
            if "cell6" in board_constraint:
                constraints.update({"cell6": wrapper_b.cell6})
            if "cell7" in board_constraint:
                constraints.update({"cell7": wrapper_b.cell7})
            if "cell8" in board_constraint:
                constraints.update({"cell8": wrapper_b.cell8})
            try:
                expression_flag = safe_eval(board_constraint, globals=constraints)
            except:
                return (b, success_flag)
            if expression_flag:
                return (b, success_flag)
            t += 1
        return (b, success_flag)
    return choose_3BV_laymine
    
# 此处的board，看似是函数，实际由于装饰器的缘故是一个局面的列表
def laymine_solvable_thread(board_constraint, attempt_times_limit, params):
    @choose_3BV(board_constraint, attempt_times_limit, params)
    def board(pp):
        return ms.laymine_solvable_thread(*pp)
    return board

def laymine(board_constraint, attempt_times_limit, params):
    @choose_3BV(board_constraint, attempt_times_limit, params)
    def board(pp):
        return ms.laymine(*pp)
    return board

def laymine_op(board_constraint, attempt_times_limit, params):
    @choose_3BV(board_constraint, attempt_times_limit, params)
    def board(pp):
        return ms.laymine_op(*pp)
    return board

def laymine_solvable_adjust(board_constraint, attempt_times_limit, params):
    # 暂时用不了
    @choose_3BV(board_constraint, attempt_times_limit, params)
    def board(pp):
        return ms.laymine_solvable_adjust(*pp)
    return board

def get_mine_times_limit(row: int, column: int):
    '''
    计算局面的雷数上限和尝试次数上限。当雷数小于等于雷数上限时，才可以用筛选法(考虑游戏体验)。
    
    Parameters
    ----------
    row : int
        >= 1, 行数/高。
    column : int
        >= 1, 列数/宽。

    Returns
    -------
    int
        雷数上限。
    int
        尝试次数上限。

    '''
    area = row * column
    if area <= 64:
        return (int(area * 0.375) + 1, 100000)
    elif area <= 256:
        return (int(area * (-area * 0.00048828125 + 0.40625)) + 2, 100000)
    elif area <= 480:
        return (int(area * (-area * 0.00013950892857 + 0.3169642857136)) + 2, 100000)
    elif area <= 864:
        return (int(area * (-area * 4.8225308641979135e-05 + 0.27314814814814997)) + 2, 50000)
    elif area <= 6400:
        return (int(area * (-area * 5.686683793619943e-06 + 0.23639477627916763)) + 2, 20000)
    else:
        return (int(area * 0.2) + 2, 10000)

def laymine_solvable_auto(row, column, mine_num, x, y):
    # 自动选择方式的无猜埋雷
    (max_mine_num, max_times) = get_mine_times_limit(row, column)
    if mine_num <= max_mine_num:
        ans = ms.laymine_solvable_thread(row, column, mine_num, x, y, max_times)
        if ans[1]:
            return ans
    return ms.laymine_solvable_adjust(row, column, mine_num, x, y)
    
    
def laymine_solvable(board_constraint, attempt_times_limit, params):
    @choose_3BV(board_constraint, attempt_times_limit, params)
    def board(pp):
        return laymine_solvable_auto(*pp)
    return board


# poses是将要打开的多个位置，尝试调整board，使得game_board不变，而这些位置不再是雷。
# poses中至少有一个踩雷了。poses必须由同一个操作引起，例如单次双击
# 返回修改后的board和成功标识位
def enumerateChangeBoard(board: ms.EvfVideo | List[List[int]], 
                         game_board: List[List[int]],
                         poses: List[Tuple[int, int]]) -> Tuple[List[List[int]], bool]:
    """
    根据游戏板面情况，对局面进行枚举。
    
    Args:
        board (List[List[int]]): 原始的游戏板面，其中-1表示雷，非负整数表示周围雷的数量。
        game_board (List[List[int]]): 当前的游戏板面，其中10表示未知，11表示必然为雷，非负整数表示周围雷的数量。
        poses (List[Tuple[int, int]]): 需要枚举的坐标点列表。
    
    Returns:
        Tuple[List[List[int]], bool]:
            - List[List[int]]: 枚举后的游戏板面，其中-1表示雷，非负整数表示周围雷的数量。
            - bool: 枚举是否成功，如果成功返回True，否则返回False。
    
    Raises:
        TypeError: 如果board不是list类型，会尝试将其转换为二维向量，如果转换失败则抛出TypeError。
    
    """
    if not isinstance(board, list):
        board = board.into_vec_vec()    
    if all([board[x][y] != -1 for x,y in poses]):
        # 全不是雷
        return board, True
    for i in range(len(board)):
        for j in range(len(board[0])):
            if game_board[i][j] == 11:
                game_board[i][j] = 10
    game_board = ms.mark_board(game_board)
    if any([game_board[x][y] == 11 for x,y in poses]):
        # 有一个必然是雷，就直接返回
        return board, False
    # 删去12不用管
    poses = list(filter(lambda xy: game_board[xy[0]][xy[1]] == 10, poses))
    
    # 第一步，将board上的10分成三份，不变区0、无约束区1、数字约束区2
    # 引入定理一：假如poses数量多于1，则必然全都在数字约束区
    # 定理二：poses必然全部在同一个段中，要么全不在
    # 统计这些区域的位置、雷数、非雷数
    # 标记一下游戏局面。由于(mine_x, mine_y)是不确定的雷，因此标记过后一定还是10
    # 记录每个格子的类型
    type_board = [[1 for i in range(len(board[0]))] for j in range(len(board))]
    rand_mine_num = 0
    rand_blank_num = 0
    constraint_mine_num = 0
    constraint_blank_num = 0
    
    matrix_ases, matrix_xses, matrix_bses = ms.refresh_matrixses(game_board)
    for idb, block in enumerate(matrix_xses):
        for idl, line in enumerate(block):
            if poses[0] in line:
                if len(line) >= EnuLimit:#枚举法的极限
                    #超过枚举极限时，暂时不能给出可能的解，有待升级
                    return board, False
                matrix_a = matrix_ases[idb][idl]
                matrix_x = matrix_xses[idb][idl]
                matrix_b = matrix_bses[idb][idl]
                constraint_mine_num = [board[x][y] for x,y in matrix_x].count(-1)
                constraint_blank_num = len(matrix_x) - constraint_mine_num
                for (i, j) in line:
                    type_board[i][j] = 2
            else:
                for (i, j) in line:
                    type_board[i][j] = 0
    # 数无约束变化区雷数、空格数
    for idr, row in enumerate(board):
        for idc, cell in enumerate(row):
            if game_board[idr][idc] == 10 and type_board[idr][idc] == 1:
                if board[idr][idc] == -1:
                    rand_mine_num += 1
                else:
                    rand_blank_num += 1
    # 第二步，假如无数字约束区、有数字约束区，求出雷数范围，根据约束筛选出可能解
    if constraint_mine_num == 0:
        if rand_blank_num >= 1:
            rand_blank_num -= 1
            # 此处poses必然只有一个元素
            (p, q) = poses[0]
            board[p][q] = 0
            type_board[p][q] = 0
        else:
            # 内部挤不下。理论上也可以在边缘（也就是不变区）多埋一个雷，
            # 但完全随机很难做到（均匀分布的逻辑太复杂，要拆解概率算法），因此放弃
            return board, False
    else:
        constraint_mine_num_max = min(constraint_mine_num + constraint_blank_num - len(poses),
                                      constraint_mine_num + rand_mine_num)
        constraint_mine_num_min = max(constraint_mine_num - rand_blank_num, 0)
        all_solution = ms.cal_all_solution(matrix_a, matrix_b)
        idposes = [matrix_x.index(pos) for pos in poses]
        all_solution = filter(lambda x: constraint_mine_num_min <= x.count(1) <=\
                              constraint_mine_num_max and\
                                  all([x[idpos] != 1 for idpos in idposes]), 
                                  all_solution)
        all_solution = list(all_solution)
        if not all_solution:
            return board, False
    # # 第三步，回填
    if constraint_mine_num > 0:
        # 假如有数字约束区
        solution = choice(all_solution)
        for idx, (x, y) in enumerate(matrix_x):
            board[x][y] = -solution[idx]
        constraint_mine_num_new = solution.count(1)
        delta = constraint_mine_num_new - constraint_mine_num
        rand_mine_num = rand_mine_num - delta
        rand_blank_num = rand_blank_num + delta
    # 随机区的局面
    rand_board = rand_mine_num * [-1] + rand_blank_num * [0]
    shuffle(rand_board)
    k = 0
    for i in range(len(board)):
        for j in range(len(board[0])):
            if game_board[i][j] == 10 and type_board[i][j] == 1:
                board[i][j] = rand_board[k]
                k += 1
            if board[i][j] >= 0:
                board[i][j] = 0
    board = ms.cal_board_numbers(board)
    return board, True


def trans_expression(expression: str):
    """
    将输入的表达式字符串进行一系列替换处理。
    
    Args:
        expression (str): 待处理的表达式字符串。
    
    Returns:
        str: 处理后的表达式字符串。
    
    具体处理规则如下：
        1. 将表达式转换为小写，并去除首尾空白字符，且仅保留前10000个字符。
        2. 将表达式中的"3bv"替换为"bbbv"。
        3. 将表达式中的"opening"替换为"op"。
        4. 将表达式中的"click"替换为"cl"。
        5. 将表达式中的双引号（"）替换为单引号（'）。
        6. 将表达式中的"island"替换为"isl"。
        7. 将表达式中的"chording"替换为"double"。
        8. 将表达式中的"solved_bbbv"替换为"bbbv_solved"。
    """
    expression = expression.lower().strip()[:10000]
    expression = expression.replace("3bv", "bbbv")
    expression = expression.replace("opening", "op")
    expression = expression.replace("click", "cl")
    expression = expression.replace("\"", "'")
    expression = expression.replace("island", "isl")
    expression = expression.replace("chording", "double")
    expression = expression.replace("solved_bbbv", "bbbv_solved")
    return expression


def trans_game_mode(mode: int) -> str:
    """
    将游戏模式数字转换为对应的中文描述。
    
    Args:
        mode (int): 游戏模式数字，取值范围在0到10之间。
    
    Returns:
        str: 返回对应的中文游戏模式描述。
    
    Raises:
        ValueError: 如果mode不在0到10的范围内，将抛出异常。
    
    """
    _translate = QtCore.QCoreApplication.translate
    if mode == 0:
        return _translate("Form", "标准")
    elif mode == 1:
        return 'upk'
    elif mode == 2:
        return 'cheat'
    elif mode == 3:
        return 'Density'
    elif mode == 4:
        return 'win7'
    elif mode == 5:
        return _translate("Form", '经典无猜')
    elif mode == 6:
        return _translate("Form", '强无猜')
    elif mode == 7:
        return _translate("Form", '弱无猜')
    elif mode == 8:
        return _translate("Form", '准无猜')
    elif mode == 9:
        return _translate("Form", '强可猜')
    elif mode == 10:
        return _translate("Form", '弱可猜')
    
# class abstract_game_board(object):
#     __slots__ = ('game_board', 'mouse_state', 'game_board_state')
#     def reset(self, *args):
#         ...
#     def step(self, *args):
#         ...
   
    
class CoreBaseVideo(ms.BaseVideo):
    mouse_state = 1
    game_board_state = 1
    x_y = (0, 0)
    def __new__(cls, board, cell_pixel_size):
        return ms.BaseVideo.__new__(cls, board, cell_pixel_size)
    def __init__(self, board, cell_pixel_size):
        super(CoreBaseVideo, self).__init__()
    @property
    def game_board(self):
        return self._game_board
    @game_board.setter
    def game_board(self, game_board):
        self._game_board = game_board
    class AlwaysZero:  
        def __getitem__(self, key):  
            class Inner:
                def __getitem__(self, inner_key):  
                    return 0  
            return Inner()
    # self.timer_video.stop()以后，槽函数可能还在跑
    # self.label.ms_board就会变成abstract_game_board
    # 使game_board_poss[x][y]永远返回0。否则此处就会报错
    game_board_poss = AlwaysZero()
    
    

        
        

# unsolvableStructure = ms_toollib.py_unsolvableStructure
# unsolvableStructure2(BoardCheck)
# 用几种模板，检测局面中是否有明显的死猜的结构
# 不考虑起手位置，因为起手必开空
# 局面至少大于4*4
# 返回0或1

def print2(arr, mode = 0):
    # 调试时便于打印 print2(BoardofGame)
    if mode == 0:
        for i in arr:
            for j in i:
                print('%2.d'%j, end=', ')
            print()
    elif mode == 1:
        for i in arr:
            for j in i:
                print('%2.d'%j.num, end=', ')
            print()
    elif mode == 2:
        for i in arr:
            for j in i:
                print('%2.d'%j.status, end=', ')
            print()

def debug_ms_board(ms_board):
    for i in range(ms_board.events_len):
        print(f"{ms_board.events_time(i)}: '{ms_board.events_mouse(i)}', ({ms_board.events_y(i)}, {ms_board.events_x(i)})")



# def updata_ini(file_name: str, data):
#     conf = configparser.ConfigParser()
#     conf.read(file_name, encoding='utf-8')
#     for i in data:
#         conf.set(i[0], i[1], str(i[2]))
#     conf.write(open(file_name, "w", encoding='utf-8'))

def main():
    # # 测试枚举法判雷速度算例
    # time1 = time.time()
    # BoardofGame = [[10]*12, [10]+[1]*10+[10], [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], \
    #                [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], \
    #                [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], \
    #                [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], \
    #                [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], [10]+[1]+[0]*8+[1]+[10], \
    #                [10]+[1]+[0]*8+[1]+[10], [10]+[1]*10+[10], [10]*12]
    # MatrixA, Matrixx, Matrixb = refreshMatrix(BoardofGame)
    # BoardofGame, NotMine, flag = SolveEnumerate(MatrixA, Matrixx, Matrixb, BoardofGame, 100)
    # print(NotMine)
    # time2 = time.time()
    # print(time2 - time1)


    # # 测试埋雷+计算3BV速度算例
    # time1 = time.time()
    # for i in range(100000):
    #     layMine(16, 30, 99, 1, 1, Min3BV=0, Max3BV=1000000, MaxTimes=1000000)
    # time2 = time.time()
    # print(time2 - time1)

    # # 测试  速度算例
    # time1 = time.time()
    # for i in range(10000):
    #     layMineOp(16, 30, 99, 1, 1)
    # time2 = time.time()
    # print(time2 - time1)

    # 测试生成无猜局面速度算例
    # num = 0
    # T = 500
    # time1 = time.time()
    # for i in range(T):
    #     (bb, Parameters) = ms.laymine_solvable_thread(16, 30, 99, 10, 10, 1000000)
    #     num += Parameters[2]
    # time2 = time.time()
    # print(time2 - time1)
    # print(num/T)




    # import minepy
    # import numpy as np
    # for ii in range(10):
    #     a = layMine(16, 30, 99, 1, 1, Min3BV=0, Max3BV=1e6, MaxTimes=1e6)[0]
    #     x = []
    #     y = []
    #     for i in range(16):
    #         for j in range(30):
    #             if a[i][j] == -1:
    #                 x.append(i)
    #                 y.append(j)
    #     mine = minepy.MINE(alpha=0.6, c=15, est="mic_approx")
    #     mine.compute_score(x, y)
    #     print(mine.mic())
    
    # a = laymine_solvable(0, 10, 100000, (8, 8, 10, 0, 0, 100000))
    # print(a)
    
    # game_board = [[ 0, 1,10,10,10,10, 1, 0],
    #               [ 1, 3,10,10,10,10, 3, 1],
    #               [ 1,10,10,10,10,10,10, 1],
    #               [ 1, 2, 3, 3, 3, 3, 2, 1],
    #               [ 1, 2, 3, 3, 3, 3, 2, 1],
    #               [ 1,10,10,10,10,10,10, 1],
    #               [ 1, 3,10,10,10,10, 3, 1],
    #               [ 0, 1,10,10,10,10, 1, 0],
    #               ]
    # board = [[ 0, 1,-1, 3,-1, 3, 1, 0],
    #          [ 1, 3, 4, 6,-1,-1, 3, 1],
    #          [ 1,-1,-1,-1,-1,-1,-1, 1],
    #          [ 1, 2, 3, 3, 3, 3, 2, 1],
    #          [ 1, 2, 3, 3, 3, 3, 2, 1],
    #          [ 1,-1,-1,-1,-1,-1,-1, 1],
    #          [ 1, 3, 5, 6,-1, 5, 3, 1],
    #          [ 0, 1,-1,-1, 3,-1, 1, 0],
    #          ]
    
    # game_board = [[10,10,10,10,10,10,10,10],
    #               [10,10,10,10,10,10,10,10],
    #               [10,10,10,10,10,10,10,10],
    #               [10,10,10, 5,10,10,10,10],
    #               [10,10,10,10,10,10,10,10],
    #               [10,10,10,10,10,10,10,10],
    #               [10,10,10,10,10,10,10,10],
    #               [10,10,10,10,10,10,10,10],
    #               ]
    # board = [[ 0, 0, 0, 0, 0, 0, 0, 0],
    #          [ 0, 0, 1, 1, 1, 0, 0, 0],
    #          [ 0, 1, 2,-1, 2, 1, 0, 0],
    #          [ 0, 1,-1, 5,-1, 2, 0, 0],
    #          [ 0, 1, 2,-1,-1, 2, 0, 0],
    #          [ 0, 0, 1, 2, 2, 1, 0, 0],
    #          [ 0, 0, 0, 0, 0, 0, 0, 0],
    #          [ 0, 0, 0, 0, 0, 0, 0, 0],
    #          ]
    
    # print2(enumerateChangeBoard2(board, game_board, [(2, 3), (3, 2), (2, 2)])[0])
    
    constraints = {
        "sin": math.sin,
        "tan": math.tan,
        "cos": math.cos,
        } # 也许还要加row, column, mine_num, level, mode
    board_constraint="all([1,2,3])"
    if "bbbv" in board_constraint:
        constraints.update({"bbbv": 120})
    try:
        expression_flag = safe_eval(board_constraint, globals=constraints)
        print(expression_flag)
    except:
        print("wrong")
        
    ...

if __name__ == '__main__':
    
    main()






