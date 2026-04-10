"""
插件配置持久化管理

负责插件配置的加载和保存到 JSON 文件。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from .config_types.other_info import OtherInfoBase

if TYPE_CHECKING:
    pass


class PluginConfigManager:
    """
    插件配置持久化管理

    目录结构::

        data/plugin_data/
            ├── hello_world/
            │   └── config.json
            └── stats_plugin/
                └── config.json

    用法::

        from plugin_manager.config_manager import PluginConfigManager
        from plugin_manager.app_paths import get_plugin_data_dir

        manager = PluginConfigManager(Path("data/plugin_data"))
        config = MyPluginOtherInfo()
        manager.load("my_plugin", config)
        # ... 使用 config ...
        manager.save("my_plugin", config)
    """

    CONFIG_FILENAME = "config.json"

    def __init__(self, base_dir: Path) -> None:
        """
        初始化配置管理器

        Args:
            base_dir: 配置文件基础目录，通常为 data/plugin_data
        """
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _config_path(self, plugin_name: str) -> Path:
        """
        获取插件配置文件路径

        Args:
            plugin_name: 插件名称

        Returns:
            配置文件完整路径
        """
        return self._base_dir / plugin_name / self.CONFIG_FILENAME

    def load(self, plugin_name: str, config: OtherInfoBase) -> OtherInfoBase:
        """
        加载插件配置

        如果配置文件不存在或加载失败，则使用默认值。

        Args:
            plugin_name: 插件名称
            config: 配置容器实例

        Returns:
            加载后的配置容器（同一实例）
        """
        path = self._config_path(plugin_name)

        if not path.exists():
            # 配置文件不存在，使用默认值
            return config

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                config.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # 加载失败，使用默认值
            # 可选：记录日志
            pass

        return config

    def save(self, plugin_name: str, config: OtherInfoBase) -> None:
        """
        保存插件配置

        Args:
            plugin_name: 插件名称
            config: 配置容器实例
        """
        path = self._config_path(plugin_name)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = config.to_dict()
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def delete(self, plugin_name: str) -> None:
        """
        删除插件配置文件

        Args:
            plugin_name: 插件名称
        """
        path = self._config_path(plugin_name)
        if path.exists():
            path.unlink()

        # 如果目录为空，也删除目录
        dir_path = path.parent
        if dir_path.exists() and not any(dir_path.iterdir()):
            dir_path.rmdir()

    def exists(self, plugin_name: str) -> bool:
        """
        检查插件配置文件是否存在

        Args:
            plugin_name: 插件名称

        Returns:
            True 表示存在
        """
        return self._config_path(plugin_name).exists()
