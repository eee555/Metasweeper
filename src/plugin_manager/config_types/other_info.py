"""
插件自定义配置容器基类

插件继承此类定义自己的配置字段。
"""

from __future__ import annotations

from typing import Any, Callable, ClassVar

from .base_config import BaseConfig


class OtherInfoBase:
    """
    插件自定义配置容器基类

    插件继承此类定义配置字段，变量名作为配置 key：

    用法::

        from plugin_manager.config_types import (
            OtherInfoBase, BoolConfig, IntConfig, ChoiceConfig, TextConfig
        )

        class MyPluginOtherInfo(OtherInfoBase):
            # 变量名 = ConfigType(默认值, 标签, 其他参数...)
            auto_save = BoolConfig(True, "自动保存", description="录制完成自动保存")
            save_interval = IntConfig(30, "保存间隔(秒)", min_value=10, max_value=300, step=10)
            output_format = ChoiceConfig(
                "evf", "输出格式",
                choices=[("evf", "EVF"), ("avi", "AVI"), ("mp4", "MP4")]
            )
            api_key = TextConfig("", "API密钥", password=True, placeholder="输入密钥...")

    然后在 PluginInfo 中绑定::

        @classmethod
        def plugin_info(cls) -> PluginInfo:
            return PluginInfo(
                name="my_plugin",
                other_info=MyPluginOtherInfo  # 绑定配置类
            )
    """

    # 子类定义的配置字段（类属性）
    _fields: ClassVar[dict[str, BaseConfig]] = {}

    def __init__(self) -> None:
        """
        初始化配置容器

        收集所有 BaseConfig 类属性，并初始化运行时值存储。
        """
        # 收集所有 BaseConfig 类属性
        fields: dict[str, BaseConfig] = {}
        for name in dir(type(self)):
            attr = getattr(type(self), name, None)
            if isinstance(attr, BaseConfig):
                fields[name] = attr

        # 使用 object.__setattr__ 设置实例属性（避免触发 __setattr__）
        object.__setattr__(self, "_fields", fields)
        object.__setattr__(self, "_values", {})
        object.__setattr__(self, "_on_change", None)  # 变化回调

        # 初始化运行时值存储（初始为默认值）
        # 注意：这里必须使用 object.__setattr__ 因为我们要直接操作 _values 字典
        values: dict[str, Any] = {name: field.default for name, field in fields.items()}
        object.__setattr__(self, "_values", values)

    def set_on_change(self, callback: Callable[[str, Any], None] | None) -> None:
        """
        设置配置值变化回调

        Args:
            callback: 回调函数，签名为 (字段名, 新值) -> None
        """
        object.__setattr__(self, "_on_change", callback)

    def __getattribute__(self, name: str) -> Any:
        """获取属性 - 拦截配置字段访问"""
        # 先获取 _fields 和 _values（避免无限递归）
        if name.startswith("_") or name in ("to_dict", "from_dict", "reset_to_defaults", "get_fields", "set_on_change"):
            return object.__getattribute__(self, name)

        try:
            fields = object.__getattribute__(self, "_fields")
            values = object.__getattribute__(self, "_values")
        except AttributeError:
            return object.__getattribute__(self, name)

        if name in fields:
            return values.get(name, fields[name].default)

        return object.__getattribute__(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        """设置配置值（带验证和回调）"""
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return

        fields = object.__getattribute__(self, "_fields")
        values = object.__getattribute__(self, "_values")

        if name in fields:
            field = fields[name]
            if not field.validate(value):
                raise ValueError(f"Invalid value for '{name}': {value}")

            old_value = values.get(name, field.default)
            values[name] = value

            # 触发变化回调
            on_change = object.__getattribute__(self, "_on_change")
            if on_change is not None and old_value != value:
                on_change(name, value)
        else:
            object.__setattr__(self, name, value)

    @classmethod
    def get_fields(cls) -> dict[str, BaseConfig]:
        """
        获取所有配置字段定义

        Returns:
            字段名到 BaseConfig 实例的映射
        """
        return {
            name: attr
            for name in dir(cls)
            if isinstance(attr := getattr(cls, name, None), BaseConfig)
        }

    def to_dict(self) -> dict[str, Any]:
        """
        导出为字典（用于保存）

        Returns:
            配置键值对字典，值已转换为存储格式
        """
        fields = object.__getattribute__(self, "_fields")
        values = object.__getattribute__(self, "_values")
        return {
            name: field.to_storage(values.get(name, field.default))
            for name, field in fields.items()
        }

    def from_dict(self, data: dict[str, Any], silent: bool = True) -> None:
        """
        从字典加载配置

        Args:
            data: 配置键值对字典
            silent: 是否静默加载（不触发变化回调），默认 True
        """
        fields = object.__getattribute__(self, "_fields")
        values = object.__getattribute__(self, "_values")
        on_change = object.__getattribute__(self, "_on_change")

        for name, field in fields.items():
            if name in data:
                try:
                    old_value = values.get(name, field.default)
                    new_value = field.from_storage(data[name])
                    values[name] = new_value

                    # 只有非静默模式且值真正变化时才触发回调
                    if not silent and on_change is not None and old_value != new_value:
                        on_change(name, new_value)
                except (ValueError, TypeError):
                    # 加载失败则使用默认值
                    values[name] = field.default

    def reset_to_defaults(self, silent: bool = True) -> None:
        """
        重置所有配置为默认值

        Args:
            silent: 是否静默重置（不触发变化回调），默认 True
        """
        fields = object.__getattribute__(self, "_fields")
        values = object.__getattribute__(self, "_values")
        on_change = object.__getattribute__(self, "_on_change")

        for name, field in fields.items():
            old_value = values.get(name, field.default)
            values[name] = field.default

            # 只有非静默模式且值真正变化时才触发回调
            if not silent and on_change is not None and old_value != field.default:
                on_change(name, field.default)

    def __repr__(self) -> str:
        fields = object.__getattribute__(self, "_fields")
        values = object.__getattribute__(self, "_values")
        values_str = ", ".join(f"{k}={v!r}" for k, v in values.items())
        return f"{type(self).__name__}({values_str})"
