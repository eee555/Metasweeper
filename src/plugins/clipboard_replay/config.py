"""
clipboard_replay - 配置定义
"""
from __future__ import annotations

from collections.abc import Iterable

from plugin_sdk import OtherInfoBase, BoolConfig
from .handlers import HANDLER_TYPES, ClipboardHandler
from utils.plugin_i18n import PluginTranslate

_translate = PluginTranslate("ClipboardReplay")


class ClipboardReplayConfig(OtherInfoBase):
    """插件配置"""

    enable_feature = BoolConfig(
        default=True,
        label=_translate("ClipboardReplay", "监听剪贴板（总开关）"),
        description=_translate("ClipboardReplay", "关闭时停用所有处理器，但保留各处理器的开关设置。"),
    )


def add_handler_fields(
    config_type: type[OtherInfoBase],
    handler_types: Iterable[type[ClipboardHandler]],
) -> None:
    fields = config_type.get_fields()
    for handler_type in handler_types:
        key = handler_type.config_key()
        if key in fields:
            raise ValueError(
                f"Duplicate clipboard handler configuration key: {key}")
        label = handler_type.display_name or handler_type.__name__
        field = BoolConfig(
            default=True,
            label=label,
            description=_translate("ClipboardReplay", "是否启用此处理器；仅在总开关打开时生效。"),
        )
        setattr(config_type, key, field)
        fields[key] = field


add_handler_fields(ClipboardReplayConfig, HANDLER_TYPES)
