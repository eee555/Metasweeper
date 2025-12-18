from enum import Enum


class ValueEnum(Enum):
    def __eq__(self, value: object) -> bool:
        if isinstance(value, Enum):
            return self.value == value.value
        return self.value == value  # 支持直接比较 value

    def __str__(self) -> str:
        return self.name


class PluginStatus(ValueEnum):
    """
    插件状态
    """

    Running = "running"
    Stopped = "stopped"
    Dead = "dead"


class MessageMode(ValueEnum):
    Event = "event"
    Context = "context"
    Error = "error"
    Unknown = "unknown"
    Heartbeat = "heartbeat"
