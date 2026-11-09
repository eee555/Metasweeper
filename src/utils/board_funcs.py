from random import shuffle, choice, sample, random, randint
from typing import List, Tuple
import math

import ms_toollib as ms
from utils.safe_eval import safe_eval
from utils.app_logger import logger

from config.constants import CELL_UNOPENED, CELL_FLAGGED, CELL_MINE, ENU_LIMIT as EnuLimit


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

            constraints = {}
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
                expression_flag = safe_eval(
                    board_constraint, extra_globals=constraints)
            except Exception:
                logger.warning(
                    "board_constraint eval failed",
                    exc_info=True,
                )
                return (b, success_flag)
            if expression_flag:
                return (b, success_flag)
            t += 1
        return (b, success_flag)
    return choose_3BV_laymine


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
    @choose_3BV(board_constraint, attempt_times_limit, params)
    def board(pp):
        return ms.laymine_solvable_adjust(*pp)
    return board


def get_mine_times_limit(row: int, column: int):
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
    (max_mine_num, max_times) = get_mine_times_limit(row, column)
    if mine_num <= max_mine_num:
        ans = ms.laymine_solvable_thread(
            row, column, mine_num, x, y, max_times)
        ans = ms.laymine_solvable_thread(
            row, column, mine_num, x, y, max_times)
        if ans[1]:
            return ans
    return ms.laymine_solvable_adjust(row, column, mine_num, x, y)


def laymine_solvable(board_constraint, attempt_times_limit, params):
    @choose_3BV(board_constraint, attempt_times_limit, params)
    def board(pp):
        return laymine_solvable_auto(*pp)
    return board

def _unique_block_vars(matrix_x_block: List[List[tuple[int, int]]]) -> List[tuple[int, int]]:
    seen = set()
    unique_vars: List[tuple[int, int]] = []
    for eq_vars in matrix_x_block:
        for coord in eq_vars:
            if coord not in seen:
                seen.add(coord)
                unique_vars.append(coord)
    return unique_vars


def _group_solutions_by_mine_count(solutions: List[List[int]]) -> dict[int, List[List[int]]]:
    grouped: dict[int, List[List[int]]] = {}
    for sol in solutions:
        count = sol.count(1)
        grouped.setdefault(count, []).append(sol)
    return grouped


def _weighted_choice(items: List[int], weights: List[int]) -> int:
    total = sum(weights)
    if total <= 0:
        raise ValueError("no positive weights")
    threshold = randint(0, total - 1)
    cumulative = 0
    for item, weight in zip(items, weights):
        cumulative += weight
        if threshold < cumulative:
            return item
    return items[-1]


def enumerate_change_board(board: ms.EvfVideo | List[List[int]],
                           game_board: List[List[int]],
                           poses: List[Tuple[int, int]],
                           must_mine: List[Tuple[int, int]] | None = None) -> Tuple[List[List[int]], bool, int, int]:
    """重排雷局，使指定格子(poses)都变成安全格、must_mine 中的格子都变成雷。

    该实现基于约束块枚举和无约束区补偿，保证从所有满足的雷局中均等概率随机选择，
    并保持全局总雷数不变（取自输入 board）。
    """
    if not isinstance(board, list):
        board = board.into_vec_vec()
    must_mine = list(must_mine or [])

    # 记录原始雷数，用于保持全局总雷数不变
    total_mine_count = sum(1 for row in board for cell in row if cell == CELL_MINE)
    max_block_len = 0
    max_solutions = 0

    # 复制 game_board，清除玩家标旗，仅保留已开数字
    game_board_copy = [list(row) for row in game_board]
    for i in range(len(game_board_copy)):
        for j in range(len(game_board_copy[0])):
            if game_board_copy[i][j] == CELL_FLAGGED:
                game_board_copy[i][j] = CELL_UNOPENED
    game_board_copy = ms.mark_board(game_board_copy)

    # 若某个 pose 被推断必为雷，则无法满足条件
    if any(game_board_copy[x][y] == CELL_FLAGGED for x, y in poses):
        return board, False, 0, 0

    # must_mine 的格子：已被推断为雷的天然满足；已打开或推断为非雷的无法满足
    forced_mine_positions: List[tuple[int, int]] = []
    for x, y in must_mine:
        value = game_board_copy[x][y]
        if value == CELL_FLAGGED:
            continue
        if value != CELL_UNOPENED:
            return board, False, 0, 0
        forced_mine_positions.append((x, y))

    # 只保留还未打开的 pose，已打开或已知安全的 pose 已经满足要求
    poses = [pos for pos in poses if game_board_copy[pos[0]][pos[1]] == CELL_UNOPENED]
    if not poses and not forced_mine_positions:
        return board, True, max_block_len, max_solutions
    pose_set = set(poses)
    forced_mine_set = set(forced_mine_positions)

    matrix_ases, matrix_xses, matrix_bses = ms.refresh_matrixses(game_board_copy)

    for block_xs in matrix_xses:
        block_vars = _unique_block_vars(block_xs)
        max_block_len = max(max_block_len, len(block_vars))

    # 约束块求解结果
    block_solution_groups: List[tuple[List[tuple[int, int]], dict[int, List[List[int]]]]] = []
    all_block_vars: set[tuple[int, int]] = set()
    fixed_mine_positions: set[tuple[int, int]] = set()

    # 统计推导出的必然雷
    for i in range(len(game_board_copy)):
        for j in range(len(game_board_copy[0])):
            if game_board_copy[i][j] == CELL_FLAGGED:
                fixed_mine_positions.add((i, j))

    # 逐个约束块求解
    for block_index, block_xs in enumerate(matrix_xses):
        for eq_index, matrix_x in enumerate(block_xs):
            if not matrix_x:
                continue
            if len(matrix_x) > EnuLimit:
                return board, False, max_block_len, max_solutions

            matrix_a = matrix_ases[block_index][eq_index]
            matrix_b = matrix_bses[block_index][eq_index]
            block_vars = _unique_block_vars([matrix_x])
            all_block_vars.update(block_vars)

            try:
                solutions = ms.cal_all_solution(matrix_a, matrix_b)
                max_solutions = max(max_solutions, len(solutions))
            except Exception:
                return board, False, max_block_len, max_solutions
            if not isinstance(solutions, list):
                solutions = list(solutions)

            pose_indices = [idx for idx, coord in enumerate(block_vars) if coord in pose_set]
            mine_indices = [idx for idx, coord in enumerate(block_vars) if coord in forced_mine_set]
            if pose_indices or mine_indices:
                filtered = []
                for sol in solutions:
                    if all(sol[idx] == 0 for idx in pose_indices) and \
                            all(sol[idx] == 1 for idx in mine_indices):
                        filtered.append(sol)
                solutions = filtered

            if not solutions:
                return board, False, max_block_len, max_solutions

            block_groups = _group_solutions_by_mine_count(solutions)
            block_solution_groups.append((block_vars, block_groups))

    free_positions: List[tuple[int, int]] = []
    for i in range(len(game_board_copy)):
        for j in range(len(game_board_copy[0])):
            if game_board_copy[i][j] == CELL_UNOPENED and (i, j) not in all_block_vars \
                    and (i, j) not in pose_set and (i, j) not in forced_mine_set:
                free_positions.append((i, j))

    # 不在任何约束块里的 must_mine 格子直接固定为雷
    free_forced_mines = [pos for pos in forced_mine_positions if pos not in all_block_vars]

    total_mine_remaining = total_mine_count - len(fixed_mine_positions) - len(free_forced_mines)
    if total_mine_remaining < 0:
        return board, False, max_block_len, max_solutions

    # 计算各个约束块按雷数的解数量
    block_count_maps: List[dict[int, int]] = []
    for _, groups in block_solution_groups:
        block_count_maps.append({mine_count: len(sols) for mine_count, sols in groups.items()})

    # dp_forward[m] = 组合前缀的解数量
    dp_forward: dict[int, int] = {0: 1}
    for count_map in block_count_maps:
        next_dp: dict[int, int] = {}
        for prefix_mine, prefix_count in dp_forward.items():
            for mine_count, sol_count in count_map.items():
                next_dp[prefix_mine + mine_count] = next_dp.get(prefix_mine + mine_count, 0) + prefix_count * sol_count
        dp_forward = next_dp

    # 统计每种约束块总雷数对应的总完整解权重
    total_weights: dict[int, int] = {}
    free_size = len(free_positions)
    for block_mine_sum, combo_count in dp_forward.items():
        free_mine_count = total_mine_remaining - block_mine_sum
        if 0 <= free_mine_count <= free_size:
            total_weights[block_mine_sum] = combo_count * math.comb(free_size, free_mine_count)

    if not total_weights:
        return board, False, max_block_len, max_solutions

    chosen_blocks_mines = _weighted_choice(list(total_weights.keys()), list(total_weights.values()))
    chosen_free_mines = total_mine_remaining - chosen_blocks_mines

    # 反向 dp 用于逐块采样
    suffix_dp: List[dict[int, int]] = [{0: 1}]
    for count_map in reversed(block_count_maps):
        current: dict[int, int] = {}
        for mine_count, sol_count in count_map.items():
            for suffix_mines, suffix_weight in suffix_dp[0].items():
                current[mine_count + suffix_mines] = current.get(mine_count + suffix_mines, 0) + sol_count * suffix_weight
        suffix_dp.insert(0, current)

    chosen_block_solutions: List[tuple[List[tuple[int, int]], List[int]]] = []
    remaining_mines = chosen_blocks_mines
    for block_index, (block_vars, groups) in enumerate(block_solution_groups):
        next_suffix = suffix_dp[block_index + 1]
        candidates: List[int] = []
        weights: List[int] = []
        for mine_count, sols in groups.items():
            tail = remaining_mines - mine_count
            if tail < 0:
                continue
            suffix_weight = next_suffix.get(tail)
            if suffix_weight is None:
                continue
            candidates.append(mine_count)
            weights.append(len(sols) * suffix_weight)
        if not candidates:
            return board, False, max_block_len, max_solutions
        chosen_mine_count = _weighted_choice(candidates, weights)
        chosen_solution = choice(groups[chosen_mine_count])
        chosen_block_solutions.append((block_vars, chosen_solution))
        remaining_mines -= chosen_mine_count

    if remaining_mines != 0:
        return board, False, max_block_len, max_solutions

    if len(free_positions) < chosen_free_mines or chosen_free_mines < 0:
        return board, False, max_block_len, max_solutions

    free_mine_positions: set[tuple[int, int]] = set()
    if chosen_free_mines:
        free_mine_positions = set(sample(free_positions, chosen_free_mines))

    # 生成最终雷局并重算数字格
    result_board = [[0] * len(board[0]) for _ in range(len(board))]
    for i in range(len(board)):
        for j in range(len(board[0])):
            if game_board_copy[i][j] == CELL_FLAGGED:
                result_board[i][j] = CELL_MINE

    for block_vars, solution in chosen_block_solutions:
        for is_mine, coord in zip(solution, block_vars):
            if is_mine:
                result_board[coord[0]][coord[1]] = CELL_MINE

    for coord in free_mine_positions:
        result_board[coord[0]][coord[1]] = CELL_MINE

    for coord in free_forced_mines:
        result_board[coord[0]][coord[1]] = CELL_MINE

    result_board = ms.cal_board_numbers(result_board)
    return result_board, True, max_block_len, max_solutions

def board_list_to_bytes(board: List[List[int]]) -> bytes:
    if not board:
        return b''
    rows = len(board)
    cols = len(board[0])
    raw_data = bytearray()
    current_byte = 0
    bit_ptr = 0
    for i in range(rows):
        row = board[i]
        for j in range(cols):
            current_byte <<= 1
            val = row[j]
            if val == CELL_MINE:
                current_byte |= 1
            bit_ptr += 1
            if bit_ptr == 8:
                raw_data.append(current_byte)
                current_byte = 0
                bit_ptr = 0
    if bit_ptr > 0:
        current_byte <<= (8 - bit_ptr)
        raw_data.append(current_byte)
    return bytes(raw_data)


# 按高位到低位展开，与 board_list_to_bytes 的位序一致。
_BOARD_BYTE_CELLS = tuple(
    tuple(-1 if value & (1 << bit) else 0 for bit in range(7, -1, -1))
    for value in range(256)
)


def board_bytes_to_board(rows: int, cols: int, board_bytes: bytes) -> list[list[int]]:
    total = rows * cols
    cells = []
    for value in board_bytes[:(total + 7) // 8]:
        cells.extend(_BOARD_BYTE_CELLS[value])
    if len(cells) < total:
        cells.extend([0] * (total - len(cells)))
    result = [cells[i * cols:(i + 1) * cols] for i in range(rows)]
    return ms.cal_board_numbers(result)
