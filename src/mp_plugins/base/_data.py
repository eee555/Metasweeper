from typing import Type
from msgspec import Struct, json


class _BaseData(Struct):
    """
    数据基类
    """

    def copy(self):
        new_data = json.decode(json.encode(self), type=type(self))
        return new_data


_subclass_cache = {}


def get_subclass_by_name(name: str) -> Type[_BaseData] | None:
    """
    根据类名获取 BaseEvent 的派生类（支持多级继承），带缓存
    """
    global _subclass_cache
    if name in _subclass_cache:
        return _subclass_cache[name]

    def _iter_subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from _iter_subclasses(sub)

    for subcls in _iter_subclasses(_BaseData):
        _subclass_cache[subcls.__name__] = subcls
        if subcls.__name__ == name:
            return subcls

    return None
