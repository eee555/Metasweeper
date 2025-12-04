import uuid
from msgspec import Struct, json
from typing import Any, Union, Type, TypeVar, Generic, Optional
from ._data import _BaseData, get_subclass_by_name
from datetime import datetime
from .mode import MessageMode

BaseData = TypeVar("BaseData", bound=_BaseData)


class Message(_BaseData):
    """
    一个消息类用于包装事件及消息的基本信息
    """

    id = str(uuid.uuid4())
    data: Any = None
    timestamp: datetime = datetime.now()
    mode: MessageMode = MessageMode.Unknown
    Source: str = "main"  # 来源，也就是消息的发送者
    class_name: str = ""

    def copy(self):
        new_message = json.decode(json.encode(self), type=Message)
        return new_message

    def __post_init__(self):
        cls = get_subclass_by_name(self.class_name)
        if cls:
            # 将原始 dict 解析成对应的 Struct
            if isinstance(self.data, dict):
                self.data = cls(**self.data)
