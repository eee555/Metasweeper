from typing import Any, Dict, List, Sequence
from ._data import _BaseData, get_subclass_by_name
import msgspec


class BaseSetting(_BaseData):
    name: str = ""
    value: Any = None
    setting_type: str = "BaseSetting"


class TextSetting(BaseSetting):
    value: str = ""
    placeholder: str = ""
    setting_type: str = "TextSetting"


class NumberSetting(BaseSetting):
    value: float = 0.0
    min_value: float = 0.0
    max_value: float = 100.0
    step: float = 1.0
    setting_type: str = "NumberSetting"


class BoolSetting(BaseSetting):
    value: bool = False
    description: str = ""
    setting_type: str = "BoolSetting"


class SelectSetting(BaseSetting):
    value: str = ""
    options: List[str] = []
    setting_type: str = "SelectSetting"


class BaseConfig(_BaseData):
    """ """

    pass


def Get_settings(data: Dict[str, Dict[str, Any]]) -> Dict[str, BaseSetting]:
    settings = {}
    for key, value in data.items():
        if settings_type := value.get("setting_type"):
            setting: BaseSetting = msgspec.json.decode(
                msgspec.json.encode(value), type=get_subclass_by_name(settings_type)
            )
            settings[key] = setting
    return settings
