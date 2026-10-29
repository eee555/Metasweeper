# ── 游戏状态 ──────────────────────────────────────────────
READY = 'ready'
PLAYING = 'playing'
JOKING = 'joking'
WIN = 'win'
FAIL = 'fail'
STUDY = 'study'
DISPLAY = 'display'
SHOW_DISPLAY = 'showdisplay'
SHOW = 'show'
JOWIN = 'jowin'
JOFAIL = 'jofail'
MODIFY = 'modify'

# ── 游戏模式 ──────────────────────────────────────────────
MODE_STANDARD = 0
MODE_WIN7 = 4
MODE_CLASSIC_NO_GUESS = 5
MODE_STRONG_NO_GUESS = 6
MODE_WEAK_NO_GUESS = 7
MODE_QUASI_NO_GUESS = 8
MODE_STRONG_GUESSABLE = 9
MODE_WEAK_GUESSABLE = 10
MODE_CHORD_RECURSIVE = 11
MODE_FLAG_RECURSIVE = 12
MODE_CHORD_FLAG_RECURSIVE = 13
MODE_NOGUESS_CHORD_RECURSIVE = 14
MODE_NOGUESS_FLAG_RECURSIVE = 15
MODE_NOGUESS_CHORD_FLAG_RECURSIVE = 16
MODE_UPK = 1
MODE_CHEAT = 2
MODE_DENSITY = 3

_NO_GUESS_MODES = {MODE_CLASSIC_NO_GUESS, MODE_STRONG_NO_GUESS}
_SOLVABLE_MODES = {MODE_CLASSIC_NO_GUESS, MODE_STRONG_NO_GUESS}
_DISABLE_AI_MODES = {MODE_STANDARD, MODE_WIN7, MODE_CLASSIC_NO_GUESS}

# ── 表情类型 ──────────────────────────────────────────────
FACE_SMILE = 14
FACE_CLICK = 15
FACE_LOST = 16
FACE_WIN = 17
FACE_SMILE_DOWN = 18

# ── 棋盘内部状态 (game_board_state) ──────────────────────
BOARD_READY = 1
BOARD_PLAYING = 2
BOARD_WIN = 3
BOARD_LOSS = 4
BOARD_PreFlaging = 5
BOARD_Display = 6

# ── 游戏局面格子编码 ──────────────────────────────────────
CELL_UNOPENED = 10
CELL_FLAGGED = 11
CELL_MINE = -1

# ── 标准棋盘配置 ──────────────────────────────────────────
BOARD_BEGINNER = (8, 8, 10)
BOARD_INTERMEDIATE = (16, 16, 40)
BOARD_EXPERT = (16, 30, 99)

# ── 难度等级 ──────────────────────────────────────────────
LEVEL_BEGINNER = 3
LEVEL_INTERMEDIATE = 4
LEVEL_EXPERT = 5
LEVEL_CUSTOM = 6

# ── 难度等级名称 ──────────────────────────────────────────
LEVEL_NAME_BEGINNER = 'BEGINNER'
LEVEL_NAME_INTERMEDIATE = 'INTERMEDIATE'
LEVEL_NAME_EXPERT = 'EXPERT'
LEVEL_NAME_CUSTOM = 'CUSTOM'

# ── 录像文件名等级前缀 ──────────────────────────────────
FILENAME_LEVEL_BEGINNER = "b_"
FILENAME_LEVEL_INTERMEDIATE = "i_"
FILENAME_LEVEL_EXPERT = "e_"
FILENAME_LEVEL_CUSTOM = "c_"

# ── 棋盘预置索引 ──────────────────────────────────────────
IDX_BEGINNER = 1
IDX_INTERMEDIATE = 2
IDX_EXPERT = 3
IDX_CUSTOM = 0

# ── 无记录哨兵值 ──────────────────────────────────────────
NO_RECORD = 999999.9

# ── 枚举法极限 ────────────────────────────────────────────
ENU_LIMIT = 55

# ── 窗口设置 ──────────────────────────────────────────────
MIN_PIX_SIZE = 5
MAX_PIX_SIZE = 255

# ── 游戏事件状态映射 ──────────────────────────────────────
GAME_EVENT_STATE_MAP = {
    READY: 1,
    PLAYING: 2,
    WIN: 3,
    FAIL: 4,
    JOKING: 2,
    JOWIN: 3,
    JOFAIL: 4,
    SHOW: 5,
    STUDY: 6,
    DISPLAY: 7,
    SHOW_DISPLAY: 8,
}

# ── 游戏状态索引 ──────────────────────────────────────
GAME_STATE_ORDER = [
    READY, STUDY, SHOW, PLAYING, JOKING, FAIL,
    WIN, JOFAIL, JOWIN, DISPLAY, SHOW_DISPLAY,
]
