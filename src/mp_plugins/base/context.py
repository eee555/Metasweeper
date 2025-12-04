from ._data import _BaseData
from .mode import PluginStatus
from datetime import datetime
from typing import List


class BaseContext(_BaseData):
    """
    上下文基类
    """

    name: str = ""
    version: str = ""


class PluginContext(BaseContext):
    """
    插件上下文
    """

    pid: int = 0
    name: str = ""
    display_name: str = ""
    description: str = ""
    version: str = ""
    author: str = ""
    author_email: str = ""
    url: str = ""
    status: PluginStatus = PluginStatus.Stopped
    heartbeat: float = datetime.now().timestamp()
    subscribers: List[str] = []
