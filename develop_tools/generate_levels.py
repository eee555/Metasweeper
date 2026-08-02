import json
import sys
import os, random

# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ms_toollib as ms

# 无猜关卡插件的关卡生成脚本
# 使用一次后就无用，留档用

def is_solvable(board: list[list[int]], x0: int, y0: int) -> int:
    """从指定位置开始扫，判断局面是否无猜，并返回难度。

    返回:
        -1 表示有猜；正整数表示无猜及其难度
    """
    if board[x0][y0] == -1:
        return -1
    if ms.unsolvable_structure(board):
        return -1
    row = len(board)
    column = len(board[0])
    game_board: list[list[int]] = [[10] * column for _ in range(row)]
    game_board = ms.refresh_board(board, game_board, [(x0, y0)])
    i, j = 0, 0
    while i < row:
        while j < column:
            if board[i][j] != -1 and game_board[i][j] == 10:
                break
            j += 1
        if j < column and board[i][j] != -1 and game_board[i][j] == 10:
            break
        j = 0
        i += 1
    if i >= row:
        return 0
    difficulty = 0
    while True:
        a_mats, xs, bs, _, _ = ms.refresh_matrixs(game_board)
        a_mats, xs, bs, game_board, not_mine, is_mine = ms.solve_direct(
            a_mats, xs, bs, game_board
        )
        if not not_mine and not is_mine:
            a_mats, xs, bs, game_board, not_mine, is_mine = ms.solve_minus(
                a_mats, xs, bs, game_board
            )
            if not not_mine and not is_mine:
                not_mine, is_mine = ms.solve_enumerate(game_board)
                difficulty += 10
                if not not_mine and not is_mine:
                    return -1
            else:
                difficulty += 3
        else:
            difficulty += 1
        if is_mine:
            for o, p in is_mine:
                game_board[o][p] = 11
        if not_mine:
            game_board = ms.refresh_board(board, game_board, not_mine)
        i, j = 0, 0
        while i < row:
            while j < column:
                if board[i][j] != -1 and game_board[i][j] == 10:
                    break
                j += 1
            if j < column and board[i][j] != -1 and game_board[i][j] == 10:
                break
            j = 0
            i += 1
        if i >= row:
            return difficulty




def _next_size(row: int, col: int) -> tuple[int, int]:
    """交替增加尺寸：6x6 -> 6x7 -> 7x7 -> 7x8 -> 8x8 -> ..."""
    if row >= 16 and col < 30:
        return row, col + 1
    if row >= 16 and col >= 30:
        if col / row < 1.88:
            return row + 1, col
        else:
            return row, col + 1
    if row == col:
        return row, col + 1
    else:
        return row + 1, col


def generate_levels(output_file="levels.json"):
    row, col, mines = 6, 6, 5
    levels = {i: [] for i in range(1, 101)}
    left_difficulties = set(range(1, 101))

    while left_difficulties:
        for _ in range(1000):
            cx = random.randint(0, row - 1)
            cy = random.randint(0, col - 1)
            board, success = ms.laymine_solvable_thread(row, col, mines, cx, cy, 1000000)
            if not success:
                row, col = _next_size(row, col)
                mines = int(row * col * 0.2)
                print(f"{row}x{col}, {mines:3d}")
                break
            difficulty = is_solvable(board, cx, cy)
            if difficulty == 0 or difficulty > 100 or len(levels[difficulty]) >= 10:
                if difficulty in left_difficulties:
                    left_difficulties.discard(difficulty)
                    print(left_difficulties)
                    continue
            else:
                print(f"[{difficulty:3d}/100] {row}x{col}, {mines:3d} mines, got {len(levels[difficulty]) + 1}/10 boards")
                levels[difficulty].append({
                    "x": cx,
                    "y": cy,
                    "r": row,
                    "c": col,
                    "m": mines,
                    "b": board
                })
        else:
            mines += 1
            if mines > (row - 1) * (col - 1):
                row, col = _next_size(row, col)
                mines = int(row * col * 0.2)
            print(f"{row}x{col}, {mines:3d}")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(levels, f, ensure_ascii=False)


    
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(levels, f, ensure_ascii=False)



if __name__ == "__main__":
    generate_levels()
