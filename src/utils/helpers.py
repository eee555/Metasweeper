import os
import sys

from PySide6.QtCore import QCoreApplication


def trans_expression(expression: str):
    expression = expression.lower().strip()[:10000]
    expression = expression.replace("3bv", "bbbv")
    expression = expression.replace("opening", "op")
    expression = expression.replace("click", "cl")
    # expression = expression.replace("\"", "'")
    expression = expression.replace("island", "isl")
    expression = expression.replace("chording", "double")
    expression = expression.replace("solved_bbbv", "bbbv_solved")
    expression = expression.replace("mine_num", "minenum")
    expression = expression.replace("width", "column")
    expression = expression.replace("height", "row")
    return expression


def trans_game_mode(mode: int) -> str:
    _translate = QCoreApplication.translate
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
        return _translate("Form", "经典无猜")
    elif mode == 6:
        return _translate("Form", "强无猜")
    elif mode == 7:
        return _translate("Form", "弱无猜")
    elif mode == 8:
        return _translate("Form", "准无猜")
    elif mode == 9:
        return _translate("Form", "强可猜")
    elif mode == 10:
        return _translate("Form", "弱可猜")
