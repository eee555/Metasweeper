import os
import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def clamp_widget_to_screen(widget, screen=None):
    """把窗口钳制回屏幕可用区域内，防止窗口留在已断开的显示器上。

    先收回右/下越界，再保证不越左/上边界（左上优先）；以可用区为准，
    即排除任务栏/程序坞/菜单栏。screen 为 None 时取窗口当前所在屏幕。
    """
    if screen is None:
        screen = widget.screen()
    avail = screen.availableGeometry()
    x, y = widget.x(), widget.y()
    if x + widget.width() > avail.right() + 1:
        x = avail.right() + 1 - widget.width()
    if y + widget.height() > avail.bottom() + 1:
        y = avail.bottom() + 1 - widget.height()
    if x < avail.left():
        x = avail.left()
    if y < avail.top():
        y = avail.top()
    widget.move(x, y)


def place_detached_panel(panel, anchor, saved_x=None, saved_y=None):
    """放置可拖拽记忆位置的分离窗口（计数器、录像控制台等）。

    首次启动（无记忆位置）时贴合主窗口左侧、顶边对齐，保证面板出现在
    用户视野内。恢复记忆位置时：位置仍落在任一已连接屏幕内（哪怕部分
    越界，只要能抓到）就原样保留，尊重双屏用户的摆放；整体落在所有
    屏幕之外（如扩展屏断开后单屏启动）时，无边框面板不可见也拖不回来，
    此时钳制回主窗口所在屏幕。
    """
    if saved_x is None or saved_y is None:
        panel.move(anchor.x() - panel.width(), anchor.y())
    else:
        panel.move(saved_x, saved_y)
        for screen in QApplication.screens():
            if screen.availableGeometry().intersects(panel.geometry()):
                return panel.pos()
    clamp_widget_to_screen(panel, anchor.screen())
    return panel.pos()


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
    elif mode == 11:
        return _translate("Form", "双击递归")
    elif mode == 12:
        return _translate("Form", "标雷递归")
    elif mode == 13:
        return _translate("Form", "双击标雷递归")
    elif mode == 14:
        return _translate("Form", "无猜双击递归")
    elif mode == 15:
        return _translate("Form", "无猜标雷递归")
    elif mode == 16:
        return _translate("Form", "无猜双击标雷递归")
