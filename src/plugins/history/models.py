"""
历史记录数据模型
"""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any

from PySide6.QtCore import QCoreApplication

from shared_types.enums import GameBoardState, GameMode, GameLevel, BaseDiaPlayEnum

from utils.plugin_i18n import PluginTranslate

_translate = PluginTranslate("HistoryPlugin")


class LogicSymbol:
    """逻辑连接符（与/或）。持久化使用稳定的数值，显示时翻译。"""

    And = 0
    Or = 1

    _SQL = {0: "and", 1: "or"}
    _known_names: dict[str, int] = {}
    # 旧版配置按界面译文持久化，覆盖源语言与全部内置语言，
    # 保证在其他语言（或翻译器尚未就绪）的环境下也能恢复。
    _ALIASES: dict[str, int] = {
        "与": 0, "and": 0, "かつ": 0,
        "或": 1, "or": 1, "または": 1,
    }

    @classmethod
    def _labels(cls):
        labels = {0: _translate("HistoryPlugin", "与"), 1: _translate("HistoryPlugin", "或")}
        cls._known_names.update((name, value) for value, name in labels.items())
        return labels

    @classmethod
    def display_names(cls):
        return [cls(value).display_name for value in (cls.And, cls.Or)]

    @classmethod
    def from_display_name(cls, name: str):
        try:
            value = int(name)
        except (TypeError, ValueError):
            cls._labels()
            key = str(name).strip()
            if key in cls._known_names:
                value = cls._known_names[key]
            elif key in cls._ALIASES:
                value = cls._ALIASES[key]
            else:
                raise ValueError(name)
        if value not in cls._SQL:
            raise ValueError(name)
        return cls(value)

    @classmethod
    def to_stable(cls, name: str) -> str | None:
        """把任意语言的显示名或编号转为稳定编号；无法识别时返回 None。"""
        try:
            return str(cls.from_display_name(name).value)
        except (TypeError, ValueError):
            return None

    def __init__(self, value: int):
        if value not in self._SQL:
            raise ValueError(value)
        self.value = value

    @property
    def display_name(self):
        return self._labels()[self.value]

    @property
    def to_sql(self):
        return self._SQL[self.value]


class CompareSymbol:
    """比较符号"""

    Equal = 0
    NotEqual = 1
    GreaterThan = 2
    LessThan = 3
    GreaterThanOrEqual = 4
    LessThanOrEqual = 5
    Contains = 6
    NotContains = 7
    Like = 8
    NotLike = 9
    _known_names: dict[str, int] = {}
    # 与 LogicSymbol 同理：兼容旧版按译文持久化的配置（全部内置语言）。
    _ALIASES: dict[str, int] = {
        "等于": 0, "equals": 0, "Gleich": 0, "等しい": 0, "Równe": 0,
        "不等于": 1, "does not equal": 1, "Ungleich": 1, "等しくない": 1, "Różne": 1,
        "大于": 2, "greater than": 2, "Größer als": 2, "より大": 2, "Większe niż": 2,
        "小于": 3, "less than": 3, "Kleiner als": 3, "より小": 3, "Mniejsze niż": 3,
        "大于等于": 4, "greater than or equal to": 4, "Größer oder gleich": 4,
        "以上": 4, "Większe lub równe niż": 4,
        "小于等于": 5, "less than or equal to": 5, "Kleiner oder gleich": 5,
        "以下": 5, "Mniejsze lub równe niż": 5,
        "包含": 6, "in list": 6, "Enthält": 6, "含む": 6, "Zawiera": 6,
        "不包含": 7, "not in list": 7, "Enthält nicht": 7, "含まない": 7, "Nie zawiera": 7,
        "包含子串": 8, "Contains substring": 8, "Enthält Teilzeichenfolge": 8,
        "部分文字列を含む": 8, "Zawiera podciągu": 8,
        "不含子串": 9, "Does not contain substring": 9,
        "Enthält keine Teilzeichenfolge": 9, "部分文字列を含まない": 9,
        "Nie zawiera podciągu": 9,
    }

    @classmethod
    def _labels(cls):
        labels = {
            0: _translate("HistoryPlugin", "等于"),
            1: _translate("HistoryPlugin", "不等于"),
            2: _translate("HistoryPlugin", "大于"),
            3: _translate("HistoryPlugin", "小于"),
            4: _translate("HistoryPlugin", "大于等于"),
            5: _translate("HistoryPlugin", "小于等于"),
            6: _translate("HistoryPlugin", "包含"),
            7: _translate("HistoryPlugin", "不包含"),
            8: _translate("HistoryPlugin", "包含子串"),
            9: _translate("HistoryPlugin", "不含子串"),
        }
        cls._known_names.update((name, value) for value, name in labels.items())
        return labels

    _SQL = {
        0: "=",
        1: "!=",
        2: ">",
        3: "<",
        4: ">=",
        5: "<=",
        6: "in",
        7: "not in",
        8: "like",
        9: "not like",
    }

    @classmethod
    def display_names(cls):
        return [cls(value).display_name for value in range(len(cls._SQL))]

    @classmethod
    def from_display_name(cls, name: str):
        try:
            value = int(name)
        except (TypeError, ValueError):
            cls._labels()
            key = str(name).strip()
            if key in cls._known_names:
                value = cls._known_names[key]
            elif key in cls._ALIASES:
                value = cls._ALIASES[key]
            else:
                raise ValueError(name)
        if value not in cls._SQL:
            raise ValueError(name)
        return cls(value)

    @classmethod
    def to_stable(cls, name: str) -> str | None:
        """把任意语言的显示名或编号转为稳定编号；无法识别时返回 None。"""
        try:
            return str(cls.from_display_name(name).value)
        except (TypeError, ValueError):
            return None

    def __init__(self, value: int):
        if value not in self._SQL:
            raise ValueError(value)
        self.value = value

    @property
    def display_name(self):
        return self._labels()[self.value]

    @property
    def to_sql(self):
        return self._SQL[self.value]


class SortOrder:
    """排序方向。持久化使用稳定编号，显示时翻译。"""

    Ascending = 0
    Descending = 1

    _SQL = {0: "ASC", 1: "DESC"}
    _known_names: dict[str, int] = {}
    # 旧版排序配置按界面译文持久化，覆盖源语言与全部内置语言。
    _ALIASES: dict[str, int] = {
        "升序": 0, "Ascending": 0, "Aufsteigend": 0, "昇順": 0, "Rosnąco": 0,
        "降序": 1, "Descending": 1, "Absteigend": 1, "降順": 1, "Malejąco": 1,
    }

    @classmethod
    def _labels(cls):
        labels = {
            0: _translate("HistoryPlugin", "升序"),
            1: _translate("HistoryPlugin", "降序"),
        }
        cls._known_names.update((name, value) for value, name in labels.items())
        return labels

    @classmethod
    def from_text(cls, name: str):
        try:
            value = int(name)
        except (TypeError, ValueError):
            cls._labels()
            key = str(name).strip()
            if key in cls._known_names:
                value = cls._known_names[key]
            elif key in cls._ALIASES:
                value = cls._ALIASES[key]
            else:
                raise ValueError(name)
        if value not in cls._SQL:
            raise ValueError(name)
        return cls(value)

    @classmethod
    def to_stable(cls, name: str) -> str | None:
        """把任意语言的显示名或编号转为稳定编号；无法识别时返回 None。"""
        try:
            return str(cls.from_text(name).value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def display_names(cls):
        return [cls(value).display_name for value in (cls.Ascending, cls.Descending)]

    def __init__(self, value: int):
        if value not in self._SQL:
            raise ValueError(value)
        self.value = value

    @property
    def display_name(self):
        return self._labels()[self.value]

    @property
    def to_sql(self):
        return self._SQL[self.value]


# ── 历史记录数据 ──────────────────────────────────────────

class HistoryData:
    """历史记录数据行（纯数据类，用类属性定义字段）"""

    replay_id: int = 0
    game_state: GameBoardState = GameBoardState.Display
    nf: int = 0
    row: int = 0
    column: int = 0
    mine_num: int = 0
    rtime: float = 0.0
    left: int = 0
    right: int = 0
    double: int = 0
    level: GameLevel = GameLevel.BEGINNER
    cl: int = 0
    ce: int = 0
    rce: int = 0
    lce: int = 0
    dce: int = 0
    bbbv: int = 0
    bbbv_solved: int = 0
    zini: int = 0
    flag: int = 0
    path: float = 0.0
    start_time: datetime = datetime.now()
    end_time: datetime = datetime.now()
    mode: GameMode = GameMode.Standard
    software: str = ""
    player_identifier: str = ""
    race_identifier: str = ""
    unique_identifier: str = ""
    is_official: int = 0
    is_fair: int = 0
    op: int = 0
    isl: int = 0
    pluck: float = 0.0
    board: str = ""

    @classmethod
    def get_field_value(cls, field_name: str):
        for name, value in inspect.getmembers(cls):
            if (
                not name.startswith("__")
                and not callable(value)
                and not name.startswith("_")
                and name == field_name
            ):
                return value

    @classmethod
    def fields(cls):
        return [
            name
            for name, value in inspect.getmembers(cls)
            if not name.startswith("__")
            and not callable(value)
            and not name.startswith("_")
        ]

    @classmethod
    def query_all(cls):
        return "select * from history"

    @classmethod
    def from_dict(cls, data: dict):
        instance = cls()
        for name, value in inspect.getmembers(cls):
            if (
                not name.startswith("__")
                and not callable(value)
                and not name.startswith("_")
            ):
                new_value = data.get(name)
                if new_value is None:
                    continue
                # Enum 类型 - 使用 try_create 处理值不在枚举中的情况
                if isinstance(value, BaseDiaPlayEnum):
                    value = value.__class__.try_create(new_value)
                # 时间戳字段转换
                elif isinstance(value, datetime):
                    if new_value:
                        value = datetime.fromtimestamp(new_value / 1_000_000)
                elif isinstance(value, float):
                    value = round(new_value, 4)
                else:
                    value = new_value
                setattr(instance, name, value)
        # 计算列：视图查询多出的字段，动态挂载
        known_fields = set(cls.fields())
        for key, val in data.items():
            if key not in known_fields and not key.startswith("_"):
                if isinstance(val, float):
                    val = round(val, 4)
                setattr(instance, key, val)
        return instance
