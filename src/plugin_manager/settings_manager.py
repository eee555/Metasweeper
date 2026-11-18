"""
插件管理器基础设置管理

管理插件管理器自身的设置，如日志等级等。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from .atomic_json import atomic_write_json

LogLevel = Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
DEFAULT_PLUGIN_PIP_INDEXES = [
    "https://pypi.org/simple",
    "https://pypi.tuna.tsinghua.edu.cn/simple",
]


def normalize_pip_indexes(urls: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw in urls:
        url = raw.strip().rstrip("/")
        if not url:
            continue
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"无效的 Python 包源 URL：{raw}")
        if url not in normalized:
            normalized.append(url)
    return normalized


@dataclass
class BasicSettings:
    """插件管理器基础设置"""
    # 主进程文件日志等级
    file_log_level: LogLevel = "DEBUG"
    # 日志查看器设置
    viewer_log_level: LogLevel = "INFO"
    viewer_auto_scroll: bool = True
    viewer_show_source: bool = False
    # 插件依赖库目录（库目录或虚拟环境目录），空表示使用默认路径
    plugin_lib_dir: str = ""
    # 手动安装插件依赖时使用的 PyPI 主源及备用源
    plugin_pip_indexes: list[str] = field(
        default_factory=lambda: DEFAULT_PLUGIN_PIP_INDEXES.copy())
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "BasicSettings":
        lib_dir = data.get("plugin_lib_dir", "")
        raw_indexes = data.get("plugin_pip_indexes", DEFAULT_PLUGIN_PIP_INDEXES)
        try:
            indexes = normalize_pip_indexes(raw_indexes) if isinstance(raw_indexes, list) else DEFAULT_PLUGIN_PIP_INDEXES.copy()
        except (AttributeError, TypeError, ValueError):
            indexes = DEFAULT_PLUGIN_PIP_INDEXES.copy()
        return cls(
            file_log_level=data.get("file_log_level", "DEBUG"),
            viewer_log_level=data.get("viewer_log_level", "INFO"),
            viewer_auto_scroll=data.get("viewer_auto_scroll", True),
            viewer_show_source=data.get("viewer_show_source", False),
            plugin_lib_dir=lib_dir if isinstance(lib_dir, str) else "",
            plugin_pip_indexes=indexes,
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
        self._data_dir = Path(data_dir).resolve()
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

    @property
    def plugin_lib_dir(self) -> str:
        configured = self._settings.plugin_lib_dir.strip()
        if not configured:
            return str(self.default_plugin_lib_dir)
        return str(Path(configured).expanduser().resolve())

    @property
    def default_plugin_lib_dir(self) -> Path:
        return self._data_dir / "plugin_libs"

    @property
    def plugin_pip_indexes(self) -> list[str]:
        return self._settings.plugin_pip_indexes.copy()

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

    def set_plugin_lib_dir(self, path: str) -> None:
        """设置插件依赖库目录，留空恢复默认路径。"""
        raw = path.strip()
        self._settings.plugin_lib_dir = str(Path(raw).expanduser().resolve()) if raw else ""
        self.save()

    def set_plugin_pip_indexes(self, urls: list[str]) -> None:
        """设置手动安装插件依赖时使用的 Python 包源列表。"""
        self._settings.plugin_pip_indexes = normalize_pip_indexes(urls)
        self.save()
