from typing import List, Tuple
import tempfile
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl, QMimeData
import ms_toollib as ms


CELL_MINE = -1
CELL_UNOPENED = 10
CELL_FLAGGED = 11
CELL_WRONG_FLAG = 14
CELL_STEPPED_MINE = 15
CELL_UNMARKED_MINE = 16


_GAME_MODE_NAMES = {
    0: "classic",
    4: "win7",
    5: "classic_no_guess",
    6: "strong_no_guess",
    7: "weak_no_guess",
    8: "quasi_no_guess",
    9: "strong_guessable",
    10: "weak_guessable",
    1: "upk",
    2: "cheat",
    3: "density",
}


def _game_mode_str(mode: int) -> str:
    return _GAME_MODE_NAMES.get(mode, str(mode))


def board_to_array_str(real_board: List[List[int]]) -> str:
    rows = []
    for row in real_board:
        rows.append("[" + ", ".join(str(c) for c in row) + "]")
    return "[" + ",\n ".join(rows) + "]"


_EMOJI_VIEW = {
    "U": "⬜",
    "0": "0️⃣",
    "1": "1️⃣",
    "2": "2️⃣",
    "3": "3️⃣",
    "4": "4️⃣",
    "5": "5️⃣",
    "6": "6️⃣",
    "7": "7️⃣",
    "8": "8️⃣",
    "F": "🚩",
    "?": "❓",
    "X": "💥",
    "@": "💣",
    "#": "❌",
    "*": "💣",
}


def _view_char_ascii(cell: int) -> str:
    if cell == CELL_MINE:
        return "*"
    if cell == CELL_UNMARKED_MINE:
        return "@"
    if cell == CELL_UNOPENED or cell == 12:
        return "U"
    if cell == CELL_FLAGGED:
        return "F"
    if cell == CELL_WRONG_FLAG:
        return "#"
    if cell == CELL_STEPPED_MINE:
        return "X"
    return str(cell)


def _view_char_emoji(cell: int) -> str:
    ascii_ch = _view_char_ascii(cell)
    return _EMOJI_VIEW.get(ascii_ch, ascii_ch)


def board_to_board_string(
    real_board: List[List[int]],
    game_board: List[List[int]],
    rows: int,
    cols: int,
    mines: int,
    game_mode: int,
    author: str = "",
    render: str = "ascii",
) -> str:
    use_emoji = render == "emoji"

    lines = []
    lines.append("# MINESWEEPER-BOARD v0.1")
    lines.append(f"# Render: {render}")
    lines.append("")
    if author:
        lines.append(f"author: {author}")
    lines.append(f"rows: {rows}")
    lines.append(f"columns: {cols}")
    lines.append(f"mines: {mines}")
    lines.append(f"game_mode: {_game_mode_str(game_mode)}")
    lines.append("")

    if real_board:
        lines.append("[real]")
        for row in real_board:
            line = ""
            for c in row:
                if c == CELL_MINE:
                    line += _EMOJI_VIEW["*"] if use_emoji else "*"
                else:
                    ch = str(c)
                    line += _EMOJI_VIEW.get(ch, ch) if use_emoji else ch
            lines.append(line)
        lines.append("")

    if game_board:
        view_fn = _view_char_emoji if use_emoji else _view_char_ascii
        lines.append("[view]")
        for row in game_board:
            line = "".join(view_fn(c) for c in row)
            lines.append(line)
        lines.append("")

    return "\n".join(lines)


def copy_board_to_clipboard(
    real_board: List[List[int]],
    game_board: List[List[int]],
    rows: int,
    cols: int,
    mines: int,
    game_mode: int,
    copy_format: int,
    author: str = "",
    render: str = "ascii",
) -> None:
    if copy_format == 0:
        text = board_to_array_str(game_board)
        QApplication.clipboard().setText(text)

    elif copy_format == 1:
        text = board_to_board_string(
            real_board, game_board, rows, cols, mines, game_mode, author, render
        )
        QApplication.clipboard().setText(text)

    else:
        text = board_to_board_string(
            real_board, game_board, rows, cols, mines, game_mode, author, render
        )
        wrapper = ms.Board(real_board)
        name = f"{rows}x{cols}_{mines}_{wrapper.bbbv}_{wrapper.op}_{wrapper.isl}.board"
        path = os.path.join(tempfile.gettempdir(), name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        url = QUrl.fromLocalFile(path)
        mime = QMimeData()
        mime.setUrls([url])
        mime.setText(text)
        QApplication.clipboard().setMimeData(mime)


_EMOJI_TO_ASCII = {
    "\u2b1c": "U",
    "\U0001f6a9": "F",
    "\u2753": "?",
    "\U0001f4a5": "X",
    "\U0001f4a3": "@",
    "\u274c": "#",
}
_EMOJI_DIGIT_SUFFIX = "\ufe0f\u20e3"


def _parse_view_line_ascii(line: str) -> List[int]:
    row = []
    for ch in line:
        if ch == "U":
            row.append(CELL_UNOPENED)
        elif ch == "F":
            row.append(CELL_FLAGGED)
        elif ch == "*":
            row.append(CELL_MINE)
        elif ch == "?":
            row.append(CELL_UNOPENED)
        elif ch == "X":
            row.append(CELL_STEPPED_MINE)
        elif ch == "@":
            row.append(CELL_UNMARKED_MINE)
        elif ch == "#":
            row.append(CELL_WRONG_FLAG)
        else:
            row.append(int(ch))
    return row


def _parse_view_line_emoji(line: str) -> List[int]:
    row = []
    i = 0
    while i < len(line):
        ch = line[i]
        ascii_ch = _EMOJI_TO_ASCII.get(ch)
        if ascii_ch:
            if ascii_ch == "U":
                row.append(CELL_UNOPENED)
            elif ascii_ch == "F":
                row.append(CELL_FLAGGED)
            elif ascii_ch == "?":
                row.append(CELL_UNOPENED)
            elif ascii_ch == "X":
                row.append(CELL_STEPPED_MINE)
            elif ascii_ch == "@":
                row.append(CELL_UNMARKED_MINE)
            elif ascii_ch == "#":
                row.append(CELL_WRONG_FLAG)
            i += 1
        elif ch == "*":
            row.append(CELL_MINE)
            i += 1
        elif ch.isdigit():
            if line[i + 1:i + 3] == _EMOJI_DIGIT_SUFFIX:
                row.append(int(ch))
                i += 3
            else:
                row.append(int(ch))
                i += 1
        else:
            i += 1
    return row


def parse_board_string(text: str) -> dict:
    result = {
        "rows": None,
        "columns": None,
        "mines": None,
        "game_mode": None,
        "render": "ascii",
        "real": None,
        "view": None,
    }
    lines = text.splitlines()
    section = None
    board_rows = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if "Render:" in stripped:
                _, _, r = stripped.partition("Render:")
                result["render"] = r.strip()
            continue

        if stripped == "[real]":
            section = "real"
            board_rows = []
            continue
        if stripped == "[view]":
            section = "view"
            board_rows = []
            continue

        if ":" in stripped and section is None:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "rows":
                result["rows"] = int(value)
            elif key == "columns":
                result["columns"] = int(value)
            elif key == "mines":
                result["mines"] = int(value)
            elif key == "game_mode":
                result["game_mode"] = value
            continue

        if section in ("real", "view"):
            board_rows.append(stripped)
            result[section] = board_rows

    return result


def board_string_to_game_board(text: str) -> Tuple[List[List[int]], str]:
    parsed = parse_board_string(text)
    if parsed["view"]:
        board_rows = parsed["view"]
        source = "view"
    elif parsed["real"]:
        board_rows = parsed["real"]
        source = "real"
    else:
        return [], ""

    is_emoji = parsed["render"] == "emoji"
    parse_fn = _parse_view_line_emoji if is_emoji else _parse_view_line_ascii

    game_board = [parse_fn(line) for line in board_rows]
    return game_board, source


_VIEW_CHARS_ASCII = set("UF*?X@#012345678")


def _is_raw_view_ascii_line(line: str) -> bool:
    return all(ch in _VIEW_CHARS_ASCII for ch in line)


def _is_raw_view_emoji_line(line: str) -> bool:
    if any(ch in _EMOJI_TO_ASCII for ch in line):
        return True
    if _EMOJI_DIGIT_SUFFIX in line:
        return True
    return False


def _try_parse_raw_view(text: str) -> Tuple[List[List[int]], int, str]:
    lines = [l.rstrip("\r") for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return [], -1, ""

    is_emoji = _is_raw_view_emoji_line(lines[0])
    if is_emoji:
        if not all(_is_raw_view_emoji_line(l) for l in lines):
            return [], -1, ""
        parse_fn = _parse_view_line_emoji
        game_board = [parse_fn(l) for l in lines]
        # Count bomba and unmarked mines as mines in emoji mode
        mine_count = sum(
            1 for row in game_board for cell in row if cell in (-1, CELL_STEPPED_MINE, CELL_UNMARKED_MINE)
        )
    else:
        if not all(_is_raw_view_ascii_line(l) for l in lines):
            return [], -1, ""
        width = len(lines[0])
        if any(len(l) != width for l in lines):
            return [], -1, ""
        parse_fn = _parse_view_line_ascii
        game_board = [parse_fn(l) for l in lines]
        # Count * (mine) and @ (unmarked mine) as mines in ascii mode
        mine_count = sum(
            1 for row in game_board for cell in row if cell in (-1, CELL_STEPPED_MINE, CELL_UNMARKED_MINE)
        )

    width = len(game_board[0])
    if any(len(r) != width for r in game_board):
        return [], -1, ""
    return game_board, mine_count, "raw_view"


def _try_parse_raw_real(text: str) -> Tuple[List[List[int]], int, str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return [], -1, ""
    rows = []
    mine_count = 0
    for line in lines:
        tokens = [t.strip() for t in line.replace(",", " ").split()]
        if not tokens:
            return [], -1, ""
        try:
            int_row = [int(t) for t in tokens]
            mine_count += sum(1 for v in int_row if v in (-1, 9))
            rows.append(int_row)
        except ValueError:
            return [], -1, ""
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        return [], -1, ""
    game_board = [
        [10 if cell in (-1, 9) else cell for cell in row] for row in rows]
    return game_board, mine_count, "raw_real"


def parse_board_text(text: str) -> Tuple[List[List[int]], int, str]:
    """Parse clipboard text as .board format or real board array.
    Returns (board, mines, source) where source is "view", "real", "array",
    "raw_view", "raw_real", or "".
    mines is -1 if unknown.
    """
    board, source = board_string_to_game_board(text)
    if board:
        parsed = parse_board_string(text)
        mines = parsed.get("mines", -1)
        if mines is None:
            mines = -1
        return board, mines, source

    try:
        import json
        data = json.loads(text)
        if isinstance(data, list) and all(isinstance(row, list) for row in data):
            mine_count = sum(
                1 for row in data for cell in row if cell in (-1, 9))
            game_board = [
                [10 if cell in (-1, 9) else int(cell) for cell in row]
                for row in data
            ]
            return game_board, mine_count, "array"
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    board, mines, source = _try_parse_raw_view(text)
    if board:
        return board, mines, source

    board, mines, source = _try_parse_raw_real(text)
    if board:
        return board, mines, source

    return [], -1, ""
