"""
共享类型模块

定义主进程和插件管理器共用的类型
"""
from .events import (
    BoardUpdateEvent,
    GameStatusChangeEvent,
    LanguageChangeEvent,
    EVENT_TYPES,
)

from .commands import (
    NewGameCommand,
    NewPresetGameCommand,
    MouseClickCommand,
    SetSkinCommand,
    COMMAND_TYPES,
    SKIN_CELL_KEYS,
    SKIN_LED_KEYS,
    SKIN_FACE_KEYS,
    SKIN_COLOR_KEYS,
)

from .queries import (
    GetBoardStateQuery,
    GetGameStatusQuery,
    GetGameContextQuery,
    BoardStateResult,
    GameStatusResult,
    GameContextResult,
    ControlPermissions,
    QUERY_TYPES,
    QUERY_RESULT_TYPES,
)

from .enums import (
    BaseDiaPlayEnum,
    GameBoardState,
    MouseState,
    GameMode,
    GameLevel,
    ButtonEventType,
)

__all__ = [
    # 事件
    "BoardUpdateEvent",
    "GameStatusChangeEvent",
    "LanguageChangeEvent",
    "EVENT_TYPES",
    # 指令
    "NewGameCommand",
    "NewPresetGameCommand",
    "MouseClickCommand",
    "SetSkinCommand",
    "COMMAND_TYPES",
    "SKIN_CELL_KEYS",
    "SKIN_LED_KEYS",
    "SKIN_FACE_KEYS",
    "SKIN_COLOR_KEYS",
    # 查询
    "GetBoardStateQuery",
    "GetGameStatusQuery",
    "GetGameContextQuery",
    "BoardStateResult",
    "GameStatusResult",
    "GameContextResult",
    "ControlPermissions",
    "QUERY_TYPES",
    "QUERY_RESULT_TYPES",
    # 枚举
    "BaseDiaPlayEnum",
    "GameBoardState",
    "MouseState",
    "GameMode",
    "GameLevel",
    "ButtonEventType",
]
