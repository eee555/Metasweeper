"""
插件管理器基础设置管理

管理插件管理器自身的设置，如日志等级等。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

from .atomic_json import atomic_write_json

LogLevel = Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass
class BasicSettings:
    """插件管理器基础设置"""
    # 主进程文件日志等级
    file_log_level: LogLevel = "DEBUG"
    # 日志查看器设置
    viewer_log_level: LogLevel = "INFO"
    viewer_auto_scroll: bool = True
    viewer_show_source: bool = False
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "BasicSettings":
        return cls(
            file_log_level=data.get("file_log_level", "DEBUG"),
            viewer_log_level=data.get("viewer_log_level", "INFO"),
            viewer_auto_scroll=data.get("viewer_auto_scroll", True),
            viewer_show_source=data.get("viewer_show_source", False),
        )


class SettingsManager:
    """
    插件管理器设置持久化管理
    
    设置文件路径: <data_dir>/plugin_manager_settings.json
    """
    
    SETTINGS_FILENAME = "plugin_manager_settings.json"
    
    # 支持的日志等级
    LOG_LEVELS: list[LogLevel] = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._settings = BasicSettings()
        self._load()
    
    def _settings_path(self) -> Path:
        return self._data_dir / self.SETTINGS_FILENAME
    
    def _load(self) -> None:
        """从文件加载设置"""
        path = self._settings_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._settings = BasicSettings.from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError,
                    ValueError, AttributeError, UnicodeDecodeError, OSError):
                pass

    def save(self) -> None:
        """保存设置到文件"""
        atomic_write_json(
            self._settings_path(), self._settings.to_dict(),
            ensure_ascii=False, trailing_newline=False)
    
    @property
    def settings(self) -> BasicSettings:
        return self._settings
    
    @property
    def file_log_level(self) -> LogLevel:
        return self._settings.file_log_level
    
    @property
    def viewer_log_level(self) -> LogLevel:
        return self._settings.viewer_log_level
    
    @property
    def viewer_auto_scroll(self) -> bool:
        return self._settings.viewer_auto_scroll
    
    @property
    def viewer_show_source(self) -> bool:
        return self._settings.viewer_show_source
    
    def set_file_log_level(self, level: LogLevel) -> None:
        """设置主进程文件日志等级"""
        if level in self.LOG_LEVELS:
            self._settings.file_log_level = level
            self.save()
    
    def set_viewer_log_level(self, level: LogLevel) -> None:
        """设置日志查看器日志等级"""
        if level in self.LOG_LEVELS:
            self._settings.viewer_log_level = level
            self.save()
    
    def set_viewer_auto_scroll(self, enabled: bool) -> None:
        """设置日志查看器自动滚动"""
        self._settings.viewer_auto_scroll = enabled
        self.save()
    
    def set_viewer_show_source(self, enabled: bool) -> None:
        """设置日志查看器显示来源"""
        self._settings.viewer_show_source = enabled
        self.save()
