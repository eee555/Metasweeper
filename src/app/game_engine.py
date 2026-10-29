import hashlib
import logging

import ms_toollib as ms
import utils
import metasweeper_checksum
from config.constants import (
    READY, PLAYING, WIN, FAIL, JOWIN, JOFAIL, DISPLAY, SHOW_DISPLAY, STUDY,
    MODE_STANDARD, MODE_WIN7, MODE_CLASSIC_NO_GUESS, MODE_STRONG_NO_GUESS,
    MODE_WEAK_NO_GUESS, MODE_QUASI_NO_GUESS, MODE_STRONG_GUESSABLE, MODE_WEAK_GUESSABLE,
    MODE_NOGUESS_CHORD_RECURSIVE, MODE_NOGUESS_FLAG_RECURSIVE,
    MODE_NOGUESS_CHORD_FLAG_RECURSIVE,
    MIN_PIX_SIZE, MAX_PIX_SIZE,
    BOARD_BEGINNER, BOARD_INTERMEDIATE, BOARD_EXPERT,
    FILENAME_LEVEL_BEGINNER, FILENAME_LEVEL_INTERMEDIATE,
    FILENAME_LEVEL_EXPERT, FILENAME_LEVEL_CUSTOM,
    NO_RECORD,
    CELL_MINE,
    BOARD_WIN, BOARD_PLAYING, BOARD_PreFlaging, BOARD_Display
)
from typing import List, Tuple


class GameEngine:
    def __init__(self, ms_board=None) -> None:
        self.ms_board = ms_board

        self._game_state: str = READY
        self._game_mode: int = MODE_STANDARD
        self._row: int = 16
        self._column: int = 30
        self._minenum: int = 99
        self._pixSize: int = 20

        self.time_10ms: int = 0
        self.mine_unflagged_num: int = self._minenum
        self.board_constraint: str = ""
        self.attempt_times_limit: int = 100000
        self._allowed_controls: set[str] = set()
        self._max_block_len: int = 0
        self._max_solutions: int = 0

        self.pending_boards: list[dict] = []
        # 是否使用预设局面。使用预设局面时，保存的录像模式必定为upk
        self.use_pending_boards_flag = False

        self._state_change_handlers = {
            PLAYING: None,  # 离开playing时的回调
        }

    # ── properties ──────────────────────────────────────────

    @property
    def pixSize(self) -> int:
        return self._pixSize

    @pixSize.setter
    def pixSize(self, value: int) -> None:
        self._pixSize = max(MIN_PIX_SIZE, min(MAX_PIX_SIZE, value))
        if self.ms_board and self._row and self._column:
            self._pixSize = min(32767 // self._column, self._pixSize)
            self._pixSize = min(32767 // self._row, self._pixSize)

    @property
    def gameMode(self) -> int:
        return self._game_mode

    @gameMode.setter
    def gameMode(self, value: int) -> None:
        if self.ms_board and hasattr(self.ms_board, 'mode') and self.ms_board.game_board_state not in (BOARD_PLAYING, BOARD_PreFlaging, BOARD_Display):
            self.ms_board.mode = value
        self._game_mode = value

    @property
    # 这个值似乎没有得到维护
    def game_state(self) -> str:
        return self._game_state

    @game_state.setter
    # 这个值似乎没有得到维护
    def game_state(self, new_state: str) -> None:
        if new_state == self._game_state:
            return
        last_state = self._game_state
        if last_state == PLAYING and self._state_change_handlers.get(PLAYING):
            self._state_change_handlers.get(PLAYING, lambda *_: None)(last_state, new_state)
        self._game_state = new_state

    @property
    def row(self) -> int:
        return self._row

    @row.setter
    def row(self, value: int) -> None:
        self._row = value

    @property
    def column(self) -> int:
        return self._column

    @column.setter
    def column(self, value: int) -> None:
        self._column = value

    @property
    def minenum(self) -> int:
        return self._minenum

    @minenum.setter
    def minenum(self, value: int) -> None:
        self._minenum = value

    # ── 局面操作 ──────────────────────────────────────────

    _LAY_MINE_DISPATCH = {
        MODE_CLASSIC_NO_GUESS: utils.laymine_solvable,
        MODE_STRONG_NO_GUESS: utils.laymine_solvable,
        MODE_STRONG_GUESSABLE: utils.laymine_solvable,
        MODE_NOGUESS_CHORD_RECURSIVE: utils.laymine_solvable,
        MODE_NOGUESS_FLAG_RECURSIVE: utils.laymine_solvable,
        MODE_NOGUESS_CHORD_FLAG_RECURSIVE: utils.laymine_solvable,
        MODE_WIN7: utils.laymine_op,
    }

    def layMine(self, i: int, j: int):
        if self.pending_boards:
            self.use_pending_boards_flag = True
            pending_board = self.pending_boards.pop(0)
            board = pending_board.get("board")
            if board and self.ms_board:
                self.ms_board.board = board
            gm = pending_board.get("game_mode", MODE_STANDARD)
            self.gameMode = gm
            return
        self.use_pending_boards_flag = False
        laymine_func = self._LAY_MINE_DISPATCH.get(self.gameMode, utils.laymine)
        Board, _ = laymine_func(
            self.board_constraint,
            self.attempt_times_limit,
            (self.row, self.column, self.minenum, i, j))

        if self.ms_board:
            self.ms_board.board = Board

    def ai(self, i: int, j: int) -> None:
        if not self.ms_board:
            return
        gm = self.gameMode
        if gm in (MODE_STANDARD, MODE_WIN7, MODE_CLASSIC_NO_GUESS):
            return
        # 游戏进行中的模式推衍（重排雷局、判负）由局面状态机（ms_toollib）自行完成，
        # 前提是埋雷时已把游戏模式告诉局面状态机。这里只处理 upk 恢复局面的第一击：
        # 首击豁免模式判定，若落在原雷局上，需要重排成安全格。
        if self.ms_board.game_board_state == BOARD_PLAYING:
            return
        board = self.ms_board.board
        game_board = self.ms_board.game_board
        if gm in (MODE_WEAK_NO_GUESS, MODE_QUASI_NO_GUESS) or \
                board[i][j] == CELL_MINE:
            b, _, self._max_block_len, self._max_solutions = utils.enumerate_change_board(
                board, game_board, [(i, j)])
            self.ms_board.board = b

    def mineNumWheel(self, delta: int) -> None:
        if self.game_state == READY:
            if delta > 0:
                if self.minenum < self.row * self.column - 1:
                    self.minenum += 1
                    self.mine_unflagged_num += 1
            elif delta < 0:
                if self.minenum > 1:
                    self.minenum -= 1
                    self.mine_unflagged_num -= 1

    # ── 检查方法 ──────────────────────────────────────────

    def is_official(self) -> bool:
        if not self.is_fair():
            return False
        if self.ms_board:
            return self.ms_board.game_board_state == BOARD_WIN and self.gameMode == MODE_STANDARD
        return False

    def is_fair(self) -> bool:
        if self.board_constraint:
            return False
        if self._allowed_controls:
            return False
        return self.game_state in (WIN, FAIL, PLAYING)

    def cell_is_in_board(self, i: int, j: int) -> bool:
        return 0 <= i < self.row and 0 <= j < self.column

    def pos_is_in_board(self, i: int, j: int) -> bool:
        return 0 <= i < self.row * self.pixSize and \
               0 <= j < self.column * self.pixSize

    def pos_round_cell(self, r: int, c: int) -> List[Tuple[int, int]]:
        return [(i, j) for i in range(max(0, r - 1), min(self.row, r + 2))
                for j in range(max(0, c - 1), min(self.column, c + 2)) if (i, j) != (r, c)]

    @staticmethod
    def checksum_module_ok():
        # return True
        return hashlib.sha256(
            bytes(metasweeper_checksum.get_self_key())
        ).hexdigest() == \
            '590028493bb58a25ffc76e2e2ad490df839a1f449435c35789d3119ca69e5d4f'

    # ── 录像文件名 ──────────────────────────────────────────

    def cal_evf_filename(self, ms_board, game_state, player_identifier,
                         replay_path="", absolute=True) -> str:
        board_key = (ms_board.row, ms_board.column, ms_board.mine_num)
        if board_key == BOARD_BEGINNER:
            filename_level = FILENAME_LEVEL_BEGINNER
        elif board_key == BOARD_INTERMEDIATE:
            filename_level = FILENAME_LEVEL_INTERMEDIATE
        elif board_key == BOARD_EXPERT:
            filename_level = FILENAME_LEVEL_EXPERT
        else:
            filename_level = FILENAME_LEVEL_CUSTOM
        if game_state in (DISPLAY, SHOW_DISPLAY):
            ms_board.current_time = NO_RECORD
        if absolute:
            file_name = replay_path + '\\'
        else:
            file_name = ""
        file_name += filename_level + \
            f'{ms_board.mode}' + '_' + \
            f'{ms_board.rtime:.3f}' + \
            '_' + f'{ms_board.bbbv}' + \
            '_' + f'{ms_board.bbbv_s:.3f}' + \
            '_' + player_identifier
        if not ms_board.is_completed:
            file_name += "_fail"
        if not ms_board.is_fair:
            file_name += "_cheat"
        if ms_board.software[0] != "元":
            file_name += "_trans"
        elif not self.checksum_module_ok():
            file_name += "_fake"
        return file_name
