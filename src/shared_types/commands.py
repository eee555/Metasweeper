"""
扫雷游戏控制指令定义
"""
from __future__ import annotations

from typing import Optional, List

from lib_zmq_plugins.shared.base import BaseCommand

from .enums import GameLevel


class NewGameCommand(BaseCommand, tag="new_game"):
    """
    新游戏指令
        mode: 游戏模式
            - 0: 标准模式
            - 4: Win7模式
            - 5: 经典无猜模式
            - 6: 强无猜模式
            - 7: 弱无猜模式
            - 8: 准无猜模式
            - 9: 强可猜模式
            - 10: 弱可猜模式
        rows: 行数（自定义模式时使用）
        cols: 列数（自定义模式时使用）
        mines: 地雷数（自定义模式时使用）
        pix_size: 格子像素大小
        board: 游戏局面（默认随机）
    """
    mode: Optional[int] = None
    rows: int = 16
    cols: int = 30
    mines: int = 99
    pix_size: Optional[int] = None
    board: Optional[List[List[int]]] = None


class MouseClickCommand(BaseCommand, tag="mouse_click"):
    """
    鼠标点击指令
    
    Attributes:
        row: 行索引（从 0 开始）
        col: 列索引（从 0 开始）
        button: 鼠标按钮
            - 0: 左键（揭开格子）
            - 1: 中键
            - 2: 右键（标旗）
        modifiers: 键盘修饰符（保留）
    """
    row: int = 0
    col: int = 0
    button: int = 0
    modifiers: int = 0


COMMAND_TYPES = [NewGameCommand, MouseClickCommand]