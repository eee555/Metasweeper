"""
控制授权管理器

管理插件对控制命令的使用权限：
- 每个控制命令只能授权给一个插件
- 未授权的控制命令，所有插件都不能发送
- 授权变更时通知相关插件
- 持久化授权配置
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

import loguru

if TYPE_CHECKING:
    from lib_zmq_plugins.shared.base import BaseCommand

logger = loguru.logger.bind(name="ControlAuth")


class ControlAuthorizationManager(QObject):
    """
    控制授权管理器（单例）

    Signals:
        authorization_changed(str, str, bool): 授权变更信号
            - 参数: (tag, plugin_name, granted)
            - granted=True 表示授权，False 表示撤销
    """

    authorization_changed = Signal(str, str, bool)

    _instance: ControlAuthorizationManager | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    def instance(cls, config_dir: Path | None = None) -> ControlAuthorizationManager:
        """获取单例"""
        if cls._instance is None:
            cls._instance = cls(config_dir)
        return cls._instance

    def __init__(self, config_dir: Path | None = None):
        if getattr(self, '_initialized', False):
            return

        super().__init__()

        if config_dir is None:
            from plugin_manager.app_paths import get_data_dir
            config_dir = get_data_dir()

        self._file = config_dir / "control_authorization.json"
        self._authorizations: dict[str, str] = {}  # {tag: plugin_name}
        self._dirty = False

        self.load()
        self._initialized = True

    # ── 持久化 ─────────────────────────────────────────

    def load(self) -> None:
        """从文件加载授权配置"""
        if not self._file.exists():
            logger.debug(f"授权配置文件不存在: {self._file}")
            return

        try:
            data = json.loads(self._file.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                self._authorizations = {
                    k: v for k, v in data.items()
                    if isinstance(k, str) and isinstance(v, str)
                }
                logger.info(f"已加载 {len(self._authorizations)} 个控制授权")
        except Exception as e:
            logger.error(f"加载授权配置失败: {e}")
            self._authorizations = {}

    def save(self) -> None:
        """保存授权配置到文件"""
        if not self._dirty:
            return

        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(self._authorizations, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            self._dirty = False
            logger.debug(f"授权配置已保存: {self._file}")
        except Exception as e:
            logger.error(f"保存授权配置失败: {e}")

    # ── 核心方法 ─────────────────────────────────────────

    def _get_tag(self, command_type: type) -> str:
        """从命令类型获取 tag"""
        tag = getattr(command_type, '__struct_config__', None)
        if tag is not None:
            tag = getattr(tag, 'tag', None)
        if tag is None:
            raise ValueError(f"无法获取命令类型的 tag: {command_type}")
        return str(tag)

    def authorize(
        self,
        command_type: type,
        plugin_name: str,
    ) -> None:
        """
        授权控制类型给指定插件

        Args:
            command_type: 命令类型
            plugin_name: 插件名称
        """
        tag = self._get_tag(command_type)
        old_plugin = self._authorizations.get(tag)

        # 先通知旧插件被撤销
        if old_plugin is not None and old_plugin != plugin_name:
            logger.info(f"控制授权撤销: {tag} (原: {old_plugin})")
            self.authorization_changed.emit(tag, old_plugin, False)

        self._authorizations[tag] = plugin_name
        self._dirty = True

        logger.info(f"控制授权: {tag} -> {plugin_name}")

        # 通知新插件被授权
        self.authorization_changed.emit(tag, plugin_name, True)

    def revoke(
        self,
        command_type: type,
    ) -> str | None:
        """
        撤销授权

        Args:
            command_type: 命令类型

        Returns:
            被撤销授权的插件名称，如果原本就没有授权则返回 None
        """
        tag = self._get_tag(command_type)
        old_plugin = self._authorizations.pop(tag, None)

        if old_plugin is not None:
            self._dirty = True
            logger.info(f"控制授权撤销: {tag} (原: {old_plugin})")
            self.authorization_changed.emit(tag, old_plugin, False)

        return old_plugin

    def is_authorized(
        self,
        command_type: type,
        plugin_name: str,
    ) -> bool:
        """
        检查插件是否有授权

        Args:
            command_type: 命令类型
            plugin_name: 插件名称

        Returns:
            True 表示已授权
        """
        tag = self._get_tag(command_type)
        return self._authorizations.get(tag) == plugin_name

    def has_control_auth(
        self,
        command_type: type,
    ) -> bool:
        """
        检查该控制类型是否已授权给某个插件

        Args:
            command_type: 命令类型

        Returns:
            True 表示已授权给某个插件
        """
        tag = self._get_tag(command_type)
        return tag in self._authorizations

    def get_authorized_plugin(
        self,
        command_type: type,
    ) -> str | None:
        """
        获取该控制类型授权给的插件

        Args:
            command_type: 命令类型

        Returns:
            插件名称，未授权则返回 None
        """
        tag = self._get_tag(command_type)
        return self._authorizations.get(tag)

    # ── 批量操作 ─────────────────────────────────────────

    def get_all_control_types(self) -> list[type]:
        """获取所有控制类型"""
        from shared_types.commands import COMMAND_TYPES
        return list(COMMAND_TYPES)

    def get_authorization_status(self) -> dict[str, str | None]:
        """
        获取所有控制类型的授权状态

        Returns:
            {tag: plugin_name | None}
        """
        result = {}
        for cmd_type in self.get_all_control_types():
            try:
                tag = self._get_tag(cmd_type)
                result[tag] = self._authorizations.get(tag)
            except ValueError:
                continue
        return result

    def validate_authorizations(
        self,
        loaded_plugins: set[str],
    ) -> list[tuple[str, str]]:
        """
        验证授权配置，清除无效插件的授权

        Args:
            loaded_plugins: 已加载的插件名称集合

        Returns:
            被清除的授权列表 [(tag, plugin_name), ...]
        """
        removed = []
        to_remove = []

        for tag, plugin_name in self._authorizations.items():
            if plugin_name not in loaded_plugins:
                to_remove.append(tag)
                removed.append((tag, plugin_name))

        for tag in to_remove:
            del self._authorizations[tag]
            self._dirty = True

        if removed:
            logger.warning(
                f"清除无效授权: {removed} (插件未加载)"
            )

        return removed

    def clear_all(self) -> None:
        """清除所有授权"""
        for tag, plugin_name in list(self._authorizations.items()):
            self.authorization_changed.emit(tag, plugin_name, False)

        self._authorizations.clear()
        self._dirty = True
        logger.info("已清除所有控制授权")

    # ── 批量设置 ─────────────────────────────────────────

    def set_authorizations(self, authorizations: dict[type, str | None]) -> None:
        """
        批量设置授权

        Args:
            authorizations: {command_type: plugin_name | None}
                - plugin_name 为 None 表示撤销授权
        """
        for command_type, plugin_name in authorizations.items():
            try:
                if plugin_name is None:
                    self.revoke(command_type)
                else:
                    self.authorize(command_type, plugin_name)
            except ValueError as e:
                logger.error(f"设置授权失败: {e}")
