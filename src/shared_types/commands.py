"""
扫雷游戏控制指令定义
"""
from __future__ import annotations

from typing import List, Optional

from lib_zmq_plugins.shared.base import BaseCommand

from .enums import GameLevel, GameMode


class NewGameCommand(BaseCommand, tag="new_random_game"):
    """
    新随机游戏指令，不安全，official和fair为false。
    
    Attributes:
        level: 游戏难度，使用 GameLevel 枚举值
            - 3: 初级 (8x8, 10雷)
            - 4: 中级 (16x16, 40雷)
            - 5: 高级 (16x30, 99雷)
            - 6: 自定义（使用 rows/cols/mines）
        rows: 行数（自定义模式时使用）
        cols: 列数（自定义模式时使用）
        mines: 地雷数（自定义模式时使用）
        mode: 可选，游戏模式，使用 GameMode 枚举值
    """
    level: int = 5
    rows: Optional[int] = None
    cols: Optional[int] = None
    mines: Optional[int] = None
    mode: Optional[int] = GameMode.Standard.value




class NewPresetGameCommand(BaseCommand, tag="new_preset_game"):
    """
    新预设游戏指令，official和fair可能为true。但是gamemode必定为upk。
    
    Attributes:
        board: 可选，预设局面，-1表示雷
        mode: 可选，游戏模式，使用 GameMode 枚举值
    """
    board: List[List[int]] = None
    mode: Optional[int] = GameMode.Standard.value



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

    
class InitOpenCommand(BaseCommand, tag="init_open"):
    """
    初始化翻开指令。此指令是安全的，但是要求局面使用预设局面，且最终模式为upk。
    此指令仅会在局面初始化时，翻开指定的格子。游戏过程中是否使用，还需要讨论，目前不可以。
    
    Attributes:
        row: 行索引（从 0 开始）
        col: 列索引（从 0 开始）
    """
    row: int = 0
    col: int = 0


COMMAND_TYPES = [NewGameCommand, NewPresetGameCommand, MouseClickCommand, InitOpenCommand]