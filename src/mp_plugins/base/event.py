from ._data import _BaseData
from datetime import datetime
import uuid


class BaseEvent(_BaseData):
    """
    事件基类
    """

    timestamp: float = datetime.now().timestamp()
