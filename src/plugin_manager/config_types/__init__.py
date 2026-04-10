"""
插件配置类型系统

提供插件自定义配置的定义、UI 反射和持久化支持。

用法::

    from plugin_manager.config_types import (
        OtherInfoBase, BoolConfig, IntConfig, ChoiceConfig, TextConfig,
        ColorConfig, FileConfig, PathConfig, LongTextConfig, RangeConfig,
    )

    class MyPluginOtherInfo(OtherInfoBase):
        auto_save = BoolConfig(True, "自动保存")
        interval = IntConfig(30, "间隔(秒)", min_value=1, max_value=300)
        theme = ChoiceConfig("dark", "主题", 
                            choices=[("light", "明亮"), ("dark", "暗黑")])
        theme_color = ColorConfig("#1976d2", "主题颜色")
        export_path = FileConfig("", "导出文件", filter="JSON (*.json)", save_mode=True)
        log_dir = PathConfig("", "日志目录")
        description = LongTextConfig("", "描述", placeholder="输入描述...")
        time_range = RangeConfig((0, 300), "时间范围(秒)")
"""

from .base_config import BaseConfig
from .bool_config import BoolConfig
from .int_config import IntConfig
from .float_config import FloatConfig
from .choice_config import ChoiceConfig
from .text_config import TextConfig
from .color_config import ColorConfig
from .file_config import FileConfig
from .path_config import PathConfig
from .long_text_config import LongTextConfig
from .range_config import RangeConfig
from .other_info import OtherInfoBase

__all__ = [
    "BaseConfig",
    "BoolConfig",
    "IntConfig",
    "FloatConfig",
    "ChoiceConfig",
    "TextConfig",
    "ColorConfig",
    "FileConfig",
    "PathConfig",
    "LongTextConfig",
    "RangeConfig",
    "OtherInfoBase",
]
